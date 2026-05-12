from fastapi import APIRouter

from app.api.v1.endpoints.agent.agents import router as agents_router
from app.api.v1.endpoints.agent.configs_models import router as configs_models_router
from app.api.v1.endpoints.agent.configs_prompts import router as configs_prompts_router
from app.api.v1.endpoints.agent.configs_templates import router as configs_templates_router
from app.api.v1.endpoints.agent.configs_tools import router as configs_tools_router
from app.api.v1.endpoints.agent.runtime import router as runtime_router
from app.api.v1.endpoints.agent.workspaces import router as workspaces_router

router = APIRouter(
    prefix="/agent",
    tags=["分析引擎管理"],
)

router.include_router(configs_models_router)
router.include_router(configs_prompts_router)
router.include_router(configs_templates_router)
router.include_router(configs_tools_router)
router.include_router(workspaces_router)
router.include_router(agents_router)
router.include_router(runtime_router)

