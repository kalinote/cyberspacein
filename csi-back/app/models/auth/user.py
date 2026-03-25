from datetime import datetime

from beanie import Document
from pydantic import Field


class UserModel(Document):
    id: str = Field(alias="_id", description="用户ID")
    username: str = Field(description="用户名")
    display_name: str = Field(description="显示名称")
    email: str | None = Field(default=None, description="邮箱")
    password_hash: str = Field(description="密码哈希")
    remark: str | None = Field(default=None, description="备注")
    login_ip: str | None = Field(default=None, description="最近登录IP")
    login_date: datetime | None = Field(default=None, description="最近登录时间")
    enabled: bool = Field(default=True, description="是否启用")
    temporary_account: bool = Field(default=False, description="是否临时账号")
    expired_at: datetime | None = Field(default=None, description="到期时间")
    groups: list[str] = Field(default_factory=list, description="用户组UUID列表")
    is_deleted: bool = Field(default=False, description="是否软删除")
    create_by: str = Field(default="system", description="创建人")
    create_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    update_by: str | None = Field(default=None, description="更新人")
    update_at: datetime | None = Field(default=None, description="更新时间")

    class Settings:
        name = "auth_users"
        indexes = [
            "id",
            "username",
            "email",
            "enabled",
            "is_deleted",
            "groups",
        ]
