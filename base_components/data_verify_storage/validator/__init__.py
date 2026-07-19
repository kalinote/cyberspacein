import logging
import math
import os
from datetime import datetime
from typing import Dict, Any, Optional
from .article import ARTICLE_SCHEMA, DATE_FIELDS as ARTICLE_DATE_FIELDS
from .forums import FORUMS_SCHEMA, DATE_FIELDS as FORUMS_DATE_FIELDS

logger = logging.getLogger(__name__)

TRANSLATION_FIELD_ALIASES = {
    "translation_content": "translate_content",
}


def _vector_dimensions() -> int:
    raw = os.getenv("ELASTICSEARCH_VECTOR_DIMS", "4096")
    try:
        dimensions = int(raw)
        if dimensions < 1:
            raise ValueError
        return dimensions
    except (TypeError, ValueError):
        logger.warning(
            "ELASTICSEARCH_VECTOR_DIMS=%r 非法，使用默认值 4096", raw
        )
        return 4096


COMMON_DATE_FORMATS = [
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M:%S.%f",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M:%S.%f",
    "%Y-%m-%dT%H:%M:%S.%fZ",
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d",
    "%Y/%m/%d %H:%M:%S",
    "%Y/%m/%d %H:%M",
    "%Y/%m/%d",
    "%d/%m/%Y %H:%M:%S",
    "%d/%m/%Y %H:%M",
    "%d/%m/%Y",
    "%d-%m-%Y %H:%M:%S",
    "%d-%m-%Y",
    "%Y%m%d %H:%M:%S",
    "%Y%m%d %H:%M",
    "%Y%m%d",
    "%Y.%m.%d %H:%M:%S",
    "%Y.%m.%d",
]


def parse_date(date_str: str) -> Optional[str]:
    """将常见时间字符串转换为 ISO 8601 格式"""
    if not date_str or not isinstance(date_str, str):
        return None
    raw = date_str.strip()
    if not raw:
        return None
    try:
        # fromisoformat 补充支持带时区偏移（例如 +08:00）的标准 ISO 8601。
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return dt.isoformat()
    except ValueError:
        pass
    for fmt in COMMON_DATE_FORMATS:
        try:
            dt = datetime.strptime(raw, fmt)
            return dt.isoformat()
        except ValueError:
            continue
    try:
        ts = float(raw)
        if 1e10 <= ts <= 2e10 or 1e12 <= ts <= 2e12:
            sec = ts if ts < 1e11 else ts / 1000
            dt = datetime.fromtimestamp(sec)
            return dt.isoformat()
    except (ValueError, OSError):
        pass
    logger.warning(f"无法解析日期格式: {date_str}")
    return None


def _sanitize_vector(value: Any, uuid: str) -> Optional[list[float]]:
    """校验 dense_vector，非法向量不应阻塞整篇实体的存储。"""
    if value is None or value == []:
        return None
    if not isinstance(value, list):
        logger.warning(
            "实体 %s 的 clean_content_vector 不是数组，已移除该向量", uuid
        )
        return None

    expected_dimensions = _vector_dimensions()
    if len(value) != expected_dimensions:
        logger.warning(
            "实体 %s 的 clean_content_vector 维度错误: expected=%d actual=%d，"
            "已移除该向量并将 vector_status 设为 false",
            uuid,
            expected_dimensions,
            len(value),
        )
        return None

    vector: list[float] = []
    for position, item in enumerate(value):
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            logger.warning(
                "实体 %s 的 clean_content_vector[%d] 不是数值，已移除该向量",
                uuid,
                position,
            )
            return None
        number = float(item)
        if not math.isfinite(number):
            logger.warning(
                "实体 %s 的 clean_content_vector[%d] 不是有限数值，已移除该向量",
                uuid,
                position,
            )
            return None
        vector.append(number)
    return vector

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
    if not isinstance(data, dict):
        logger.error("数据必须是 JSON 对象，当前类型: %s", type(data).__name__)
        return None
    if "uuid" not in data or "entity_type" not in data:
        logger.error("数据缺失必要字段: uuid 或 entity_type")
        return None

    uuid = str(data["uuid"]).strip() if data["uuid"] is not None else ""
    if not uuid:
        logger.error("数据的 uuid 不能为空")
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
    normalized_data = dict(data)
    for old_name, new_name in TRANSLATION_FIELD_ALIASES.items():
        if old_name in normalized_data and new_name not in normalized_data:
            normalized_data[new_name] = normalized_data[old_name]

    for key, value in normalized_data.items():
        if key in schema:
            # 这里可以添加更严格的类型检查，目前仅做字段过滤
            validated_data[key] = value
    
    # 确保 uuid 和 entity_type 存在 (因为它们也在 schema 中)
    validated_data["uuid"] = uuid
    if "entity_type" not in validated_data:
        validated_data["entity_type"] = data["entity_type"]

    # 4. 转换日期格式
    for date_field in date_fields:
        if date_field in validated_data and validated_data[date_field]:
            iso_date = parse_date(validated_data[date_field])
            if iso_date:
                validated_data[date_field] = iso_date
            else:
                # date mapping 无法接收任意字符串；移除非法的可选时间字段，
                # 避免一处脏值导致整个实体写入失败。
                del validated_data[date_field]
                logger.warning(
                    "实体 %s 的日期字段 %s 无法解析，已移除该字段",
                    uuid,
                    date_field,
                )

    # 5. dense_vector 对维度和数值类型有严格要求。向量异常时仍保存正文，
    # 并标记为待重新向量化。
    if "clean_content_vector" in validated_data:
        vector = _sanitize_vector(validated_data["clean_content_vector"], uuid)
        if vector is None:
            validated_data.pop("clean_content_vector", None)
            validated_data["vector_status"] = False
        else:
            validated_data["clean_content_vector"] = vector

    # 6. 添加 update_at
    validated_data["update_at"] = datetime.now().replace(microsecond=0).isoformat()

    return validated_data
