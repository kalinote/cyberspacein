from typing import List, Type
from beanie import Document

from app.models.action import NodeTypeConfigModel


def get_all_models() -> List[Type[Document]]:
    """获取所有需要注册的 Beanie Document 模型"""
    return [
        NodeTypeConfigModel,
    ]
