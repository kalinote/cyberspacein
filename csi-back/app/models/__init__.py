from typing import List, Type
from beanie import Document

from app.models.action.configs import ActionNodesHandleConfigModel
from app.models.action.components_task import BaseComponentsTaskConfigModel
from app.models.action.node import ActionNodeModel
from app.models.action.blueprint import ActionBlueprintModel
from app.models.action.action import ActionInstanceModel, ActionInstanceNodeModel
from app.models.action.accounts import AccountModel
from app.models.action.sandbox import SandboxModel
from app.models.platform.platform import PlatformModel
from app.models.agent.configs import AgentModelConfigModel, AgentPromptTemplateModel
from app.models.agent.nanobot import (
    NanobotAgentModel,
    NanobotHistoryModel,
    NanobotHistoryStateModel,
    NanobotMemoryDocsModel,
    NanobotSessionMessagesModel,
    NanobotSessionModel,
    NanobotWorkspaceModel,
)
from app.models.annotation import AnnotationModel
from app.models.search_template import SearchTemplateModel
from app.models.auth.group import GroupModel
from app.models.auth.user import UserModel
from app.models.auth.permission_code import PermissionCodeModel

def get_all_models() -> List[Type[Document]]:
    """获取所有需要注册的 Beanie Document 模型"""
    return [
        ActionNodeModel,
        ActionBlueprintModel,
        ActionInstanceModel,
        ActionInstanceNodeModel,
        AccountModel,
        SandboxModel,
        ActionNodesHandleConfigModel,
        BaseComponentsTaskConfigModel,
        PlatformModel,
        AgentModelConfigModel,
        AgentPromptTemplateModel,
        NanobotWorkspaceModel,
        NanobotAgentModel,
        NanobotSessionModel,
        NanobotSessionMessagesModel,
        NanobotMemoryDocsModel,
        NanobotHistoryModel,
        NanobotHistoryStateModel,
        AnnotationModel,
        SearchTemplateModel,
        GroupModel,
        UserModel,
        PermissionCodeModel,
    ]
