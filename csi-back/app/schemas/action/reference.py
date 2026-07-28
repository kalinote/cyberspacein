"""行动 Reference 流、队列绑定和控制帧契约。"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator


REFERENCE_EOS_TYPE = "csi.reference.eos.v1"
REFERENCE_ABORT_TYPE = "csi.reference.abort.v1"
REFERENCE_CONTROL_CONTENT_TYPE = (
    "application/vnd.cyberspacein.reference-control+json"
)
REFERENCE_PROTOCOL_EOS_V1 = "eos-v1"


class ReferenceProtocolEnum(str, Enum):
    """Reference 流支持的结束协议。"""

    EOS_V1 = REFERENCE_PROTOCOL_EOS_V1


class ReferenceProducerKindEnum(str, Enum):
    """Reference 流的数据生产者类型。"""

    COMPONENT = "component"
    NATIVE = "native"
    INPUT_BRIDGE = "input_bridge"
    OUTPUT_BRIDGE = "output_bridge"


class ReferenceStreamDescriptor(BaseModel):
    """描述一个归属于指定 Action 运行时的 Reference 队列。"""

    stream_id: str = Field(min_length=1)
    queue_name: str = Field(min_length=1)
    owner_action_id: str = Field(min_length=1)
    protocol_version: ReferenceProtocolEnum = ReferenceProtocolEnum.EOS_V1
    expected_producer_ids: list[str] = Field(default_factory=list)
    termination: Literal["eos"] = "eos"

    @field_validator("expected_producer_ids")
    @classmethod
    def deduplicate_producers(cls, values: list[str]) -> list[str]:
        """保留生产者声明顺序并去重。"""
        return list(dict.fromkeys(value for value in values if value))


class ReferenceQueueBinding(BaseModel):
    """冻结一条执行计划边对应的 Reference 队列信息。"""

    edge_id: str = Field(min_length=1)
    stream_id: str = Field(min_length=1)
    queue_name: str = Field(min_length=1)
    owner_action_id: str = Field(min_length=1)
    source_node_id: str = Field(min_length=1)
    source_port_id: str = Field(min_length=1)
    target_node_id: str = Field(min_length=1)
    target_port_id: str = Field(min_length=1)
    protocol_version: ReferenceProtocolEnum = ReferenceProtocolEnum.EOS_V1
    producer_kind: ReferenceProducerKindEnum = ReferenceProducerKindEnum.COMPONENT
    expected_producer_ids: list[str] = Field(default_factory=list)
    control_status: Literal["open", "eos", "abort"] = "open"

    @field_validator("expected_producer_ids")
    @classmethod
    def deduplicate_producers(cls, values: list[str]) -> list[str]:
        """保留生产者声明顺序并去重。"""
        return list(dict.fromkeys(value for value in values if value))


class ReferenceControlFrame(BaseModel):
    """控制消息的诊断载荷，协议识别仅依赖 AMQP Properties。"""

    stream_id: str = Field(min_length=1)
    producer_id: str = Field(min_length=1)
    action_id: str = Field(min_length=1)
    status: Literal["eos", "abort"]
    reason: str | None = None
