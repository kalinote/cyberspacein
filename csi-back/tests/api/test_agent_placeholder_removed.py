"""MIGRATION_PLAN §12.17：确认占位常量已移除（仅检查 app 源码，不含文档）。"""

from __future__ import annotations

from pathlib import Path


def test_placeholder_removed() -> None:
    root = Path(__file__).resolve().parents[2]
    agent_dir = root / "app" / "api" / "v1" / "endpoints" / "agent"
    text = "\n".join(path.read_text(encoding="utf-8") for path in agent_dir.glob("*.py"))
    assert "PLACEHOLDER_MESSAGE" not in text

