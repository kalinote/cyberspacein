import json
from app.db.elasticsearch import get_es
from langchain.tools import tool
from datetime import datetime, timezone

from app.schemas.constants import ENTITY_TYPE_INDEX_MAP, EntityType

@tool(parse_docstring=True)
def get_current_time(time_zone: str = "Asia/Shanghai") -> str:
    """
    获取当前时间，时区默认东八区。返回时间格式为：YYYY-MM-DD HH:MM:SS 时区
    
    Args:
        time_zone: 时区, default: Asia/Shanghai
    """
    return datetime.now(timezone(time_zone)).strftime("%Y-%m-%d %H:%M:%S") + " " + time_zone

@tool(parse_docstring=True)
async def get_entity(uuid: str, entity_type: str, fields: list[str] | None = None) -> str:
    """
    从 Elasticsearch 中读取实体的部分或全部字段内容。
    若 fields 不为 None，则只返回这些字段，否则返回全部字段。返回命中文档的 _source 内容（JSON 字符串）。
    若无命中则返回空或说明。仅用于读取授权字段（如 clean_content）。
    
    Args:
        uuid: 文档UUID
        entity_type: 实体类型
        fields: 要读取的字段列表，默认读取所有字段, default: None
    """
    # TODO: 增加字段读取权限控制，尝试使用 https://docs.langchain.com/oss/python/langchain/tools#accessing-context
    client = get_es()
    try:
        search_args = {
            "index": ENTITY_TYPE_INDEX_MAP.get(entity_type, entity_type),
            "query": {"term": {"uuid": uuid}},
            "size": 1,
        }
        if fields is not None:
            search_args["_source"] = fields
        resp = await client.search(**search_args)
        hits = resp.get("hits", {}).get("hits", [])
        if not hits:
            return json.dumps({"error": "未找到对应文档", "uuid": uuid, "entity_type": entity_type})
        src = hits[0].get("_source", {})
        return json.dumps(src, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e), "uuid": uuid, "entity_type": entity_type})



all_tools = {
    "get_current_time": get_current_time,
    "get_entity": get_entity,
}
