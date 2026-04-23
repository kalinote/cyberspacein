"""AgentService：nanobot_agents 集合的 CRUD 与资源子集校验。

主要职责：
1. 基础 CRUD（create / get / list_page / list_brief / update / delete），遵守
   `(workspace_id, name)` 联合唯一约束。
2. **资源子集校验**：Agent 选定的 `prompt_template_id / model_config_id / tools / skills /
   mcp_servers` 必须均是所属 Workspace 对应白名单的子集；非法组合在入库前直接拒绝。
3. **运行时保护**：Agent 处于 `RUNNING / AWAITING_APPROVAL` 时拒绝更新 / 删除（防止线上状态被改掉）。
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from loguru import logger

import app.utils.status_codes as status_codes
from app.models.agent.nanobot import NanobotAgentModel, NanobotWorkspaceModel
from app.schemas.agent.nanobot_agent import (
    AgentServiceError,
    NanobotAgentCreateRequestSchema,
    NanobotAgentUpdateRequestSchema,
)
from app.schemas.constants import NanobotAgentStatusEnum
from app.utils.id_lib import generate_id

logger = logger.bind(name=__name__)


# Agent 处于这些状态时拒绝一切结构性修改（update / delete），避免改坏正在跑的会话。
_RUNNING_STATUSES: set[NanobotAgentStatusEnum] = {
    NanobotAgentStatusEnum.RUNNING,
    NanobotAgentStatusEnum.AWAITING_APPROVAL,
}


class AgentService:
    """Agent 业务编排入口，对 API 层暴露 async 方法。

    所有写操作在持久化前统一做「资源子集校验」，失败时以 `AgentServiceError` 抛出，
    供路由层转换为 `ApiResponseSchema.error`。
    """

    # ------------------------- 查询 -------------------------

    @classmethod
    async def get(cls, agent_id: str) -> NanobotAgentModel:
        """按 id 获取 Agent，查不到时抛业务异常。"""
        doc = await NanobotAgentModel.find_one({"_id": agent_id})
        if doc is None:
            raise AgentServiceError(
                status_codes.NOT_FOUND_AGENT,
                f"Agent 不存在: {agent_id}",
            )
        return doc

    @classmethod
    async def list_page(
        cls,
        *,
        page: int,
        page_size: int,
        workspace_id: str | None = None,
        search: str | None = None,
    ) -> tuple[list[NanobotAgentModel], int]:
        """分页列出 Agent，支持按 workspace_id 过滤 + 名称 / 描述模糊搜索。"""
        query_filters: dict[str, Any] = {}
        if workspace_id:
            query_filters["workspace_id"] = workspace_id
        if search:
            pattern = re.compile(re.escape(search), re.IGNORECASE)
            query_filters["$or"] = [
                {"name": {"$regex": pattern}},
                {"description": {"$regex": pattern}},
            ]
        query = NanobotAgentModel.find(query_filters)
        total = await query.count()
        skip = (page - 1) * page_size
        items = await query.skip(skip).limit(page_size).to_list()
        return items, total

    @classmethod
    async def list_brief(
        cls, *, workspace_id: str | None = None
    ) -> list[NanobotAgentModel]:
        """返回 Agent 简表（id / name / workspace_id / status），供下拉使用，按创建时间降序。"""
        query_filters: dict[str, Any] = {}
        if workspace_id:
            query_filters["workspace_id"] = workspace_id
        return await NanobotAgentModel.find(query_filters).sort("-created_at").to_list()

    # ------------------------- 创建 -------------------------

    @classmethod
    async def create(cls, data: NanobotAgentCreateRequestSchema) -> NanobotAgentModel:
        """创建 Agent：先查 workspace，再做资源子集校验，最后写库。"""
        workspace = await cls._get_workspace(data.workspace_id)
        cls._validate_subset(
            workspace=workspace,
            prompt_template_id=data.prompt_template_id,
            model_config_id=data.model_config_id,
            tools=data.tools,
            skills=data.skills,
            mcp_servers=data.mcp_servers,
        )

        name_conflict = await NanobotAgentModel.find_one(
            {"workspace_id": data.workspace_id, "name": data.name}
        )
        if name_conflict is not None:
            raise AgentServiceError(
                status_codes.CONFLICT_NAME,
                f"同一工作区内 Agent 名称已存在: workspace={data.workspace_id} name={data.name}",
            )

        agent_id = generate_id(
            f"agent:{data.workspace_id}:{data.name}:{datetime.now().isoformat()}"
        )
        doc = NanobotAgentModel(
            id=agent_id,
            workspace_id=data.workspace_id,
            name=data.name,
            description=data.description,
            prompt_template_id=data.prompt_template_id,
            model_config_id=data.model_config_id,
            tools=list(data.tools),
            skills=list(data.skills),
            mcp_servers=list(data.mcp_servers),
            llm_config=dict(data.llm_config or {}),
        )
        await doc.insert()
        logger.info(
            f"创建 Agent 成功: id={agent_id} workspace={data.workspace_id} name={data.name}"
        )
        return doc

    # ------------------------- 更新 -------------------------

    @classmethod
    async def update(
        cls,
        agent_id: str,
        data: NanobotAgentUpdateRequestSchema,
    ) -> NanobotAgentModel:
        """更新 Agent：校验非运行时 + 重新做资源子集校验。"""
        doc = await cls.get(agent_id)

        if doc.status in _RUNNING_STATUSES:
            raise AgentServiceError(
                status_codes.CONFLICT_STATE,
                f"Agent 当前处于 {doc.status.value} 状态，无法修改配置",
            )

        if data.name != doc.name:
            name_conflict = await NanobotAgentModel.find_one(
                {"workspace_id": doc.workspace_id, "name": data.name}
            )
            if name_conflict is not None and name_conflict.id != agent_id:
                raise AgentServiceError(
                    status_codes.CONFLICT_NAME,
                    f"同一工作区内 Agent 名称已存在: workspace={doc.workspace_id} name={data.name}",
                )

        workspace = await cls._get_workspace(doc.workspace_id)
        cls._validate_subset(
            workspace=workspace,
            prompt_template_id=data.prompt_template_id,
            model_config_id=data.model_config_id,
            tools=data.tools,
            skills=data.skills,
            mcp_servers=data.mcp_servers,
        )

        doc.name = data.name
        doc.description = data.description
        doc.prompt_template_id = data.prompt_template_id
        doc.model_config_id = data.model_config_id
        doc.tools = list(data.tools)
        doc.skills = list(data.skills)
        doc.mcp_servers = list(data.mcp_servers)
        doc.llm_config = dict(data.llm_config or {})
        doc.updated_at = datetime.now()
        await doc.save()
        logger.info(f"更新 Agent 成功: id={agent_id} name={data.name}")
        return doc

    # ------------------------- 删除 -------------------------

    @classmethod
    async def delete(cls, agent_id: str) -> None:
        """删除 Agent：处于运行态时拒绝。"""
        doc = await cls.get(agent_id)
        if doc.status in _RUNNING_STATUSES:
            raise AgentServiceError(
                status_codes.CONFLICT_STATE,
                f"Agent 当前处于 {doc.status.value} 状态，无法删除，请先终止或等待完成",
            )
        await doc.delete()
        logger.info(f"删除 Agent 成功: id={agent_id}")

    # ------------------------- 内部工具 -------------------------

    @staticmethod
    async def _get_workspace(workspace_id: str) -> NanobotWorkspaceModel:
        workspace = await NanobotWorkspaceModel.find_one({"_id": workspace_id})
        if workspace is None:
            raise AgentServiceError(
                status_codes.NOT_FOUND_WORKSPACE,
                f"工作区不存在: {workspace_id}",
            )
        return workspace

    @staticmethod
    def _validate_subset(
        *,
        workspace: NanobotWorkspaceModel,
        prompt_template_id: str,
        model_config_id: str,
        tools: list[str],
        skills: list[str],
        mcp_servers: list[str],
    ) -> None:
        """校验 Agent 选定资源均 ⊆ Workspace 白名单；任一违规即抛出错误。"""
        violations: list[str] = []

        if prompt_template_id not in set(workspace.prompt_template_ids):
            violations.append(
                f"prompt_template_id={prompt_template_id} 不在 Workspace 白名单内"
            )
        if model_config_id not in set(workspace.model_config_ids):
            violations.append(
                f"model_config_id={model_config_id} 不在 Workspace 白名单内"
            )

        if len(set(tools)) != len(tools):
            violations.append("tools 中存在重复项")
        extra_tools = set(tools) - set(workspace.enabled_tools)
        if extra_tools:
            violations.append(f"tools 不在 Workspace 白名单内: {sorted(extra_tools)}")

        if len(set(skills)) != len(skills):
            violations.append("skills 中存在重复项")
        extra_skills = set(skills) - set(workspace.enabled_skills)
        if extra_skills:
            violations.append(f"skills 不在 Workspace 白名单内: {sorted(extra_skills)}")

        if len(set(mcp_servers)) != len(mcp_servers):
            violations.append("mcp_servers 中存在重复项")
        extra_mcp = set(mcp_servers) - set((workspace.enabled_mcp_servers or {}).keys())
        if extra_mcp:
            violations.append(
                f"mcp_servers 不在 Workspace 白名单内: {sorted(extra_mcp)}"
            )

        if violations:
            raise AgentServiceError(
                status_codes.INVALID_ARGUMENT,
                "Agent 选定资源不满足 Workspace 白名单子集约束",
                data={"violations": violations},
            )
