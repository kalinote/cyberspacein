from typing import List, Dict, Any, Optional
from app.schemas.general import DictModel

def pack_dict(data: Optional[Dict[str, Any]]) -> Optional[List[DictModel]]:
    """
    将字典转换为 List[DictModel]
    """
    if data is None:
        return None
    return [DictModel(key=k, value=v) for k, v in data.items()]

def unpack_dict(data: Optional[List[DictModel]]) -> Optional[Dict[str, Any]]:
    """
    将 List[DictModel] 转换为字典
    """
    if data is None:
        return None
    return {item.key: item.value for item in data}
