from datetime import datetime

from beanie import Document
from pydantic import Field
from pymongo import ASCENDING, IndexModel


class PermissionCodeModel(Document):
    id: str = Field(alias="_id", description="权限码ID")
    perm_key: str = Field(description="权限码唯一标识")
    name: str = Field(description="权限名称")
    category: str = Field(description="分类")
    desc: str | None = Field(default=None, description="描述")
    tags: list[str] = Field(default_factory=list, description="标签")
    module: str = Field(default="", description="所属模块")
    resource: str = Field(default="", description="所属资源")
    source: str = Field(default="placeholder", description="来源：standard/placeholder")
    backend_enforced: bool = Field(default=False, description="是否可用于后端接口授权")
    system_reserved: bool = Field(default=False, description="是否系统保留权限")
    delegable: bool = Field(default=True, description="是否允许委派")
    default_enabled: bool = Field(default=True, description="清单默认启用状态")
    yaml_version: str | None = Field(default=None, description="YAML 同步版本")
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
            IndexModel(
                [("perm_key", ASCENDING)],
                unique=True,
                partialFilterExpression={"is_deleted": False},
                name="uq_auth_permission_codes_key_active",
            ),
            "category",
            "source",
            "enabled",
            "is_deleted",
        ]

