"""
ChromaDB 客户端管理
提供 ChromaDB 持久化客户端的单例管理和生命周期控制。
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import chromadb
from chromadb import Collection
from chromadb.config import Settings as ChromaSettings
from loguru import logger

from app.core.config import settings


class ChromaManager:
    """ChromaDB 管理器（单例模式）。

    管理 ChromaDB 持久化客户端的初始化、关闭和集合操作。
    ChromaDB 嵌入 Python 进程，无需额外部署。
    """

    _instance: Optional["ChromaManager"] = None
    _client: Optional[chromadb.PersistentClient] = None
    _text_collection: Optional[Collection] = None

    def __new__(cls) -> "ChromaManager":
        """单例模式，确保全局只有一个 ChromaManager 实例。"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @property
    def client(self) -> chromadb.PersistentClient:
        """获取 ChromaDB 持久化客户端。

        Returns:
            chromadb.PersistentClient: ChromaDB 客户端

        Raises:
            RuntimeError: 客户端未初始化
        """
        if self._client is None:
            raise RuntimeError("ChromaDB 客户端未初始化，请先调用 initialize()")
        return self._client

    @property
    def text_collection(self) -> Collection:
        """获取文本 Embedding 集合。

        Returns:
            Collection: ChromaDB 集合

        Raises:
            RuntimeError: 集合未初始化
        """
        if self._text_collection is None:
            raise RuntimeError("ChromaDB 文本集合未初始化，请先调用 initialize()")
        return self._text_collection

    def initialize(self) -> None:
        """初始化 ChromaDB 客户端和集合。

        创建持久化客户端（数据存储在配置路径下），
        并获取或创建文本 Embedding 集合。
        """
        if self._client is not None:
            logger.info("ChromaDB 客户端已经初始化，跳过")
            return

        # 确保数据目录存在
        chroma_path = Path(settings.CHROMA_DB_PATH)
        chroma_path.mkdir(parents=True, exist_ok=True)

        logger.info(f"初始化 ChromaDB，数据路径: {chroma_path.absolute()}")

        # 创建持久化客户端
        self._client = chromadb.PersistentClient(
            path=str(chroma_path.absolute()),
            settings=ChromaSettings(
                anonymized_telemetry=False,
                allow_reset=False,
            ),
        )

        # 获取或创建文本 Embedding 集合
        self._text_collection = self._client.get_or_create_collection(
            name=settings.CHROMA_COLLECTION_TEXT,
            metadata={
                "hnsw:space": settings.CHROMA_DISTANCE_FN,
                "description": "投标文件文本段落 Embedding 集合",
            },
        )

        # 获取集合中的文档数量
        count = self._text_collection.count()
        logger.info(
            f"ChromaDB 初始化完成，集合 '{settings.CHROMA_COLLECTION_TEXT}' "
            f"现有 {count} 条记录"
        )

    def get_collection_info(self) -> dict:
        """获取集合信息。

        Returns:
            dict: 集合名称和记录数
        """
        return {
            "name": self._text_collection.name if self._text_collection else None,
            "count": self._text_collection.count() if self._text_collection else 0,
            "metadata": self._text_collection.metadata if self._text_collection else {},
        }

    def reset(self) -> None:
        """重置 ChromaDB（清空所有数据）。

        警告：此操作不可逆，会删除所有向量数据。
        """
        if self._client:
            collections = self._client.list_collections()
            for collection in collections:
                self._client.delete_collection(collection.name)
            logger.warning("ChromaDB 所有集合已删除，数据已清空")
            self._text_collection = None

    def close(self) -> None:
        """关闭 ChromaDB 客户端。

        清理资源，持久化数据。
        """
        if self._client:
            # ChromaDB PersistentClient 会自动持久化
            logger.info("ChromaDB 客户端已关闭")
            self._client = None
            self._text_collection = None
            ChromaManager._instance = None
