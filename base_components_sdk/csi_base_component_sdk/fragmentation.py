from __future__ import annotations

import hashlib
import math
import os
from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar
from uuid import uuid4


FRAGMENT_MESSAGE_TYPE = "csi.message.fragment.v1"
FRAGMENT_HEADER_ID = "x-csi-fragment-id"
FRAGMENT_HEADER_INDEX = "x-csi-fragment-index"
FRAGMENT_HEADER_COUNT = "x-csi-fragment-count"
FRAGMENT_HEADER_ORIGINAL_SIZE = "x-csi-original-size"
FRAGMENT_HEADER_ORIGINAL_SHA256 = "x-csi-original-sha256"
FRAGMENT_HEADER_ORIGINAL_MESSAGE_ID = "x-csi-original-message-id"

DEFAULT_FRAGMENT_THRESHOLD_BYTES = 12 * 1024 * 1024
DEFAULT_FRAGMENT_BYTES = 8 * 1024 * 1024
DEFAULT_MAX_LOGICAL_MESSAGE_BYTES = 256 * 1024 * 1024
MAX_PENDING_FRAGMENT_GROUPS = 128
MAX_FRAGMENT_COUNT = 4096

TokenT = TypeVar("TokenT")


class FragmentProtocolError(RuntimeError):
    """表示消息分片元数据、大小或完整性不符合协议。"""


def _read_positive_int(name: str, default: int) -> int:
    """读取可选正整数环境变量，未设置时返回默认值。"""
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} 必须是正整数") from exc
    if value <= 0:
        raise ValueError(f"{name} 必须是正整数")
    return value


@dataclass(frozen=True)
class FragmentSettings:
    """保存消息分片阈值、物理分片大小和逻辑消息上限。"""

    threshold_bytes: int = DEFAULT_FRAGMENT_THRESHOLD_BYTES
    fragment_bytes: int = DEFAULT_FRAGMENT_BYTES
    max_logical_message_bytes: int = DEFAULT_MAX_LOGICAL_MESSAGE_BYTES

    def __post_init__(self) -> None:
        if self.threshold_bytes <= 0:
            raise ValueError("消息分片阈值必须大于 0")
        if self.fragment_bytes <= 0:
            raise ValueError("物理分片大小必须大于 0")
        if self.fragment_bytes > self.threshold_bytes:
            raise ValueError("物理分片大小不能超过消息分片阈值")
        if self.threshold_bytes > self.max_logical_message_bytes:
            raise ValueError("消息分片阈值不能超过逻辑消息大小上限")

    @classmethod
    def from_env(cls) -> "FragmentSettings":
        """从可选环境变量加载配置，未设置的字段使用默认值。"""
        return cls(
            threshold_bytes=_read_positive_int(
                "CSI_RABBITMQ_FRAGMENT_THRESHOLD_BYTES",
                DEFAULT_FRAGMENT_THRESHOLD_BYTES,
            ),
            fragment_bytes=_read_positive_int(
                "CSI_RABBITMQ_FRAGMENT_BYTES",
                DEFAULT_FRAGMENT_BYTES,
            ),
            max_logical_message_bytes=_read_positive_int(
                "CSI_RABBITMQ_MAX_LOGICAL_MESSAGE_BYTES",
                DEFAULT_MAX_LOGICAL_MESSAGE_BYTES,
            ),
        )


@dataclass(frozen=True)
class EncodedFragment:
    """表示待发布的单个物理消息分片。"""

    body: bytes
    message_id: str
    headers: dict[str, Any]


@dataclass(frozen=True)
class ParsedFragment:
    """表示经过类型和边界校验的物理消息分片。"""

    fragment_id: str
    index: int
    count: int
    original_size: int
    original_sha256: str
    original_message_id: str
    body: bytes


@dataclass(frozen=True)
class AssembledMessage(Generic[TokenT]):
    """表示重组完成的逻辑消息及其全部物理交付令牌。"""

    body: bytes
    message_id: str
    tokens: tuple[TokenT, ...]


@dataclass
class _AssemblyState(Generic[TokenT]):
    count: int
    original_size: int
    original_sha256: str
    original_message_id: str
    chunks: dict[int, bytes] = field(default_factory=dict)
    tokens_by_index: dict[int, list[TokenT]] = field(default_factory=dict)
    arrival_tokens: list[TokenT] = field(default_factory=list)


def encode_fragments(
    body: bytes,
    message_id: str,
    settings: FragmentSettings,
) -> list[EncodedFragment]:
    """超过阈值时拆分消息，未超过阈值时返回空列表。"""
    size = len(body)
    if size > settings.max_logical_message_bytes:
        raise FragmentProtocolError(
            "逻辑消息大小 "
            f"{size} 超过上限 {settings.max_logical_message_bytes}"
        )
    if size <= settings.threshold_bytes:
        return []

    fragment_id = uuid4().hex
    checksum = hashlib.sha256(body).hexdigest()
    count = math.ceil(size / settings.fragment_bytes)
    fragments: list[EncodedFragment] = []
    for index in range(count):
        start = index * settings.fragment_bytes
        fragment_body = body[start : start + settings.fragment_bytes]
        fragments.append(
            EncodedFragment(
                body=fragment_body,
                message_id=f"fragment:{fragment_id}:{index}",
                headers={
                    FRAGMENT_HEADER_ID: fragment_id,
                    FRAGMENT_HEADER_INDEX: index,
                    FRAGMENT_HEADER_COUNT: count,
                    FRAGMENT_HEADER_ORIGINAL_SIZE: size,
                    FRAGMENT_HEADER_ORIGINAL_SHA256: checksum,
                    FRAGMENT_HEADER_ORIGINAL_MESSAGE_ID: message_id,
                },
            )
        )
    return fragments


