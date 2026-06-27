"""
核心配置模块
通过环境变量读取应用配置，敏感信息不硬编码在代码中。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import ClassVar

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用核心配置，从环境变量读取。"""

    # ---- 应用基本信息 ----
    APP_NAME: str = "BASS-MVP"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    # ---- 服务端口 ----
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # ---- CORS ----
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:5273", "http://localhost:3000", "http://localhost:3007"]
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: list[str] = ["*"]
    CORS_ALLOW_HEADERS: list[str] = ["*"]

    # ---- Gitee AI Embedding API ----
    GITEE_AI_API_KEY: str = ""
    GITEE_AI_BASE_URL: str = "https://ai.gitee.com/v1"
    GITEE_AI_MODEL: str = "Qwen3-Embedding-8B"
    GITEE_AI_TIMEOUT: int = 60
    GITEE_AI_MAX_RETRIES: int = 3

    # ---- PostgreSQL 数据库 ----
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "bass_mvp"
    POSTGRES_USER: str = "bass_user"
    POSTGRES_PASSWORD: str = "bass_password"
    DATABASE_URL: str | None = None

    @property
    def db_url(self) -> str:
        """获取数据库连接URL。"""
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # ---- Redis ----
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: str = ""
    REDIS_URL: str | None = None

    @property
    def redis_url(self) -> str:
        """获取Redis连接URL。"""
        if self.REDIS_URL:
            return self.REDIS_URL
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    # ---- Celery ----
    CELERY_BROKER_URL: str | None = None
    CELERY_RESULT_BACKEND: str | None = None

    @property
    def celery_broker_url(self) -> str:
        """获取Celery Broker URL。"""
        if self.CELERY_BROKER_URL:
            return self.CELERY_BROKER_URL
        return self.redis_url

    @property
    def celery_result_backend(self) -> str:
        """获取Celery Result Backend URL。"""
        if self.CELERY_RESULT_BACKEND:
            return self.CELERY_RESULT_BACKEND
        return self.redis_url

    # ---- ChromaDB ----
    CHROMA_DB_PATH: str = "./data/chromadb"
    CHROMA_COLLECTION_TEXT: str = "text_embeddings"
    CHROMA_DISTANCE_FN: str = "cosine"

    # ---- 文档分块 ----
    CHUNK_SIZE: int = 512
    """文档分块的 token 大小。"""
    CHUNK_OVERLAP: int = 128
    """文档分块的滑动窗口重叠 token 数。"""

    # ---- 文件上传 ----
    UPLOAD_DIR: str = "./data/uploads"
    MAX_FILE_SIZE: int = 100 * 1024 * 1024  # 100MB
    ALLOWED_EXTENSIONS: list[str] = [".pdf", ".docx", ".doc"]

    # ---- 报告 ----
    REPORT_DIR: str = "./data/reports"
    REPORT_PAGE_SIZE: str = "A4"

    # ---- 日志 ----
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "./data/logs/bass.log"
    LOG_FORMAT: str = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    )

    # ---- Sentry ----
    SENTRY_DSN: str = ""
    SENTRY_ENVIRONMENT: str = "development"

    # ---- 风险评分权重（6维度，对应 PRD REQ-016）----
    TEXT_SIMILARITY_WEIGHT: float = 0.30
    """文本相似度权重（满分30分）。"""
    STRUCTURE_SIMILARITY_WEIGHT: float = 0.15
    """目录结构相似度权重（满分15分）。"""
    IMAGE_SIMILARITY_WEIGHT: float = 0.15
    """图片相似度权重（满分15分）。"""
    TABLE_SIMILARITY_WEIGHT: float = 0.10
    """表格相似度权重（满分10分）。"""
    ERROR_CONSISTENCY_WEIGHT: float = 0.20
    """错别字一致性权重（满分20分）。"""
    METADATA_CONSISTENCY_WEIGHT: float = 0.10
    """元数据一致性权重（满分10分）。"""

    # ---- 相似度阈值 ----
    SIMILARITY_THRESHOLD: float = 0.8
    """文本语义相似度阈值（>此值标记为高相似）。"""
    SIMILARITY_HIGH_THRESHOLD: float = 80.0
    """高相似度阈值（>此值标记为异常）。"""
    SIMILARITY_MEDIUM_THRESHOLD: float = 60.0
    """中相似度阈值。"""

    # ---- 图片相似度 ----
    IMAGE_SIMILARITY_THRESHOLD: float = 0.85
    """图片三哈希融合相似度阈值。"""

    # ---- 风险等级阈值（PRD REQ-017: 0-30/31-60/61-80/81-100）----
    RISK_LEVEL_LOW: float = 0.30
    """低风险上限（0-30分）。"""
    RISK_LEVEL_MEDIUM: float = 0.60
    """中风险上限（31-60分）。"""
    RISK_LEVEL_HIGH: float = 0.85
    """高风险上限（61-85分，以上为 CRITICAL）。"""

    # ---- 报告生成 ----
    REPORT_DIR: str = "./data/reports"
    """报告输出目录。"""
    REPORT_PAGE_SIZE: str = "A4"
    """报告页面尺寸。"""

    # ---- 错误检测 ----
    PYCORRECTOR_ENABLED: bool = True
    """是否启用 pycorrector 进行错别字检测。"""

    # ---- 一键异步数据库 URL（用于 Alembic） ----
    DATABASE_URL_SYNC: str | None = None

    @property
    def db_url_sync(self) -> str:
        """获取同步数据库连接URL（用于 Alembic）。"""
        if self.DATABASE_URL_SYNC:
            return self.DATABASE_URL_SYNC
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # ---- 项目根目录 ----
    ROOT_DIR: ClassVar[Path] = Path(__file__).resolve().parent.parent.parent

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
    }


# 全局单例
settings = Settings()
