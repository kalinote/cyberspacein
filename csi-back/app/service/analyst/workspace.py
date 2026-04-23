"""WorkspaceService：nanobot_workspaces 集合的 CRUD 与白名单一致性校验。

主要职责：
1. 基础 CRUD（create / get / list / update / delete），遵守 `(_id)` 与 `(name)` 唯一。
2. 资源存在性校验：`prompt_template_ids` / `model_config_ids` 必须均指向已存在的 `AgentPromptTemplateModel`
   / `AgentModelConfigModel` 记录；`enabled_mcp_servers` value 必须可被 `MCPServerConfig` 解析。
3. 白名单收窄级联校验：更新 Workspace 时，如果**收窄**了某字段（去掉了某 tool / skill / mcp / prompt_template /
   model_config），必须确认该 Workspace 下已有的 `NanobotAgentModel` 仍在引用被移除项；一旦存在引用则拒绝更新
   （保守策略，由 TODO #17 明确）。
4. 删除保护：存在关联 Agent 时拒绝删除 Workspace。
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from loguru import logger

import app.utils.status_codes as status_codes
from app.models.agent.configs import AgentModelConfigModel, AgentPromptTemplateModel
from app.models.agent.nanobot import NanobotAgentModel, NanobotWorkspaceModel
from app.schemas.agent.workspace import (
    MCPServerConfigSchema,
    NanobotWorkspaceCreateRequestSchema,
    NanobotWorkspaceUpdateRequestSchema,
    WorkspaceServiceError,
)
from app.service.nanobot.config.schema import MCPServerConfig
from app.utils.id_lib import generate_id

logger = logger.bind(name=__name__)


class WorkspaceService:
    """Workspace 业务编排入口，对 API 层暴露 async 方法。

    所有写操作在持久化前统一做「资源存在性校验」和（更新时）「白名单收窄级联校验」，
    失败时以 `WorkspaceServiceError` 形式抛出，供路由层转换为 `ApiResponseSchema.error`。
    """

    # ------------------------- 查询 -------------------------

    @classmethod
    async def get(cls, workspace_id: str) -> NanobotWorkspaceModel:
        """按 id 获取 Workspace，查不到时抛业务异常。"""
        doc = await NanobotWorkspaceModel.find_one({"_id": workspace_id})
        if doc is None:
            raise WorkspaceServiceError(
                status_codes.NOT_FOUND_WORKSPACE,
                f"工作区不存在: {workspace_id}",
            )
        return doc

    @classmethod
    async def list_page(
        cls,
        *,
        page: int,
        page_size: int,
        search: str | None = None,
    ) -> tuple[list[NanobotWorkspaceModel], int]:
        """分页列出 Workspace，可按名称 / 描述模糊搜索。"""
        query_filters: dict[str, Any] = {}
        if search:
            pattern = re.compile(re.escape(search), re.IGNORECASE)
            query_filters["$or"] = [
                {"name": {"$regex": pattern}},
                {"description": {"$regex": pattern}},
            ]
        query = NanobotWorkspaceModel.find(query_filters)
        total = await query.count()
        skip = (page - 1) * page_size
        items = await query.skip(skip).limit(page_size).to_list()
        return items, total

    @classmethod
    async def list_all_brief(cls) -> list[NanobotWorkspaceModel]:
        """返回全部 Workspace（仅给下拉列表使用，默认按创建时间降序）。"""
        return await NanobotWorkspaceModel.find_all().sort("-created_at").to_list()

    # ------------------------- 创建 -------------------------

    @classmethod
    async def create(cls, data: NanobotWorkspaceCreateRequestSchema) -> NanobotWorkspaceModel:
        """创建 Workspace：先做资源存在性校验，再写库。"""
        await cls._validate_resources_exist(
            prompt_template_ids=data.prompt_template_ids,
            model_config_ids=data.model_config_ids,
            mcp_servers=data.enabled_mcp_servers,
        )

        name_conflict = await NanobotWorkspaceModel.find_one({"name": data.name})
        if name_conflict is not None:
            raise WorkspaceServiceError(
                status_codes.CONFLICT_NAME,
                f"工作区名称已存在: {data.name}",
            )

        workspace_id = generate_id(f"workspace:{data.name}:{datetime.now().isoformat()}")
        doc = NanobotWorkspaceModel(
            id=workspace_id,
            name=data.name,
            description=data.description,
            prompt_template_ids=list(data.prompt_template_ids),
            model_config_ids=list(data.model_config_ids),
            enabled_tools=list(data.enabled_tools),
            enabled_skills=list(data.enabled_skills),
            enabled_mcp_servers={
                name: payload.model_dump() for name, payload in data.enabled_mcp_servers.items()
            },
        )
        await doc.insert()
        logger.info(f"创建工作区成功: id={workspace_id} name={data.name}")
        return doc

    # ------------------------- 更新 -------------------------

    @classmethod
    async def update(
        cls,
        workspace_id: str,
        data: NanobotWorkspaceUpdateRequestSchema,
    ) -> NanobotWorkspaceModel:
        """更新 Workspace：校验资源存在 + 白名单收窄级联一致性。"""
        doc = await cls.get(workspace_id)

        if data.name != doc.name:
            name_conflict = await NanobotWorkspaceModel.find_one({"name": data.name})
            if name_conflict is not None and name_conflict.id != workspace_id:
                raise WorkspaceServiceError(
                    status_codes.CONFLICT_NAME,
                    f"工作区名称已存在: {data.name}",
                )

        await cls._validate_resources_exist(
            prompt_template_ids=data.prompt_template_ids,
            model_config_ids=data.model_config_ids,
            mcp_servers=data.enabled_mcp_servers,
        )

        await cls._validate_narrowing_cascade(workspace_id=workspace_id, new_data=data)

        doc.name = data.name
        doc.description = data.description
        doc.prompt_template_ids = list(data.prompt_template_ids)
        doc.model_config_ids = list(data.model_config_ids)
        doc.enabled_tools = list(data.enabled_tools)
        doc.enabled_skills = list(data.enabled_skills)
        doc.enabled_mcp_servers = {
            name: payload.model_dump() for name, payload in data.enabled_mcp_servers.items()
        }
        doc.updated_at = datetime.now()
        await doc.save()
        logger.info(f"更新工作区成功: id={workspace_id} name={data.name}")
        return doc

    # ------------------------- 删除 -------------------------

    @classmethod
    async def delete(cls, workspace_id: str) -> None:
        """删除 Workspace：必须先清空其下属 Agent，否则拒绝。"""
        doc = await cls.get(workspace_id)

        referenced = await NanobotAgentModel.find({"workspace_id": workspace_id}).count()
        if referenced > 0:
            raise WorkspaceServiceError(
                status_codes.CONFLICT_STATE,
                f"工作区 {workspace_id} 下仍有 {referenced} 个 Agent，无法删除",
            )

        await doc.delete()
        logger.info(f"删除工作区成功: id={workspace_id}")

    # ------------------------- 内部校验 -------------------------

    @staticmethod
    async def _validate_resources_exist(
        *,
        prompt_template_ids: list[str],
        model_config_ids: list[str],
        mcp_servers: dict[str, MCPServerConfigSchema],
    ) -> None:
        """校验外部资源（模板 / 模型 / MCP 配置）合法性。"""
        unique_prompt_ids = set(prompt_template_ids)
        if len(unique_prompt_ids) != len(prompt_template_ids):
            raise WorkspaceServiceError(
                status_codes.INVALID_ARGUMENT,
                "prompt_template_ids 中存在重复项",
            )
        unique_model_ids = set(model_config_ids)
        if len(unique_model_ids) != len(model_config_ids):
            raise WorkspaceServiceError(
                status_codes.INVALID_ARGUMENT,
                "model_config_ids 中存在重复项",
            )

        if unique_prompt_ids:
            existing_prompts = await AgentPromptTemplateModel.find(
                {"_id": {"$in": list(unique_prompt_ids)}}
            ).to_list()
            existing_prompt_ids = {doc.id for doc in existing_prompts}
            missing = unique_prompt_ids - existing_prompt_ids
            if missing:
                raise WorkspaceServiceError(
                    status_codes.NOT_FOUND_TEMPLATE,
                    f"提示词模板不存在: {sorted(missing)}",
                )

        if unique_model_ids:
            existing_models = await AgentModelConfigModel.find(
                {"_id": {"$in": list(unique_model_ids)}}
            ).to_list()
            existing_model_ids = {doc.id for doc in existing_models}
            missing = unique_model_ids - existing_model_ids
            if missing:
                raise WorkspaceServiceError(
                    status_codes.NOT_FOUND_MODEL_CONFIG,
                    f"模型配置不存在: {sorted(missing)}",
                )

        for server_name, payload in mcp_servers.items():
            if not server_name:
                raise WorkspaceServiceError(
                    status_codes.INVALID_ARGUMENT,
                    "enabled_mcp_servers 的 key（server_name）不能为空字符串",
                )
            try:
                MCPServerConfig.model_validate(payload.model_dump())
            except Exception as exc:
                raise WorkspaceServiceError(
                    status_codes.INVALID_ARGUMENT,
                    f"MCP 服务 {server_name} 配置不合法: {exc}",
                ) from exc

    @staticmethod
    async def _validate_narrowing_cascade(
        *,
        workspace_id: str,
        new_data: NanobotWorkspaceUpdateRequestSchema,
    ) -> None:
        """白名单收窄时校验所有关联 Agent 均仍然合法；若有任一 Agent 失效则拒绝更新。"""
        agents = await NanobotAgentModel.find({"workspace_id": workspace_id}).to_list()
        if not agents:
            return

        new_prompt_ids = set(new_data.prompt_template_ids)
        new_model_ids = set(new_data.model_config_ids)
        new_tools = set(new_data.enabled_tools)
        new_skills = set(new_data.enabled_skills)
        new_mcp_names = set(new_data.enabled_mcp_servers.keys())

        conflicts: list[str] = []
        for agent in agents:
            if agent.prompt_template_id and agent.prompt_template_id not in new_prompt_ids:
                conflicts.append(
                    f"Agent[{agent.id}:{agent.name}] 仍在引用已移除的 prompt_template_id="
                    f"{agent.prompt_template_id}"
                )
            if agent.model_config_id and agent.model_config_id not in new_model_ids:
                conflicts.append(
                    f"Agent[{agent.id}:{agent.name}] 仍在引用已移除的 model_config_id="
                    f"{agent.model_config_id}"
                )
            removed_tools = set(agent.tools or []) - new_tools
            if removed_tools:
                conflicts.append(
                    f"Agent[{agent.id}:{agent.name}] 仍在引用已移除的 tools={sorted(removed_tools)}"
                )
            removed_skills = set(agent.skills or []) - new_skills
            if removed_skills:
                conflicts.append(
                    f"Agent[{agent.id}:{agent.name}] 仍在引用已移除的 skills={sorted(removed_skills)}"
                )
            removed_mcps = set(agent.mcp_servers or []) - new_mcp_names
            if removed_mcps:
                conflicts.append(
                    f"Agent[{agent.id}:{agent.name}] 仍在引用已移除的 mcp_servers={sorted(removed_mcps)}"
                )

        if conflicts:
            raise WorkspaceServiceError(
                status_codes.CONFLICT_STATE,
                "白名单收窄与关联 Agent 冲突，请先调整 Agent 后再更新工作区",
                data={"conflicts": conflicts},
            )
