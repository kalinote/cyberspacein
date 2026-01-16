import logging
import re
from datetime import datetime
from fastapi import APIRouter, Depends, Query
from typing import Optional

from app.schemas.platform import PlatformBaseInfoSchema, PlatformCreateRequest
from app.schemas.general import PageParams, PageResponse
from app.schemas.response import ApiResponse
from app.models.platform.platform import PlatformModel
from app.utils.id_lib import generate_id
from app.utils.async_fetch import async_download_file
from app.utils.file_security import validate_image_file, get_file_extension_from_mime, calculate_file_hash
from app.utils.cos import upload_bytes_with_public_url, file_exists

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/platform",
    tags=["platform"],
)

@router.post("", response_model=ApiResponse[PlatformBaseInfoSchema], summary="创建平台")
async def create_platform(data: PlatformCreateRequest):
    platform_id = generate_id(data.name + data.url)
    
    existing_platform = await PlatformModel.find_one({"_id": platform_id})
    if existing_platform:
        return ApiResponse.error(code=400, message=f"平台已存在，名称: {data.name} 或 URL: {data.url}")
    
    existing_by_name = await PlatformModel.find_one({"name": data.name})
    if existing_by_name:
        return ApiResponse.error(code=400, message=f"平台名称已存在: {data.name}")
    
    existing_by_url = await PlatformModel.find_one({"url": data.url})
    if existing_by_url:
        return ApiResponse.error(code=400, message=f"平台URL已存在: {data.url}")
    
    processed_logo = ""
    if data.logo and data.logo.strip():
        try:
            logger.info(f"开始下载logo: {data.logo}")
            logo_data = await async_download_file(data.logo)
            
            is_valid, message, mime_type = validate_image_file(logo_data, data.logo)
            if is_valid and mime_type:
                # logger.info(f"Logo安全检查通过: {message}")
                
                file_hash = calculate_file_hash(logo_data, algorithm='sha256')
                file_ext = get_file_extension_from_mime(mime_type)
                object_key = f"logo/{file_hash}{file_ext}"
                
                if await file_exists(object_key):
                    logger.info(f"Logo文件已存在于COS中，直接使用: {object_key}")
                    processed_logo = object_key
                else:
                    cos_url = await upload_bytes_with_public_url(
                        logo_data,
                        object_key,
                        content_type=mime_type
                    )
                    processed_logo = cos_url
                    logger.info(f"Logo上传成功: {cos_url}")
            else:
                logger.warning(f"Logo安全检查失败: {message}，将使用空logo")
        except Exception as e:
            logger.error(f"处理logo时发生错误: {e}，将使用空logo")
    
    platform_model = PlatformModel(
        id=platform_id,
        name=data.name,
        description=data.description,
        type=data.type,
        status=data.status,
        url=data.url,
        logo=processed_logo,
        tags=data.tags,
        category=data.category,
        sub_category=data.sub_category,
        confidence=data.confidence
    )
    
    await platform_model.insert()
    logger.info(f"成功创建平台: {platform_id} - {data.name}")
    
    response_data = PlatformBaseInfoSchema(
        id=platform_model.id,
        name=platform_model.name,
        description=platform_model.description,
        type=platform_model.type,
        status=platform_model.status,
        created_at=platform_model.created_at,
        updated_at=platform_model.updated_at,
        url=platform_model.url,
        logo=platform_model.logo,
        tags=platform_model.tags,
        category=platform_model.category,
        sub_category=platform_model.sub_category,
        confidence=platform_model.confidence
    )
    
    return ApiResponse.success(data=response_data)

@router.get("/list", response_model=PageResponse[PlatformBaseInfoSchema], summary="获取平台列表")
async def get_platform_list(
    params: PageParams = Depends(),
    type: Optional[str] = Query(None, description="平台类型筛选"),
    status: Optional[str] = Query(None, description="平台状态筛选"),
    category: Optional[str] = Query(None, description="平台分类筛选"),
    search: Optional[str] = Query(None, description="搜索关键词，用于模糊搜索平台名称和描述")
):
    skip = (params.page - 1) * params.page_size
    
    query_filters = {}
    if type:
        query_filters["type"] = type
    if status:
        query_filters["status"] = status
    if category:
        query_filters["category"] = category
    
    if search:
        search_pattern = re.compile(re.escape(search), re.IGNORECASE)
        query_filters["$or"] = [
            {"name": {"$regex": search_pattern}},
            {"description": {"$regex": search_pattern}}
        ]
    
    if query_filters:
        query = PlatformModel.find(query_filters)
    else:
        query = PlatformModel.find_all()
    
    total = await query.count()
    platforms = await query.skip(skip).limit(params.page_size).to_list()
    
    results = []
    for platform in platforms:
        results.append(PlatformBaseInfoSchema(
            id=platform.id,
            name=platform.name,
            description=platform.description,
            type=platform.type,
            status=platform.status,
            created_at=platform.created_at,
            updated_at=platform.updated_at,
            url=platform.url,
            logo=platform.logo,
            tags=platform.tags,
            category=platform.category,
            sub_category=platform.sub_category,
            confidence=platform.confidence
        ))
    
    return PageResponse.create(results, total, params.page, params.page_size)
