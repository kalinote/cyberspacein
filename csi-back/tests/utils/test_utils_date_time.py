from datetime import datetime

from app.utils.date_time import parse_datetime


def test_parse_datetime_none():
    """None 返回 None。"""
    assert parse_datetime(None) is None


def test_parse_datetime_datetime_strips_microseconds():
    """datetime 输入会去掉微秒。"""
    dt = datetime(2026, 1, 19, 23, 56, 46, 123456)
    out = parse_datetime(dt)
    assert out == datetime(2026, 1, 19, 23, 56, 46)


def test_parse_datetime_iso_with_z():
    """带 Z 的 ISO 字符串能解析且微秒为 0、带时区。"""
    s = "2026-01-19T23:56:46Z"
    out = parse_datetime(s)
    assert out is not None
    assert out.microsecond == 0
    assert out.tzinfo is not None


def test_parse_datetime_iso_no_tz():
    """无时区 ISO 字符串按 strptime 解析。"""
    s = "2026-01-19T23:56:47"
    out = parse_datetime(s)
    assert out == datetime(2026, 1, 19, 23, 56, 47)


def test_parse_datetime_invalid_string():
    """非法日期字符串返回 None。"""
    assert parse_datetime("not-a-date") is None


def test_parse_datetime_unsupported_type():
    """非 str/datetime 类型返回 None。"""
    assert parse_datetime(12345) is None
