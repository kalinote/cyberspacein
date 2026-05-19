from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from app.schemas.constants import NanobotMemoryDocTypeEnum

if TYPE_CHECKING:
    from app.models.agent.nanobot import NanobotMemoryDocsModel


class ModelConfigListItemSchema(BaseModel):
    id: str = Field(description="模型配置ID")
    name: str = Field(description="模型配置名称")


class AgentPromptBriefSchema(BaseModel):
    id: str = Field(description="AGENT 内置提示词文档 ID")
    name: str = Field(description="文档名称")
    description: str | None = Field(default=None, description="文档描述")


class SystemPromptCreateRequestSchema(BaseModel):
    workspace_id: str = Field(description="工作区ID", min_length=1)
    type: NanobotMemoryDocTypeEnum = Field(description="系统指令模板类型")
    name: str = Field(description="系统指令模板名称", min_length=1)
    description: str | None = Field(default=None, description="系统指令模板描述")
    content: str = Field(description="系统指令模板内容")


class SystemPromptUpdateRequestSchema(BaseModel):
    workspace_id: str = Field(description="工作区ID", min_length=1)
    type: NanobotMemoryDocTypeEnum = Field(description="系统指令模板类型")
    name: str = Field(description="系统指令模板名称", min_length=1)
    description: str | None = Field(default=None, description="系统指令模板描述")
    content: str = Field(description="系统指令模板内容")


class SystemPromptSchema(BaseModel):
    id: str = Field(description="系统指令模板ID")
    workspace_id: str = Field(description="工作区ID")
    type: NanobotMemoryDocTypeEnum = Field(description="系统指令模板类型")
    name: str = Field(description="系统指令模板名称")
    description: str | None = Field(default=None, description="系统指令模板描述")
    content: str = Field(description="系统指令模板内容")
    created_at: datetime = Field(description="创建时间")
    updated_at: datetime = Field(description="更新时间")

    @classmethod
    def from_doc(cls, doc: "NanobotMemoryDocsModel") -> "SystemPromptSchema":
        return cls(
            id=str(doc.id),
            workspace_id=doc.workspace_id,
            type=doc.type,
            name=doc.name,
            description=doc.description,
            content=doc.content,
            created_at=doc.created_at,
            updated_at=doc.updated_at,
        )
