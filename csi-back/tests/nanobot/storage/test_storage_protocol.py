"""MIGRATION_PLAN §12.2：SessionStore / MemoryBackend Protocol 契约。"""

from __future__ import annotations

from typing import Any

from app.service.nanobot.storage import MongoMemoryBackend, MongoSessionStore
from app.service.nanobot.storage.base import MemoryBackend, SessionStore


def test_protocol_isinstance_pass() -> None:
    assert isinstance(MongoSessionStore(), SessionStore)
    assert isinstance(MongoMemoryBackend(), MemoryBackend)


class _StubSessionStoreMissingMethods:
    """仅实现部分方法，用于验证 Protocol 结构检查。"""

    async def load(self, session_id: str) -> Any:
        return None


class _StubMemoryBackendMissingMethods:
    async def read_doc(self, workspace_id: str, doc_type: str) -> str:
        return ""


def test_protocol_isinstance_fail_incomplete_session_store() -> None:
    assert not isinstance(_StubSessionStoreMissingMethods(), SessionStore)


def test_protocol_isinstance_fail_incomplete_memory_backend() -> None:
    assert not isinstance(_StubMemoryBackendMissingMethods(), MemoryBackend)
