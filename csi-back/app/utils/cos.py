import logging
import io
from typing import Optional, BinaryIO, Dict, List
from contextlib import asynccontextmanager
from aioboto3 import Session
from botocore.exceptions import ClientError
from app.core.config import settings

logger = logging.getLogger(__name__)

cos_session: Optional[Session] = None
cos_config: Optional[Dict] = None


async def init_cos():
    """初始化COS连接"""
    global cos_session, cos_config
    
    if not all([
        settings.COS_ENDPOINT,
        settings.COS_ACCESS_KEY_ID,
        settings.COS_SECRET_ACCESS_KEY,
        settings.COS_BUCKET_NAME
    ]):
        logger.warning("COS配置不完整，跳过初始化")
        return
    
    cos_session = Session()
    cos_config = {
        'endpoint_url': settings.COS_ENDPOINT,
        'aws_access_key_id': settings.COS_ACCESS_KEY_ID,
        'aws_secret_access_key': settings.COS_SECRET_ACCESS_KEY,
        'region_name': settings.COS_REGION
    }
    
    async with cos_session.client('s3', **cos_config) as client:
        try:
            await client.head_bucket(Bucket=settings.COS_BUCKET_NAME)
            logger.info(f"已连接到COS存储桶: {settings.COS_BUCKET_NAME}")
        except ClientError as e:
            logger.error(f"连接COS存储桶失败: {e}")
            raise


async def close_cos():
    """关闭COS连接"""
    global cos_session, cos_config
    cos_session = None
    cos_config = None


@asynccontextmanager
async def get_cos_client():
    """获取COS客户端实例（异步上下文管理器）"""
    if cos_session is None or cos_config is None:
        raise RuntimeError("COS未初始化，请先调用 init_cos()")
    async with cos_session.client('s3', **cos_config) as client:
        yield client


async def upload_file(
    file_path: str,
    object_key: str,
    bucket_name: Optional[str] = None,
    content_type: Optional[str] = None,
    metadata: Optional[Dict[str, str]] = None
) -> str:
    """
    上传文件到COS
    
    Args:
        file_path: 本地文件路径
        object_key: 对象键（在存储桶中的路径）
        bucket_name: 存储桶名称，默认使用配置中的存储桶
        content_type: 文件MIME类型
        metadata: 元数据字典
    
    Returns:
        对象的URL路径
    """
    bucket = bucket_name or settings.COS_BUCKET_NAME
    
    extra_args = {}
    if content_type:
        extra_args['ContentType'] = content_type
    if metadata:
        extra_args['Metadata'] = metadata
    
    try:
        async with get_cos_client() as client:
            with open(file_path, 'rb') as f:
                await client.upload_fileobj(
                    f,
                    bucket,
                    object_key,
                    ExtraArgs=extra_args if extra_args else None
                )
        logger.info(f"文件上传成功: {object_key}")
        return object_key
    except Exception as e:
        logger.error(f"文件上传失败 {object_key}: {e}")
        raise


async def upload_fileobj(
    file_obj: BinaryIO,
    object_key: str,
    bucket_name: Optional[str] = None,
    content_type: Optional[str] = None,
    metadata: Optional[Dict[str, str]] = None
) -> str:
    """
    上传文件对象到COS
    
    Args:
        file_obj: 文件对象（BytesIO等）
        object_key: 对象键（在存储桶中的路径）
        bucket_name: 存储桶名称，默认使用配置中的存储桶
        content_type: 文件MIME类型
        metadata: 元数据字典
    
    Returns:
        对象的URL路径
    """
    bucket = bucket_name or settings.COS_BUCKET_NAME
    
    extra_args = {}
    if content_type:
        extra_args['ContentType'] = content_type
    if metadata:
        extra_args['Metadata'] = metadata
    
    try:
        file_obj.seek(0)
        async with get_cos_client() as client:
            await client.upload_fileobj(
                file_obj,
                bucket,
                object_key,
                ExtraArgs=extra_args if extra_args else None
            )
        logger.info(f"文件对象上传成功: {object_key}")
        return object_key
    except Exception as e:
        logger.error(f"文件对象上传失败 {object_key}: {e}")
        raise


