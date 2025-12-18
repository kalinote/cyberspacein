from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    API_V1_STR: str
    APP_NAME: str
    DEBUG: bool
    
    MARIADB_URL: str
    
    MONGODB_URL: str
    MONGODB_USERNAME: str
    MONGODB_PASSWORD: str
    MONGODB_DB_NAME: str
    
    REDIS_URL: str
    REDIS_PASSWORD: str
    
    ELASTICSEARCH_URL: str
    ELASTICSEARCH_USER: str
    ELASTICSEARCH_PASSWORD: str

    CRAWLAB_BASE_URL: str
    CRAWLAB_TOKEN: str

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"

settings = Settings()

