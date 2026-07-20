from __future__ import annotations

import sys

from csi_base_component_sdk.runner import _load_entrypoint


def test_load_entrypoint_from_current_component_directory(tmp_path, monkeypatch):
    entry_module = tmp_path / "component_entry.py"
    entry_module.write_text(
        "def run(ctx):\n"
        "    return {'loaded': True}\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "path",
        [path for path in sys.path if path not in ("", str(tmp_path))],
    )
    sys.modules.pop("component_entry", None)

    try:
        function = _load_entrypoint("component_entry:run")
        assert function(None) == {"loaded": True}
        assert sys.path[0] == str(tmp_path)
    finally:
        sys.modules.pop("component_entry", None)