async def upload_bytes(
    data: bytes,
    object_key: str,
    bucket_name: Optional[str] = None,
    content_type: Optional[str] = None,
    metadata: Optional[Dict[str, str]] = None
) -> str:
    """
    上传字节数据到COS
    
    Args:
        data: 字节数据
        object_key: 对象键（在存储桶中的路径）
        bucket_name: 存储桶名称，默认使用配置中的存储桶
        content_type: 文件MIME类型
        metadata: 元数据字典
    
    Returns:
        对象的URL路径
    """
    file_obj = io.BytesIO(data)
    return await upload_fileobj(
        file_obj,
        object_key,
        bucket_name,
        content_type,
        metadata
    )


async def download_file(
    object_key: str,
    local_path: str,
    bucket_name: Optional[str] = None
) -> str:
    """
    从COS下载文件到本地
    
    Args:
        object_key: 对象键（在存储桶中的路径）
        local_path: 本地保存路径
        bucket_name: 存储桶名称，默认使用配置中的存储桶
    
    Returns:
        本地文件路径
    """
    bucket = bucket_name or settings.COS_BUCKET_NAME
    
    try:
        async with get_cos_client() as client:
            await client.download_file(bucket, object_key, local_path)
        logger.info(f"文件下载成功: {object_key} -> {local_path}")
        return local_path
    except ClientError as e:
        if e.response['Error']['Code'] == '404':
            logger.error(f"对象不存在: {object_key}")
        else:
            logger.error(f"文件下载失败 {object_key}: {e}")
        raise
    except Exception as e:
        logger.error(f"文件下载失败 {object_key}: {e}")
        raise


async def download_fileobj(
    object_key: str,
    file_obj: BinaryIO,
    bucket_name: Optional[str] = None
) -> BinaryIO:
    """
    从COS下载文件到文件对象
    
    Args:
        object_key: 对象键（在存储桶中的路径）
        file_obj: 文件对象（用于接收数据）
        bucket_name: 存储桶名称，默认使用配置中的存储桶
    
    Returns:
        文件对象
    """
    bucket = bucket_name or settings.COS_BUCKET_NAME
    
    try:
        async with get_cos_client() as client:
            await client.download_fileobj(bucket, object_key, file_obj)
        file_obj.seek(0)
        logger.info(f"文件对象下载成功: {object_key}")
        return file_obj
    except ClientError as e:
        if e.response['Error']['Code'] == '404':
            logger.error(f"对象不存在: {object_key}")
        else:
            logger.error(f"文件对象下载失败 {object_key}: {e}")
        raise
    except Exception as e:
        logger.error(f"文件对象下载失败 {object_key}: {e}")
        raise


async def download_bytes(
    object_key: str,
    bucket_name: Optional[str] = None
) -> bytes:
    """
    从COS下载文件为字节数据
    
    Args:
        object_key: 对象键（在存储桶中的路径）
        bucket_name: 存储桶名称，默认使用配置中的存储桶
    
    Returns:
        字节数据
    """
    file_obj = io.BytesIO()
    await download_fileobj(object_key, file_obj, bucket_name)
    return file_obj.getvalue()


async def delete_file(
    object_key: str,
    bucket_name: Optional[str] = None
) -> bool:
    """
    从COS删除文件
    
    Args:
        object_key: 对象键（在存储桶中的路径）
        bucket_name: 存储桶名称，默认使用配置中的存储桶
    
    Returns:
        是否删除成功
    """
    bucket = bucket_name or settings.COS_BUCKET_NAME
    
    try:
        async with get_cos_client() as client:
            await client.delete_object(Bucket=bucket, Key=object_key)
        logger.info(f"文件删除成功: {object_key}")
        return True
    except ClientError as e:
        logger.error(f"文件删除失败 {object_key}: {e}")
        raise
    except Exception as e:
        logger.error(f"文件删除失败 {object_key}: {e}")
        raise


async def delete_files(
    object_keys: List[str],
    bucket_name: Optional[str] = None
) -> Dict[str, bool]:
    """
    批量删除COS文件
    
    Args:
        object_keys: 对象键列表
        bucket_name: 存储桶名称，默认使用配置中的存储桶
    
    Returns:
        删除结果字典 {object_key: success}
    """
    if not object_keys:
        return {}
    
    bucket = bucket_name or settings.COS_BUCKET_NAME
    
    delete_objects = [{'Key': key} for key in object_keys]
    
    try:
        async with get_cos_client() as client:
            response = await client.delete_objects(
                Bucket=bucket,
                Delete={'Objects': delete_objects}
            )
        
        deleted = {obj['Key']: True for obj in response.get('Deleted', [])}
        errors = {err['Key']: False for err in response.get('Errors', [])}
        
        result = {**deleted, **errors}
        logger.info(f"批量删除完成: 成功 {len(deleted)}, 失败 {len(errors)}")
        return result
    except Exception as e:
        logger.error(f"批量删除失败: {e}")
        raise


