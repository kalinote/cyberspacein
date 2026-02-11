import json
import logging
from typing import Annotated, Any, Literal

from langchain_core.runnables import RunnableConfig
from langchain_core.tools.base import InjectedToolArg
from app.db.elasticsearch import get_es
from langchain.tools import tool
from datetime import datetime, timezone

from app.schemas.agent.agent import MessageEventPayloadSchema
from app.schemas.constants import ENTITY_TYPE_INDEX_MAP


logger = logging.getLogger(__name__)

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
        uuid: 实体UUID
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

@tool(parse_docstring=True)
async def modify_entity(uuid: str, entity_type: str, field: str, value: str, value_type: Literal["string", "number", "boolean", "array", "object"] = "string") -> str:
    """
    修改 Elasticsearch 中的实体字段内容。返回修改结果（JSON 字符串）。
    在修改前会向用户提交修改申请，申请通过后才会实际上进行修改。
    
    Args:
        uuid: 实体UUID
        entity_type: 实体类型
        field: 要修改的字段
        value: 修改后的值，字符串类型，工具会根据 value_type 自动转换为相应的类型
        value_type: 修改后的值类型，默认 string，可选 number, boolean, array, object，其中 array 和 object 需要是有效的 JSON 字符串
    """
    client = get_es()
    if not client:
        return json.dumps({"error": "Elasticsearch连接未初始化", "uuid": uuid, "entity_type": entity_type})
    try:
        if value_type == "string":
            value = str(value)
        elif value_type == "number":
            value = float(value)
        elif value_type == "boolean":
            value = bool(value)
        elif value_type in ["array", "object"]:
            value = json.loads(value)
    except Exception as e:
        return json.dumps({"error": f"转换值类型失败: {str(e)}", "uuid": uuid, "entity_type": entity_type, "value_type": value_type})
    index = ENTITY_TYPE_INDEX_MAP.get(entity_type, entity_type)
    try:
        search_resp = await client.search(
            index=index,
            query={"term": {"uuid": uuid}},
            size=1,
        )
        hits = search_resp.get("hits", {}).get("hits", [])
        if not hits:
            return json.dumps({"error": "未找到对应文档", "uuid": uuid, "entity_type": entity_type})
        doc_id = hits[0]["_id"]
        await client.update(
            index=index,
            id=doc_id,
            body={"doc": {field: value}},
        )
        return json.dumps({
            "success": True,
            "message": "字段已更新",
            "uuid": uuid,
            "entity_type": entity_type,
            "field": field,
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({
            "error": str(e),
            "uuid": uuid,
            "entity_type": entity_type,
            "field": field,
        }, ensure_ascii=False)

@tool(parse_docstring=True)
async def notify_user(
    message: str,
    level: Literal["info", "warning", "error"] = "info",
    config: Annotated[RunnableConfig | None, InjectedToolArg] = None,
) -> str:
    """
    向用户发送通知，返回通知结果（JSON 字符串）。
    
    Args:
        message: 通知消息
        level: 消息级别，默认 info，可选 warning, error
    """
    if isinstance(config, dict):
        thread_id = (config.get("configurable") or {}).get("thread_id")
    else:
        configurable = getattr(config, "configurable", None) if config else None
        thread_id = configurable.get("thread_id") if isinstance(configurable, dict) else None
    if not thread_id:
        logger.warning("notify_user: 无 thread_id，跳过 SSE 推送")
        return json.dumps({"success": False, "message": "无法推送：缺少会话上下文"}, ensure_ascii=False)
    payload = MessageEventPayloadSchema(thread_id=thread_id, message=message, level=level)
    
    from app.service.agent.agent import AgentService
    await AgentService.broadcast_sse(thread_id, AgentService.sse_event("message", payload))
    return json.dumps({"success": True, "message": "已将消息推送到用户"}, ensure_ascii=False)

all_tools = {
    "get_current_time": get_current_time,
    "get_entity": get_entity,
    "modify_entity": modify_entity,
    "notify_user": notify_user,
}
