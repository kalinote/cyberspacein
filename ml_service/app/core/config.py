from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
from app.utils.network import get_local_ip


class Settings(BaseSettings):
    API_V1_STR: str = "/api/v1"
    APP_NAME: str = "ML Service"
    DEBUG: bool = False
    
    SERVER_HOST: Optional[str] = None
    SERVER_PORT: Optional[int] = None
    
    LINGUA_LOW_ACCURACY_MODE: bool = False
    LINGUA_PRELOAD_MODELS: bool = True
    LINGUA_SUPPORTED_LANGUAGES: Optional[str] = None
    
    TRANSLATE_MODEL_PATH: Optional[str] = None
    TRANSLATE_N_THREADS: Optional[int] = None
    TRANSLATE_N_CTX: Optional[int] = None
    TRANSLATE_MAX_TOKENS: Optional[int] = None
    TRANSLATE_TEMPERATURE: Optional[float] = None
    TRANSLATE_TOP_P: Optional[float] = None
    TRANSLATE_THREAD_POOL_SIZE: Optional[int] = None
    
    GENERIC_MODEL_PATH: Optional[str] = None
    GENERIC_N_THREADS: Optional[int] = None
    GENERIC_N_CTX: Optional[int] = None
    GENERIC_MAX_TOKENS: Optional[int] = None
    GENERIC_TEMPERATURE: Optional[float] = None
    GENERIC_TOP_P: Optional[float] = None
    GENERIC_THREAD_POOL_SIZE: Optional[int] = None
    
    EMBEDDING_MODEL_PATH: Optional[str] = None
    EMBEDDING_DIM: int = 2560
    
    REDIS_URL: Optional[str] = None
    REDIS_PASSWORD: Optional[str] = None
    TRANSLATE_RESULT_TTL: int = 1800
    KEYWORDS_RESULT_TTL: int = 1800
    ENTITIES_RESULT_TTL: int = 1800

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore"
    )
    
    @property
    def api_base_url(self) -> str:
        host = self.SERVER_HOST or get_local_ip()
        port = self.SERVER_PORT or 8080
        return f"http://{host}:{port}{self.API_V1_STR}"

settings = Settings()
