"""app.service.component 对外部 Crawlab 调用的测试（HTTP 使用 mock）。"""

from unittest.mock import AsyncMock

import pytest

from app.service import component as component_svc


@pytest.mark.asyncio
async def test_get_components_success(monkeypatch: pytest.MonkeyPatch) -> None:
    # 正常返回 unwrap_response 解包后的 data 字段
    monkeypatch.setattr(
        "app.service.component.async_get",
        AsyncMock(return_value={"data": {"list": []}}),
    )
    out = await component_svc.get_components(page=1, page_size=10)
    assert out == {"list": []}


@pytest.mark.asyncio
async def test_get_components_exception_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    # 请求异常时返回 None
    monkeypatch.setattr(
        "app.service.component.async_get",
        AsyncMock(side_effect=RuntimeError("network")),
    )
    out = await component_svc.get_components()
    assert out is None
