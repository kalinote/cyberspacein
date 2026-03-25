from datetime import datetime

from pydantic import BaseModel, Field

from app.models.auth.group import GroupModel


class GroupCreateRequest(BaseModel):
    group_name: str = Field(description="用户组唯一标识")
    display_name: str = Field(description="用户组展示名称")
    remark: str | None = Field(default=None, description="备注")
    enabled: bool = Field(default=True, description="是否启用")
    permissions: list[str] = Field(default_factory=list, description="权限码列表")


class GroupUpdateRequest(BaseModel):
    display_name: str | None = Field(default=None, description="用户组展示名称")
    remark: str | None = Field(default=None, description="备注")
    enabled: bool | None = Field(default=None, description="是否启用")
    permissions: list[str] | None = Field(default=None, description="权限码列表")


class GroupResponse(BaseModel):
    uuid: str = Field(description="用户组ID")
    create_by: str = Field(description="创建人")
    create_at: datetime = Field(description="创建时间")
    update_by: str | None = Field(description="更新人")
    update_at: datetime | None = Field(description="更新时间")
    remark: str | None = Field(description="备注")
    group_name: str = Field(description="用户组唯一标识")
    display_name: str = Field(description="用户组展示名称")
    enabled: bool = Field(description="是否启用")
    permissions: list[str] = Field(description="权限码列表")

    @classmethod
    def from_doc(cls, doc: GroupModel) -> "GroupResponse":
        return cls(
            uuid=doc.id,
            create_by=doc.create_by,
            create_at=doc.create_at,
            update_by=doc.update_by,
            update_at=doc.update_at,
            remark=doc.remark,
            group_name=doc.group_name,
            display_name=doc.display_name,
            enabled=doc.enabled,
            permissions=doc.permissions,
        )
