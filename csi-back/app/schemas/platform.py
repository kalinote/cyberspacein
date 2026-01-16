from datetime import datetime
from pydantic import BaseModel, Field

class PlatformBaseInfoSchema(BaseModel):
    """
    平台基本信息
    """
    uuid: str = Field(description="平台ID")
    name: str = Field(description="平台名称")
    description: str = Field(description="平台描述")
    type: str = Field(description="平台类型")
    status: str = Field(description="平台状态")
    created_at: datetime = Field(description="平台创建时间")
    updated_at: datetime = Field(description="平台更新时间")
    url: str = Field(description="平台URL")
    logo: str = Field(description="平台Logo")
    tags: list[str] = Field(description="平台标签")
    category: str = Field(description="平台分类")
    sub_category: str = Field(description="平台子分类")