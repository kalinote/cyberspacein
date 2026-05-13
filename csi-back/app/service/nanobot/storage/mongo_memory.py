"""MemoryBackend 的 MongoDB 实现

集合对应关系：
  - nanobot_memory_docs     ↔ NanobotMemoryDocsModel（MEMORY / SOUL / USER / AGENT 等）
  - nanobot_history         ↔ NanobotHistoryModel（append-only 摘要条目）
  - nanobot_history_state   ↔ NanobotHistoryStateModel（last_cursor / last_dream_cursor）

数据按 workspace_id 隔离，同 workspace 下所有 Agent 共享。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from beanie.odm.enums import SortDirection
from loguru import logger
from pymongo import ReturnDocument

from app.models.agent.nanobot import (
    NanobotHistoryModel,
    NanobotHistoryStateModel,
    NanobotMemoryDocsModel,
)
from app.schemas.constants import NanobotMemoryDocTypeEnum


logger = logger.bind(name=__name__)


class MongoMemoryBackend:
    """MemoryBackend 的 MongoDB 实现"""

    # ------------------------------------------------------------------
    # memory docs（按 type 区分；同 workspace 同 type 可多份，读写取 updated_at 最新一条）
    # TODO: 后续改成每一类可以读取多条，全部读取并拼接到一起
    # ------------------------------------------------------------------

    async def read_doc(self, workspace_id: str, doc_type: str) -> str:
        docs = await (
            NanobotMemoryDocsModel.find(
                {"workspace_id": workspace_id, "type": doc_type},
            )
            .sort(("updated_at", SortDirection.DESCENDING))
            .limit(1)
            .to_list()
        )
        return docs[0].content if docs else ""

    async def write_doc(self, workspace_id: str, doc_type: str, content: str) -> None:
        now = datetime.now()
        docs = await (
            NanobotMemoryDocsModel.find(
                {"workspace_id": workspace_id, "type": doc_type},
            )
            .sort(("updated_at", SortDirection.DESCENDING))
            .limit(1)
            .to_list()
        )
        doc = docs[0] if docs else None
        if doc is None:
            await NanobotMemoryDocsModel(
                workspace_id=workspace_id,
                type=NanobotMemoryDocTypeEnum(doc_type),
                name=doc_type,
                description=None,
                content=content,
                created_at=now,
                updated_at=now,
            ).insert()
        else:
            doc.content = content
            doc.updated_at = now
            await doc.save()

    # ------------------------------------------------------------------
    # history（append-only 摘要条目）
    # ------------------------------------------------------------------

    async def append_history(self, workspace_id: str, entry: str) -> int:
        """追加历史条目，原子分配 cursor 并同步更新 nanobot_history_state.last_cursor"""
        now = datetime.now()

        # 通过 $inc + upsert 原子分配 cursor，返回更新后的 state
        collection = NanobotHistoryStateModel.get_pymongo_collection()
        updated = await collection.find_one_and_update(
            {"_id": workspace_id},
            {
                "$inc": {"last_cursor": 1},
                "$set": {"updated_at": now},
                "$setOnInsert": {"last_dream_cursor": 0},
            },
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        new_cursor = int(updated["last_cursor"])

        await NanobotHistoryModel(
            workspace_id=workspace_id,
            cursor=new_cursor,
            content=entry,
            created_at=now,
        ).insert()

        return new_cursor

    async def read_history(
        self,
        workspace_id: str,
        since_cursor: int = 0,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        query = NanobotHistoryModel.find(
            {
                "workspace_id": workspace_id,
                "cursor": {"$gt": since_cursor},
            }
        ).sort("+cursor")
        if limit is not None:
            query = query.limit(limit)
        docs = await query.to_list()
        return [
            {
                "cursor": d.cursor,
                "content": d.content,
                "created_at": d.created_at,
            }
            for d in docs
        ]

    async def compact_history(self, workspace_id: str, max_entries: int) -> int:
        """若历史条目数超过 max_entries，按 cursor 升序删除最旧的"""
        if max_entries < 0:
            return 0

        total = await NanobotHistoryModel.find(
            {"workspace_id": workspace_id}
        ).count()
        if total <= max_entries:
            return 0

        to_delete = total - max_entries
        oldest = (
            await NanobotHistoryModel
            .find({"workspace_id": workspace_id})
            .sort("+cursor")
            .limit(to_delete)
            .to_list()
        )
        if not oldest:
            return 0

        cutoff_cursor = oldest[-1].cursor
        collection = NanobotHistoryModel.get_pymongo_collection()
        result = await collection.delete_many({
            "workspace_id": workspace_id,
            "cursor": {"$lte": cutoff_cursor},
        })
        deleted = int(result.deleted_count)
        logger.debug(
            "workspace {} 压缩历史：删除 cursor≤{} 的 {} 条",
            workspace_id,
            cutoff_cursor,
            deleted,
        )
        return deleted

    # ------------------------------------------------------------------
    # cursors
    # ------------------------------------------------------------------

    async def get_cursors(self, workspace_id: str) -> tuple[int, int]:
        state = await NanobotHistoryStateModel.find_one({"_id": workspace_id})
        if state is None:
            return (0, 0)
        return (state.last_cursor, state.last_dream_cursor)

    async def set_dream_cursor(self, workspace_id: str, cursor: int) -> None:
        now = datetime.now()
        state = await NanobotHistoryStateModel.find_one({"_id": workspace_id})
        if state is None:
            await NanobotHistoryStateModel(
                id=workspace_id,
                last_cursor=0,
                last_dream_cursor=cursor,
                updated_at=now,
            ).insert()
        else:
            state.last_dream_cursor = cursor
            state.updated_at = now
            await state.save()
