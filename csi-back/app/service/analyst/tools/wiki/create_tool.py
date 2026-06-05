"""wiki_create 业务工具。"""
from __future__ import annotations

import json
from typing import Any

from loguru import logger

from app.service.analyst.context import get_current_session_id
from app.service.analyst.tools._context import require_agent_id
from app.service.analyst.utils.wiki_apply import apply_wiki_create
from app.service.nanobot.agent.tools.base import Tool, tool_parameters

logger = logger.bind(name=__name__)


@tool_parameters({
    "type": "object",
    "properties": {
        "title": {"type": "string", "description": "页面标题", "minLength": 1},
        "source_note": {"type": "string", "description": "来源说明"},
        "categories": {
            "type": "array",
            "items": {"type": "string"},
            "description": "分类标签列表",
        },
        "reason": {
            "type": "string",
            "description": "创建说明，展示给审批人",
            "minLength": 1,
        },
    },
    "required": ["title", "reason"],
    "additionalProperties": False,
})
class WikiCreateTool(Tool):
    @property
    def name(self) -> str:
        return "wiki_create"

    @property
    def description(self) -> str:
        return "创建新的 Wiki 专题页，经人工审批后落库。"

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
            "title": kwargs.get("title"),
            "source_note": kwargs.get("source_note"),
            "categories": kwargs.get("categories") or [],
            "reason": kwargs.get("reason") or "",
        }

        try:
            outcome = await HitlService.request_approval(
                agent_id,
                session_id,
                HitlSource.TOOL_WIKI_CREATE,
                payload,
            )
        except RuntimeError as exc:
            return f"[错误] {exc}"
        except Exception as exc:
            logger.exception(
                f"wiki_create 等待审批异常: agent_id={agent_id} session_id={session_id}"
            )
            return f"[错误] 等待审批异常: {exc}"

        if outcome.rejections:
            reason_text = "；".join(r or "" for r in outcome.rejections)
            return f"创建被拒绝：{reason_text or '未提供理由'}"

        if not outcome.approved:
            return "创建未获得批准，未执行。"

        result, err = await apply_wiki_create(payload, agent_id=agent_id)
        if err:
            return err
        logger.info(
            f"wiki_create 已落库: agent_id={agent_id} wiki_id={result.get('wikiId')}"
        )
        return json.dumps(result, ensure_ascii=False)
