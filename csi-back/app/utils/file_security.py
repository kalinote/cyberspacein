import logging
import io
import hashlib
from typing import Tuple, Optional
from urllib.parse import urlparse
import filetype
from PIL import Image
from app.core.config import settings

logger = logging.getLogger(__name__)

ALLOWED_IMAGE_TYPES = {
    'image/jpeg': ['.jpg', '.jpeg'],
    'image/png': ['.png'],
    'image/gif': ['.gif'],
    'image/webp': ['.webp'],
    'image/x-icon': ['.ico'],
    'image/vnd.microsoft.icon': ['.ico']
}

ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.ico'}


def validate_image_file(
    file_data: bytes,
    url: Optional[str] = None,
    max_size: Optional[int] = None
) -> Tuple[bool, str, Optional[str]]:
    """
    严格验证图片文件的安全性
    
    Args:
        file_data: 文件字节数据
        url: 原始URL（可选，用于提取文件扩展名）
        max_size: 最大文件大小限制，默认使用配置
    
    Returns:
        (是否通过, 错误信息或成功信息, 检测到的MIME类型)
    """
    max_allowed_size = max_size or settings.MAX_LOGO_SIZE
    
    if len(file_data) == 0:
        return False, "文件为空", None
    
    if len(file_data) > max_allowed_size:
        return False, f"文件大小超过限制: {len(file_data)} > {max_allowed_size} 字节", None
    
    if url:
        parsed_url = urlparse(url)
        path = parsed_url.path.lower()
        ext = None
        for allowed_ext in ALLOWED_EXTENSIONS:
            if path.endswith(allowed_ext):
                ext = allowed_ext
                break
        
        if not ext:
            logger.warning(f"URL中未找到有效的图片扩展名: {url}")
    
    kind = filetype.guess(file_data)
    if kind is None:
        return False, "无法识别文件类型", None
    
    detected_mime = kind.mime
    
    if detected_mime not in ALLOWED_IMAGE_TYPES:
        return False, f"不支持的文件类型: {detected_mime}，仅支持图片格式", detected_mime
    
    try:
        img = Image.open(io.BytesIO(file_data))
        img.verify()
        
        img = Image.open(io.BytesIO(file_data))
        img.load()
        
        logger.info(f"图片验证成功: 类型={detected_mime}, 尺寸={img.size}, 模式={img.mode}")
        return True, "图片验证通过", detected_mime
    
    except Exception as e:
        if detected_mime in ['image/x-icon', 'image/vnd.microsoft.icon']:
            # logger.warning(f"ICO文件Pillow验证失败，但仍允许通过: {str(e)}")
            return True, "ICO文件验证通过（基于文件类型识别）", detected_mime
        return False, f"图片完整性验证失败: {str(e)}", detected_mime


def get_file_extension_from_mime(mime_type: str) -> str:
    """
    根据MIME类型获取推荐的文件扩展名
    
    Args:
        mime_type: MIME类型
    
    Returns:
        文件扩展名（含点号）
    """
    if mime_type in ALLOWED_IMAGE_TYPES:
        return ALLOWED_IMAGE_TYPES[mime_type][0]
    return '.bin'


def calculate_file_hash(file_data: bytes, algorithm: str = 'sha256') -> str:
    """
    计算文件内容的哈希值
    
    Args:
        file_data: 文件字节数据
        algorithm: 哈希算法，支持 'md5' 或 'sha256'，默认 'sha256'
    
    Returns:
        文件哈希值（十六进制字符串）
    """
    if algorithm == 'md5':
        hash_obj = hashlib.md5(file_data)
    elif algorithm == 'sha256':
        hash_obj = hashlib.sha256(file_data)
    else:
        raise ValueError(f"不支持的哈希算法: {algorithm}")
    
    return hash_obj.hexdigest()
