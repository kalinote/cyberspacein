"""Wiki 工具共用的字段裁剪。"""
from __future__ import annotations

from typing import Any


def pick_fields(data: dict[str, Any], fields: list[str] | None) -> dict[str, Any]:
    if not fields:
        return data
    cleaned = [str(f).strip() for f in fields if str(f).strip()]
    if not cleaned:
        return data
    return {k: data[k] for k in cleaned if k in data}
