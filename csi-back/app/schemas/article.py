from pydantic import Field
from app.schemas.general import BaseEntitySchema

class ArticleSchema(BaseEntitySchema):
    title: str | None = Field(default=None, description="标题")
    cover_image: str | None = Field(default=None, description="封面图/缩略图 URL")
    likes: int | None = Field(default=None, description="点赞数")
