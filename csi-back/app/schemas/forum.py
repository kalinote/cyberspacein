from pydantic import Field
from app.schemas.general import BaseEntitySchema

class ForumSchema(BaseEntitySchema):
    topic_id: str | None = Field(default=None, description="整个帖子的id")
    parent_id: str | None = Field(default=None, description="父ID。该回复直接回复的对象的 ID。用于构建 Reddit 风格的树状评论结构")
    floor: int | None = Field(default=None, description="楼层号。BBS 特有（如 1楼、2楼）。用于按顺序排序展示。主贴通常为 1 或 0")
    thread_type: str | None = Field(default=None, description="帖子类型，分为thread(主贴，也就是1楼)、comment(评论)、featured(点评，一般附属于主贴或某个恢复，只有少量信息，没有单独的楼层号，也不能被回复)")
    category_tag: str | None = Field(default=None, description="帖子内部的分类标签。如 [求助], [原创], [Discussion]")
    title: str | None = Field(default=None, description="主标题，回复贴此字段继承主贴主标题标题")
    files_urls: list[str] | None = Field(default=None, description="图片、视频或附件等文件的直接链接列表，用于后续下载和分析")
    status_flags: list[str] | None = Field(default=None, description="帖子的特殊状态。枚举值：locked (锁定), stickied (置顶), essence (精华/加精), solved (已解决)")
    likes: int | None = Field(default=None, description="点赞数")
    dislikes: int | None = Field(default=None, description="点踩数")
    collections: int | None = Field(default=None, description="收藏数")
    comments: int | None = Field(default=None, description="评论数")
    views: int | None = Field(default=None, description="浏览量")
    topic_thread_uuid: str | None = Field(default=None, description="对应主贴的uuid。根据platform和topic_id查询thread_type为thread且last_edit_at最新的记录的uuid")
