"""MIGRATION_PLAN §12.17：确认占位常量已移除（仅检查 app 源码，不含文档）。"""

from __future__ import annotations

from pathlib import Path


def test_placeholder_removed() -> None:
    root = Path(__file__).resolve().parents[2]
    text = (root / "app" / "api" / "v1" / "endpoints" / "agent.py").read_text(encoding="utf-8")
    assert "PLACEHOLDER_MESSAGE" not in text

