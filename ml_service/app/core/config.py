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
