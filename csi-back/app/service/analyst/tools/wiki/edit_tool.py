"""wiki_edit 业务工具。"""
from __future__ import annotations

import json
from typing import Any

from loguru import logger

from app.service.analyst.context import get_current_session_id
from app.service.analyst.tools._context import require_agent_id
from app.service.analyst.utils.wiki_apply import (
    WIKI_EDIT_OPERATIONS,
    apply_wiki_edit,
    validate_wiki_edit_params,
)
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
    "description": (
        "operation 对应的业务参数。add_section：title、parent_section（必填），"
        "可选 after_section、content；勿传 section_id。"
        "patch_section/move_section：section_id 须来自 wiki_read 的 contentTree.section。"
    ),
    "properties": {
        "title": {"type": "string", "description": "章节标题（add_section）或 patch_section 改标题"},
        "source_note": {"type": "string", "description": "patch_meta"},
        "categories": {"type": "array", "items": {"type": "string"}, "description": "patch_meta"},
        "status": {
            "type": "string",
            "enum": ["draft", "building", "published"],
            "description": "patch_meta",
        },
        "content": {
            "type": "string",
            "description": (
                "Markdown 正文。注释用 [^a][^b]…[^aa][^ab]…，参考资料用 [^1][^2][^3]…"
            ),
        },
        "infobox": _WIKI_INFOBOX_SCHEMA,
        "infobox_set": {"type": "boolean", "description": "为 true 时应用 infobox（含清空）"},
        "parent_section": {
            "type": "string",
            "description": "add_section/move_section：父章节 section（新建子节常用 main）",
        },
        "after_section": {
            "type": "string",
            "description": "add_section/move_section：插入到该兄弟章节之后，可选",
        },
        "section_id": {
            "type": "string",
            "description": "仅 patch_section/move_section；须为 wiki_read 已有 section，勿自行编造",
        },
        "items": {
            "type": "array",
            "description": (
                "整表替换（勿用 key/content）。put_footnotes：items 每项 {id, text}，"
                "id 为字母 a、b、c…aa、ab（与正文 [^a] 一致）。"
                "put_references：items 每项 {id, text, url, entityType, entityUuid}，"
                "id 为数字 1、2、3（与正文 [^1] 一致）；须先 search_entities 或 get_entity 确认实体，"
                "entityUuid/entityType 取自检索结果，url 为 /details/{entityType}/{entityUuid}。"
            ),
            "items": {
                "type": "object",
                "properties": {
                    "id": {
                        "type": "string",
                        "description": "put_footnotes：字母 a/b/c…aa/ab；put_references：数字 1/2/3",
                    },
                    "text": {"type": "string", "description": "脚注正文或文献条目显示文本"},
                    "url": {
                        "type": "string",
                        "description": "put_references：/details/{entityType}/{entityUuid}",
                    },
                    "entityType": {
                        "type": "string",
                        "description": "put_references：库内实体类型（search_entities 的 entityType）",
                    },
                    "entityUuid": {
                        "type": "string",
                        "description": "put_references：库内实体 uuid（search_entities 的 uuid）",
                    },
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
                "编辑操作类型。add_section 仅需 title+parent_section（勿传 section_id）。"
                "patch_section/move_section 的 section_id 须来自 wiki_read。"
                "put_footnotes/put_references 见 params.items 与引用规范。"
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
            "编辑已有 Wiki 页（meta/main/章节/脚注/参考文献/移动），经人工审批后落库。"
            "编辑前须 wiki_read 获取 expected_revision、章节 section 与现有 footnotes/references。"
            "add_section：title、parent_section，可选 content；勿传 section_id（见 newSectionId）。"
            "patch_section/move_section：section_id 须来自 wiki_read，不可自编。"
            "引用：注释正文 [^a][^b]…[^aa]、脚注 id 用字母；参考资料正文 [^1][^2]…、"
            "文献 id 用数字；文献须对应库内实体（先 search_entities/get_entity），"
            "entityUuid/entityType 取自检索结果，url 为 /details/{entityType}/{entityUuid}。"
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
        params_dict = params if isinstance(params, dict) else {}
        param_err = validate_wiki_edit_params(operation, params_dict)
        if param_err:
            return param_err

        payload = {
            "wiki_id": kwargs.get("wiki_id"),
            "operation": operation,
            "expected_revision": kwargs.get("expected_revision"),
            "change_summary": kwargs.get("change_summary") or "",
            "params": params_dict,
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
