import asyncio
import json
from typing import Any

from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse
from loguru import logger

from app.models.agent.configs import AgentPromptTemplateModel
from app.models.agent.nanobot import NanobotAgentModel
from app.schemas.agent.agent import (
    AgentRuntimeRequestSchema,
    ApproveRequestSchema,
    CancelAgentRequestSchema,
    CancelAgentResponseSchema,
    SendAgentMessageResponseSchema,
    StartAgentResponseSchema,
)
from app.schemas.agent.nanobot_agent import AgentServiceError
from app.schemas.response import ApiResponseSchema
from app.service.analyst.service import AnalystService
from app.utils.jinja_injection import merge_rendered_user_prompts, render_user_prompt
import app.utils.status_codes as status_codes

logger = logger.bind(name=__name__)

router = APIRouter()


async def _fetch_agent_template_user_prompt(agent_id: str) -> str:
    agent = await NanobotAgentModel.find_one({"_id": agent_id})
    if not agent:
        raise AgentServiceError(
            status_codes.NOT_FOUND_AGENT,
            f"Agent 不存在: {agent_id}",
        )

    tpl = await AgentPromptTemplateModel.find_one({"_id": agent.prompt_template_id})
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
    return prompt


@router.post(
    "/start",
    response_model=ApiResponseSchema[StartAgentResponseSchema],
    summary="启动分析引擎",
    description=(
        "成功时返回 `data.session_id`。后续 SSE `/agent/status` 会收到 `user_message`（首轮用户输入）与 `status` 等事件；"
        "取消与审批接口均须携带同一 `session_id`。"
        "请求体 `auto_approve=true` 时，本轮 run 内写操作工具自动批准，无需调用 `/agent/approve`（仅本轮有效）。"
        "请求体 `merge_user_prompts=true` 时，将提示词模板 user_prompt（前）与请求 user_prompt（后）分别 Jinja 渲染后合并，"
        "两段之间空一行，且请求 `user_prompt` 必填。"
        "当环境变量 `NANOBOT_AGENT_MAX_PARALLEL_SESSIONS` 大于 0 且该 Agent 在库中 `running` 会话数已达上限时，"
        "返回 HTTP 200 且业务码为冲突态（`CONFLICT_STATE`），不会在库中新建本会话。"
    ),
)
async def start_agent(data: AgentRuntimeRequestSchema):
    try:
        injection_param = dict(data.injection_param)
        request_user_prompt = str(data.user_prompt or "").strip()

        if data.merge_user_prompts:
            if not request_user_prompt:
                raise AgentServiceError(
                    status_codes.INVALID_ARGUMENT,
                    "merge_user_prompts 启用时 user_prompt 不能为空",
                )
            tpl_user_prompt = await _fetch_agent_template_user_prompt(data.agent_id)
            rendered_tpl = render_user_prompt(
                tpl_user_prompt, injection_param
            ).strip()
            rendered_req = render_user_prompt(
                request_user_prompt, injection_param
            ).strip()
            if not rendered_tpl:
                raise AgentServiceError(
                    status_codes.INVALID_ARGUMENT,
                    "提示词模板 user_prompt 渲染后为空",
                )
            if not rendered_req:
                raise AgentServiceError(
                    status_codes.INVALID_ARGUMENT,
                    "用户提示词渲染后为空",
                )
            final_user_prompt = merge_rendered_user_prompts(
                rendered_tpl, rendered_req
            )
        else:
            raw_user_prompt = request_user_prompt
            if not raw_user_prompt:
                raw_user_prompt = await _fetch_agent_template_user_prompt(
                    data.agent_id
                )
            final_user_prompt = render_user_prompt(
                raw_user_prompt, injection_param
            ).strip()
            if not final_user_prompt:
                raise AgentServiceError(
                    status_codes.INVALID_ARGUMENT,
                    "用户提示词为空，且模板渲染后仍为空",
                )

        session_id = await AnalystService.start_agent(
            agent_id=data.agent_id,
            user_prompt=final_user_prompt,
            context=injection_param,
            auto_approve=data.auto_approve,
        )
    except AgentServiceError as exc:
        return ApiResponseSchema.error(code=exc.code, message=exc.message, data=exc.data)
    return ApiResponseSchema.success(
        data=StartAgentResponseSchema(agent_id=data.agent_id, session_id=session_id)
    )


@router.post(
    "/message",
    response_model=ApiResponseSchema[SendAgentMessageResponseSchema],
    summary="向已结束会话提交续聊消息",
    description=(
        "仅当会话状态为 `completed`、`failed` 或 `cancelled` 时可提交；"
        "`running`、`awaiting_approval`、`paused` 等状态返回冲突错误。"
        "成功后会话重新进入 `running`，并通过 SSE 推送 `user_message`（用户本轮输入）与 `status`；"
        "后续仍通过 `/agent/status` 订阅其它事件。"
        "请求体 `auto_approve=true` 时，本轮 run 内写操作工具自动批准，无需调用 `/agent/approve`（仅本轮有效）。"
    ),
)
async def send_agent_message(data: AgentRuntimeRequestSchema):
    try:
        session_id = str(data.session_id or "").strip()
        if not session_id:
            raise AgentServiceError(
                status_codes.INVALID_ARGUMENT, "session_id 不能为空"
            )

        raw_user_prompt = str(data.user_prompt or "").strip()
        if not raw_user_prompt:
            raise AgentServiceError(
                status_codes.INVALID_ARGUMENT, "user_prompt 不能为空"
            )

        injection_param = dict(data.injection_param)
        final_user_prompt = render_user_prompt(
            raw_user_prompt, injection_param
        ).strip()
        if not final_user_prompt:
            raise AgentServiceError(
                status_codes.INVALID_ARGUMENT,
                "用户提示词为空，且模板渲染后仍为空",
            )

        session_id = await AnalystService.send_message(
            agent_id=data.agent_id,
            session_id=session_id,
            user_prompt=final_user_prompt,
            context=injection_param,
            auto_approve=data.auto_approve,
        )
    except AgentServiceError as exc:
        return ApiResponseSchema.error(code=exc.code, message=exc.message, data=exc.data)
    return ApiResponseSchema.success(
        data=SendAgentMessageResponseSchema(
            agent_id=data.agent_id, session_id=session_id
        )
    )

# TODO: SSE接口增加分页拉取(滚动)防止内容过多导致前端卡死
@router.get("/status", summary="订阅指定会话的状态事件流（SSE）")
async def get_agent_status(
    request: Request,
    agent_id: str = Query(..., description="分析引擎ID"),
    session_id: str = Query(..., description="会话ID"),
):
    queue = await AnalystService.subscribe(agent_id, session_id)

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

