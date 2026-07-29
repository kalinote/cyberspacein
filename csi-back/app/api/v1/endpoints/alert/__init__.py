from fastapi import APIRouter

from app.api.v1.endpoints.alert.routes import router as alert_router

router = APIRouter(prefix="/alerts")
router.include_router(alert_router)