async def file_exists(
    object_key: str,
    bucket_name: Optional[str] = None
) -> bool:
    bucket = bucket_name or settings.COS_BUCKET_NAME
    
    try:
        async with get_cos_client() as client:
            response = await client.head_object(Bucket=bucket, Key=object_key)
            if response.get('DeleteMarker') or response.get('Metadata', {}).get('x-amz-delete-marker'):
                return False
                
            return True
    except ClientError as e:
        if e.response['Error']['Code'] in ['404', 'NoSuchKey']:
            return False
        logger.error(f"检查文件存在性失败 {object_key}: {e}")
        raise


async def get_file_url(
    object_key: str,
    bucket_name: Optional[str] = None,
    expires_in: int = 3600
) -> str:
    """
    获取文件的预签名URL
    
    Args:
        object_key: 对象键（在存储桶中的路径）
        bucket_name: 存储桶名称，默认使用配置中的存储桶
        expires_in: URL过期时间（秒），默认3600秒
    
    Returns:
        预签名URL
    """
    bucket = bucket_name or settings.COS_BUCKET_NAME
    
    try:
        async with get_cos_client() as client:
            url = client.generate_presigned_url(
                'get_object',
                Params={'Bucket': bucket, 'Key': object_key},
                ExpiresIn=expires_in
            )
        return url
    except Exception as e:
        logger.error(f"生成预签名URL失败 {object_key}: {e}")
        raise


async def list_files(
    prefix: str = "",
    bucket_name: Optional[str] = None,
    max_keys: int = 1000
) -> List[Dict]:
    """
    列出存储桶中的文件
    
    Args:
        prefix: 对象键前缀（用于过滤）
        bucket_name: 存储桶名称，默认使用配置中的存储桶
        max_keys: 最大返回数量
    
    Returns:
        文件信息列表，每个元素包含 Key, Size, LastModified 等
    """
    bucket = bucket_name or settings.COS_BUCKET_NAME
    
    try:
        async with get_cos_client() as client:
            response = await client.list_objects_v2(
                Bucket=bucket,
                Prefix=prefix,
                MaxKeys=max_keys
            )
        
        files = response.get('Contents', [])
        logger.info(f"列出文件成功: 前缀={prefix}, 数量={len(files)}")
        return files
    except Exception as e:
        logger.error(f"列出文件失败: {e}")
        raise


async def get_file_metadata(
    object_key: str,
    bucket_name: Optional[str] = None
) -> Dict:
    """
    获取文件的元数据
    
    Args:
        object_key: 对象键（在存储桶中的路径）
        bucket_name: 存储桶名称，默认使用配置中的存储桶
    
    Returns:
        文件元数据字典
    """
    bucket = bucket_name or settings.COS_BUCKET_NAME
    
    try:
        async with get_cos_client() as client:
            response = await client.head_object(Bucket=bucket, Key=object_key)
        metadata = {
            'ContentLength': response.get('ContentLength'),
            'ContentType': response.get('ContentType'),
            'LastModified': response.get('LastModified'),
            'ETag': response.get('ETag'),
            'Metadata': response.get('Metadata', {})
        }
        return metadata
    except ClientError as e:
        if e.response['Error']['Code'] == '404':
            logger.error(f"对象不存在: {object_key}")
        else:
            logger.error(f"获取文件元数据失败 {object_key}: {e}")
        raise
    except Exception as e:
        logger.error(f"获取文件元数据失败 {object_key}: {e}")
        raise

async def upload_bytes_with_public_url(
    data: bytes,
    object_key: str,
    bucket_name: Optional[str] = None,
    content_type: Optional[str] = None,
    metadata: Optional[Dict[str, str]] = None
) -> str:
    """
    上传字节数据到COS并返回公共访问URL
    
    Args:
        data: 字节数据
        object_key: 对象键（在存储桶中的路径）
        bucket_name: 存储桶名称，默认使用配置中的存储桶
        content_type: 文件MIME类型
        metadata: 元数据字典
    
    Returns:
        公共访问URL
    """
    await upload_bytes(data, object_key, bucket_name, content_type, metadata)
    return object_key