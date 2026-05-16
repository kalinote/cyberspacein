"""业务工具：注入到 AgentLoop 的 ToolRegistry 中，供 LLM 调用。

全部通过 `ContextVar(current_agent_id / current_session_id)` 拉当前运行的 agent/session；
依赖 `AnalystService` 做 SSE 广播与 HITL 决策的同步（避免跨模块循环依赖，import 在方法体内）。

工具清单（MIGRATION_PLAN §3.3）：
- `get_current_time` ：返回当前时间字符串，无状态。
- `get_entity`       ：按 `(entity_type, entity_uuid)` 去 Elasticsearch 拉实体。
- `modify_entity`    ：经 `HitlService.request_approval` 人工审批；通过后写回 Elasticsearch。
- `notify_user`      ：SSE `notification` 广播一条消息。
- `write_todos`      ：写 `NanobotSessionModel.todos` + SSE `todos`；供 LLM 自行拆解任务。
- `web_search` / `web_fetch` ：联网搜索与页面抓取（实现见 `web_tools.py`，运行参数见 `WEB_RUNTIME`）。

工具注册时用 `ToolRegistry.register(tool)`；`AnalystService.build_bot` 会按 agent.tools
白名单做一次过滤，只注册 agent 明确启用的工具（agent.tools 为空时视作不启用任何业务工具，
保留 AgentLoop 默认注册的内置工具）。
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from loguru import logger

from app.models.agent.nanobot import NanobotSessionModel
from app.schemas.agent.result import SUBMIT_TASK_RESULT_TOOL_NAME, SubmitTaskResultParams
from app.schemas.constants import (
    ENTITY_TYPE_INDEX_MAP,
    EntityType,
    NanobotSessionStatusEnum,
)
from app.service.analyst.context import (
    current_task_completion,
    get_current_agent_id,
    get_current_session_id,
)
from app.service.analyst.web_tools import (
    WEB_RUNTIME,
    WebFetchTool,
    WebSearchTool,
)
from app.service.nanobot.agent.tools.base import Tool, tool_parameters

logger = logger.bind(name=__name__)


def _require_agent_id() -> str:
    agent_id = get_current_agent_id()
    if not agent_id:
        raise RuntimeError("业务工具必须在 AnalystService.run_analysis 的 ContextVar 作用域内调用")
    return agent_id


# ---------------------------------------------------------------------------
# get_current_time
# ---------------------------------------------------------------------------


@tool_parameters({
    "type": "object",
    "properties": {},
    "additionalProperties": False,
})
class GetCurrentTimeTool(Tool):
    """返回当前服务器时间（ISO 8601），便于 LLM 进行时间推理。"""

    @property
    def name(self) -> str:
        return "get_current_time"

    @property
    def description(self) -> str:
        return "获取当前服务器时间（ISO 8601 字符串）。"

    @property
    def read_only(self) -> bool:
        return True

    async def execute(self, **kwargs: Any) -> str:
        return datetime.now().isoformat()


# ---------------------------------------------------------------------------
# get_entity
# ---------------------------------------------------------------------------


@tool_parameters({
    "type": "object",
    "properties": {
        "entity_type": {
            "type": "string",
            "enum": [e.value for e in EntityType],
            "description": "实体类型",
        },
        "entity_uuid": {
            "type": "string",
            "description": "实体的唯一标识（ES 文档 _id）",
            "minLength": 1,
        },
        "fields": {
            "type": "array",
            "items": {"type": "string", "minLength": 1},
            "description": (
                "可选。仅拉取 `_source` 中列出的字段（Elasticsearch `_source_includes`）。"
                "善用该字段可显著减小返回体积，"
                "避免整篇文档触发工具结果落盘后仅保留短预览而无法看到所需字段内容"
            ),
        },
    },
    "required": ["entity_type", "entity_uuid"],
    "additionalProperties": False,
})
class GetEntityTool(Tool):
    """按 (entity_type, entity_uuid) 从 Elasticsearch 拉实体详情。"""

    @property
    def name(self) -> str:
        return "get_entity"

    @property
    def description(self) -> str:
        return (
            "根据实体类型和 UUID 从 Elasticsearch 获取 `_source`。"
            "默认返回全部字段的 JSON；若只需正文或少数键，务必传入 `fields`"
            "以控制体积，避免无关字段占用上下文"
        )

    @property
    def read_only(self) -> bool:
        return True

    async def execute(self, **kwargs: Any) -> str:
        from app.db.elasticsearch import get_es

        entity_type = kwargs.get("entity_type")
        entity_uuid = kwargs.get("entity_uuid")
        raw_fields = kwargs.get("fields")
        index = ENTITY_TYPE_INDEX_MAP.get(entity_type)
        if index is None:
            return f"[错误] 不支持的实体类型: {entity_type}"
        es = get_es()
        if es is None:
            return "[错误] Elasticsearch 未初始化"
        get_kw: dict[str, Any] = {"index": index, "id": entity_uuid}
        if isinstance(raw_fields, list) and raw_fields:
            cleaned = [str(f).strip() for f in raw_fields if str(f).strip()]
            if cleaned:
                get_kw["_source_includes"] = cleaned
        try:
            resp = await es.get(**get_kw)
        except Exception as exc:
            logger.exception(
                f"get_entity 查询失败: type={entity_type} uuid={entity_uuid}"
            )
            return f"[错误] 查询实体失败: {exc}"
        source = resp.get("_source") or {}
        return json.dumps(source, ensure_ascii=False)


# ---------------------------------------------------------------------------
# modify_entity
# ---------------------------------------------------------------------------


@tool_parameters({
    "type": "object",
    "properties": {
        "entity_type": {
            "type": "string",
            "enum": [e.value for e in EntityType],
            "description": "待修改的实体类型",
        },
        "entity_uuid": {
            "type": "string",
            "description": "待修改的实体 UUID",
            "minLength": 1,
        },
        "modifications": {
            "type": "array",
            "description": "要应用的字段修改列表",
            "items": {
                "type": "object",
                "properties": {
                    "field": {"type": "string", "description": "字段路径"},
                    "action": {
                        "type": "string",
                        "enum": ["set", "append", "remove"],
                        "description": "修改动作",
                    },
                    "value": {"description": "新值（action=set/append 时必填）"},
                },
                "required": ["field", "action"],
            },
            "minItems": 1,
        },
        "reason": {
            "type": "string",
            "description": "本次修改的说明，会展示给审批人",
            "minLength": 1,
        },
    },
    "required": ["entity_type", "entity_uuid", "modifications", "reason"],
    "additionalProperties": False,
})
class ModifyEntityTool(Tool):
    """对实体发起修改，经 HITL 人工审批后生效。握手见 `HitlService.request_approval`。"""

    @property
    def name(self) -> str:
        return "modify_entity"

    @property
    def description(self) -> str:
        return "对指定实体发起修改，会经过人工审批后再生效。"

    @property
    def exclusive(self) -> bool:
        return True

    async def execute(self, **kwargs: Any) -> str:
        from app.schemas.agent.hitl import HitlSource
        from app.service.analyst.hitl import HitlService

        agent_id = _require_agent_id()
        session_id = get_current_session_id()
        if not session_id:
            return "[错误] 缺少 session 上下文"

        payload = {
            "entity_type": kwargs.get("entity_type"),
            "entity_uuid": kwargs.get("entity_uuid"),
            "modifications": kwargs.get("modifications") or [],
            "reason": kwargs.get("reason") or "",
        }

        try:
            outcome = await HitlService.request_approval(
                agent_id,
                session_id,
                HitlSource.TOOL_MODIFY_ENTITY,
                payload,
            )
        except RuntimeError as exc:
            return f"[错误] {exc}"
        except Exception as exc:
            logger.exception(
                f"modify_entity 等待审批异常: agent_id={agent_id} session_id={session_id}"
            )
            return f"[错误] 等待审批异常: {exc}"

        if outcome.rejections:
            reason_text = "；".join(r or "" for r in outcome.rejections)
            return f"修改被拒绝：{reason_text or '未提供理由'}"

        if not outcome.approved:
            return "修改未获得任何批准，未执行。"

        from app.service.analyst.utils.entity_modify import apply_entity_modifications_to_es

        write_err = await apply_entity_modifications_to_es(
            str(payload["entity_type"]),
            str(payload["entity_uuid"]),
            payload["modifications"],
        )
        if write_err:
            return f"[错误] 应用修改失败: {write_err}"

        logger.info(
            f"modify_entity 已写入 ES: agent_id={agent_id} "
            f"entity={payload['entity_type']}:{payload['entity_uuid']} "
            f"modifications_count={len(payload['modifications'])}"
        )
        return (
            f"修改已获批准（共 {len(outcome.approved)} 条决策），"
            f"已对实体 {payload['entity_type']}:{payload['entity_uuid']} "
            f"应用 {len(payload['modifications'])} 项修改并写入 Elasticsearch。"
        )


# ---------------------------------------------------------------------------
# notify_user
# ---------------------------------------------------------------------------


@tool_parameters({
    "type": "object",
    "properties": {
        "message": {
            "type": "string",
            "description": "通知内容（将通过 SSE 广播给前端）",
            "minLength": 1,
        },
        "level": {
            "type": "string",
            "enum": ["info", "warning", "error"],
            "description": "通知级别",
        },
    },
    "required": ["message"],
    "additionalProperties": False,
})
class NotifyUserTool(Tool):
    """通过 SSE 给前端推一条 `notification` 事件。"""

    @property
    def name(self) -> str:
        return "notify_user"

    @property
    def description(self) -> str:
        return "向用户推送一条实时通知消息。"

    async def execute(self, **kwargs: Any) -> str:
        from app.service.analyst.service import AnalystService

        agent_id = _require_agent_id()
        message = str(kwargs.get("message") or "").strip()
        level = kwargs.get("level") or "info"
        if not message:
            return "[错误] message 不能为空"
        await AnalystService.broadcast_sse(
            agent_id,
            "notification",
            {
                "agent_id": agent_id,
                "session_id": get_current_session_id(),
                "level": level,
                "message": message,
                "created_at": datetime.now().isoformat(),
            },
        )
        return "通知已发送"


# ---------------------------------------------------------------------------
# write_todos
# ---------------------------------------------------------------------------


@tool_parameters({
    "type": "object",
    "properties": {
        "todos": {
            "type": "array",
            "description": "任务项列表，完整覆盖当前会话 todos",
            "items": {
                "type": "object",
                "properties": {
                    "content": {"type": "string", "minLength": 1},
                    "status": {
                        "type": "string",
                        "enum": ["pending", "in_progress", "completed", "cancelled"],
                    },
                    "id": {"type": "string"},
                },
                "required": ["content", "status"],
                "additionalProperties": True,
            },
            "minItems": 0,
        },
    },
    "required": ["todos"],
    "additionalProperties": False,
})
class WriteTodosTool(Tool):
    """写入当前会话的 todos 列表（完整覆盖），并 SSE 广播给前端。"""

    @property
    def name(self) -> str:
        return "write_todos"

    @property
    def description(self) -> str:
        return "更新当前会话的待办事项列表（会完全覆盖旧列表）。"

    @property
    def exclusive(self) -> bool:
        return True

    async def execute(self, **kwargs: Any) -> str:
        from app.service.analyst.service import AnalystService

        agent_id = _require_agent_id()
        sid = get_current_session_id()
        if not sid:
            return "[错误] 缺少 session 上下文"
        todos = kwargs.get("todos") or []
        normalized = [_normalize_todo(item) for item in todos]

        session = await NanobotSessionModel.find_one({"_id": sid})
        if session is None:
            return f"[错误] 当前会话不存在: {sid}"
        session.todos = normalized
        session.updated_at = datetime.now()
        await session.save()

        await AnalystService.broadcast_sse(
            agent_id,
            "todos",
            {
                "agent_id": agent_id,
                "session_id": sid,
                "todos": normalized,
            },
        )
        return f"已更新待办 {len(normalized)} 条"


# ---------------------------------------------------------------------------
# submit_task_result（必选注册，不在 agent.tools 白名单内）
# ---------------------------------------------------------------------------


@tool_parameters({
    "type": "object",
    "properties": {
        "success": {"type": "boolean", "description": "是否达成任务目标"},
        "failure_reason": {
            "type": ["string", "null"],
            "description": "失败原因；success 为 true 时用 null",
        },
        "short_summary": {"type": "string", "description": "简短摘要"},
        "payload": {
            "type": "object",
            "description": "完整结构化业务结果",
            "additionalProperties": True,
        },
    },
    "required": ["success", "short_summary"],
    "additionalProperties": False,
})
class SubmitTaskResultTool(Tool):
    """提交机读任务结果；调用后下一轮由模型输出用户可见 Markdown。"""

    @property
    def name(self) -> str:
        return SUBMIT_TASK_RESULT_TOOL_NAME

    @property
    def description(self) -> str:
        return (
            "任务机读结果收口：在业务数据已就绪时调用，写入权威 success/payload。"
            "调用后你应仅在下一轮回复中用 Markdown 向用户总结，勿再调用工具。"
        )

    @property
    def exclusive(self) -> bool:
        return True

    async def execute(self, **kwargs: Any) -> str:
        from app.service.analyst.service import AnalystService

        _require_agent_id()
        params = SubmitTaskResultParams.model_validate(kwargs)
        data = params.model_dump()
        current_task_completion.set(data)

        agent_id = get_current_agent_id() or ""
        await AnalystService.broadcast_sse(
            agent_id,
            "task_submitted",
            {
                "agent_id": agent_id,
                "session_id": get_current_session_id(),
                "success": params.success,
                "short_summary": (params.short_summary or "")[:500],
            },
        )
        return (
            "任务机读结果已记录。请在本轮之后仅回复面向用户的 Markdown 总结，"
            "不要调用任何工具，不要使用 JSON。"
        )


def _normalize_todo(item: dict[str, Any]) -> dict[str, Any]:
    """标准化 todo 条目，补齐缺失字段并丢弃未知字段。"""
    return {
        "id": str(item.get("id") or ""),
        "content": str(item.get("content") or "").strip(),
        "status": str(item.get("status") or "pending"),
        "updated_at": datetime.now().isoformat(),
    }


# ---------------------------------------------------------------------------
# 统一注册入口
# ---------------------------------------------------------------------------


BUSINESS_TOOL_CLASSES: dict[str, type[Tool]] = {
    "get_current_time": GetCurrentTimeTool,
    "get_entity": GetEntityTool,
    "modify_entity": ModifyEntityTool,
    "notify_user": NotifyUserTool,
    "write_todos": WriteTodosTool,
    "web_search": WebSearchTool,
    "web_fetch": WebFetchTool,
}


def build_business_tools(enabled_names: list[str]) -> list[Tool]:
    """按名称白名单实例化业务工具。未识别的名字静默忽略并打 warn 日志。"""
    tools: list[Tool] = []
    for name in enabled_names or []:
        cls = BUSINESS_TOOL_CLASSES.get(name)
        if cls is None:
            logger.warning(f"未知业务工具名，已忽略: {name}")
            continue
        if name == "web_search":
            tools.append(cls(config=WEB_RUNTIME.search, proxy=WEB_RUNTIME.proxy))
            continue
        if name == "web_fetch":
            tools.append(cls(proxy=WEB_RUNTIME.proxy))
            continue
        tools.append(cls())
    return tools


__all__ = [
    "GetCurrentTimeTool",
    "GetEntityTool",
    "ModifyEntityTool",
    "NotifyUserTool",
    "WriteTodosTool",
    "SubmitTaskResultTool",
    "BUSINESS_TOOL_CLASSES",
    "build_business_tools",
]
