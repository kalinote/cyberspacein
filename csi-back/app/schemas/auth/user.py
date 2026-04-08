from datetime import datetime

from pydantic import BaseModel, Field

from app.models.auth.user import UserModel


class UserCreateRequest(BaseModel):
    username: str = Field(description="用户名")
    password: str = Field(description="密码")
    display_name: str = Field(description="显示名称")
    email: str | None = Field(default=None, description="邮箱")
    remark: str | None = Field(default=None, description="备注")
    enabled: bool = Field(default=True, description="是否启用")
    temporary_account: bool = Field(default=False, description="是否临时账号")
    expired_at: datetime | None = Field(default=None, description="到期时间")
    groups: list[str] = Field(default_factory=list, description="用户组UUID列表")


class UserUpdateRequest(BaseModel):
    display_name: str | None = Field(default=None, description="显示名称")
    email: str | None = Field(default=None, description="邮箱")
    remark: str | None = Field(default=None, description="备注")
    enabled: bool | None = Field(default=None, description="是否启用")
    temporary_account: bool | None = Field(default=None, description="是否临时账号")
    expired_at: datetime | None = Field(default=None, description="到期时间")
    groups: list[str] | None = Field(default=None, description="用户组UUID列表")
    password: str | None = Field(default=None, description="密码")


class UserStatusUpdateRequest(BaseModel):
    enabled: bool = Field(description="是否启用")


class UserResponse(BaseModel):
    uuid: str = Field(description="用户ID")
    create_by: str = Field(description="创建人")
    create_at: datetime = Field(description="创建时间")
    update_by: str | None = Field(description="更新人")
    update_at: datetime | None = Field(description="更新时间")
    remark: str | None = Field(description="备注")
    username: str = Field(description="用户名")
    display_name: str = Field(description="显示名称")
    email: str | None = Field(description="邮箱")
    login_ip: str | None = Field(description="最近登录IP")
    login_date: datetime | None = Field(description="最近登录时间")
    enabled: bool = Field(description="是否启用")
    temporary_account: bool = Field(description="是否临时账号")
    expired_at: datetime | None = Field(description="到期时间")
    groups: list[str] = Field(description="用户组UUID列表")

    @classmethod
    def from_doc(cls, doc: UserModel) -> "UserResponse":
        return cls(
            uuid=doc.id,
            create_by=doc.create_by,
            create_at=doc.create_at,
            update_by=doc.update_by,
            update_at=doc.update_at,
            remark=doc.remark,
            username=doc.username,
            display_name=doc.display_name,
            email=doc.email,
            login_ip=doc.login_ip,
            login_date=doc.login_date,
            enabled=doc.enabled,
            temporary_account=doc.temporary_account,
            expired_at=doc.expired_at,
            groups=doc.groups,
        )
