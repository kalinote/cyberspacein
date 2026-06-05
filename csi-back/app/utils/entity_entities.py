from __future__ import annotations

from typing import Any

from app.schemas.general import EntityEntitiesSchema

_ENTITY_CATEGORY_KEYS = (
    "person",
    "organization",
    "location",
    "company",
    "network_user",
    "region",
)


def _as_str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if item is not None]


def parse_entities(raw: Any) -> EntityEntitiesSchema | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        return None
    return EntityEntitiesSchema(
        **{key: _as_str_list(raw.get(key)) for key in _ENTITY_CATEGORY_KEYS}
    )
