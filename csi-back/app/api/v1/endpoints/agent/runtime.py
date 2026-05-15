import asyncio
import json
from typing import Any

from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse
from loguru import logger

from app.models.agent.configs import AgentPromptTemplateModel
from app.models.agent.nanobot import NanobotAgentModel
from app.schemas.agent.agent import (
    ApproveRequestSchema,
    CancelAgentRequestSchema,
    CancelAgentResponseSchema,
    StartAgentRequestSchema,
    StartAgentResponseSchema,
)
from app.schemas.agent.nanobot_agent import AgentServiceError
from app.schemas.response import ApiResponseSchema
from app.service.analyst.service import AnalystService
from app.utils.jinja_injection import render_user_prompt
import app.utils.status_codes as status_codes

logger = logger.bind(name=__name__)

router = APIRouter()


@router.post(
    "/start",
    response_model=ApiResponseSchema[StartAgentResponseSchema],
    summary="启动分析引擎",
    description=(
        "成功时返回 `data.session_id`。后续 SSE `/agent/status`、取消与审批接口均须携带同一 `session_id`。"
        "当环境变量 `NANOBOT_AGENT_MAX_PARALLEL_SESSIONS` 大于 0 且该 Agent 在库中 `running` 会话数已达上限时，"
        "返回 HTTP 200 且业务码为冲突态（`CONFLICT_STATE`），不会在库中新建本会话。"
    ),
)
async def start_agent(data: StartAgentRequestSchema):
    try:
        context = {
            **data.extra_context,
            **({"entity_uuid": data.entity_uuid} if data.entity_uuid else {}),
            **({"entity_type": data.entity_type.value} if data.entity_type else {})
        }

        raw_user_prompt = str(data.user_prompt or "").strip()
        if not raw_user_prompt:
            agent = await NanobotAgentModel.find_one({"_id": data.agent_id})
            if not agent:
                raise AgentServiceError(
                    status_codes.NOT_FOUND_AGENT,
                    f"Agent 不存在: {data.agent_id}",
                )

            tpl = await AgentPromptTemplateModel.find_one(
                {"_id": agent.prompt_template_id}
            )
            if not tpl:
                raise AgentServiceError(
                    status_codes.NOT_FOUND_TEMPLATE,
                    f"Agent 绑定的提示词模板不存在: {agent.prompt_template_id}",
                )

            prompt = str(tpl.user_prompt or "").strip()
            if not prompt:
                raise AgentServiceError(
                    status_codes.INVALID_ARGUMENT,
                    "该 Agent 的提示词模板默认 user_prompt 为空",
                    data={"prompt_template_id": agent.prompt_template_id},
                )
            raw_user_prompt = prompt

        final_user_prompt = render_user_prompt(raw_user_prompt, context).strip()
        if not final_user_prompt:
            raise AgentServiceError(
                status_codes.INVALID_ARGUMENT,
                "用户提示词为空，且模板渲染后仍为空",
            )

        session_id = await AnalystService.start_agent(
            agent_id=data.agent_id,
            user_prompt=final_user_prompt,
            context=context,
        )
    except AgentServiceError as exc:
        return ApiResponseSchema.error(code=exc.code, message=exc.message, data=exc.data)
    return ApiResponseSchema.success(
        data=StartAgentResponseSchema(agent_id=data.agent_id, session_id=session_id)
    )


@router.get("/status", summary="订阅指定会话的状态事件流（SSE）")
async def get_agent_status(
    request: Request,
    agent_id: str = Query(..., description="分析引擎ID"),
    session_id: str = Query(..., description="会话ID"),
    debug: bool = Query(False, description="是否开启调试模式（开启后会通过 SSE 额外返回更详细信息）"),
):
    debug_enabled = (
        debug
        if isinstance(debug, bool)
        else bool(getattr(debug, "default", False))
    )
    queue = await AnalystService.subscribe(agent_id, session_id, debug=debug_enabled)

    async def event_stream():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=15.0)
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
                    continue
                event = payload.get("event", "message")
                data_str = json.dumps(payload.get("data"), ensure_ascii=False, default=str)
                event_id = payload.get("id")
                if event_id is not None:
                    yield f"id: {event_id}\nevent: {event}\ndata: {data_str}\n\n"
                else:
                    yield f"event: {event}\ndata: {data_str}\n\n"
        finally:
            await AnalystService.unsubscribe(agent_id, session_id, queue)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/approve", response_model=ApiResponseSchema[Any], summary="提交行为批准")
async def approve_agent(data: ApproveRequestSchema):
    try:
        await AnalystService.submit_approval(data.agent_id, data.session_id, data.decisions)
    except AgentServiceError as exc:
        return ApiResponseSchema.error(code=exc.code, message=exc.message, data=exc.data)
    return ApiResponseSchema.success(data=None, message="批准决策已提交")


@router.post(
    "/cancel",
    response_model=ApiResponseSchema[CancelAgentResponseSchema],
    summary="取消正在运行的分析引擎",
)
async def cancel_agent(data: CancelAgentRequestSchema):
    cancelled = await AnalystService.cancel_agent(
        data.agent_id, data.session_id, reason=data.reason
    )
    return ApiResponseSchema.success(
        data=CancelAgentResponseSchema(agent_id=data.agent_id, cancelled=cancelled),
        message="取消请求已发送" if cancelled else "该 Agent 当前没有正在运行的任务",
    )

