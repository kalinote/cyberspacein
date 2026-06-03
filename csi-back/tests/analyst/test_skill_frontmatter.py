from app.service.analyst.skill_frontmatter import (
    build_skill_md,
    infer_file_type,
    is_allowed_text_path,
    parse_frontmatter,
    split_promoted_fields,
    strip_frontmatter,
    validate_skill_name,
)


def test_parse_and_split_promoted():
    raw = """---
name: demo-skill
description: A demo
always: true
homepage: https://example.com
---
# Body
"""
    fm = parse_frontmatter(raw)
    assert fm is not None
    name, desc, always, meta = split_promoted_fields(fm)
    assert name == "demo-skill"
    assert desc == "A demo"
    assert always is True
    assert meta.get("homepage") == "https://example.com"
    assert strip_frontmatter(raw).startswith("# Body")


def test_validate_skill_name():
    assert validate_skill_name("my-skill") is None
    assert validate_skill_name("Bad Name") is not None


def test_infer_file_type_and_path_guard():
    assert infer_file_type("SKILL.md") == "skill"
    assert infer_file_type("references/x.md") == "reference"
    assert is_allowed_text_path("../evil.md") is False
    assert is_allowed_text_path("scripts/a.py") is True


def test_build_skill_md():
    md = build_skill_md("demo", "说明", False, {}, "正文")
    assert md.startswith("---")
    assert "name: demo" in md
    assert "正文" in md
