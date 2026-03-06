from fastapi import APIRouter

from app.api.v1.endpoints.action.instance import router as instance_router
from app.api.v1.endpoints.action.blueprint import router as blueprint_router
from app.api.v1.endpoints.action.resource import router as resource_router
from app.api.v1.endpoints.action.sdk import router as sdk_router
from app.api.v1.endpoints.action.configs import router as configs_router
from app.api.v1.endpoints.action.task_configs import router as task_configs_router

router = APIRouter(prefix="/action", tags=["行动管理"])
router.include_router(instance_router)
router.include_router(blueprint_router)
router.include_router(resource_router)
router.include_router(sdk_router)
router.include_router(configs_router)
router.include_router(task_configs_router)
