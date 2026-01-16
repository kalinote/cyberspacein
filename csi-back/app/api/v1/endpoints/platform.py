from datetime import datetime
from fastapi import APIRouter, Depends

from app.schemas.platform import PlatformBaseInfoSchema
from app.schemas.general import PageParams, PageResponse

router = APIRouter(
    prefix="/platform",
    tags=["platform"],
)

@router.get("/list", response_model=PageResponse[PlatformBaseInfoSchema], summary="获取平台列表")
async def get_platform_list(
    params: PageParams = Depends()
):
    mock_data = PlatformBaseInfoSchema(
        uuid="fb5bebe1b7df48e6606fdffed2cf8b14",
        name="Bilibili",
        description="Bilibili是一个中国的视频分享平台，用户可以在上面观看和上传各种类型的视频。平台以弹幕评论系统为特色，用户可以在观看视频时发送实时评论，这些评论会以弹幕的形式显示在视频画面上。Bilibili主要面向年轻用户群体，内容涵盖动画、游戏、音乐、科技、生活等多个领域。",
        type="视频网站",
        status="正常",
        created_at=datetime(2025, 1, 1),
        updated_at=datetime(2025, 1, 1),
        url="https://www.bilibili.com",
        logo="https://www.bilibili.com/favicon.ico",
        tags=["视频分享", "二次元", "弹幕", "社交媒体"],
        category="娱乐",
        sub_category="视频"
    )
    
    return PageResponse.create([mock_data], total=1, page=params.page, page_size=params.page_size)
