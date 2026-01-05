from beanie import Document
from pydantic import Field

from app.schemas.enum import ActionConfigIOTypeEnum
from app.schemas.general import DictModel

class ActionNodesHandleConfigModel(Document):
    id: str = Field(alias="_id")
    handle_name: str = Field(description="连接点名称")
    type: ActionConfigIOTypeEnum = Field(description="接口类型")
    label: str = Field(description="标签")
    color: str = Field(description="颜色代码")
    other_compatible_interfaces: list[str] = Field(default=[], description="其他兼容接口id列表")
    custom_style: list[DictModel] | None = None

    class Settings:
        name = "action_nodes_handle_configs"
        indexes = [
            "handle_name",
            "type",
        ]
        