"""Standard permission registry and route matrix invariants."""

from app.core.permissions import (
    BACKEND_PERMISSION_CODES,
    PERMISSION_DEFINITIONS,
    PERMISSION_REGISTRY,
    STANDARD_PERMISSION_CODES,
)
from app.core.route_permissions import ROUTE_PERMISSIONS, validate_fastapi_routes
from app.main import app


def test_permission_manifest_is_unique_and_well_formed() -> None:
    codes = [item.code for item in PERMISSION_DEFINITIONS]
    assert len(codes) == len(set(codes))
    assert set(codes) == set(PERMISSION_REGISTRY) == set(STANDARD_PERMISSION_CODES)
    assert "*" in codes
    assert all(item.name and item.module and item.resource and item.description for item in PERMISSION_DEFINITIONS)


def test_page_permissions_never_authorize_backend() -> None:
    assert not any(code.startswith("page:") for code in BACKEND_PERMISSION_CODES)
    assert all(item.backend_enforced for item in PERMISSION_DEFINITIONS if item.code in BACKEND_PERMISSION_CODES)


def test_every_business_route_has_one_exact_matrix_entry() -> None:
    keys = [(item.method, item.path) for item in ROUTE_PERMISSIONS]
    assert len(keys) == len(set(keys))
    validate_fastapi_routes(app.routes)


def test_matrix_never_uses_page_permission_for_backend() -> None:
    for item in ROUTE_PERMISSIONS:
        if item.permission:
            assert item.permission in BACKEND_PERMISSION_CODES
