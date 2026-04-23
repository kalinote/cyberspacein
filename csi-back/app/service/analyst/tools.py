"""业务工具：注入到 AgentLoop 的 ToolRegistry 中，供 LLM 调用。

全部通过 `ContextVar(current_agent_id / current_session_id)` 拉当前运行的 agent/session；
依赖 `AnalystService` 做 SSE 广播与 HITL 决策的同步（避免跨模块循环依赖，import 在方法体内）。

工具清单（MIGRATION_PLAN §3.3）：
- `get_current_time` ：返回当前时间字符串，无状态。
- `get_entity`       ：按 `(entity_type, entity_uuid)` 去 Elasticsearch 拉实体。
- `modify_entity`    ：HITL 握手 —— 写 `pending_approval` → SSE `approval_required` →
                        `await AnalystService.await_approval()` → 按决策返回 approve/reject 文本。
                        实际的实体写回业务（ES / DB）可以在审批通过分支中按需扩展；当前版本
                        仅作握手骨架，落地逻辑留 TODO 注释。
- `notify_user`      ：SSE `notification` 广播一条消息，不改 DB。
- `write_todos`      ：写 `NanobotAgentModel.todos` + SSE `todos`；供 LLM 自行拆解任务。

工具注册时用 `ToolRegistry.register(tool)`；`AnalystService.build_bot` 会按 agent.tools
白名单做一次过滤，只注册 agent 明确启用的工具（agent.tools 为空时视作不启用任何业务工具，
保留 AgentLoop 默认注册的内置工具）。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from loguru import logger

from app.models.agent.nanobot import NanobotAgentModel
from app.schemas.constants import (
    ENTITY_TYPE_INDEX_MAP,
    EntityType,
    NanobotAgentStatusEnum,
)
from app.service.analyst.context import get_current_agent_id, get_current_session_id
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
        return "根据实体类型和 UUID 获取实体的完整原始数据（来自 Elasticsearch）。"

    @property
    def read_only(self) -> bool:
        return True

    async def execute(self, **kwargs: Any) -> str:
        from app.db.elasticsearch import get_es

        entity_type = kwargs.get("entity_type")
        entity_uuid = kwargs.get("entity_uuid")
        index = ENTITY_TYPE_INDEX_MAP.get(entity_type)
        if index is None:
            return f"[错误] 不支持的实体类型: {entity_type}"
        es = get_es()
        if es is None:
            return "[错误] Elasticsearch 未初始化"
        try:
            resp = await es.get(index=index, id=entity_uuid)
        except Exception as exc:
            logger.exception(
                f"get_entity 查询失败: type={entity_type} uuid={entity_uuid}"
            )
            return f"[错误] 查询实体失败: {exc}"
        source = resp.get("_source") or {}
        return str(source)


# ---------------------------------------------------------------------------
# modify_entity —— HITL 握手核心
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
    """对实体发起修改 —— 工具内部完成 HITL 审批握手。

    执行流程：
    1) 写 `NanobotAgentModel.status=AWAITING_APPROVAL` + `pending_approval=payload`，
       `AnalystService.broadcast_sse("approval_required", payload)`；
    2) `await AnalystService.await_approval(agent_id)` 阻塞等待 `/agent/approve` 写入决策；
    3) 解析 decisions：
       - 全 `approve`  → （TODO: 实际写回 ES / DB；当前仅日志）
       - 存在 `reject` → 返回被拒说明
    4) 复位 `status=RUNNING` + `pending_approval=None` + SSE `status=running`。
    """

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
        from app.service.analyst.service import AnalystService

        agent_id = _require_agent_id()
        session_id = get_current_session_id()

        payload = {
            "entity_type": kwargs.get("entity_type"),
            "entity_uuid": kwargs.get("entity_uuid"),
            "modifications": kwargs.get("modifications") or [],
            "reason": kwargs.get("reason") or "",
            "requested_at": datetime.now().isoformat(),
            "session_id": session_id,
        }

        agent = await NanobotAgentModel.find_one({"_id": agent_id})
        if agent is None:
            return f"[错误] 当前 agent 不存在: {agent_id}"
        agent.status = NanobotAgentStatusEnum.AWAITING_APPROVAL
        agent.pending_approval = payload
        agent.updated_at = datetime.now()
        await agent.save()
        await AnalystService.broadcast_sse(
            agent_id,
            "approval_required",
            {
                "agent_id": agent_id,
                "session_id": session_id,
                "payload": payload,
            },
        )
        await AnalystService.broadcast_sse(
            agent_id,
            "status",
            {"agent_id": agent_id, "status": NanobotAgentStatusEnum.AWAITING_APPROVAL.value},
        )

        try:
            decision_msg = await AnalystService.await_approval(agent_id)
        except Exception as exc:
            logger.exception(
                f"modify_entity 等待审批异常: agent_id={agent_id} session_id={session_id}"
            )
            return f"[错误] 等待审批异常: {exc}"

        decisions = decision_msg.get("decisions") or []
        approved, rejections = _parse_approval_decisions(decisions)

        # 复位 agent 状态
        agent = await NanobotAgentModel.find_one({"_id": agent_id})
        if agent is not None:
            agent.status = NanobotAgentStatusEnum.RUNNING
            agent.pending_approval = None
            agent.updated_at = datetime.now()
            await agent.save()
        await AnalystService.broadcast_sse(
            agent_id,
            "status",
            {"agent_id": agent_id, "status": NanobotAgentStatusEnum.RUNNING.value},
        )

        if rejections:
            reason_text = "；".join(r or "" for r in rejections)
            return f"修改被拒绝：{reason_text or '未提供理由'}"

        if not approved:
            return "修改未获得任何批准，未执行。"

        # TODO(#20 后续): 在此处按 modifications 真正写回 ES / DB。
        # 当前版本只记录日志，保持握手骨架可测。
        logger.info(
            f"modify_entity 审批通过: agent_id={agent_id} "
            f"entity={payload['entity_type']}:{payload['entity_uuid']} "
            f"modifications_count={len(payload['modifications'])}"
        )
        return (
            f"修改已获批准（共 {len(approved)} 条决策），"
            f"对实体 {payload['entity_type']}:{payload['entity_uuid']} 的修改将被应用。"
        )


def _parse_approval_decisions(
    decisions: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    """把 `/agent/approve` 提交的决策列表拆成 (approved, rejection_reasons)。

    单条决策约定：`{"action": "approve" | "reject", "reason": "..."}`，
    兼容前端可能传 `{"approved": True/False}` 这种简写。
    """
    approved: list[dict[str, Any]] = []
    rejections: list[str] = []
    for item in decisions or []:
        action = str(item.get("action") or "").lower()
        if not action:
            action = "approve" if item.get("approved") else "reject"
        if action in {"approve", "approved", "yes"}:
            approved.append(item)
        else:
            rejections.append(str(item.get("reason") or ""))
    return approved, rejections


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
            "description": "任务项列表，完整覆盖 agent.todos",
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
    """写入当前 agent 的 todos 列表（完整覆盖），并 SSE 广播给前端。"""

    @property
    def name(self) -> str:
        return "write_todos"

    @property
    def description(self) -> str:
        return "更新当前 Agent 的待办事项列表（会完全覆盖旧列表）。"

    @property
    def exclusive(self) -> bool:
        return True

    async def execute(self, **kwargs: Any) -> str:
        from app.service.analyst.service import AnalystService

        agent_id = _require_agent_id()
        todos = kwargs.get("todos") or []
        normalized = [_normalize_todo(item) for item in todos]

        agent = await NanobotAgentModel.find_one({"_id": agent_id})
        if agent is None:
            return f"[错误] 当前 agent 不存在: {agent_id}"
        agent.todos = normalized
        agent.updated_at = datetime.now()
        await agent.save()

        await AnalystService.broadcast_sse(
            agent_id,
            "todos",
            {
                "agent_id": agent_id,
                "session_id": get_current_session_id(),
                "todos": normalized,
            },
        )
        return f"已更新待办 {len(normalized)} 条"


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
}


def build_business_tools(enabled_names: list[str]) -> list[Tool]:
    """按名称白名单实例化业务工具。未识别的名字静默忽略并打 warn 日志。"""
    tools: list[Tool] = []
    for name in enabled_names or []:
        cls = BUSINESS_TOOL_CLASSES.get(name)
        if cls is None:
            logger.warning(f"未知业务工具名，已忽略: {name}")
            continue
        tools.append(cls())
    return tools


__all__ = [
    "GetCurrentTimeTool",
    "GetEntityTool",
    "ModifyEntityTool",
    "NotifyUserTool",
    "WriteTodosTool",
    "BUSINESS_TOOL_CLASSES",
    "build_business_tools",
]
