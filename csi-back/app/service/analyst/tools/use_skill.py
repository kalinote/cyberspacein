"""use_skill：按 skill_id 加载 Skill 正文或子文件。"""
from __future__ import annotations

import json
from typing import Any

from loguru import logger

from app.models.agent.nanobot import NanobotAgentModel, NanobotWorkspaceModel
from app.service.analyst.skill_service import SkillService
from app.service.analyst.tools._context import require_agent_id
from app.service.nanobot.agent.tools.base import Tool, tool_parameters

logger = logger.bind(name=__name__)


@tool_parameters({
    "type": "object",
    "properties": {
        "skill_id": {
            "type": "string",
            "description": "Skill ID（须在本 Agent 与 Workspace 白名单内）",
            "minLength": 1,
        },
        "path": {
            "type": "string",
            "description": "相对路径，默认 SKILL.md；子文档如 references/examples.md",
        },
    },
    "required": ["skill_id"],
    "additionalProperties": False,
})
class UseSkillTool(Tool):
    @property
    def name(self) -> str:
        return "use_skill"

    @property
    def description(self) -> str:
        return (
            "加载已启用 Skill 的正文或附属文件。"
            "always 技能主文档通常已在 system prompt 中；需要 references/scripts 等附录时指定 path。"
        )

    @property
    def read_only(self) -> bool:
        return True

    async def execute(self, **kwargs: Any) -> str:
        agent_id = require_agent_id()
        skill_id = str(kwargs.get("skill_id") or "").strip()
        path = str(kwargs.get("path") or "SKILL.md").strip() or "SKILL.md"

        agent = await NanobotAgentModel.find_one({"_id": agent_id})
        if agent is None:
            return "Error: 当前 Agent 不存在"

        workspace = await NanobotWorkspaceModel.find_one({"_id": agent.workspace_id})
        if workspace is None:
            return "Error: 当前 Workspace 不存在"

        allowed = set(workspace.enabled_skills or []) & set(agent.skills or [])
        if skill_id not in allowed:
            return f"Error: Skill {skill_id} 未在本 Agent/Workspace 白名单内"

        content, err = await SkillService.load_for_tool(skill_id, path)
        if err:
            return f"Error: {err}"
        skill = await SkillService.get_by_id(skill_id)
        title = skill.name if skill else skill_id
        payload = {
            "skill_id": skill_id,
            "name": title,
            "path": path.replace("\\", "/").lstrip("/"),
            "content": content,
        }
        return json.dumps(payload, ensure_ascii=False, indent=2)
