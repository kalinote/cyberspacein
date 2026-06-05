"""entity_modify 工具函数测试。"""
from __future__ import annotations

from typing import Any

import pytest

from app.schemas.constants import EntityType
from app.service.analyst.utils import entity_modify as em


def test_apply_modifications_set_and_nested() -> None:
    source = {"title": "a", "meta": {"k": 1}}
    doc = em.apply_modifications_to_source(
        source,
        [
            {"field": "title", "action": "set", "value": "b"},
            {"field": "meta.k", "action": "set", "value": 2},
        ],
    )
    assert doc["title"] == "b"
    assert doc["meta"] == {"k": 2}
    assert "update_at" in doc
    assert source["title"] == "a"


def test_apply_modifications_append_remove() -> None:
    source = {"tags": ["a", "b"]}
    doc = em.apply_modifications_to_source(
        source,
        [
            {"field": "tags", "action": "append", "value": "c"},
            {"field": "tags", "action": "remove", "value": "a"},
        ],
    )
    assert doc["tags"] == ["b", "c"]


@pytest.mark.asyncio
async def test_apply_entity_modifications_to_es_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    class _ES:
        async def get(self, *, index: str, id: str):
            assert index == "article" and id == "u1"
            return {"_source": {"title": "old", "tags": ["x"]}}

        async def update(self, *, index: str, id: str, body: dict):
            captured["index"] = index
            captured["id"] = id
            captured["body"] = body

    monkeypatch.setattr(em, "get_es", lambda: _ES())
    err = await em.apply_entity_modifications_to_es(
        EntityType.ARTICLE.value,
        "u1",
        [
            {"field": "title", "action": "set", "value": "new"},
            {"field": "tags", "action": "append", "value": "y"},
        ],
    )
    assert err is None
    assert captured["body"]["doc"]["title"] == "new"
    assert captured["body"]["doc"]["tags"] == ["x", "y"]


@pytest.mark.asyncio
async def test_apply_entity_modifications_to_es_not_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from elasticsearch.exceptions import NotFoundError

    class _ES:
        async def get(self, **_kw):
            raise NotFoundError(404, "not found", {})

    monkeypatch.setattr(em, "get_es", lambda: _ES())
    err = await em.apply_entity_modifications_to_es(
        EntityType.ARTICLE.value,
        "missing",
        [{"field": "title", "action": "set", "value": "x"}],
    )
    assert err and "不存在" in err
