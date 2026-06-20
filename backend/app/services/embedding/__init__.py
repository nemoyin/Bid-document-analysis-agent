"""
Embedding 向量化服务模块
提供 Gitee AI Embedding API 封装和向量存储服务。
"""

from app.services.embedding.gitee_client import GiteeEmbeddingClient
from app.services.embedding.embedding_service import EmbeddingService

__all__ = [
    "GiteeEmbeddingClient",
    "EmbeddingService",
]
