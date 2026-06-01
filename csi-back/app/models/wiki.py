from datetime import datetime

from beanie import Document
from pydantic import BaseModel, Field
from pymongo import ASCENDING, DESCENDING, IndexModel, TEXT

from app.schemas.constants import WikiPageStatusEnum, WikiRevisionChangeTypeEnum


class WikiInfoboxRowModel(BaseModel):
    label: str = Field(description="标签")
    value: str = Field(description="值")


class WikiInfoboxModel(BaseModel):
    caption: str | None = Field(default=None, description="标题")
    series: str | None = Field(default=None, description="系列说明")
    image: str | None = Field(default=None, description="图片 URL")
    rows: list[WikiInfoboxRowModel] = Field(default_factory=list, description="信息行")


class WikiContentNodeModel(BaseModel):
    section: str = Field(description="章节唯一 ID")
    title: str = Field(default="", description="章节标题")
    content: str = Field(default="", description="Markdown 正文")
    infobox: WikiInfoboxModel | None = Field(default=None, description="信息框")
    children: list["WikiContentNodeModel"] = Field(default_factory=list, description="子章节")


class WikiFootnoteModel(BaseModel):
    id: str = Field(description="脚注 ID（字母）")
    text: str = Field(description="脚注正文")


class WikiReferenceModel(BaseModel):
    id: str = Field(description="参考文献 ID（数字字符串）")
    text: str = Field(description="参考文献条目")
    url: str | None = Field(default=None, description="链接")
    entity_type: str | None = Field(default=None, description="关联实体类型")
    entity_uuid: str | None = Field(default=None, description="关联实体 UUID")


class WikiPageSnapshotModel(BaseModel):
    title: str = Field(description="页面标题")
    source_note: str | None = Field(default=None, description="来源说明")
    content_tree: WikiContentNodeModel = Field(description="内容树")
    footnotes: list[WikiFootnoteModel] = Field(default_factory=list)
    references: list[WikiReferenceModel] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)
    status: WikiPageStatusEnum = Field(description="发布状态")


class WikiPageModel(Document):
    id: str = Field(alias="_id", description="Wiki 页 ID（32 位 hex）")
    title: str = Field(description="页面标题")
    source_note: str | None = Field(default=None, description="来源说明")
    content_tree: WikiContentNodeModel = Field(description="内容树，根节点 section=main")
    footnotes: list[WikiFootnoteModel] = Field(default_factory=list)
    references: list[WikiReferenceModel] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)
    status: WikiPageStatusEnum = Field(
        default=WikiPageStatusEnum.DRAFT, description="发布状态"
    )
    revision: int = Field(default=1, description="修订号，与乐观锁共用")
    search_blob: str = Field(default="", description="搜索用扁平文本")
    created_by: str | None = Field(default=None, description="创建者")
    last_modified: datetime = Field(default_factory=datetime.now)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    class Settings:
        name = "wiki_pages"
        indexes = [
            IndexModel([("status", ASCENDING)]),
            IndexModel([("updated_at", DESCENDING)]),
            IndexModel([("title", ASCENDING)]),
            IndexModel([("search_blob", TEXT)]),
        ]


class WikiPageRevisionModel(Document):
    id: str = Field(alias="_id", description="快照记录 ID")
    wiki_id: str = Field(description="所属 Wiki 页 ID")
    revision: int = Field(description="与保存后页 revision 一致")
    snapshot: WikiPageSnapshotModel = Field(description="全量内容快照")
    change_type: WikiRevisionChangeTypeEnum = Field(description="变更类型")
    target_section: str | None = Field(default=None, description="目标章节 section")
    change_summary: str = Field(default="", description="变更说明")
    operator: str | None = Field(default=None, description="操作者")
    restored_from_revision: int | None = Field(
        default=None, description="恢复来源 revision"
    )
    created_at: datetime = Field(default_factory=datetime.now)

    class Settings:
        name = "wiki_page_revisions"
        indexes = [
            IndexModel([("wiki_id", ASCENDING), ("revision", ASCENDING)], unique=True),
            IndexModel([("wiki_id", ASCENDING), ("created_at", DESCENDING)]),
        ]
