from typing import Any

from beanie import Document
from pydantic import Field


class CheckpointModel(Document):
    thread_id: str = Field(..., description="会话/线程 ID，用于区分不同会话")
    checkpoint_ns: str = Field("", description="checkpoint 命名空间")
    checkpoint_id: str = Field(..., description="当前 checkpoint 的唯一 ID")
    parent_checkpoint_id: str | None = Field(None, description="上一 checkpoint 的 ID，用于形成历史链")
    type: str = Field(..., description="checkpoint 序列化类型标识")
    checkpoint: Any = Field(..., description="序列化后的整份 checkpoint 状态（channel_values、channel_versions 等）")
    metadata: Any = Field(..., description="序列化后的元数据（如 step、source）")

    class Settings:
        name = "agent_checkpointer"
        indexes = [
            "thread_id", "checkpoint_ns", "checkpoint_id"
        ]


class CheckpointWriteModel(Document):
    thread_id: str = Field(..., description="会话/线程 ID")
    checkpoint_ns: str = Field("", description="checkpoint 命名空间")
    checkpoint_id: str = Field(..., description="所属 checkpoint 的 ID")
    task_id: str = Field(..., description="产生该写入的图任务 ID")
    task_path: str = Field("", description="任务路径，子图时使用")
    idx: int = Field(..., description="写入序号（channel 在 WRITES_IDX_MAP 中的索引或顺序）")
    channel: str = Field(..., description="写入的 channel 名（如 messages）")
    type: str = Field(..., description="该条 value 的序列化类型")
    value: Any = Field(..., description="序列化后的单条写入内容")

    class Settings:
        name = "agent_checkpointer_writes"
        indexes = [
            "thread_id", "checkpoint_ns", "checkpoint_id", "task_id", "idx"
        ]