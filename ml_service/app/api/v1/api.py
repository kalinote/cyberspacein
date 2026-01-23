from fastapi import APIRouter
from app.api.v1.endpoints import language, translate, keywords

api_router = APIRouter()
api_router.include_router(language.router)
api_router.include_router(translate.router)
api_router.include_router(keywords.router)