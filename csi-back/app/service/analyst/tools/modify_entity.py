"""modify_entity 业务工具。"""

from __future__ import annotations

from typing import Any

from loguru import logger

from app.schemas.constants import EntityType
from app.service.analyst.context import get_current_session_id
from app.service.analyst.tools._context import require_agent_id
from app.service.nanobot.agent.tools.base import Tool, tool_parameters

logger = logger.bind(name=__name__)


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

        agent_id = require_agent_id()
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
