from typing import Any
from app.schemas.general import DictModelSchema

def pack_dict(data: dict[str, Any] | None) -> list[DictModelSchema] | None:
    """
    将字典转换为 List[DictModel]
    """
    if data is None:
        return []
    return [DictModelSchema(key=k, value=v) for k, v in data.items()]

def unpack_dict(data: list[DictModelSchema] | None) -> dict[str, Any] | None:
    """
    将 List[DictModel] 转换为字典
    """
    if data is None:
        return {}
    return {item.key: item.value for item in data}
