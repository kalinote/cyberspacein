from datetime import datetime
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from app.schemas.agent.result import TaskSubmissionRecordSchema
from app.schemas.constants import NanobotSessionStatusEnum

if TYPE_CHECKING:
    from app.models.agent.nanobot import NanobotSessionModel


class NanobotSessionSchema(BaseModel):
    """分析会话列表项（不含 steps / todos / user_prompt）。"""

    id: str = Field(description="会话ID")
    agent_id: str = Field(description="所属 AgentID")
    agent_name: str | None = Field(default=None, description="所属 Agent 名称")
    workspace_id: str = Field(description="所属工作区ID")
    metadata: dict[str, Any] = Field(default_factory=dict, description="会话元数据")
    last_consolidated_seq: int = Field(default=0, description="已合并到 history 的消息 seq 上限")
    status: NanobotSessionStatusEnum = Field(description="本会话运行状态")
    pending_approval: dict[str, Any] | None = Field(default=None, description="待审批载荷（HITL）")
    result: dict[str, Any] | None = Field(default=None, description="最近一次 run 回合快照")
    task_submissions: list[TaskSubmissionRecordSchema] = Field(
        default_factory=list,
        description="submit_task_result 历史（详情接口返回；列表默认为空）",
    )
    error_message: str | None = Field(default=None, description="失败或取消时的错误说明")
    started_at: datetime | None = Field(default=None, description="进入运行态的时间")
    finished_at: datetime | None = Field(default=None, description="结束时间")
    created_at: datetime = Field(description="创建时间")
    updated_at: datetime = Field(description="更新时间")

    @classmethod
    def from_doc(
        cls,
        doc: "NanobotSessionModel",
        *,
        agent_name: str | None = None,
        include_task_submissions: bool = False,
    ) -> "NanobotSessionSchema":
        submissions: list[TaskSubmissionRecordSchema] = []
        if include_task_submissions and doc.task_submissions:
            for raw in doc.task_submissions:
                if isinstance(raw, dict):
                    try:
                        submissions.append(TaskSubmissionRecordSchema.model_validate(raw))
                    except Exception:
                        continue
        return cls(
            id=doc.id,
            agent_id=doc.agent_id,
            agent_name=agent_name,
            workspace_id=doc.workspace_id,
            metadata=dict(doc.metadata or {}),
            last_consolidated_seq=doc.last_consolidated_seq,
            status=doc.status,
            pending_approval=doc.pending_approval,
            result=doc.result,
            task_submissions=submissions,
            error_message=doc.error_message,
            started_at=doc.started_at,
            finished_at=doc.finished_at,
            created_at=doc.created_at,
            updated_at=doc.updated_at,
        )
