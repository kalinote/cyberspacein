"""get_entity 分段读取辅助逻辑测试。"""
from __future__ import annotations

import app.service.analyst.tools.get_entity as ge


def test_apply_field_limits_slices_strings() -> None:
    source = {"raw_content": "0123456789", "title": "hi"}
    result = ge._apply_field_limits(
        source,
        {"raw_content": {"offset": 2, "limit": 4}},
    )
    assert result["raw_content"] == "2345"
    assert result["title"] == "hi"
    assert source["raw_content"] == "0123456789"


def test_apply_field_limits_offset_beyond_returns_empty() -> None:
    source = {"raw_content": "abc"}
    result = ge._apply_field_limits(source, {"raw_content": {"offset": 10, "limit": 5}})
    assert result["raw_content"] == ""


def test_apply_field_limits_missing_key_ignored() -> None:
    source = {"title": "x"}
    result = ge._apply_field_limits(source, {"missing": {"offset": 0, "limit": 1}})
    assert result == {"title": "x"}


def test_apply_field_limits_non_string_ignored() -> None:
    source = {"count": 42, "tags": ["a"]}
    result = ge._apply_field_limits(
        source,
        {"count": {"offset": 0, "limit": 1}, "tags": {"offset": 0, "limit": 1}},
    )
    assert result == source


def test_apply_field_limits_offset_only() -> None:
    source = {"raw_content": "abcdef"}
    result = ge._apply_field_limits(source, {"raw_content": {"offset": 3}})
    assert result["raw_content"] == "def"


def test_compute_field_length_report_without_limits() -> None:
    report = ge._compute_field_length_report({"title": "ab", "n": 1}, None)
    assert report["title"] == {"original": 2}
    assert report["n"]["original"] == 1


def test_compute_field_length_report_with_limits() -> None:
    source = {"raw_content": "0123456789"}
    report = ge._compute_field_length_report(
        source,
        {"raw_content": {"offset": 2, "limit": 3}},
    )
    assert report["raw_content"] == {"original": 10, "limited": 3}


def test_format_oversize_error_contains_details() -> None:
    msg = ge._format_oversize_error(
        20000,
        16000,
        {
            "title": {"original": 42},
            "raw_content": {"original": 12000, "limited": 1000},
        },
    )
    assert msg.startswith("[错误]")
    assert "上限 16000" in msg
    assert "当前 20000" in msg
    assert "title: 原 42" in msg
    assert "raw_content: 原 12000，截取后 1000" in msg
    assert "limits" in msg
