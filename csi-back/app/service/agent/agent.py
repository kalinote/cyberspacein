import asyncio
import copy
import uuid
from datetime import datetime

from beanie.operators import Set
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command

from app.models.agent.agent import AgentModel, AgentSessionModel
from app.models.agent.configs import AgentModelConfigModel
from app.schemas.agent.agent import (
    AgentStatusPayloadSchema,
    ApprovalRequiredPayloadSchema,
    StartAgentRequestSchema,
)
from app.service.agent.motor_checkpinter import MotorCheckpointerSaver
from langchain.agents import create_agent
from langchain.agents.middleware import TodoListMiddleware, HumanInTheLoopMiddleware
from langchain_openai import ChatOpenAI

from app.service.agent.tools import all_tools
from app.utils.agent import (
    get_step_detail,
    modify_entity_approval_description,
    normalize_todo,
    parse_approval_decision,
    update_session_status,
)

TODO_MIDDLEWARE_SYSTEM_PROMPT = """\
使用 `write_todos` 创建并维护任务列表，使用户能监控进度。
- 任务开始时：用 write_todos 创建任务分解。
- 每步完成后：用 write_todos 更新列表，将对应项标为 completed，并将下一项标为 in_progress。
- 每轮最多调用一次 write_todos，不可并行多次调用。
- 若任务步骤很少、流程明确，可不使用该工具，直接执行即可。"""

TODO_MIDDLEWARE_TOOL_DESCRIPTION = """\
## write_todos 工具

用于创建和维护结构化任务列表，便于跟踪进度并让用户看到当前步骤。

使用时机：任务开始前创建任务分解；每完成一步后更新列表（将已完成项标为 completed、当前进行项标为 in_progress）。
任务状态：pending=未开始，in_progress=进行中，completed=已完成。
约束：每轮最多调用一次，每次传入完整列表（整表替换）。"""

