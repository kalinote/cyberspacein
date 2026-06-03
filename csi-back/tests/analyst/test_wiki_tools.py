"""Wiki 业务工具单元测试。"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

import app.service.analyst.context as ctx
import app.service.analyst.hitl as hitl_module
import app.service.analyst.tools as tools_module
import app.service.analyst.tools.registry as registry_module
from app.schemas.agent.hitl import HitlSource
from app.schemas.constants import WikiPageStatusEnum
from app.schemas.general import PageResponseSchema
from app.schemas.wiki import WikiPageDetailSchema, WikiPageListItemSchema
from app.service.analyst.hitl import HitlOutcome
from app.service.analyst.tools.wiki._fields import pick_fields
from app.service.wiki.exceptions import WikiPageNotFoundError


def _set_agent_ctx(agent_id: str = "a1", session_id: str = "s1") -> tuple[Any, Any]:
    t1 = ctx.current_agent_id.set(agent_id)
    t2 = ctx.current_session_id.set(session_id)
    return t1, t2


def _reset_agent_ctx(tokens: tuple[Any, Any]) -> None:
    t1, t2 = tokens
    ctx.current_session_id.reset(t2)
    ctx.current_agent_id.reset(t1)


def _hitl_outcome(
    *,
    approved: list[dict] | None = None,
    rejections: list[str] | None = None,
    resolution: str = "approved",
) -> HitlOutcome:
    approved = approved if approved is not None else [{"action": "approve"}]
    rejections = rejections if rejections is not None else []
    return HitlOutcome(
        approved=approved,
        rejections=rejections,
        resolution=resolution,
        approval_request_id="req-1",
        raw={},
    )


def _list_item() -> WikiPageListItemSchema:
    now = datetime(2026, 1, 1)
    return WikiPageListItemSchema(
        id="a" * 32,
        title="专题",
        source_note=None,
        status=WikiPageStatusEnum.DRAFT,
        categories=[],
        last_modified=now,
        revision=1,
        created_at=now,
    )


def _detail() -> WikiPageDetailSchema:
    return WikiPageDetailSchema(
        id="a" * 32,
        title="专题",
        source_note=None,
        last_modified=datetime(2026, 1, 1),
        revision=2,
        status=WikiPageStatusEnum.DRAFT,
        content_tree={
            "section": "main",
            "title": "",
            "content": "导语",
            "children": [],
        },
        footnotes=[],
        references=[],
        categories=[],
        citation_health={
            "missingRefs": [],
            "missingFootnotes": [],
            "orphanReferences": [],
            "orphanFootnotes": [],
        },
    )


def test_wiki_tools_in_registry() -> None:
    for name in ("wiki_list", "wiki_read", "wiki_create", "wiki_edit"):
        assert name in tools_module.BUSINESS_TOOL_CLASSES


def test_build_business_tools_includes_wiki() -> None:
    tools = tools_module.build_business_tools(["wiki_list", "wiki_read"])
    assert [t.name for t in tools] == ["wiki_list", "wiki_read"]


def test_pick_fields() -> None:
    data = {"id": "1", "title": "T", "revision": 2}
    assert pick_fields(data, ["id", "revision"]) == {"id": "1", "revision": 2}


@pytest.mark.asyncio
async def test_wiki_list_success(monkeypatch: pytest.MonkeyPatch) -> None:
    page = PageResponseSchema.create(items=[_list_item()], total=1, page=1, page_size=10)
    monkeypatch.setattr(
        "app.service.analyst.tools.wiki.list_tool.WikiPageService.list_pages",
        AsyncMock(return_value=page),
    )
    out = await tools_module.WikiListTool().execute(q="test")
    body = json.loads(out)
    assert body["total"] == 1
    assert body["items"][0]["title"] == "专题"


@pytest.mark.asyncio
async def test_wiki_read_with_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.service.analyst.tools.wiki.read_tool.WikiPageService.get_page",
        AsyncMock(return_value=_detail()),
    )
    out = await tools_module.WikiReadTool().execute(
        wiki_id="a" * 32,
        fields=["id", "revision", "title"],
    )
    body = json.loads(out)
    assert set(body.keys()) == {"id", "revision", "title"}


@pytest.mark.asyncio
async def test_wiki_read_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.service.analyst.tools.wiki.read_tool.WikiPageService.get_page",
        AsyncMock(side_effect=WikiPageNotFoundError("不存在")),
    )
    out = await tools_module.WikiReadTool().execute(wiki_id="x")
    assert "不存在" in out


@pytest.mark.asyncio
async def test_wiki_create_hitl_and_apply(monkeypatch: pytest.MonkeyPatch) -> None:
    tokens = _set_agent_ctx()
    captured: dict[str, Any] = {}

    async def _request(agent_id: str, session_id: str, source: str, payload: dict) -> HitlOutcome:
        captured.update(source=source, payload=payload)
        return _hitl_outcome()

    apply_mock = AsyncMock(
        return_value=({"ok": True, "wikiId": "w1", "revision": 1}, None)
    )
    monkeypatch.setattr(hitl_module.HitlService, "request_approval", _request)
    monkeypatch.setattr(
        "app.service.analyst.tools.wiki.create_tool.apply_wiki_create",
        apply_mock,
    )
    try:
        out = await tools_module.WikiCreateTool().execute(
            title="新专题",
            reason="需要新建",
        )
    finally:
        _reset_agent_ctx(tokens)

    body = json.loads(out)
    assert body["ok"] is True
    assert captured["source"] == HitlSource.TOOL_WIKI_CREATE
    assert captured["payload"]["title"] == "新专题"
    apply_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_wiki_create_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    tokens = _set_agent_ctx()
    monkeypatch.setattr(
        hitl_module.HitlService,
        "request_approval",
        AsyncMock(
            return_value=_hitl_outcome(
                approved=[],
                rejections=["不需要"],
                resolution="rejected",
            )
        ),
    )
    try:
        out = await tools_module.WikiCreateTool().execute(title="T", reason="r")
    finally:
        _reset_agent_ctx(tokens)
    assert out == "创建被拒绝：不需要"


@pytest.mark.asyncio
async def test_wiki_edit_hitl_and_apply(monkeypatch: pytest.MonkeyPatch) -> None:
    tokens = _set_agent_ctx()
    captured: dict[str, Any] = {}

    async def _request(agent_id: str, session_id: str, source: str, payload: dict) -> HitlOutcome:
        captured.update(source=source, payload=payload)
        return _hitl_outcome()

    apply_mock = AsyncMock(
        return_value=({"ok": True, "wikiId": "a" * 32, "revision": 3}, None)
    )
    monkeypatch.setattr(hitl_module.HitlService, "request_approval", _request)
    monkeypatch.setattr(
        "app.service.analyst.tools.wiki.edit_tool.apply_wiki_edit",
        apply_mock,
    )
    try:
        out = await tools_module.WikiEditTool().execute(
            wiki_id="a" * 32,
            operation="patch_main",
            expected_revision=2,
            params={"content": "新导语"},
            reason="更新导语",
        )
    finally:
        _reset_agent_ctx(tokens)

    body = json.loads(out)
    assert body["revision"] == 3
    assert captured["source"] == HitlSource.TOOL_WIKI_EDIT
    assert captured["payload"]["operation"] == "patch_main"
    apply_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_wiki_edit_invalid_operation() -> None:
    tokens = _set_agent_ctx()
    try:
        out = await tools_module.WikiEditTool().execute(
            wiki_id="a" * 32,
            operation="delete_section",
            expected_revision=1,
            reason="r",
        )
    finally:
        _reset_agent_ctx(tokens)
    assert "不支持的 operation" in out
