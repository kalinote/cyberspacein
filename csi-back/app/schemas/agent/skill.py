from datetime import datetime
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from app.models.agent.skill import NanobotSkillModel


class SkillUploadItemSchema(BaseModel):
    skill_id: str = Field(description="Skill ID")
    name: str = Field(description="Skill 名称")
    file_count: int = Field(description="写入的文件数量")
    always: bool = Field(description="是否 always 注入")


class SkillUploadResponseSchema(BaseModel):
    """zip 上传结果；单 skill 与多 skill 包统一返回列表。"""

    skills: list[SkillUploadItemSchema] = Field(default_factory=list, description="本次写入的 skill")
    total: int = Field(description="skill 数量")


class SkillFileBriefSchema(BaseModel):
    path: str = Field(description="相对路径")
    file_type: str = Field(description="文件类型")


class NanobotSkillListItemSchema(BaseModel):
    id: str = Field(description="Skill ID")
    name: str = Field(description="Skill 名称")
    description: str = Field(description="描述")
    always: bool = Field(description="是否 always")
    file_count: int = Field(default=0, description="文件数量")
    created_at: datetime = Field(description="创建时间")
    updated_at: datetime = Field(description="更新时间")


class NanobotSkillDetailSchema(BaseModel):
    id: str = Field(description="Skill ID")
    name: str = Field(description="Skill 名称")
    description: str = Field(description="描述")
    always: bool = Field(description="是否 always")
    meta: dict[str, Any] = Field(default_factory=dict, description="扩展元数据")
    files: list[SkillFileBriefSchema] = Field(default_factory=list, description="文件清单")
    created_at: datetime = Field(description="创建时间")
    updated_at: datetime = Field(description="更新时间")


class SkillListBriefSchema(BaseModel):
    """配置 UI 下拉用。"""

    id: str = Field(description="Skill ID")
    name: str = Field(description="Skill 名称")
    description: str = Field(description="描述")
    always: bool = Field(description="是否 always")


class SkillCreateRequestSchema(BaseModel):
    name: str = Field(description="Skill 名称（小写连字符）")
    description: str = Field(default="", description="描述")
    always: bool = Field(default=False, description="是否 always 注入")
    meta: dict[str, Any] = Field(default_factory=dict, description="扩展元数据")
    skill_md_body: str = Field(default="", description="SKILL.md frontmatter 之后的正文")


class SkillUpdateRequestSchema(BaseModel):
    name: str = Field(description="Skill 名称")
    description: str = Field(default="", description="描述")
    always: bool = Field(default=False, description="是否 always 注入")
    meta: dict[str, Any] = Field(default_factory=dict, description="扩展元数据")


class SkillFileContentSchema(BaseModel):
    path: str = Field(description="相对路径")
    file_type: str = Field(description="文件类型")
    content: str = Field(description="文件内容")
    updated_at: datetime = Field(description="更新时间")


class SkillFileUpsertRequestSchema(BaseModel):
    content: str = Field(description="文件内容")


class SkillFileCreateRequestSchema(BaseModel):
    path: str = Field(description="相对路径")
    content: str = Field(description="文件内容")


class SkillServiceError(Exception):
    def __init__(self, code: int, message: str, data: Any | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data
