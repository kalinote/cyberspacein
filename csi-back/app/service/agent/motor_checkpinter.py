from collections.abc import AsyncIterator, Sequence
from datetime import datetime
from typing import Any, Optional

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import (
    WRITES_IDX_MAP,
    BaseCheckpointSaver,
    ChannelVersions,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
    get_checkpoint_id,
)
from langgraph.checkpoint.serde.base import SerializerProtocol
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from pymongo import UpdateOne
from app.models.agent.checkpoint import CheckpointModel, CheckpointWriteModel
from langgraph.checkpoint.mongodb.utils import dumps_metadata, loads_metadata



def _pending_writes_from_serde(
    serde: SerializerProtocol, serialized_writes: list[dict[str, Any]]
) -> list[tuple[str, str, Any]]:
    """反序列化待写入记录"""
    return [
        (
            wdoc["task_id"],
            wdoc["channel"],
            serde.loads_typed((wdoc["type"], wdoc["value"])),
        )
        for wdoc in serialized_writes
    ]


class MotorCheckpointerSaver(BaseCheckpointSaver):
    """基于 MongoDB（Beanie/Motor）的 LangGraph checkpoint 存储，用于图状态的持久化与恢复。"""

    def __init__(
        self,
        ttl: Optional[int] = None,
        serde: Optional[SerializerProtocol] = None,
    ) -> None:
        """ttl 用于 TTL 过期索引；serde 未传时使用 JsonPlusSerializer。"""
        super().__init__()
        self.ttl = ttl
        self.serde = serde if serde is not None else JsonPlusSerializer()

    async def aget_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        """按 config 取单个 checkpoint：有 checkpoint_id 则按 id 取，否则取该 thread 下最新一条，并拉取 pending writes 组装为 CheckpointTuple。"""
        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "")
        # 有 checkpoint_id 则按 id 取，否则取该 thread 下最新一条
        if checkpoint_id := get_checkpoint_id(config):
            doc = await CheckpointModel.find_one({
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": checkpoint_id,
            })
        else:
            docs = await CheckpointModel.find({
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
            }).sort("-checkpoint_id").limit(1).to_list()
            doc = docs[0] if docs else None
        if doc is None:
            return None
        # 拉取该 checkpoint 的 pending writes，反序列化后组装为 CheckpointTuple
        config_values = {
            "thread_id": thread_id,
            "checkpoint_ns": checkpoint_ns,
            "checkpoint_id": doc.checkpoint_id,
        }
        checkpoint = self.serde.loads_typed((doc.type, doc.checkpoint))
        write_docs = await CheckpointWriteModel.find({
            "thread_id": thread_id,
            "checkpoint_ns": checkpoint_ns,
            "checkpoint_id": doc.checkpoint_id,
        }).to_list()
        serialized_writes = [
            {"task_id": w.task_id, "channel": w.channel, "type": w.type, "value": w.value}
            for w in write_docs
        ]
        pending_writes = _pending_writes_from_serde(self.serde, serialized_writes)
        return CheckpointTuple(
            {"configurable": config_values},
            checkpoint,
            loads_metadata(self.serde, doc.metadata),
            (
                {
                    "configurable": {
                        "thread_id": thread_id,
                        "checkpoint_ns": checkpoint_ns,
                        "checkpoint_id": doc.parent_checkpoint_id,
                    }
                }
                if doc.parent_checkpoint_id
                else None
            ),
            pending_writes,
        )

    async def alist(
        self,
        config: Optional[RunnableConfig],
        *,
        filter: Optional[dict[str, Any]] = None,
        before: Optional[RunnableConfig] = None,
        limit: Optional[int] = None,
    ) -> AsyncIterator[CheckpointTuple]:
        """按 thread/ns、metadata 过滤、before、limit 列出 checkpoint，逐个 yield CheckpointTuple。"""
        # 按 thread/ns、metadata 过滤、before、limit 构建查询
        query: dict[str, Any] = {}
        if config is not None:
            if "thread_id" in config["configurable"]:
                query["thread_id"] = config["configurable"]["thread_id"]
            if "checkpoint_ns" in config["configurable"]:
                query["checkpoint_ns"] = config["configurable"]["checkpoint_ns"]
        if filter:
            for key, value in filter.items():
                query[f"metadata.{key}"] = dumps_metadata(self.serde, value)
        if before is not None:
            query["checkpoint_id"] = {"$lt": before["configurable"]["checkpoint_id"]}
        cursor = CheckpointModel.find(query).sort("-checkpoint_id")
        if limit is not None:
            cursor = cursor.limit(limit)
        async for doc in cursor:
            config_values = {
                "thread_id": doc.thread_id,
                "checkpoint_ns": doc.checkpoint_ns,
                "checkpoint_id": doc.checkpoint_id,
            }
            write_docs = await CheckpointWriteModel.find({
                "thread_id": doc.thread_id,
                "checkpoint_ns": doc.checkpoint_ns,
                "checkpoint_id": doc.checkpoint_id,
            }).to_list()
            serialized_writes = [
                {"task_id": w.task_id, "channel": w.channel, "type": w.type, "value": w.value}
                for w in write_docs
            ]
            pending_writes = _pending_writes_from_serde(self.serde, serialized_writes)
            yield CheckpointTuple(
                config={"configurable": config_values},
                checkpoint=self.serde.loads_typed((doc.type, doc.checkpoint)),
                metadata=loads_metadata(self.serde, doc.metadata),
                parent_config=(
                    {
                        "configurable": {
                            "thread_id": doc.thread_id,
                            "checkpoint_ns": doc.checkpoint_ns,
                            "checkpoint_id": doc.parent_checkpoint_id,
                        }
                    }
                    if doc.parent_checkpoint_id
                    else None
                ),
                pending_writes=pending_writes,
            )

    async def aput(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        """将当前步的 checkpoint 写入 MongoDB，已存在则更新否则插入，返回带 checkpoint_id 的 config。"""
        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "")
        checkpoint_id = checkpoint["id"]
        type_, serialized_checkpoint = self.serde.dumps_typed(checkpoint)
        meta = metadata.copy()
        meta.update(config.get("metadata", {}))
        doc = await CheckpointModel.find_one({
            "thread_id": thread_id,
            "checkpoint_ns": checkpoint_ns,
            "checkpoint_id": checkpoint_id,
        })
        if doc is not None:
            doc.type = type_
            doc.checkpoint = serialized_checkpoint
            doc.metadata = dumps_metadata(self.serde, meta)
            await doc.save()
        else:
            new_doc = CheckpointModel(
                thread_id=thread_id,
                checkpoint_ns=checkpoint_ns,
                checkpoint_id=checkpoint_id,
                parent_checkpoint_id=config["configurable"].get("checkpoint_id"),
                type=type_,
                checkpoint=serialized_checkpoint,
                metadata=dumps_metadata(self.serde, meta),
            )
            await new_doc.insert()
        return {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": checkpoint_id,
            }
        }

    async def aput_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        """将某任务的 channel 写入序列批量 upsert 到 CheckpointWriteDoc 集合。"""
        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "")
        checkpoint_id = config["configurable"]["checkpoint_id"]
        # 所有 channel 在 WRITES_IDX_MAP 内用 $set，否则 $setOnInsert
        set_method = (
            "$set" if all(w[0] in WRITES_IDX_MAP for w in writes) else "$setOnInsert"
        )
        coll = CheckpointWriteModel.get_pymongo_collection()
        operations = []
        for idx, (channel, value) in enumerate(writes):
            upsert_query = {
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": checkpoint_id,
                "task_id": task_id,
                "task_path": task_path,
                "idx": WRITES_IDX_MAP.get(channel, idx),
            }
            type_, serialized_value = self.serde.dumps_typed(value)
            update_doc: dict[str, Any] = {
                "channel": channel,
                "type": type_,
                "value": serialized_value,
            }
            update_op: dict[str, Any] = {set_method: update_doc, "$setOnInsert": {"created_at": datetime.utcnow()}}
            operations.append(
                UpdateOne(
                    filter=upsert_query,
                    update=update_op,
                    upsert=True,
                )
            )
        if operations:
            await coll.bulk_write(operations)

    async def adelete_thread(self, thread_id: str) -> None:
        """删除该 thread_id 下所有 CheckpointDoc 与 CheckpointWriteDoc。"""
        await CheckpointModel.find({"thread_id": thread_id}).delete()
        await CheckpointWriteModel.find({"thread_id": thread_id}).delete()
