"""MIGRATION_PLAN §12.17：agent router 注册数量回归（含提示词模板删除）。"""

from __future__ import annotations

from fastapi import FastAPI

from app.api.v1.endpoints import agent as agent_ep


def test_router_registers_all_54_endpoints() -> None:
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
    assert len(paths) == 55
    assert ("POST", "/api/v1/agent/skills/upload") in paths
    assert ("POST", "/api/v1/agent/skills") in paths
    assert ("PUT", "/api/v1/agent/skills/{skill_id}") in paths
    assert ("DELETE", "/api/v1/agent/skills/{skill_id}") in paths
    assert ("GET", "/api/v1/agent/skills/{skill_id}/files/content") in paths
    assert ("PUT", "/api/v1/agent/skills/{skill_id}/files/content") in paths
    assert ("POST", "/api/v1/agent/skills/{skill_id}/files") in paths
    assert ("DELETE", "/api/v1/agent/skills/{skill_id}/files") in paths
    assert ("GET", "/api/v1/agent/configs/skills-list") in paths
    assert ("GET", "/api/v1/agent/configs/filter/skills") in paths
    assert ("GET", "/api/v1/agent/configs/filter/agent-prompts") in paths
    assert ("GET", "/api/v1/agent/sessions/{session_id}") in paths
    assert ("POST", "/api/v1/agent/sandbox/create") in paths
    assert ("DELETE", "/api/v1/agent/sandbox/{sandbox_id}") in paths
    assert ("GET", "/api/v1/agent/sandbox/list") in paths
    assert ("GET", "/api/v1/agent/sandbox/detail/{sandbox_id}") in paths

