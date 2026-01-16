from datetime import datetime
from beanie import Document
from pydantic import Field


class PlatformModel(Document):
    """
    平台信息模型
    """
    id: str = Field(alias="_id")
    name: str = Field(description="平台名称")
    description: str = Field(description="平台描述")
    type: str = Field(description="平台类型")
    net_type: str = Field(description="网络类型(Tor/明网)")
    status: str = Field(description="平台状态")
    created_at: datetime = Field(default_factory=datetime.now, description="平台创建时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="平台更新时间")
    url: str = Field(description="平台URL")
    logo: str = Field(description="平台Logo")
    tags: list[str] = Field(default_factory=list, description="平台标签")
    category: str = Field(description="平台分类")
    sub_category: str = Field(description="平台子分类")
    confidence: float = Field(default=1, description="平台信任度")
    
    class Settings:
        name = "platforms"
        indexes = [
            "id",
            "name",
            "type",
            "status",
            "category",
        ]
