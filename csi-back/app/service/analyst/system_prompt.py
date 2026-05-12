from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId
from loguru import logger

import app.utils.status_codes as status_codes
from app.models.agent.nanobot import NanobotMemoryDocsModel
from app.schemas.agent.configs import (
    SystemPromptCreateRequestSchema,
    SystemPromptUpdateRequestSchema,
)
from app.schemas.constants import NanobotMemoryDocTypeEnum

logger = logger.bind(name=__name__)


class SystemPromptServiceError(Exception):
    def __init__(self, code: int, message: str, data: Any | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data


class SystemPromptService:
    @classmethod
    async def create(
        cls,
        data: SystemPromptCreateRequestSchema,
    ) -> NanobotMemoryDocsModel:
        existing = await cls._find_by_workspace_type(data.workspace_id, data.type)
        if existing is not None:
            raise SystemPromptServiceError(
                status_codes.CONFLICT_EXISTS,
                f"系统指令模板已存在: workspace={data.workspace_id} type={data.type.value}",
            )

        doc = NanobotMemoryDocsModel(
            workspace_id=data.workspace_id,
            type=data.type,
            content=data.content,
        )
        await doc.insert()
        logger.info(f"创建系统指令模板成功: id={doc.id} workspace={data.workspace_id} type={data.type.value}")
        return doc

    @classmethod
    async def get(cls, system_prompt_id: str) -> NanobotMemoryDocsModel:
        doc = await NanobotMemoryDocsModel.find_one(cls._id_query(system_prompt_id))
        if doc is None:
            raise SystemPromptServiceError(
                status_codes.NOT_FOUND,
                f"系统指令模板不存在: {system_prompt_id}",
            )
        return doc

    @classmethod
    async def list_page(
        cls,
        *,
        page: int,
        page_size: int,
        workspace_id: str | None = None,
        type: NanobotMemoryDocTypeEnum | None = None,
        search: str | None = None,
    ) -> tuple[list[NanobotMemoryDocsModel], int]:
        query_filters: dict[str, Any] = {}
        if workspace_id:
            query_filters["workspace_id"] = workspace_id
        if type is not None:
            query_filters["type"] = type
        if search:
            query_filters["content"] = {"$regex": re.compile(re.escape(search), re.IGNORECASE)}

        query = NanobotMemoryDocsModel.find(query_filters)
        total = await query.count()
        skip = (page - 1) * page_size
        items = await query.skip(skip).limit(page_size).to_list()
        return items, total

    @classmethod
    async def update(
        cls,
        system_prompt_id: str,
        data: SystemPromptUpdateRequestSchema,
    ) -> NanobotMemoryDocsModel:
        doc = await cls.get(system_prompt_id)
        existing = await cls._find_by_workspace_type(data.workspace_id, data.type)
        if existing is not None and str(existing.id) != str(doc.id):
            raise SystemPromptServiceError(
                status_codes.CONFLICT_EXISTS,
                f"系统指令模板已存在: workspace={data.workspace_id} type={data.type.value}",
            )

        doc.workspace_id = data.workspace_id
        doc.type = data.type
        doc.content = data.content
        doc.updated_at = datetime.now()
        await doc.save()
        logger.info(f"更新系统指令模板成功: id={doc.id} workspace={data.workspace_id} type={data.type.value}")
        return doc

    @classmethod
    async def delete(cls, system_prompt_id: str) -> None:
        doc = await cls.get(system_prompt_id)
        await doc.delete()
        logger.info(f"删除系统指令模板成功: id={system_prompt_id}")

    @staticmethod
    async def _find_by_workspace_type(
        workspace_id: str,
        prompt_type: NanobotMemoryDocTypeEnum,
    ) -> NanobotMemoryDocsModel | None:
        return await NanobotMemoryDocsModel.find_one(
            {
                "workspace_id": workspace_id,
                "type": prompt_type,
            }
        )

    @staticmethod
    def _id_query(system_prompt_id: str) -> dict[str, Any]:
        try:
            return {"_id": ObjectId(system_prompt_id)}
        except InvalidId:
            return {"_id": system_prompt_id}
