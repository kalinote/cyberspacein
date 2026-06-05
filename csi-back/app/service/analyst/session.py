"""SessionService：nanobot_sessions 集合的分页查询。"""
from __future__ import annotations

from typing import Any

from app.models.agent.nanobot import NanobotAgentModel, NanobotSessionModel
from app.schemas.agent.nanobot_session import NanobotSessionSchema
from app.schemas.constants import NanobotSessionStatusEnum


class SessionService:
    @classmethod
    async def list_page(
        cls,
        *,
        page: int,
        page_size: int,
        agent_id: str | None = None,
        workspace_id: str | None = None,
        status: NanobotSessionStatusEnum | None = None,
    ) -> tuple[list[NanobotSessionSchema], int]:
        query_filters: dict[str, Any] = {}
        if agent_id:
            query_filters["agent_id"] = agent_id
        if workspace_id:
            query_filters["workspace_id"] = workspace_id
        if status is not None:
            query_filters["status"] = status.value

        base_query = NanobotSessionModel.find(query_filters)
        total = await base_query.count()
        skip = (page - 1) * page_size
        docs = (
            await base_query.sort("-created_at").skip(skip).limit(page_size).to_list()
        )

        agent_ids = list({d.agent_id for d in docs})
        name_by_agent: dict[str, str] = {}
        if agent_ids:
            agents = await NanobotAgentModel.find({"_id": {"$in": agent_ids}}).to_list()
            name_by_agent = {a.id: a.name for a in agents}

        items = [
            NanobotSessionSchema.from_doc(
                doc,
                agent_name=name_by_agent.get(doc.agent_id),
            )
            for doc in docs
        ]
        return items, total

    @classmethod
    async def get_detail(cls, session_id: str) -> NanobotSessionSchema | None:
        """按会话 ID 查询详情（字段与列表项一致）。"""
        session_id = str(session_id or "").strip()
        if not session_id:
            return None
        doc = await NanobotSessionModel.find_one({"_id": session_id})
        if doc is None:
            return None
        agent = await NanobotAgentModel.find_one({"_id": doc.agent_id})
        agent_name = agent.name if agent is not None else None
        return NanobotSessionSchema.from_doc(
            doc,
            agent_name=agent_name,
            include_task_submissions=True,
        )
