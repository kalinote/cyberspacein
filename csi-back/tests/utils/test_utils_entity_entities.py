"""app.utils.entity_entities 命名实体解析测试。"""

from app.schemas.general import EntityEntitiesSchema
from app.utils.entity_entities import parse_entities


def test_parse_entities_missing_returns_none():
    assert parse_entities(None) is None


def test_parse_entities_invalid_type_returns_none():
    assert parse_entities("bad") is None
    assert parse_entities([]) is None


def test_parse_entities_full_object():
    raw = {
        "person": ["张维平", "梅姨"],
        "organization": ["公安部"],
        "location": [],
        "company": [],
        "network_user": [],
        "region": [],
    }
    result = parse_entities(raw)
    assert isinstance(result, EntityEntitiesSchema)
    assert result.person == ["张维平", "梅姨"]
    assert result.organization == ["公安部"]
    assert result.location == []


def test_parse_entities_empty_dict_normalizes_categories():
    result = parse_entities({})
    assert isinstance(result, EntityEntitiesSchema)
    assert result.person == []
    assert result.region == []


def test_parse_entities_coerces_non_list_to_empty():
    result = parse_entities({"person": "solo"})
    assert result is not None
    assert result.person == []
