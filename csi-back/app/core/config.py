from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, Any
from app.utils.network import get_local_ip

class Settings(BaseSettings):
    API_V1_STR: str
    APP_NAME: str
    DEBUG: bool
    ENVIRONMENT: str = "development"
    
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

    NANOBOT_AGENT_MAX_PARALLEL_SESSIONS: int = 0
    NANOBOT_SHUTDOWN_TIMEOUT_S: float = 30.0

    EMBEDDING_MODEL: str = "Qwen/Qwen3-Embedding-8B"
    EMBEDDING_MODEL_URL: str = "https://api.siliconflow.cn/v1/embeddings"
    EMBEDDING_MODEL_API_KEY: str = ""

    DOCKER_HOST: Optional[str] = None
    AIO_SANDBOX_IMAGE: str = ""
    WINDOWS_SANDBOX_IMAGE: str = ""
    WINDOWS_TEMPLATE_VOLUME: str = "win_template_vol"
    SANDBOX_PORT_RANGE: str = "16700-16799"

    HYBRID_TOTAL_CAP: int = 10000
    RRF_K: int = 60
    VECTOR_NUM_CANDIDATES_MULTIPLIER: int = 100
    VECTOR_NUM_CANDIDATES_MIN: int = 2000
    VECTOR_NUM_CANDIDATES_MAX: int = 10000

    AUTH_SECRET_KEY: str = "please-change-auth-secret-key"
    AUTH_ISSUER: str = "csi-back"
    AUTH_AUDIENCE: str = "csi-user-api"
    COMPONENT_AUTH_AUDIENCE: str = "csi-action-sdk"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    COMPONENT_TOKEN_EXPIRE_MINUTES: int = 30
    COMPONENT_BOOTSTRAP_EXPIRE_SECONDS: int = 300
    AUTH_REDIS_NAMESPACE: str = "csi:auth"
    LOGIN_FAILURE_THRESHOLD: int = 5
    LOGIN_FAILURE_WINDOW_SECONDS: int = 900
    LOGIN_LOCK_SECONDS: int = 900
    LOGIN_RATE_LIMIT_ACCOUNT: int = 10
    LOGIN_RATE_LIMIT_SOURCE: int = 30
    LOGIN_RATE_LIMIT_WINDOW_SECONDS: int = 60
    TEMPORARY_ACCOUNT_MAX_DAYS: int = 90
    INIT_SYSTEM_USERNAME: str = "system"
    INIT_SYSTEM_PASSWORD: str = "system123456"
    INIT_SYSTEM_DISPLAY_NAME: str = "系统"
    INIT_SYSTEM_EMAIL: str = "system@example.com"
    INIT_SYSTEM_GROUP_NAME: str = "system"

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

    @property
    def normalized_environment(self) -> str:
        return self.ENVIRONMENT.strip().lower()

    def validate_auth_security(self) -> None:
        """Validate authentication settings before the application starts."""
        if self.normalized_environment not in {"development", "test", "production"}:
            raise RuntimeError("ENVIRONMENT 必须是 development、test 或 production")
        if self.ACCESS_TOKEN_EXPIRE_MINUTES <= 0:
            raise RuntimeError("ACCESS_TOKEN_EXPIRE_MINUTES 必须大于 0")
        if self.COMPONENT_TOKEN_EXPIRE_MINUTES <= 0:
            raise RuntimeError("COMPONENT_TOKEN_EXPIRE_MINUTES 必须大于 0")
        if self.COMPONENT_BOOTSTRAP_EXPIRE_SECONDS <= 0:
            raise RuntimeError("COMPONENT_BOOTSTRAP_EXPIRE_SECONDS 必须大于 0")
        if not self.AUTH_REDIS_NAMESPACE.strip() or any(char in self.AUTH_REDIS_NAMESPACE for char in "*?[]"):
            raise RuntimeError("AUTH_REDIS_NAMESPACE 不能为空且不能包含通配符")
        if self.TEMPORARY_ACCOUNT_MAX_DAYS <= 0:
            raise RuntimeError("TEMPORARY_ACCOUNT_MAX_DAYS 必须大于 0")
        positive_fields = {
            "LOGIN_FAILURE_THRESHOLD": self.LOGIN_FAILURE_THRESHOLD,
            "LOGIN_FAILURE_WINDOW_SECONDS": self.LOGIN_FAILURE_WINDOW_SECONDS,
            "LOGIN_LOCK_SECONDS": self.LOGIN_LOCK_SECONDS,
            "LOGIN_RATE_LIMIT_ACCOUNT": self.LOGIN_RATE_LIMIT_ACCOUNT,
            "LOGIN_RATE_LIMIT_SOURCE": self.LOGIN_RATE_LIMIT_SOURCE,
            "LOGIN_RATE_LIMIT_WINDOW_SECONDS": self.LOGIN_RATE_LIMIT_WINDOW_SECONDS,
        }
        invalid = [name for name, value in positive_fields.items() if value <= 0]
        if invalid:
            raise RuntimeError(f"认证防护配置必须大于 0: {', '.join(invalid)}")
        if self.normalized_environment == "production":
            forbidden_secrets = {
                "please-change-auth-secret-key",
                "change-me",
                "secret",
            }
            if len(self.AUTH_SECRET_KEY) < 32 or self.AUTH_SECRET_KEY in forbidden_secrets:
                raise RuntimeError("生产环境 AUTH_SECRET_KEY 必须是至少 32 位的非默认密钥")
            forbidden_passwords = {"system123456", "admin123456", "password", "admin"}
            if len(self.INIT_SYSTEM_PASSWORD) < 12 or self.INIT_SYSTEM_PASSWORD in forbidden_passwords:
                raise RuntimeError("生产环境 INIT_SYSTEM_PASSWORD 不得使用默认值且至少 12 位")

class SettingsProxy:
    """Stable reference used by modules that import ``settings`` once."""

    def __init__(self, current: Settings):
        object.__setattr__(self, "_current", current)

    def snapshot(self) -> Settings:
        return object.__getattribute__(self, "_current")

    def swap(self, current: Settings) -> None:
        object.__setattr__(self, "_current", current)

    def __getattr__(self, name: str) -> Any:
        return getattr(self.snapshot(), name)


from app.core.system_config import system_config_manager

settings = SettingsProxy(system_config_manager.bootstrap(Settings))
system_config_manager.bind_settings(settings)

