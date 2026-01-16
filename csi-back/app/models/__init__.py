from typing import List, Type
from beanie import Document

from app.models.action.configs import ActionNodesHandleConfigModel
from app.models.action.node import ActionNodeModel
from app.models.action.blueprint import ActionBlueprintModel
from app.models.action.action import ActionInstanceModel, ActionInstanceNodeModel
from app.models.platform.platform import PlatformModel


def get_all_models() -> List[Type[Document]]:
    """获取所有需要注册的 Beanie Document 模型"""
    return [
        ActionNodeModel,
        ActionBlueprintModel,
        ActionInstanceModel,
        ActionInstanceNodeModel,
        ActionNodesHandleConfigModel,
        PlatformModel
    ]
