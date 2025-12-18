from fastapi import APIRouter
from app.api.v1.endpoints import action

api_router = APIRouter()
api_router.include_router(action.router)
