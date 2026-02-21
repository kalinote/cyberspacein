from fastapi import APIRouter

from app.api.v1.endpoints import (
    action,
    agent,
    annotation,
    article,
    embedding,
    forum,
    highlight,
    html_analyze,
    platform,
    search,
    timeline
)

api_router = APIRouter()

api_router.include_router(action.router)
api_router.include_router(annotation.router)
api_router.include_router(article.router)
api_router.include_router(forum.router)
api_router.include_router(highlight.router)
api_router.include_router(platform.router)
api_router.include_router(search.router)
api_router.include_router(html_analyze.router)
api_router.include_router(agent.router)
api_router.include_router(embedding.router)
api_router.include_router(timeline.router)