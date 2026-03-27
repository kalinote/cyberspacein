from datetime import datetime

from beanie import Document
from pydantic import Field


class PermissionCodeModel(Document):
    id: str = Field(alias="_id", description="权限码ID")
    perm_key: str = Field(description="权限码唯一标识")
    name: str = Field(description="权限名称")
    category: str = Field(description="分类")
    desc: str | None = Field(default=None, description="描述")
    tags: list[str] = Field(default_factory=list, description="标签")
    enabled: bool = Field(default=True, description="是否启用")
    is_deleted: bool = Field(default=False, description="是否软删除")
    create_by: str = Field(default="system", description="创建人")
    create_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    update_by: str | None = Field(default=None, description="更新人")
    update_at: datetime | None = Field(default=None, description="更新时间")

    class Settings:
        name = "auth_permission_codes"
        indexes = [
            "id",
            "perm_key",
            "category",
            "enabled",
            "is_deleted",
        ]