class AgentService:
    task_lock = asyncio.Lock()
    sse_lock = asyncio.Lock()
    sse_subscribers: dict[str, list[asyncio.Queue]] = {}
    running_tasks: dict[str, asyncio.Task] = {}
    motor_checkpointer = MotorCheckpointerSaver()
    cancel_reasons: dict[str, str] = {}
    pending_resumes: dict[str, asyncio.Queue] = {}

    @staticmethod
    async def broadcast_sse(thread_id: str, payload: dict) -> None:
        async with AgentService.sse_lock:
            queues = list(AgentService.sse_subscribers.get(thread_id, []))
        for q in queues:
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                pass

    @staticmethod
    def sse_event(event_type: str, data: AgentStatusPayloadSchema | ApprovalRequiredPayloadSchema | dict) -> dict:
        if hasattr(data, "model_dump"):
            data = data.model_dump(mode="json")
        return {"type": event_type, "data": data}

    @staticmethod
    def session_to_status_payload(doc: AgentSessionModel, is_running: bool) -> AgentStatusPayloadSchema:
        fields = getattr(doc, "fields", {})
        pending_approval = getattr(doc, "pending_approval", None)
        return AgentStatusPayloadSchema(
            thread_id=doc.thread_id,
            status=doc.status,
            fields=fields,
            steps=doc.steps,
            todos=doc.todos,
            pending_approval=pending_approval,
            updated_at=doc.updated_at,
            is_running=is_running,
        )

    @staticmethod
    async def create_agent(system_prompt: str, agent_template: AgentModel, model_config: AgentModelConfigModel):
        return create_agent(
            model=ChatOpenAI(
                model=model_config.model,
                api_key=model_config.api_key,
                base_url=model_config.base_url,
                # TODO 设置其他模型配置(比如temperature等)
            ),
            tools=[tool for tool in all_tools.values() if tool.name in agent_template.tools],
            system_prompt=system_prompt,
            middleware=[
                TodoListMiddleware(
                    system_prompt=TODO_MIDDLEWARE_SYSTEM_PROMPT,
                    tool_description=TODO_MIDDLEWARE_TOOL_DESCRIPTION
                ),
                HumanInTheLoopMiddleware(
                    interrupt_on={
                        "modify_entity": {
                            "allowed_decisions": ["approve", "reject"],
                            "description": modify_entity_approval_description,
                        }
                    },
                )
            ],
            checkpointer=AgentService.motor_checkpointer,
        )

    @staticmethod
    async def run_agent(thread_id: str, agent: CompiledStateGraph, inputs: dict | None = None, config: dict | None = None):
        if not config:
            config = {"configurable": {"thread_id": thread_id}}
        current_input: dict | Command | None = inputs

        try:
            while True:
                stream = agent.astream(
                    current_input,
                    config=config,
                    stream_mode=["updates", "values"],
                )
                interrupted = False
                async for item in stream:
                    if isinstance(item, (list, tuple)) and len(item) == 2:
                        mode, data = item[0], item[1]
                    else:
                        mode, data = "updates", item
                    if mode == "updates" and isinstance(data, dict):
                        for node_name, state_update in data.items():
                            doc = await AgentSessionModel.find_one({"thread_id": thread_id})
                            if doc:
                                step = {
                                    "node": node_name,
                                    "ts": datetime.now().isoformat(),
                                    **get_step_detail(state_update),
                                }
                                new_steps = doc.steps + [step]
                                new_todos = (
                                    [normalize_todo(t) for t in (state_update.get("todos") or [])]
                                    if isinstance(state_update, dict) and "todos" in state_update
                                    else doc.todos
                                )
                                now = datetime.now()
                                await doc.update(
                                    Set({
                                        AgentSessionModel.status: "running",
                                        AgentSessionModel.steps: new_steps,
                                        AgentSessionModel.todos: new_todos,
                                        AgentSessionModel.updated_at: now,
                                    })
                                )
                                doc.status = "running"
                                doc.steps = new_steps
                                doc.todos = new_todos
                                doc.updated_at = now
                                await AgentService.broadcast_sse(
                                    thread_id,
                                    AgentService.sse_event("status", AgentService.session_to_status_payload(doc, True)),
                                )
                    elif mode == "values" and isinstance(data, dict) and "__interrupt__" in data:
                        it = data["__interrupt__"]
                        hitl_payload = (
                            {}
                            if not it or not hasattr(it[0], "value")
                            else (
                                it[0].value
                                if isinstance(it[0].value, dict)
                                else ({"value": str(it[0].value)} if it[0].value is not None else {})
                            )
                        )
                        doc = await AgentSessionModel.find_one({"thread_id": thread_id})
                        if doc:
                            doc.status = "awaiting_approval"
                            doc.pending_approval = copy.deepcopy(hitl_payload) if hitl_payload else None
                            doc.updated_at = datetime.now()
                            await doc.save()
                        await AgentService.broadcast_sse(
                            thread_id,
                            AgentService.sse_event(
                                "approval_required",
                                ApprovalRequiredPayloadSchema(payload=hitl_payload, thread_id=thread_id),
                            ),
                        )
                        q = AgentService.pending_resumes.setdefault(thread_id, asyncio.Queue())
                        decisions = await q.get()
                        decision_type = parse_approval_decision(decisions)
                        decision_detail = copy.deepcopy(decisions[0]) if decisions and isinstance(decisions[0], dict) else None
                        doc = await AgentSessionModel.find_one({"thread_id": thread_id})
                        if doc:
                            if doc.steps:
                                last_step = doc.steps[-1]
                                last_step["approval_decision"] = decision_type
                                last_step["approval_decision_detail"] = decision_detail
                                last_step["approved_at"] = datetime.now().isoformat()
                                if doc.pending_approval is not None:
                                    last_step["approval_payload"] = copy.deepcopy(doc.pending_approval)
                            doc.pending_approval = None
                            doc.status = "running"
                            doc.updated_at = datetime.now()
                            await doc.save()
                            await AgentService.broadcast_sse(
                                thread_id,
                                AgentService.sse_event("status", AgentService.session_to_status_payload(doc, True)),
                            )
                        else:
                            await update_session_status(thread_id, "running")
                        current_input = Command(resume={"decisions": decisions})
                        interrupted = True
                        break
                if not interrupted:
                    break
        except asyncio.CancelledError:
            reason = AgentService.cancel_reasons.pop(thread_id, "pause")
            status = "paused" if reason == "pause" else "cancelled"
            doc = await update_session_status(thread_id, status)
            if doc:
                await AgentService.broadcast_sse(
                    thread_id, AgentService.sse_event("status", AgentService.session_to_status_payload(doc, False))
                )
            raise
        finally:
            async with AgentService.task_lock:
                AgentService.running_tasks.pop(thread_id, None)
            AgentService.pending_resumes.pop(thread_id, None)
            doc = await AgentSessionModel.find_one({"thread_id": thread_id})
            if doc and doc.status == "running":
                doc = await update_session_status(thread_id, "completed")
                if doc:
                    await AgentService.broadcast_sse(
                        thread_id, AgentService.sse_event("status", AgentService.session_to_status_payload(doc, False))
                    )

    @staticmethod
    async def start_agent(system_prompt: str, user_prompt: str, agent_template: AgentModel, model_config: AgentModelConfigModel, data: StartAgentRequestSchema):
        thread_id = str(uuid.uuid4())
        await AgentSessionModel(
            thread_id=thread_id,
            status="running",
            fields=data.model_dump(),
            steps=[],
            todos=[],
        ).insert()

        agent = await AgentService.create_agent(system_prompt, agent_template, model_config)
        inputs = {
            "messages": [{"role": "user", "content": user_prompt}],
        }
        
        task = asyncio.create_task(AgentService.run_agent(thread_id, agent, inputs))
        AgentService.running_tasks[thread_id] = task
        return thread_id
