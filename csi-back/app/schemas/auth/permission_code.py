from datetime import datetime

from pydantic import BaseModel, Field

from app.models.auth.permission_code import PermissionCodeModel


class PermissionCodeCreateRequest(BaseModel):
    perm_key: str = Field(description="占位权限码唯一标识")
    name: str = Field(min_length=1, description="权限名称")
    category: str = Field(min_length=1, description="分类")
    desc: str | None = Field(default=None, description="描述")
    tags: list[str] = Field(default_factory=list, description="标签")
    enabled: bool = Field(default=True, description="是否启用")


class PermissionCodeBatchCreateRequest(BaseModel):
    items: list[PermissionCodeCreateRequest]


class PermissionCodeUpdateRequest(BaseModel):
    name: str | None = None
    category: str | None = None
    desc: str | None = None
    tags: list[str] | None = None
    enabled: bool | None = None
    impact_acknowledged: bool = False


class PermissionCodeMigrationRequest(BaseModel):
    target_perm_key: str = Field(description="目标权限码")
    remove_source: bool = Field(default=False, description="迁移后删除来源占位权限")


class PermissionCodeListQuery(BaseModel):
    category: str | None = None
    enabled: bool | None = None
    tags: list[str] = Field(default_factory=list)
    keyword: str | None = None
    source: str | None = None


class PermissionImpactResponse(BaseModel):
    group_ids: list[str] = Field(default_factory=list)
    user_ids: list[str] = Field(default_factory=list)
    group_count: int = 0
    user_count: int = 0


class PermissionCodeResponse(BaseModel):
    uuid: str
    create_by: str
    create_at: datetime
    update_by: str | None
    update_at: datetime | None
    perm_key: str
    name: str
    category: str
    desc: str | None
    tags: list[str]
    module: str
    resource: str
    source: str
    backend_enforced: bool
    system_reserved: bool
    delegable: bool
    default_enabled: bool
    enabled: bool
    yaml_version: str | None

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
            module=doc.module,
            resource=doc.resource,
            source=doc.source,
            backend_enforced=doc.backend_enforced,
            system_reserved=doc.system_reserved,
            delegable=doc.delegable,
            default_enabled=doc.default_enabled,
            enabled=doc.enabled,
            yaml_version=doc.yaml_version,
        )
