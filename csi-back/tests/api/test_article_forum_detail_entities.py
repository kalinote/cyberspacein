"""文章/论坛详情接口 entities 字段契约测试。"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from app.api.v1.endpoints import article as article_ep
from app.api.v1.endpoints import forum as forum_ep


class _FakeES:
    def __init__(self, source: dict[str, Any]) -> None:
        self._source = source

    async def get(self, index: str, id: str) -> dict[str, Any]:
        return {"_source": self._source}

    async def search(self, index: str, body: dict[str, Any]) -> dict[str, Any]:
        return {"hits": {"hits": []}}


def _article_client(monkeypatch: pytest.MonkeyPatch, source: dict[str, Any]) -> TestClient:
    app = FastAPI()
    app.include_router(article_ep.router, prefix="/api/v1")
    monkeypatch.setattr(article_ep, "get_es", lambda: _FakeES(source))
    async def _no_platform(*_args: Any, **_kwargs: Any) -> None:
        return None

    monkeypatch.setattr(article_ep.PlatformModel, "find_one", _no_platform)
    return TestClient(app)


def _forum_client(monkeypatch: pytest.MonkeyPatch, source: dict[str, Any]) -> TestClient:
    app = FastAPI()
    app.include_router(forum_ep.router, prefix="/api/v1")
    monkeypatch.setattr(forum_ep, "get_es", lambda: _FakeES(source))
    async def _no_platform(*_args: Any, **_kwargs: Any) -> None:
        return None

    monkeypatch.setattr(forum_ep.PlatformModel, "find_one", _no_platform)
    return TestClient(app)


def _minimal_source(**extra: Any) -> dict[str, Any]:
    return {
        "uuid": "u1",
        "entity_type": "article",
        **extra,
    }


def test_article_detail_entities_present(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _article_client(
        monkeypatch,
        _minimal_source(
            entities={
                "person": ["甲"],
                "organization": [],
                "location": [],
                "company": [],
                "network_user": [],
                "region": [],
            }
        ),
    )
    r = client.get("/api/v1/article/detail/u1")
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == 0
    entities = body["data"]["entities"]
    assert entities["person"] == ["甲"]
    assert entities["organization"] == []


def test_article_detail_entities_absent_is_null(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _article_client(monkeypatch, _minimal_source())
    r = client.get("/api/v1/article/detail/u1")
    assert r.status_code == 200
    assert r.json()["data"]["entities"] is None


def test_forum_detail_entities_present(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _forum_client(
        monkeypatch,
        {
            "uuid": "f1",
            "entity_type": "forum",
            "entities": {"person": ["乙"], "organization": ["机构"]},
        },
    )
    r = client.get("/api/v1/forum/detail/f1")
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == 0
    entities = body["data"]["entities"]
    assert entities["person"] == ["乙"]
    assert entities["organization"] == ["机构"]
    assert entities["location"] == []


def test_forum_detail_entities_absent_is_null(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _forum_client(
        monkeypatch,
        {"uuid": "f1", "entity_type": "forum"},
    )
    r = client.get("/api/v1/forum/detail/f1")
    assert r.status_code == 200
    assert r.json()["data"]["entities"] is None
