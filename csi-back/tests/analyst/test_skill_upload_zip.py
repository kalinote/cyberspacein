import io
import zipfile

import pytest

from app.service.analyst.skill_upload import SkillUploadService
from app.schemas.agent.skill import SkillServiceError


def _make_zip(files: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for path, content in files.items():
            zf.writestr(path, content)
    return buf.getvalue()


def _skill_md(name: str) -> str:
    return f"""---
name: {name}
description: desc for {name}
always: false
---
# {name}
"""


def test_resolve_skill_root_flat():
    entries = {"SKILL.md": _skill_md("zip-demo"), "references/a.md": "ref"}
    prefix, files = SkillUploadService._resolve_skill_root(entries)
    assert prefix == ""
    assert "SKILL.md" in files
    assert files["references/a.md"] == "ref"


def test_resolve_skill_root_nested():
    entries = {
        "zip-demo/SKILL.md": _skill_md("zip-demo"),
        "zip-demo/references/a.md": "ref",
    }
    prefix, files = SkillUploadService._resolve_skill_root(entries)
    assert prefix == "zip-demo/"
    assert files["SKILL.md"] == entries["zip-demo/SKILL.md"]


def test_split_multi_skill_packages():
    entries = {
        "my/SKILL.md": _skill_md("my"),
        "my/references/a.md": "a",
        "clawhub/SKILL.md": _skill_md("clawhub"),
        "clawhub/readme.md": "b",
    }
    packages = SkillUploadService._split_into_skill_packages(entries)
    assert len(packages) == 2
    by_name = {}
    for pkg in packages:
        fm = pkg["SKILL.md"]
        assert "name: my" in fm or "name: clawhub" in fm
        if "name: my" in fm:
            by_name["my"] = pkg
        else:
            by_name["clawhub"] = pkg
    assert "references/a.md" in by_name["my"]
    assert "readme.md" in by_name["clawhub"]


def test_split_rejects_flat_plus_nested():
    entries = {
        "SKILL.md": _skill_md("root-skill"),
        "other/SKILL.md": _skill_md("other"),
    }
    with pytest.raises(SkillServiceError, match="不能同时"):
        SkillUploadService._split_into_skill_packages(entries)


def test_split_rejects_orphan_files():
    entries = {
        "my/SKILL.md": _skill_md("my"),
        "orphan.txt": "x",
    }
    with pytest.raises(SkillServiceError, match="无法归属"):
        SkillUploadService._split_into_skill_packages(entries)


def test_collect_zip_rejects_traversal():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("../SKILL.md", _skill_md("bad"))
    with pytest.raises(SkillServiceError):
        SkillUploadService._collect_zip_entries(zipfile.ZipFile(io.BytesIO(buf.getvalue())))
