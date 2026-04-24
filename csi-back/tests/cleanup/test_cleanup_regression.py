"""MIGRATION_PLAN §12.18：清理回归（禁用旧 agent/langgraph 链路）。"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

from tests.conftest import apply_minimal_settings_env


def _repo_root() -> Path:
    # tests/cleanup/test_*.py -> tests/cleanup -> tests -> repo_root
    return Path(__file__).resolve().parents[2]


def _scan_py_files(base: Path) -> list[Path]:
    this = Path(__file__).resolve()
    return [p for p in base.rglob("*.py") if p.is_file() and p.resolve() != this]


def _assert_no_forbidden_refs(paths: list[Path], *, patterns: list[str]) -> None:
    bad: list[str] = []
    for p in paths:
        try:
            text = p.read_text(encoding="utf-8")
        except Exception:
            # 某些环境可能出现编码问题；这类文件若存在也不应包含关键禁用符号
            text = p.read_text(errors="ignore")
        for pat in patterns:
            if pat in text:
                bad.append(f"{p.as_posix()} contains {pat!r}")
    assert not bad, "发现禁用引用：\n" + "\n".join(bad[:50])


def test_legacy_agent_paths_absent() -> None:
    root = _repo_root()
    assert not (root / "app" / "service" / "agent").exists()
    assert not (root / "app" / "models" / "agent" / "agent.py").exists()
    assert not (root / "app" / "models" / "agent" / "checkpoint.py").exists()


def test_no_forbidden_agent_imports_in_app() -> None:
    root = _repo_root()
    patterns = [
        "app.service.agent.",
        "CheckpointModel",
        "motor_checkpinter",
        "agent_checkpointer",
        "from langgraph",
        "import langgraph",
    ]
    _assert_no_forbidden_refs(_scan_py_files(root / "app"), patterns=patterns)


def test_tests_dir_no_legacy_references() -> None:
    root = _repo_root()
    patterns = [
        "CheckpointModel",
        "motor_checkpinter",
        "agent_checkpointer",
        "app.service.agent.",
    ]
    _assert_no_forbidden_refs(_scan_py_files(root / "tests"), patterns=patterns)


def test_main_import_chain_clean(monkeypatch: pytest.MonkeyPatch) -> None:
    apply_minimal_settings_env(monkeypatch)

    # 避免复用其它测试已导入的模块状态，先尽量清理相关前缀
    for k in list(sys.modules.keys()):
        if k.startswith(("langgraph", "app.service.agent", "app.models.agent.checkpoint", "app.models.agent.agent")):
            sys.modules.pop(k, None)

    import app.main  # noqa: F401

    forbidden_prefixes = [
        "langgraph",
        "langchain.chat_models",
        "langchain.agents",
        "app.service.agent",
        "app.models.agent.checkpoint",
        "app.models.agent.agent",
    ]
    loaded = list(sys.modules.keys())
    assert not any(m == p or m.startswith(p + ".") for m in loaded for p in forbidden_prefixes)


def test_langchain_core_only_via_embedding(monkeypatch: pytest.MonkeyPatch) -> None:
    apply_minimal_settings_env(monkeypatch)
    import app.utils.embedding  # noqa: F401

    allowed = ("langchain_core", "langchain_openai")
    forbidden = []
    for name in sys.modules.keys():
        if not name.startswith("langchain"):
            continue
        if name.startswith(allowed):
            continue
        forbidden.append(name)
    assert not forbidden, "发现不允许的 langchain 模块加载：\n" + "\n".join(sorted(forbidden)[:50])

