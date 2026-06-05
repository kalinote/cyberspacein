"""search_entities 业务工具单元测试。"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

import app.service.analyst.tools as tools_module
from app.schemas.general import PageResponseSchema
from app.schemas.search import EntitySearchToolHitSchema


def test_search_entities_in_registry() -> None:
    assert "search_entities" in tools_module.BUSINESS_TOOL_CLASSES


def test_build_business_tools_includes_search_entities() -> None:
    tools = tools_module.build_business_tools(["search_entities"])
    assert len(tools) == 1
    assert tools[0].name == "search_entities"
    assert tools[0].read_only is True


@pytest.mark.asyncio
async def test_search_entities_es_not_initialized(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.db.elasticsearch.get_es", lambda: None)
    out = await tools_module.SearchEntitiesTool().execute(keywords=["测试"])
    assert "Elasticsearch 未初始化" in out


@pytest.mark.asyncio
async def test_search_entities_empty_keywords() -> None:
    out = await tools_module.SearchEntitiesTool().execute(keywords=[])
    assert "keywords 必须为非空" in out


@pytest.mark.asyncio
async def test_search_entities_success(monkeypatch: pytest.MonkeyPatch) -> None:
    hit = EntitySearchToolHitSchema(
        uuid="u1",
        entity_type="article",
        title="标题",
        snippets=["<em>命中</em>片段"],
        keywords_hits=1,
    )
    page = PageResponseSchema.create(items=[hit], total=1, page=1, page_size=10)

    class _ES:
        pass

    monkeypatch.setattr("app.db.elasticsearch.get_es", lambda: _ES())
    monkeypatch.setattr(
        "app.service.search.search_entities_keyword",
        AsyncMock(return_value=page),
    )
    out = await tools_module.SearchEntitiesTool().execute(
        keywords=["测试", "关键词"],
        keyword_match_mode="and",
        page=1,
        page_size=10,
    )
    body = json.loads(out)
    assert body["total"] == 1
    assert body["items"][0]["uuid"] == "u1"
    assert body["items"][0]["entityType"] == "article"
    assert body["items"][0]["title"] == "标题"
    assert body["items"][0]["snippets"] == ["<em>命中</em>片段"]
    assert body["items"][0]["keywordsHits"] == 1


@pytest.mark.asyncio
async def test_search_entities_invalid_match_mode() -> None:
    out = await tools_module.SearchEntitiesTool().execute(
        keywords=["a"],
        keyword_match_mode="xor",
    )
    assert "keyword_match_mode" in out
