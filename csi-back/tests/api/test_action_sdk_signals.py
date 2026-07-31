from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.api.v1.endpoints.action import sdk as sdk_endpoint
from app.core.exceptions import BadRequestException, ForbiddenException
from app.schemas.component_signal import (
    ComponentSignalBatchRequest,
    ComponentSignalBatchResponse,
    ComponentSignalReport,
    ComponentSignalReportResult,
    ComponentSignalResourceRef,
)
from app.service.component_signal.ingestion import ComponentSignalIngestionService


def batch() -> ComponentSignalBatchRequest:
    """构造组件信号 API 请求。"""
    return ComponentSignalBatchRequest(
        reports=[
            ComponentSignalReport(
                report_id="report-1",
                definition_key="component.demo.health",
                definition_version=1,
                resource=ComponentSignalResourceRef(
                    resource_id="resource-1",
                ),
                value="abnormal",
                observed_at=datetime.now(timezone.utc),
            )
        ]
    )


def request(content_length: str | None = None):
    """构造已通过组件路由鉴权的请求对象。"""
    headers = {}
    if content_length is not None:
        headers["content-length"] = content_length
    return SimpleNamespace(
        state=SimpleNamespace(
            component_context=SimpleNamespace(
                action_id="action-1",
                node_instance_id="node-1",
                component_run_id="run-1",
                component_id="component-a",
            )
        ),
        headers=headers,
    )


@pytest.mark.asyncio
async def test_submit_signals_returns_ingestion_result(monkeypatch) -> None:
    ingest = AsyncMock(
        return_value=ComponentSignalBatchResponse(
            results=[
                ComponentSignalReportResult(
                    report_id="report-1",
                    status="accepted",
                    observation_id="observation-1",
                )
            ]
        )
    )
    monkeypatch.setattr(
        ComponentSignalIngestionService,
        "ingest_batch",
        ingest,
    )

    response = await sdk_endpoint.submit_signals(
        "run-1",
        batch(),
        request(),
    )

    assert response.code == 0
    assert response.data.results[0].status == "accepted"
    ingest.assert_awaited_once()


@pytest.mark.asyncio
async def test_submit_signals_rejects_oversized_request(monkeypatch) -> None:
    monkeypatch.setattr(
        sdk_endpoint.settings,
        "COMPONENT_SIGNAL_MAX_REQUEST_BYTES",
        10,
    )

    with pytest.raises(BadRequestException, match="大小超过限制"):
        await sdk_endpoint.submit_signals(
            "run-1",
            batch(),
            request("11"),
        )


@pytest.mark.asyncio
async def test_submit_signals_maps_definition_authorization_failure(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        ComponentSignalIngestionService,
        "ingest_batch",
        AsyncMock(side_effect=PermissionError("无权上报")),
    )

    with pytest.raises(ForbiddenException, match="无权上报"):
        await sdk_endpoint.submit_signals(
            "run-1",
            batch(),
            request(),
        )
