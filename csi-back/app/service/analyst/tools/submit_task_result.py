"""submit_task_result 业务工具（分析会话固定注册）。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.models.agent.nanobot import NanobotSessionModel
from app.schemas.agent.result import (
    SUBMIT_TASK_RESULT_TOOL_NAME,
    SubmitTaskResultParams,
    TaskSubmissionRecordSchema,
)
from app.utils.id_lib import generate_id
from app.service.analyst.context import (
    current_task_completion,
    get_current_agent_id,
    get_current_session_id,
)
from app.service.analyst.tools._context import require_agent_id
from app.service.nanobot.agent.tools.base import Tool, tool_parameters


@tool_parameters({
    "type": "object",
    "properties": {
        "success": {"type": "boolean", "description": "是否达成任务目标"},
        "failure_reason": {
            "type": ["string", "null"],
            "description": "失败原因；success 为 true 时用 null",
        },
        "short_summary": {"type": "string", "description": "简短摘要"},
        "payload": {
            "type": "object",
            "description": "完整结构化业务结果",
            "additionalProperties": True,
        },
    },
    "required": ["success", "short_summary"],
    "additionalProperties": False,
})
class SubmitTaskResultTool(Tool):
    """提交机读任务结果。"""

    @property
    def name(self) -> str:
        return SUBMIT_TASK_RESULT_TOOL_NAME

    @property
    def description(self) -> str:
        return (
            "记录一段可交付工作的机读结果（success、failure_reason、short_summary、payload）。"
            "在子任务完成、明确失败或需要固化业务结果时调用；简单问答或任务未完成时不必调用。"
        )

    @property
    def exclusive(self) -> bool:
        return False

    async def execute(self, **kwargs: Any) -> str:
        from app.service.analyst.service import AnalystService

        require_agent_id()
        params = SubmitTaskResultParams.model_validate(kwargs)

        agent_id = get_current_agent_id() or ""
        session_id = get_current_session_id() or ""
        submission_id = generate_id(f"submission:{session_id}:{datetime.now().isoformat()}")
        record = TaskSubmissionRecordSchema.from_submit_params(submission_id, params)
        record_dict = record.model_dump()
        current_task_completion.set(record_dict)

        if session_id:
            sess = await NanobotSessionModel.find_one({"_id": session_id})
            if sess is not None:
                sess.task_submissions = list(sess.task_submissions or []) + [record_dict]
                sess.updated_at = datetime.now()
                await sess.save()
                submission_index = len(sess.task_submissions) - 1
            else:
                submission_index = 0
        else:
            submission_index = 0

        await AnalystService.broadcast_sse(
            agent_id,
            "task_submitted",
            {
                "agent_id": agent_id,
                "session_id": session_id,
                "submission_id": submission_id,
                "index": submission_index,
                "success": params.success,
                "short_summary": (params.short_summary or "")[:500],
            },
        )
        return (
            "任务机读结果已记录。可继续对话、处理下一子任务，或用 Markdown 向用户说明。"
        )
