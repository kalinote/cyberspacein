import logging
from datetime import datetime
from typing import Dict, Any, Optional
from .article import ARTICLE_SCHEMA, DATE_FIELDS as ARTICLE_DATE_FIELDS
from .forums import FORUMS_SCHEMA, DATE_FIELDS as FORUMS_DATE_FIELDS

logger = logging.getLogger(__name__)

def parse_date(date_str: str) -> Optional[str]:
    """将 yyyy-MM-dd HH:mm:ss 转换为 ISO 8601 格式"""
    if not date_str:
        return None
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
        return dt.isoformat()
    except ValueError:
        logger.warning(f"无法解析日期格式: {date_str}")
        return None

def validate_and_transform(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    验证并转换数据
    1. 检查必要字段 (uuid, entity_type)
    2. 根据 entity_type 选择 schema
    3. 过滤非 schema 字段
    4. 转换日期格式
    5. 添加 update_at
    """
    # 1. 检查必要字段
    if "uuid" not in data or "entity_type" not in data:
        logger.error("数据缺失必要字段: uuid 或 entity_type")
        return None

    entity_type = data["entity_type"]
    
    # 2. 选择 schema
    if entity_type == "article":
        schema = ARTICLE_SCHEMA
        date_fields = ARTICLE_DATE_FIELDS
    elif entity_type == "forum":
        schema = FORUMS_SCHEMA
        date_fields = FORUMS_DATE_FIELDS
    else:
        logger.error(f"未知的 entity_type: {entity_type}")
        return None

    validated_data = {}
    
    # 3. 验证并过滤字段
    for key, value in data.items():
        if key in schema:
            # 这里可以添加更严格的类型检查，目前仅做字段过滤
            validated_data[key] = value
    
    # 确保 uuid 和 entity_type 存在 (因为它们也在 schema 中)
    if "uuid" not in validated_data:
        validated_data["uuid"] = data["uuid"]
    if "entity_type" not in validated_data:
        validated_data["entity_type"] = data["entity_type"]

    # 4. 转换日期格式
    for date_field in date_fields:
        if date_field in validated_data and validated_data[date_field]:
            iso_date = parse_date(validated_data[date_field])
            if iso_date:
                validated_data[date_field] = iso_date
            else:
                # 如果日期解析失败，视情况决定是否保留原值或删除，这里选择保留原值但打印警告
                pass

    # 5. 添加 update_at
    validated_data["update_at"] = datetime.now().isoformat()

    return validated_data
