from fastapi import APIRouter

from app.api.v1.endpoints.action.instance import router as instance_router
from app.api.v1.endpoints.action.blueprint import router as blueprint_router
from app.api.v1.endpoints.action.resource import router as resource_router
from app.api.v1.endpoints.action.sdk import router as sdk_router
from app.api.v1.endpoints.action.configs import router as configs_router
from app.api.v1.endpoints.action.components_task import router as components_task_router
from app.api.v1.endpoints.action.accounts import router as accounts_router
from app.api.v1.endpoints.action.sandbox import router as sandbox_router

router = APIRouter(prefix="/action")
router.include_router(instance_router)
router.include_router(blueprint_router)
router.include_router(resource_router)
router.include_router(sdk_router)
router.include_router(configs_router)
router.include_router(components_task_router)
router.include_router(accounts_router)
router.include_router(sandbox_router)