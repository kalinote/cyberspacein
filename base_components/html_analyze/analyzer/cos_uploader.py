import os
import logging
import threading
import time
from typing import Optional
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError, NoCredentialsError
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class COSUploader:
    
    def __init__(self):
        self.endpoint = os.getenv('COS_ENDPOINT')
        self.access_key = os.getenv('COS_ACCESS_KEY')
        self.secret_key = os.getenv('COS_SECRET_KEY')
        self.bucket = os.getenv('COS_BUCKET')
        self.region = os.getenv('COS_REGION', 'us-east-1')
        self.base_url = os.getenv('COS_BASE_URL')
        
        self.client: Optional[boto3.client] = None
        self._initialized = False
        self._initialize_lock = threading.Lock()
        
    def _initialize(self) -> bool:
        if self._initialized:
            return True

        with self._initialize_lock:
            if self._initialized:
                return True

            if not all([self.endpoint, self.access_key, self.secret_key, self.bucket]):
                logger.warning("COS配置不完整，媒体本地化功能将被禁用")
                return False

            try:
                self.client = boto3.client(
                    's3',
                    endpoint_url=self.endpoint,
                    aws_access_key_id=self.access_key,
                    aws_secret_access_key=self.secret_key,
                    region_name=self.region,
                    config=Config(
                        connect_timeout=max(
                            float(os.getenv("COS_CONNECT_TIMEOUT_SECONDS", "10")),
                            0.1,
                        ),
                        read_timeout=max(
                            float(os.getenv("COS_READ_TIMEOUT_SECONDS", "30")),
                            0.1,
                        ),
                        retries={
                            "total_max_attempts": max(
                                int(os.getenv("COS_MAX_ATTEMPTS", "2")),
                                1,
                            ),
                            "mode": "standard",
                        },
                    ),
                )
                self._initialized = True
                logger.info(f"COS客户端初始化成功: {self.endpoint}")
                return True
            except Exception as e:
                logger.error(f"COS客户端初始化失败: {e}")
                return False
    
    def file_exists(self, file_key: str, deadline: float | None = None) -> bool:
        if deadline is not None and time.monotonic() >= deadline:
            return False
        if not self._initialize():
            return False
        
        try:
            self.client.head_object(Bucket=self.bucket, Key=file_key)
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return False
            logger.error(f"检查文件存在性失败: {e}")
            return False
        except Exception as e:
            logger.error(f"检查文件存在性异常: {e}")
            return False
    
    def upload_file(
        self,
        file_content: bytes,
        file_hash: str,
        content_type: Optional[str] = None,
        deadline: float | None = None,
    ) -> Optional[str]:
        if deadline is not None and time.monotonic() >= deadline:
            return None
        if not self._initialize():
            return None
        
        extension = self._guess_extension(content_type, file_content)
        file_key = f"content_resource/{file_hash}{extension}"
        
        if self.file_exists(file_key, deadline=deadline):
            logger.debug(f"文件已存在，跳过上传: {file_key}")
            return self.get_file_url(file_key)

        if deadline is not None and time.monotonic() >= deadline:
            return None
        
        try:
            extra_args = {}
            if content_type:
                extra_args['ContentType'] = content_type
            
            self.client.put_object(
                Bucket=self.bucket,
                Key=file_key,
                Body=file_content,
                **extra_args
            )
            
            file_url = self.get_file_url(file_key)
            logger.info(f"文件上传成功: {file_key}")
            return file_url
            
        except NoCredentialsError:
            logger.error("COS凭证无效")
            return None
        except ClientError as e:
            logger.error(f"文件上传失败: {e}")
            return None
        except Exception as e:
            logger.error(f"文件上传异常: {e}")
            return None
    
    def get_file_url(self, file_key: str) -> str:
        if self.base_url:
            return f"{self.base_url.rstrip('/')}/{file_key}"
        else:
            endpoint = self.endpoint.rstrip('/')
            return f"{endpoint}/{self.bucket}/{file_key}"
    
    def _guess_extension(self, content_type: Optional[str], file_content: bytes) -> str:
        if content_type:
            content_type_lower = content_type.lower()
            if 'jpeg' in content_type_lower or 'jpg' in content_type_lower:
                return '.jpg'
            elif 'png' in content_type_lower:
                return '.png'
            elif 'gif' in content_type_lower:
                return '.gif'
            elif 'webp' in content_type_lower:
                return '.webp'
            elif 'svg' in content_type_lower:
                return '.svg'
            elif 'mp4' in content_type_lower:
                return '.mp4'
            elif 'webm' in content_type_lower:
                return '.webm'
            elif 'ogg' in content_type_lower:
                return '.ogg'
            elif 'mp3' in content_type_lower:
                return '.mp3'
            elif 'wav' in content_type_lower:
                return '.wav'
        
        if len(file_content) >= 4:
            header = file_content[:4]
            if header[:2] == b'\xff\xd8':
                return '.jpg'
            elif header == b'\x89PNG':
                return '.png'
            elif header[:3] == b'GIF':
                return '.gif'
            elif header[:4] == b'RIFF' and len(file_content) >= 12 and file_content[8:12] == b'WEBP':
                return '.webp'
        
        return ''
    
    def is_configured(self) -> bool:
        return all([self.endpoint, self.access_key, self.secret_key, self.bucket])
