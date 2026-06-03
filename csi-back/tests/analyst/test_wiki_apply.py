"""wiki_apply 单元测试。"""
from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from app.schemas.constants import WikiPageStatusEnum
from app.schemas.wiki import WikiPageDetailSchema
from app.service.analyst.utils import wiki_apply as wiki_apply_module
from app.service.analyst.utils.wiki_apply import apply_wiki_create, apply_wiki_edit
from app.service.wiki.exceptions import WikiRevisionConflictError


def _detail(wiki_id: str = "a" * 32, revision: int = 2) -> WikiPageDetailSchema:
    return WikiPageDetailSchema(
        id=wiki_id,
        title="T",
        source_note=None,
        last_modified=datetime(2026, 1, 1),
        revision=revision,
        status=WikiPageStatusEnum.DRAFT,
        content_tree={
            "section": "main",
            "title": "",
            "content": "",
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


@pytest.mark.asyncio
async def test_apply_wiki_create_success(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_create = AsyncMock(return_value=_detail(revision=1))
    monkeypatch.setattr(
        wiki_apply_module.WikiPageService,
        "create_page",
        mock_create,
    )
    result, err = await apply_wiki_create(
        {"title": "新页", "categories": ["c1"], "reason": "r"},
        agent_id="agent1",
    )
    assert err is None
    assert result["ok"] is True
    assert result["revision"] == 1
    mock_create.assert_awaited_once_with(
        title="新页",
        source_note=None,
        categories=["c1"],
        operator="agent:agent1",
    )


@pytest.mark.asyncio
async def test_apply_wiki_create_empty_title() -> None:
    result, err = await apply_wiki_create({"title": "  "})
    assert result is None
    assert "标题不能为空" in err


@pytest.mark.asyncio
async def test_apply_wiki_edit_patch_meta(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_patch = AsyncMock(return_value=_detail(revision=3))
    monkeypatch.setattr(wiki_apply_module.WikiPageService, "patch_meta", mock_patch)
    payload = {
        "wiki_id": "a" * 32,
        "operation": "patch_meta",
        "expected_revision": 2,
        "change_summary": "s",
        "params": {"title": "新标题", "status": "published"},
    }
    result, err = await apply_wiki_edit(payload, agent_id="a1")
    assert err is None
    assert result["revision"] == 3
    mock_patch.assert_awaited_once()
    kw = mock_patch.await_args.kwargs
    assert kw["title"] == "新标题"
    assert kw["status"] == WikiPageStatusEnum.PUBLISHED
    assert kw["operator"] == "agent:a1"


@pytest.mark.asyncio
async def test_apply_wiki_edit_add_section(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_add = AsyncMock(return_value=(_detail(revision=4), "sec_new"))
    monkeypatch.setattr(wiki_apply_module.WikiPageService, "add_section", mock_add)
    result, err = await apply_wiki_edit(
        {
            "wiki_id": "b" * 32,
            "operation": "add_section",
            "expected_revision": 3,
            "params": {
                "parent_section": "main",
                "title": "章节",
            },
        },
    )
    assert err is None
    assert result["newSectionId"] == "sec_new"


@pytest.mark.asyncio
async def test_apply_wiki_edit_revision_conflict(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        wiki_apply_module.WikiPageService,
        "patch_main",
        AsyncMock(
            side_effect=WikiRevisionConflictError(
                "修订号冲突：当前 5，提交 3"
            )
        ),
    )
    result, err = await apply_wiki_edit(
        {
            "wiki_id": "c" * 32,
            "operation": "patch_main",
            "expected_revision": 3,
            "params": {"content": "x"},
        },
    )
    assert result is None
    assert "241003" in err
    assert "wiki_read" in err


@pytest.mark.asyncio
async def test_apply_wiki_edit_invalid_operation() -> None:
    result, err = await apply_wiki_edit(
        {
            "wiki_id": "d" * 32,
            "operation": "delete_page",
            "expected_revision": 1,
            "params": {},
        },
    )
    assert result is None
    assert "不支持的 operation" in err
