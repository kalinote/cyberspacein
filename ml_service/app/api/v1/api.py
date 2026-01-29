from fastapi import APIRouter
from app.api.v1.endpoints import language, translate, keywords, entities, embedding, html_analyze

api_router = APIRouter()
api_router.include_router(language.router)
api_router.include_router(translate.router)
api_router.include_router(keywords.router)
api_router.include_router(entities.router)
api_router.include_router(embedding.router)
api_router.include_router(html_analyze.router)