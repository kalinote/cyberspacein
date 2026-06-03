from datetime import datetime
from typing import Any

from beanie import Document
from pydantic import Field
from pymongo import ASCENDING, IndexModel


class NanobotSkillModel(Document):
    """全局 Skill 元数据（聚合根）。"""

    id: str = Field(alias="_id", description="Skill ID")
    name: str = Field(description="Skill 名称，全局唯一")
    description: str = Field(default="", description="Skill 描述")
    always: bool = Field(default=False, description="是否始终注入 system prompt")
    meta: dict[str, Any] = Field(default_factory=dict, description="其余 frontmatter 字段")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")

    class Settings:
        name = "nanobot_skills"
        indexes = [
            IndexModel([("name", ASCENDING)], unique=True),
            "created_at",
            "updated_at",
        ]


class NanobotSkillFileModel(Document):
    """Skill 附属文件（SKILL.md、references、scripts 等）。"""

    skill_id: str = Field(description="所属 Skill ID")
    path: str = Field(description="zip 内相对路径，如 SKILL.md、references/examples.md")
    file_type: str = Field(description="文件类型：skill / reference / script / asset / other")
    content: str = Field(description="文本内容")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")

    class Settings:
        name = "nanobot_skill_files"
        indexes = [
            IndexModel([("skill_id", ASCENDING), ("path", ASCENDING)], unique=True),
            "skill_id",
            "created_at",
        ]
