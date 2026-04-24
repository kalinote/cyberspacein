"""MIGRATION_PLAN §12.17：agent router 注册数量回归。"""

from __future__ import annotations

from fastapi import FastAPI

from app.api.v1.endpoints import agent as agent_ep


def test_router_registers_all_26_endpoints() -> None:
    app = FastAPI()
    app.include_router(agent_ep.router, prefix="/api/v1")
    paths = []
    for r in app.routes:
        methods = getattr(r, "methods", None)
        path = getattr(r, "path", "")
        if not methods or "/api/v1/agent" not in path:
            continue
        for m in methods:
            if m in {"HEAD", "OPTIONS"}:
                continue
            paths.append((m, path))
    assert len(paths) == 26

