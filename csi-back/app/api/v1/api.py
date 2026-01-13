from fastapi import APIRouter
from app.api.v1.endpoints import action, article

api_router = APIRouter()
api_router.include_router(action.router)
api_router.include_router(article.router)
