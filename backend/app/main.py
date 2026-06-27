"""
FastAPI 应用入口
投标标书智能分析监督系统 (BASS-MVP) 后端服务。
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from pathlib import Path as FilePath

from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from loguru import logger

from app.core.config import settings
from app.core.logging import setup_logging
from app.core.middleware import setup_middleware
from app.services.chroma_manager import ChromaManager
@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理。

    - 启动时: 初始化日志、中间件、数据库连接、ChromaDB 等
    - 关闭时: 清理资源
    """
    # ---- 启动 ----
    logger.info(f"{settings.APP_NAME} v{settings.APP_VERSION} 启动中...")
    logger.info(f"Debug模式: {settings.DEBUG}")
    logger.info(f"Gitee AI API: {settings.GITEE_AI_BASE_URL}")
    logger.info(f"ChromaDB路径: {settings.CHROMA_DB_PATH}")
    logger.info(f"上传目录: {settings.UPLOAD_DIR}")

    # 初始化 ChromaDB
    chroma_manager = ChromaManager()
    try:
        chroma_manager.initialize()
        app.state.chroma_manager = chroma_manager
        logger.info("ChromaDB 初始化完成")
    except Exception as exc:
        logger.error(f"ChromaDB 初始化失败: {exc!s}")
        app.state.chroma_manager = None

    # 尝试初始化数据库表（首次运行时创建）
    try:
        from app.db.init_db import init_database
        await init_database()
    except Exception as exc:
        logger.warning(f"数据库初始化跳过（可能在 Docker 中运行）: {exc!s}")

    yield

    # ---- 关闭 ----
    logger.info(f"{settings.APP_NAME} 服务正在关闭...")

    # 关闭 ChromaDB
    if hasattr(app.state, "chroma_manager") and app.state.chroma_manager:
        try:
            app.state.chroma_manager.close()
            logger.info("ChromaDB 已关闭")
        except Exception as exc:
            logger.error(f"ChromaDB 关闭失败: {exc!s}")
def create_app() -> FastAPI:
    """创建并配置 FastAPI 应用实例。

    Returns:
        FastAPI: 配置完成的 FastAPI 应用
    """
    # 初始化日志
    setup_logging()

    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="投标标书智能分析监督系统 API",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )

    # 配置中间件
    setup_middleware(app)

    # ---- 注册路由 ----
    @app.get("/api/v1/health", tags=["系统"])
    async def health_check():
        """健康检查接口。"""
        chroma_ok = hasattr(app.state, "chroma_manager") and app.state.chroma_manager is not None
        return {
            "code": 0,
            "message": "success",
            "data": {
                "status": "healthy",
                "version": settings.APP_VERSION,
                "debug": settings.DEBUG,
                "chroma_initialized": chroma_ok,
            },
        }

    # 注册 v1 API 路由
    from app.api.v1 import router as api_v1_router
    app.include_router(api_v1_router)

    # ---- 图片预览服务 ----
    @app.get("/api/v1/images/preview", tags=["系统"])
    async def serve_image(path: str = Query(..., description="图片文件路径")):
        """提供图片预览服务。

        根据文件路径提供图片文件，仅允许访问上传目录和项目数据目录下的图片。
        用于前端图片相似度对比预览。
        """
        # 安全检查：仅允许访问上传目录下的文件
        file_path = FilePath(path)
        allowed_dirs = [
            FilePath(settings.UPLOAD_DIR).resolve(),
            FilePath(settings.ROOT_DIR).resolve() / "data",
        ]

        resolved = file_path.resolve()
        allowed = any(
            str(resolved).startswith(str(allowed_dir.resolve()))
            for allowed_dir in allowed_dirs
        )
        if not allowed:
            raise HTTPException(status_code=403, detail="不允许访问该路径")

        if not file_path.exists():
            raise HTTPException(status_code=404, detail="图片文件不存在")

        if not file_path.is_file():
            raise HTTPException(status_code=400, detail="路径不是文件")

        # 只允许图片类型
        ext = file_path.suffix.lower()
        if ext not in ('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.tiff', '.tif'):
            raise HTTPException(status_code=400, detail=f"不支持的文件类型: {ext}")

        return FileResponse(str(file_path), media_type=f"image/{ext.lstrip('.')}")

    # ---- 前端静态文件服务（Docker 模式） ----
    frontend_dist = os.environ.get("FRONTEND_DIST_DIR")
    if frontend_dist and os.path.isdir(frontend_dist):
        # 挂载静态资源
        app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dist, "assets")), name="assets")
        logger.info(f"前端静态文件已挂载: {frontend_dist}")

        # SPA 兜底路由
        @app.route("/{path:path}", methods=["GET"])
        async def serve_spa(path: str):
            # API 路由不需要处理
            if path.startswith("api/"):
                from fastapi.responses import JSONResponse
                return JSONResponse({"code": 404, "message": "not found"}, status_code=404)
            index_path = os.path.join(frontend_dist, "index.html")
            if os.path.isfile(index_path):
                return FileResponse(index_path, media_type="text/html")
            return JSONResponse({"code": 404, "message": "not found"}, status_code=404)

    logger.info(f"应用创建完成，监听 {settings.HOST}:{settings.PORT}")
    return app
app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )

