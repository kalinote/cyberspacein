import logging
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from app.core.config import settings
from app.core.exceptions import ApiException
from app.schemas.response import ApiResponseSchema
from app.middleware.response import ResponseMiddleware
from app.service.ml.language import language_service

logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO if not settings.DEBUG else logging.DEBUG)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await language_service.initialize()
    
    yield
    
    await language_service.cleanup()


app = FastAPI(
    title=settings.APP_NAME,
    openapi_url="/openapi.json",
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
            code=422,
            message="请求参数验证失败",
            data={"errors": errors}
        ).model_dump()
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logging.exception(f"未处理的异常: {str(exc)}")
    return JSONResponse(
        status_code=200,
        content=ApiResponseSchema.error(
            code=500,
            message="服务器内部错误" if not settings.DEBUG else str(exc),
            data=None
        ).model_dump()
    )


from app.api.v1 import api as api_v1
app.include_router(api_v1.api_router, prefix=settings.API_V1_STR)
