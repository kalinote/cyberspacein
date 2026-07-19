from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from loguru import logger

from app.core.config import settings
from app.core.logging_config import setup_logging

setup_logging()

from app.core.exceptions import ApiException
from app.schemas.response import ApiResponseSchema
from app.middleware.response import ResponseMiddleware
import app.utils.status_codes as status_codes
from app.db import (
    init_mariadb, close_mariadb,
    init_mongodb, close_mongodb,
    init_redis, close_redis,
    init_elasticsearch, close_elasticsearch,
    init_rabbitmq, close_rabbitmq
)
from app.utils.cos import init_cos, close_cos
from app.utils.embedding import init_embedding_client, close_embedding_client
from app.service.auth import ensure_default_admin
from app.core.system_config import system_config_manager

logger = logger.bind(name=__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.validate_auth_security()
    await init_mariadb()
    await init_mongodb()
    await init_redis()
    await init_elasticsearch()
    await init_rabbitmq()
    await init_cos()
    await init_embedding_client()
    from app.core.permissions import sync_standard_permissions
    await sync_standard_permissions()
    await ensure_default_admin()
    from app.service.nanobot.bootstrap import ensure_builtin_agent_prompts
    await ensure_builtin_agent_prompts()

    system_config_manager.commit_bootstrap()
    from app.service.system_config_history import SystemConfigHistoryService
    await SystemConfigHistoryService.flush_outbox(system_config_manager)
    await SystemConfigHistoryService.ensure_baseline(system_config_manager)

    yield

    system_config_manager.mark_not_ready()

    from app.service.analyst.service import AnalystService
    await AnalystService.shutdown_running_agents()

    await close_embedding_client()
    await close_cos()
    await close_rabbitmq()
    await close_mariadb()
    await close_mongodb()
    await close_redis()
    await close_elasticsearch()


app = FastAPI(
    title=settings.APP_NAME,
    openapi_url="/openapi.json",
    swagger_ui_parameters={"persistAuthorization": True},
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(ResponseMiddleware)


@app.get("/health/live", include_in_schema=False)
async def health_live():
    return {"status": "live", "boot_id": system_config_manager.boot_id}


@app.get("/health/ready", include_in_schema=False)
async def health_ready():
    if not system_config_manager.ready:
        return JSONResponse(status_code=503, content={"status": "not_ready"})
    return {
        "status": "ready",
        "boot_id": system_config_manager.boot_id,
        "version": system_config_manager.state()["version"],
    }


@app.exception_handler(ApiException)
async def api_exception_handler(request: Request, exc: ApiException):
    return JSONResponse(
        status_code=200,
        content=ApiResponseSchema.error(
            code=exc.code,
            message=exc.message,
            data=exc.data
        ).model_dump()
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = []
    for error in exc.errors():
        field = " -> ".join(str(loc) for loc in error["loc"])
        errors.append(f"{field}: {error['msg']}")
    
    return JSONResponse(
        status_code=200,
        content=ApiResponseSchema.error(
            code=status_codes.VALIDATION_ERROR,
            message="请求参数验证失败",
            data={"errors": errors}
        ).model_dump()
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    try:
        normalized_code = status_codes.build_status_code(
            status_codes.StatusCodeSource.HTTP_STANDARD,
            exc.status_code,
        )
    except ValueError:
        normalized_code = status_codes.INTERNAL_ERROR
    return JSONResponse(
        status_code=200,
        content=ApiResponseSchema.error(
            code=normalized_code,
            message=str(exc.detail) if exc.detail else "请求处理失败",
            data=None
        ).model_dump()
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.exception("未处理的异常")
    return JSONResponse(
        status_code=200,
        content=ApiResponseSchema.error(
            code=status_codes.INTERNAL_ERROR,
            message="服务器内部错误",
            data=None
        ).model_dump()
    )


from app.api.v1 import api as api_v1
app.include_router(api_v1.api_router, prefix=settings.API_V1_STR)

from app.core.route_permissions import validate_fastapi_routes
validate_fastapi_routes(app.routes)
