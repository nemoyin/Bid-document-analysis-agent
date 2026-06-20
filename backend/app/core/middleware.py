"""
中间件配置模块
配置 CORS、请求追踪、访问日志等中间件。
"""

from __future__ import annotations

import time
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware


class RequestTracingMiddleware(BaseHTTPMiddleware):
    """请求追踪中间件

    为每个请求分配唯一追踪ID，记录请求处理时间。
    """

    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        request.state.start_time = time.time()

        # 记录请求开始
        logger.info(
            f"[{request_id}] {request.method} {request.url.path} - 请求开始"
        )

        try:
            response = await call_next(request)
            elapsed = time.time() - request.state.start_time

            # 记录请求完成
            logger.info(
                f"[{request_id}] {request.method} {request.url.path} - "
                f"完成，状态码: {response.status_code}，耗时: {elapsed:.3f}s"
            )

            # 添加追踪ID到响应头
            response.headers["X-Request-ID"] = request_id
            return response
        except Exception as exc:
            elapsed = time.time() - request.state.start_time
            logger.error(
                f"[{request_id}] {request.method} {request.url.path} - "
                f"异常: {exc!s}，耗时: {elapsed:.3f}s"
            )
            raise


def setup_middleware(app: FastAPI) -> None:
    """配置应用中间件。

    Args:
        app: FastAPI应用实例
    """
    from app.core.config import settings

    # CORS中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
        allow_methods=settings.CORS_ALLOW_METHODS,
        allow_headers=settings.CORS_ALLOW_HEADERS,
    )

    # 请求追踪中间件
    app.add_middleware(RequestTracingMiddleware)

    logger.debug("中间件配置完成")
