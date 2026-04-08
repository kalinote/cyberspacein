from datetime import datetime

from pydantic import BaseModel, Field

from app.models.auth.permission_code import PermissionCodeModel


class PermissionCodeCreateRequest(BaseModel):
    perm_key: str = Field(description="权限码唯一标识")
    name: str = Field(description="权限名称")
    category: str = Field(description="分类")
    desc: str | None = Field(default=None, description="描述")
    tags: list[str] = Field(default_factory=list, description="标签")
    enabled: bool = Field(default=True, description="是否启用")


class PermissionCodeBatchCreateRequest(BaseModel):
    items: list[PermissionCodeCreateRequest] = Field(description="待批量创建的权限码列表")


class PermissionCodeUpdateRequest(BaseModel):
    perm_key: str | None = Field(default=None, description="权限码唯一标识")
    name: str | None = Field(default=None, description="权限名称")
    category: str | None = Field(default=None, description="分类")
    desc: str | None = Field(default=None, description="描述")
    tags: list[str] | None = Field(default=None, description="标签")
    enabled: bool | None = Field(default=None, description="是否启用")


class PermissionCodeListQuery(BaseModel):
    category: str | None = Field(default=None, description="分类")
    enabled: bool | None = Field(default=None, description="是否启用")
    tags: list[str] = Field(default_factory=list, description="标签（任一命中）")
    keyword: str | None = Field(default=None, description="关键词（匹配 perm_key/name/desc）")


class PermissionCodeResponse(BaseModel):
    uuid: str = Field(description="权限码ID")
    create_by: str = Field(description="创建人")
    create_at: datetime = Field(description="创建时间")
    update_by: str | None = Field(description="更新人")
    update_at: datetime | None = Field(description="更新时间")

    perm_key: str = Field(description="权限码唯一标识")
    name: str = Field(description="权限名称")
    category: str = Field(description="分类")
    desc: str | None = Field(description="描述")
    tags: list[str] = Field(description="标签")
    enabled: bool = Field(description="是否启用")

    @classmethod
    def from_doc(cls, doc: PermissionCodeModel) -> "PermissionCodeResponse":
        return cls(
            uuid=doc.id,
            create_by=doc.create_by,
            create_at=doc.create_at,
            update_by=doc.update_by,
            update_at=doc.update_at,
            perm_key=doc.perm_key,
            name=doc.name,
            category=doc.category,
            desc=doc.desc,
            tags=doc.tags,
            enabled=doc.enabled,
        )

