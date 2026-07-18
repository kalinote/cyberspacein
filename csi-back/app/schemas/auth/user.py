from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.models.auth.user import UserModel


class UserCreateRequest(BaseModel):
    username: str = Field(min_length=1, max_length=128, description="用户名")
    password: str = Field(min_length=1, description="密码")
    display_name: str = Field(min_length=1, max_length=128, description="显示名称")
    email: str | None = Field(default=None, description="邮箱")
    remark: str | None = Field(default=None, description="备注")
    enabled: bool = Field(default=True, description="是否启用")
    temporary_account: bool = Field(default=False, description="是否临时账号")
    expired_at: datetime | None = Field(default=None, description="到期时间")
    groups: list[str] = Field(default_factory=list, description="用户组 UUID 列表")

    @field_validator("username", "display_name")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("字段不能为空")
        return normalized

    @field_validator("email")
    @classmethod
    def normalize_optional_email(cls, value: str | None) -> str | None:
        return value.strip() if value and value.strip() else None


class UserProfileUpdateRequest(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=128)
    email: str | None = None
    remark: str | None = None

    @field_validator("display_name")
    @classmethod
    def strip_optional_display_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("显示名称不能为空")
        return normalized

    @field_validator("email")
    @classmethod
    def normalize_optional_email(cls, value: str | None) -> str | None:
        return value.strip() if value and value.strip() else None


class UserGroupUpdateRequest(BaseModel):
    groups: list[str] = Field(default_factory=list, description="用户组 UUID 列表")


class UserPasswordUpdateRequest(BaseModel):
    password: str = Field(min_length=1, description="新密码")


class UserStatusUpdateRequest(BaseModel):
    enabled: bool = Field(description="是否启用")


class UserExpiryUpdateRequest(BaseModel):
    temporary_account: bool = Field(description="是否临时账号")
    expired_at: datetime | None = Field(default=None, description="到期时间")


class AssignmentScopeUpdateRequest(BaseModel):
    restrict_permission_assignment: bool = Field(description="是否限制权限分配范围")


class UserListItemResponse(BaseModel):
    uuid: str
    username: str
    display_name: str
    enabled: bool
    temporary_account: bool
    expired_at: datetime | None
    is_system: bool
    authorization_version: int
    create_at: datetime

    @classmethod
    def from_doc(cls, doc: UserModel) -> "UserListItemResponse":
        return cls(
            uuid=doc.id,
            username=doc.username,
            display_name=doc.display_name,
            enabled=doc.enabled,
            temporary_account=doc.temporary_account,
            expired_at=doc.expired_at,
            is_system=doc.is_system,
            authorization_version=doc.authorization_version,
            create_at=doc.create_at,
        )


class UserResponse(BaseModel):
    uuid: str
    create_by: str
    create_at: datetime
    update_by: str | None
    update_at: datetime | None
    remark: str | None
    username: str
    display_name: str
    email: str | None
    login_ip: str | None
    login_date: datetime | None
    enabled: bool
    temporary_account: bool
    expired_at: datetime | None
    groups: list[str]
    is_system: bool
    restrict_permission_assignment: bool
    authorization_version: int

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
            is_system=doc.is_system,
            restrict_permission_assignment=doc.restrict_permission_assignment,
            authorization_version=doc.authorization_version,
        )


# Compatibility alias for imports outside the permission endpoints. It intentionally
# exposes profile fields only; sensitive mutations use their dedicated schemas above.
UserUpdateRequest = UserProfileUpdateRequest
