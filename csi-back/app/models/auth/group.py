from datetime import datetime

from beanie import Document
from pydantic import Field


class GroupModel(Document):
    id: str = Field(alias="_id", description="用户组ID")
    group_name: str = Field(description="用户组唯一标识")
    display_name: str = Field(description="用户组展示名称")
    remark: str | None = Field(default=None, description="备注")
    enabled: bool = Field(default=True, description="是否启用")
    permissions: list[str] = Field(default_factory=list, description="权限码列表")
    is_deleted: bool = Field(default=False, description="是否软删除")
    create_by: str = Field(default="system", description="创建人")
    create_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    update_by: str | None = Field(default=None, description="更新人")
    update_at: datetime | None = Field(default=None, description="更新时间")

    class Settings:
        name = "auth_groups"
        indexes = [
            "id",
            "group_name",
            "enabled",
            "is_deleted",
        ]
