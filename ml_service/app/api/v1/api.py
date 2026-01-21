from fastapi import APIRouter
from app.api.v1.endpoints import language

api_router = APIRouter()
api_router.include_router(language.router)
