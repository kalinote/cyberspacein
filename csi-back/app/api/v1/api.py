from fastapi import APIRouter, Depends
from app.core.route_permissions import authorize_registered_route

from app.api.v1.endpoints import (
    action,
    auth,
    agent,
    annotation,
    article,
    embedding,
    forum,
    highlight,
    overview,
    platform,
    search,
    system,
    system_config,
    timeline,
    wiki,
)

api_router = APIRouter(dependencies=[Depends(authorize_registered_route)])

api_router.include_router(action.router)
api_router.include_router(annotation.router)
api_router.include_router(article.router)
api_router.include_router(forum.router)
api_router.include_router(highlight.router)
api_router.include_router(platform.router)
api_router.include_router(search.router)
api_router.include_router(overview.router)
api_router.include_router(agent.router)
api_router.include_router(embedding.router)
api_router.include_router(timeline.router)
api_router.include_router(auth.router)
api_router.include_router(system.router)
api_router.include_router(system_config.router)
api_router.include_router(wiki.router)
