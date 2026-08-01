from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field
from beanie.exceptions import CollectionWasNotInitialized

from app.models.agent.configs import AgentPromptTemplateModel
from app.models.agent.nanobot import NanobotAgentModel, NanobotSessionModel
from app.models.agent.runtime import NanobotRunModel
from app.schemas.agent.nanobot_agent import AgentServiceError
from app.service.analyst.service import AnalystService
from app.utils.jinja_injection import merge_rendered_user_prompts, render_user_prompt
import app.utils.status_codes as status_codes


class AnalysisInvocationRequest(BaseModel):
    """分析调用门面请求。"""

    agent_id: str
    user_prompt: str | None = None
    injection_param: dict[str, Any] = Field(default_factory=dict)
    merge_user_prompts: bool = False
    auto_approve: bool = False
    approval_policy: Literal["manual", "auto_readonly", "auto_all"] = "manual"
    initiator_user_id: str | None = None


class AnalysisInvocationRef(BaseModel):
    """分析运行稳定引用。"""

    agent_id: str
    session_id: str
    run_id: str | None = None


class AnalysisInvocationOutcome(BaseModel):
    """分析运行持久化结果。"""

    status: Literal[
        "queued",
        "running",
        "awaiting_approval",
        "completed",
        "failed",
        "cancelled",
        "paused",
        "interrupted",
    ]
    result: dict[str, Any] | None = None
    error_message: str | None = None
    pending_approval: dict[str, Any] | None = None


class AnalysisInvocationService:
    """供 Agent API 使用的分析应用层门面。"""

    @staticmethod
    async def submit(
        request: AnalysisInvocationRequest,
    ) -> AnalysisInvocationRef:
        """准备提示词并持久化投递分析Run。"""
        injection_param = dict(request.injection_param)
        request_user_prompt = str(request.user_prompt or "").strip()
        if request.merge_user_prompts:
            if not request_user_prompt:
                raise AgentServiceError(
                    status_codes.INVALID_ARGUMENT,
                    "merge_user_prompts 启用时 user_prompt 不能为空",
                )
            template_prompt = await AnalysisInvocationService._template_prompt(
                request.agent_id
            )
            rendered_template = render_user_prompt(
                template_prompt,
                injection_param,
            ).strip()
            rendered_request = render_user_prompt(
                request_user_prompt,
                injection_param,
            ).strip()
            if not rendered_template:
                raise AgentServiceError(
                    status_codes.INVALID_ARGUMENT,
                    "提示词模板 user_prompt 渲染后为空",
                )
            if not rendered_request:
                raise AgentServiceError(
                    status_codes.INVALID_ARGUMENT,
                    "用户提示词渲染后为空",
                )
            final_user_prompt = merge_rendered_user_prompts(
                rendered_template,
                rendered_request,
            )
        else:
            raw_user_prompt = request_user_prompt or await (
                AnalysisInvocationService._template_prompt(request.agent_id)
            )
            final_user_prompt = render_user_prompt(
                raw_user_prompt,
                injection_param,
            ).strip()
            if not final_user_prompt:
                raise AgentServiceError(
                    status_codes.INVALID_ARGUMENT,
                    "用户提示词为空，且模板渲染后仍为空",
                )

        start_kwargs = {
            "agent_id": request.agent_id,
            "user_prompt": final_user_prompt,
            "context": injection_param,
            "auto_approve": (
                request.auto_approve or request.approval_policy == "auto_all"
            ),
            "initiator_user_id": request.initiator_user_id,
        }
        session_id = await AnalystService.start_agent(**start_kwargs)
        try:
            session = await NanobotSessionModel.find_one({"_id": session_id})
        except CollectionWasNotInitialized:
            session = None
        return AnalysisInvocationRef(
            agent_id=request.agent_id,
            session_id=session_id,
            run_id=session.active_run_id if session else None,
        )

    @staticmethod
    async def get_outcome(
        ref: AnalysisInvocationRef,
    ) -> AnalysisInvocationOutcome | None:
        """读取持久化Run状态用于事件漏失后的对账。"""
        run = None
        if ref.run_id:
            run = await NanobotRunModel.find_one({"_id": ref.run_id})
        if run is None:
            run = await NanobotRunModel.find(
                {"session_id": ref.session_id}
            ).sort("-generation").first_or_none()
        if run is None:
            return None
        session = await NanobotSessionModel.find_one({"_id": ref.session_id})
        return AnalysisInvocationOutcome(
            status=run.status.value,
            result=run.result,
            error_message=run.error_message,
            pending_approval=(
                session.pending_approval
                if session and isinstance(session.pending_approval, dict)
                else None
            ),
        )

    @staticmethod
    async def cancel(ref: AnalysisInvocationRef, reason: str) -> bool:
        """持久化取消分析Run。"""
        return await AnalystService.cancel_agent(
            ref.agent_id,
            ref.session_id,
            reason=reason,
        )

    @staticmethod
    async def _template_prompt(agent_id: str) -> str:
        """读取Agent绑定的默认用户提示词。"""
        agent = await NanobotAgentModel.find_one({"_id": agent_id})
        if not agent:
            raise AgentServiceError(
                status_codes.NOT_FOUND_AGENT,
                f"Agent 不存在: {agent_id}",
            )
        template = await AgentPromptTemplateModel.find_one(
            {"_id": agent.prompt_template_id}
        )
        if not template:
            raise AgentServiceError(
                status_codes.NOT_FOUND_TEMPLATE,
                f"Agent 绑定的提示词模板不存在: {agent.prompt_template_id}",
            )
        prompt = str(template.user_prompt or "").strip()
        if not prompt:
            raise AgentServiceError(
                status_codes.INVALID_ARGUMENT,
                "该 Agent 的提示词模板默认 user_prompt 为空",
                data={"prompt_template_id": agent.prompt_template_id},
            )
        return prompt
