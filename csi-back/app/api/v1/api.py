from fastapi import APIRouter
from app.api.v1.endpoints import action, article, forum, highlight, platform, search, html_analyze

api_router = APIRouter()
api_router.include_router(action.router)
api_router.include_router(article.router)
api_router.include_router(forum.router)
api_router.include_router(highlight.router)
api_router.include_router(platform.router)
api_router.include_router(search.router)
api_router.include_router(html_analyze.router)