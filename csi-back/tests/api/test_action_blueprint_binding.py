from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.api.v1.endpoints.action import blueprint as blueprint_endpoint
from app.models.action.blueprint import ActionBlueprintModel
from app.schemas.action.interface import BlueprintValidationIssue
from app.service.blueprint_revision import BlueprintRevisionService
from app.service.boundary_binding_validator import (
    BlueprintBindingValidationError,
)


@pytest.mark.asyncio
async def test_validate_blueprint_returns_structured_binding_issues(
    monkeypatch,
) -> None:
    issues = [
        BlueprintValidationIssue(
            code="binding_mixed_direction",
            message="目标节点不能混合绑定输入和输出",
            node_id="input-boundary",
            details={"target_node_id": "target"},
        )
    ]
    monkeypatch.setattr(
        ActionBlueprintModel,
        "find_one",
        AsyncMock(return_value=SimpleNamespace(id="blueprint-1")),
    )
    monkeypatch.setattr(
        BlueprintRevisionService,
        "validate",
        AsyncMock(
            side_effect=BlueprintBindingValidationError(issues)
        ),
    )

    response = await blueprint_endpoint.validate_blueprint("blueprint-1")

    assert response.code == 0
    assert response.data.valid is False
    assert response.data.errors == [
        {
            "code": "binding_mixed_direction",
            "message": "目标节点不能混合绑定输入和输出",
            "node_id": "input-boundary",
            "edge_id": None,
            "details": {"target_node_id": "target"},
        }
    ]
