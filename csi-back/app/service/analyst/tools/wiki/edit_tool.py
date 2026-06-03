"""wiki_edit 业务工具。"""
from __future__ import annotations

import json
from typing import Any

from loguru import logger

from app.service.analyst.context import get_current_session_id
from app.service.analyst.tools._context import require_agent_id
from app.service.analyst.utils.wiki_apply import WIKI_EDIT_OPERATIONS, apply_wiki_edit
from app.service.nanobot.agent.tools.base import Tool, tool_parameters

logger = logger.bind(name=__name__)

_WIKI_INFOBOX_SCHEMA = {
    "type": "object",
    "properties": {
        "caption": {"type": "string"},
        "series": {"type": "string"},
        "image": {"type": "string"},
        "rows": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "label": {"type": "string"},
                    "value": {"type": "string"},
                },
                "required": ["label", "value"],
            },
        },
    },
}

_PARAMS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "description": "operation 对应的业务参数（不含 wiki_id / expected_revision）",
    "properties": {
        "title": {"type": "string"},
        "source_note": {"type": "string"},
        "categories": {"type": "array", "items": {"type": "string"}},
        "status": {"type": "string", "enum": ["draft", "building", "published"]},
        "content": {"type": "string"},
        "infobox": _WIKI_INFOBOX_SCHEMA,
        "infobox_set": {"type": "boolean", "description": "为 true 时应用 infobox（含清空）"},
        "parent_section": {"type": "string"},
        "after_section": {"type": "string"},
        "section_id": {"type": "string"},
        "items": {
            "type": "array",
            "description": (
                "整表替换。put_footnotes：每项必填 id、text（勿用 key/content）；"
                "put_references：每项必填 id、text，可选 url、entityType、entityUuid。"
                "结构与 wiki_read 返回的 footnotes/references 一致。"
            ),
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string", "description": "脚注/文献标识"},
                    "text": {"type": "string", "description": "脚注正文或文献显示文本"},
                    "url": {"type": "string", "description": "仅 put_references"},
                    "entityType": {"type": "string", "description": "仅 put_references"},
                    "entityUuid": {"type": "string", "description": "仅 put_references"},
                },
            },
        },
    },
}


@tool_parameters({
    "type": "object",
    "properties": {
        "wiki_id": {
            "type": "string",
            "description": "Wiki 页 ID（32 位 hex）",
            "minLength": 1,
        },
        "operation": {
            "type": "string",
            "enum": sorted(WIKI_EDIT_OPERATIONS),
            "description": (
                "编辑操作类型。put_footnotes 时 params.items 每项为 {id, text}；"
                "put_references 时 params.items 每项至少含 {id, text}。"
            ),
        },
        "expected_revision": {
            "type": "integer",
            "minimum": 1,
            "description": "乐观锁修订号，须来自 wiki_read",
        },
        "change_summary": {
            "type": "string",
            "description": "变更摘要，写入版本历史",
        },
        "params": _PARAMS_SCHEMA,
        "reason": {
            "type": "string",
            "description": "修改说明，展示给审批人",
            "minLength": 1,
        },
    },
    "required": ["wiki_id", "operation", "expected_revision", "reason"],
    "additionalProperties": False,
})
class WikiEditTool(Tool):
    @property
    def name(self) -> str:
        return "wiki_edit"

    @property
    def description(self) -> str:
        return (
            "编辑已有 Wiki 页（meta/main/章节/脚注/参考文献/移动），"
            "经人工审批后落库。编辑前须 wiki_read 获取 expected_revision；不提供删除。"
            "put_footnotes/put_references 的 params.items 字段名为 id、text（勿用 key/content），"
            "与 wiki_read 的 footnotes/references 结构一致。"
        )

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

        operation = str(kwargs.get("operation") or "").strip()
        if operation not in WIKI_EDIT_OPERATIONS:
            return f"[错误] 不支持的 operation: {operation}"

        params = kwargs.get("params")
        if params is not None and not isinstance(params, dict):
            return "[错误] params 必须为对象"

        payload = {
            "wiki_id": kwargs.get("wiki_id"),
            "operation": operation,
            "expected_revision": kwargs.get("expected_revision"),
            "change_summary": kwargs.get("change_summary") or "",
            "params": params or {},
            "reason": kwargs.get("reason") or "",
        }

        try:
            outcome = await HitlService.request_approval(
                agent_id,
                session_id,
                HitlSource.TOOL_WIKI_EDIT,
                payload,
            )
        except RuntimeError as exc:
            return f"[错误] {exc}"
        except Exception as exc:
            logger.exception(
                f"wiki_edit 等待审批异常: agent_id={agent_id} session_id={session_id}"
            )
            return f"[错误] 等待审批异常: {exc}"

        if outcome.rejections:
            reason_text = "；".join(r or "" for r in outcome.rejections)
            return f"编辑被拒绝：{reason_text or '未提供理由'}"

        if not outcome.approved:
            return "编辑未获得批准，未执行。"

        result, err = await apply_wiki_edit(payload, agent_id=agent_id)
        if err:
            return err
        logger.info(
            f"wiki_edit 已落库: agent_id={agent_id} wiki_id={result.get('wikiId')} "
            f"operation={operation} revision={result.get('revision')}"
        )
        return json.dumps(result, ensure_ascii=False)
