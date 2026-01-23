from fastapi import APIRouter
from app.api.v1.endpoints import language, translate

api_router = APIRouter()
api_router.include_router(language.router)
api_router.include_router(translate.router)