from typing import Any

from fastapi import APIRouter
from loguru import logger

from app.models.agent.configs import AgentModelConfigModel, AgentPromptTemplateModel
from app.models.agent.nanobot import NanobotAgentModel, NanobotMemoryDocsModel, NanobotWorkspaceModel
from app.schemas.agent.agent import ToolDescriptorSchema
from app.schemas.response import ApiResponseSchema
from app.service.analyst.tools import BUSINESS_TOOL_CLASSES

logger = logger.bind(name=__name__)

router = APIRouter(prefix="/configs")


@router.get(
    "/tools",
    response_model=ApiResponseSchema[list[ToolDescriptorSchema]],
    summary="查询可用业务工具列表（含元信息）",
)
async def get_agent_tools():
    results: list[ToolDescriptorSchema] = []
    for name, cls in BUSINESS_TOOL_CLASSES.items():
        try:
            instance = cls()
            results.append(
                ToolDescriptorSchema(
                    name=instance.name,
                    description=instance.description,
                    read_only=bool(instance.read_only),
                    exclusive=bool(instance.exclusive),
                )
            )
        except Exception as exc:
            logger.warning(f"构造工具描述失败，已跳过: {name} err={exc}")
    return ApiResponseSchema.success(data=results)


@router.get(
    "/tools-list",
    response_model=ApiResponseSchema[list[str]],
    summary="查询可用业务工具名称列表",
)
async def get_agent_tools_list():
    return ApiResponseSchema.success(data=list(BUSINESS_TOOL_CLASSES.keys()))


@router.get("/statistics", response_model=ApiResponseSchema[dict[str, int]], summary="配置资源数量统计")
async def get_configs_statistics():
    data = {
        "model_configs": await AgentModelConfigModel.find().count(),
        "prompt_templates": await AgentPromptTemplateModel.find().count(),
        "system_prompts": await NanobotMemoryDocsModel.find().count(),
        "workspaces": await NanobotWorkspaceModel.find().count(),
        "agents": await NanobotAgentModel.find().count(),
        "business_tools": len(BUSINESS_TOOL_CLASSES),
    }
    return ApiResponseSchema.success(data=data)

