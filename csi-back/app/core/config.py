from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
from app.utils.network import get_local_ip

class Settings(BaseSettings):
    API_V1_STR: str
    APP_NAME: str
    DEBUG: bool
    
    SERVER_HOST: Optional[str] = None
    SERVER_PORT: Optional[int] = None
    
    MARIADB_URL: str
    
    MONGODB_URL: str
    MONGODB_USERNAME: str
    MONGODB_PASSWORD: str
    MONGODB_DB_NAME: str
    
    REDIS_URL: str
    REDIS_PASSWORD: str
    ACTION_CACHE_TTL: int = 600
    
    ELASTICSEARCH_URL: str
    ELASTICSEARCH_USER: str
    ELASTICSEARCH_PASSWORD: str

    RABBITMQ_HOST: str
    RABBITMQ_PORT: int
    RABBITMQ_USERNAME: str
    RABBITMQ_PASSWORD: str
    RABBITMQ_VHOST: str = "/"

    CRAWLAB_BASE_URL: str
    CRAWLAB_TOKEN: str

    COS_ENDPOINT: str
    COS_ACCESS_KEY_ID: str
    COS_SECRET_ACCESS_KEY: str
    COS_BUCKET_NAME: str
    COS_REGION: str

    USE_PROXY: bool = False
    OUT_SERVICE_PROXY: Optional[str] = None
    MAX_LOGO_SIZE: int = 5 * 1024 * 1024

    EMBEDDING_MODEL: str = "Qwen/Qwen3-Embedding-8B"
    EMBEDDING_MODEL_URL: str = "https://api.siliconflow.cn/v1/embeddings"
    EMBEDDING_MODEL_API_KEY: str = ""

    HYBRID_TOTAL_CAP: int = 10000
    RRF_K: int = 60
    VECTOR_NUM_CANDIDATES_MULTIPLIER: int = 10

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore"
    )
    
    @property
    def api_base_url(self) -> str:
        """
        获取完整的 API base URL (http://host:port/api/v1)
        如果未配置 SERVER_HOST 和 SERVER_PORT，则自动获取本机 IP 并使用默认端口 8080
        """
        host = self.SERVER_HOST or get_local_ip()
        port = self.SERVER_PORT or 8080
        return f"http://{host}:{port}{self.API_V1_STR}"

settings = Settings()

