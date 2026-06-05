from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.v1.endpoints import wiki as wiki_ep
from app.schemas.constants import WikiPageStatusEnum
from app.schemas.general import PageResponseSchema
from app.schemas.wiki import (
    WikiCitationHealthSchema,
    WikiContentNodeSchema,
    WikiPageDetailSchema,
    WikiPageListItemSchema,
    WikiRevisionDiffSchema,
    WikiRevisionDiffSummarySchema,
)
from app.service.wiki.exceptions import WikiPageNotFoundError, WikiRevisionNotFoundError


def _detail() -> WikiPageDetailSchema:
    return WikiPageDetailSchema(
        id="a" * 32,
        title="测试",
        source_note=None,
        last_modified=datetime.now(),
        revision=1,
        status=WikiPageStatusEnum.DRAFT,
        content_tree=WikiContentNodeSchema(
            section="main", title="", content="", children=[]
        ),
        footnotes=[],
        references=[],
        categories=[],
        citation_health=WikiCitationHealthSchema(),
    )


@pytest.fixture
def wiki_app() -> FastAPI:
    app = FastAPI()
    app.include_router(wiki_ep.router, prefix="/api/v1")
    return app


@pytest.mark.asyncio
async def test_list_pages_route_registered(wiki_app: FastAPI) -> None:
    transport = ASGITransport(app=wiki_app)
    with patch.object(
        wiki_ep.WikiPageService,
        "list_pages",
        new_callable=AsyncMock,
        return_value=PageResponseSchema.create(items=[], total=0, page=1, page_size=10),
    ):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/wiki/pages")
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("total") == 0 or body.get("code") == 0


@pytest.mark.asyncio
async def test_get_page_not_found(wiki_app: FastAPI) -> None:
    transport = ASGITransport(app=wiki_app)
    with patch.object(
        wiki_ep.WikiPageService,
        "get_page",
        new_callable=AsyncMock,
        side_effect=WikiPageNotFoundError("不存在"),
    ):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/wiki/pages/missing")
    assert resp.status_code == 200
    assert resp.json()["code"] == 241001


@pytest.mark.asyncio
async def test_create_page_success(wiki_app: FastAPI) -> None:
    transport = ASGITransport(app=wiki_app)
    with patch.object(
        wiki_ep.WikiPageService,
        "create_page",
        new_callable=AsyncMock,
        return_value=_detail(),
    ):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/wiki/pages",
                json={"title": "标题"},
            )
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0
    assert data["data"]["id"] == "a" * 32


@pytest.mark.asyncio
async def test_delete_section_accepts_camel_case_revision_query(
    wiki_app: FastAPI,
) -> None:
    transport = ASGITransport(app=wiki_app)
    with patch.object(
        wiki_ep.WikiPageService,
        "delete_section",
        new_callable=AsyncMock,
        return_value=_detail(),
    ) as mock_delete:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.delete(
                f"/api/v1/wiki/pages/{'a' * 32}/sections/sec1?expectedRevision=3"
            )
    assert resp.status_code == 200
    assert resp.json()["code"] == 0
    mock_delete.assert_awaited_once_with(
        "a" * 32,
        "sec1",
        expected_revision=3,
        change_summary="",
    )


@pytest.mark.asyncio
async def test_diff_revisions_success(wiki_app: FastAPI) -> None:
    wiki_id = "a" * 32
    diff_data = WikiRevisionDiffSchema(
        wiki_id=wiki_id,
        from_revision=1,
        to_revision=2,
        summary=WikiRevisionDiffSummarySchema(),
    )
    transport = ASGITransport(app=wiki_app)
    with patch.object(
        wiki_ep.WikiPageService,
        "diff_revisions",
        new_callable=AsyncMock,
        return_value=diff_data,
    ) as mock_diff:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                f"/api/v1/wiki/pages/{wiki_id}/revisions/diff",
                params={"from": 1, "to": 2},
            )
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["fromRevision"] == 1
    assert body["data"]["toRevision"] == 2
    mock_diff.assert_awaited_once_with(wiki_id, 1, 2)


@pytest.mark.asyncio
async def test_diff_revisions_not_found(wiki_app: FastAPI) -> None:
    transport = ASGITransport(app=wiki_app)
    with patch.object(
        wiki_ep.WikiPageService,
        "diff_revisions",
        new_callable=AsyncMock,
        side_effect=WikiRevisionNotFoundError("不存在"),
    ):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                f"/api/v1/wiki/pages/{'a' * 32}/revisions/diff",
                params={"from": 1, "to": 99},
            )
    assert resp.status_code == 200
    assert resp.json()["code"] == 241006


def test_router_path_count() -> None:
    app = FastAPI()
    app.include_router(wiki_ep.router, prefix="/api/v1")
    paths = [r.path for r in app.routes if hasattr(r, "path") and "/wiki/" in r.path]
    assert len(paths) >= 16
