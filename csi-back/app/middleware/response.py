import json
import logging
from typing import Callable
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.schemas.response import ApiResponse

logger = logging.getLogger(__name__)


class ResponseMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = None
        try:
            response = await call_next(request)
            
            exclude_paths = ["/openapi.json", "/docs", "/redoc"]
            if any(request.url.path == path for path in exclude_paths):
                return response
            
            if response.status_code == 200 and "application/json" in response.headers.get("content-type", ""):
                response_body = b""
                async for chunk in response.body_iterator:
                    response_body += chunk
                
                try:
                    original_data = json.loads(response_body.decode())
                    
                    response_headers = dict(response.headers)
                    response_headers.pop("content-length", None)
                    
                    if not isinstance(original_data, dict) or "code" not in original_data:
                        wrapped_response = ApiResponse.success(data=original_data)
                        return JSONResponse(
                            content=wrapped_response.model_dump(),
                            status_code=200,
                            headers=response_headers
                        )
                    else:
                        return JSONResponse(
                            content=original_data,
                            status_code=200,
                            headers=response_headers
                        )
                except json.JSONDecodeError:
                    return Response(
                        content=response_body,
                        status_code=response.status_code,
                        headers=dict(response.headers),
                        media_type=response.media_type
                    )
            
            return response
            
        except Exception as e:
            logger.exception(f"响应中间件处理异常: {str(e)}")
            if response is not None:
                return response
            return JSONResponse(
                content=ApiResponse.error(code=500, message=f"服务器内部错误: {str(e)}").model_dump(),
                status_code=500
            )