def parse_fragment(
    body: bytes,
    message_type: str | None,
    headers: dict[str, Any] | None,
    settings: FragmentSettings,
) -> ParsedFragment | None:
    """识别并校验物理分片，普通业务消息返回 None。"""
    if message_type != FRAGMENT_MESSAGE_TYPE:
        return None
    metadata = headers or {}
    try:
        fragment_id = str(metadata[FRAGMENT_HEADER_ID])
        index = int(metadata[FRAGMENT_HEADER_INDEX])
        count = int(metadata[FRAGMENT_HEADER_COUNT])
        original_size = int(metadata[FRAGMENT_HEADER_ORIGINAL_SIZE])
        original_sha256 = str(metadata[FRAGMENT_HEADER_ORIGINAL_SHA256])
        original_message_id = str(metadata[FRAGMENT_HEADER_ORIGINAL_MESSAGE_ID])
    except (KeyError, TypeError, ValueError) as exc:
        raise FragmentProtocolError("消息分片缺少有效元数据") from exc

    if not fragment_id or not original_message_id:
        raise FragmentProtocolError("消息分片标识和原始消息 ID 不能为空")
    if count <= 1 or index < 0 or index >= count:
        raise FragmentProtocolError("消息分片序号或总数无效")
    if original_size <= settings.threshold_bytes:
        raise FragmentProtocolError("无需分片的消息使用了分片协议")
    if original_size > settings.max_logical_message_bytes:
        raise FragmentProtocolError(
            "逻辑消息大小 "
            f"{original_size} 超过上限 {settings.max_logical_message_bytes}"
        )
    if count > MAX_FRAGMENT_COUNT:
        raise FragmentProtocolError("消息分片总数超过允许上限")
    if not body or len(body) > settings.threshold_bytes:
        raise FragmentProtocolError("物理消息分片大小无效")
    if len(original_sha256) != 64:
        raise FragmentProtocolError("消息分片 SHA-256 元数据无效")

    return ParsedFragment(
        fragment_id=fragment_id,
        index=index,
        count=count,
        original_size=original_size,
        original_sha256=original_sha256,
        original_message_id=original_message_id,
        body=body,
    )


class FragmentAssembler(Generic[TokenT]):
    """按分片组重组逻辑消息，并保留所有物理交付令牌。"""

    def __init__(self, settings: FragmentSettings):
        self.settings = settings
        self._states: dict[str, _AssemblyState[TokenT]] = {}

    @property
    def has_pending(self) -> bool:
        """返回是否存在尚未完整重组的分片组。"""
        return bool(self._states)

    def add(
        self,
        fragment: ParsedFragment,
        token: TokenT,
    ) -> AssembledMessage[TokenT] | None:
        """加入单个分片，完整时返回逻辑消息，否则返回 None。"""
        state = self._states.get(fragment.fragment_id)
        if state is None:
            if len(self._states) >= MAX_PENDING_FRAGMENT_GROUPS:
                raise FragmentProtocolError("待重组消息组数量超过允许上限")
            state = _AssemblyState(
                count=fragment.count,
                original_size=fragment.original_size,
                original_sha256=fragment.original_sha256,
                original_message_id=fragment.original_message_id,
            )
            self._states[fragment.fragment_id] = state
        elif (
            state.count != fragment.count
            or state.original_size != fragment.original_size
            or state.original_sha256 != fragment.original_sha256
            or state.original_message_id != fragment.original_message_id
        ):
            raise FragmentProtocolError("同一分片组的元数据不一致")

        existing = state.chunks.get(fragment.index)
        if existing is not None and existing != fragment.body:
            raise FragmentProtocolError("同一序号出现内容不同的重复分片")
        if existing is None:
            state.chunks[fragment.index] = fragment.body
        state.tokens_by_index.setdefault(fragment.index, []).append(token)
        state.arrival_tokens.append(token)

        if len(state.chunks) != state.count:
            return None

        assembled = b"".join(state.chunks[index] for index in range(state.count))
        del self._states[fragment.fragment_id]
        if len(assembled) != state.original_size:
            raise FragmentProtocolError("消息分片重组后的大小不一致")
        if hashlib.sha256(assembled).hexdigest() != state.original_sha256:
            raise FragmentProtocolError("消息分片重组后的 SHA-256 不一致")
        return AssembledMessage(
            body=assembled,
            message_id=state.original_message_id,
            tokens=tuple(state.arrival_tokens),
        )

    def discard_pending(self) -> tuple[TokenT, ...]:
        """清空并返回所有未完成分片持有的交付令牌。"""
        tokens = tuple(
            token
            for state in self._states.values()
            for token in state.arrival_tokens
        )
        self._states.clear()
        return tokens
