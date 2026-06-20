"""
Embedding 高层封装服务。
整合 ChromaDB 向量存储，提供文档分块、向量化存储和语义搜索功能。
"""

from __future__ import annotations

import uuid
from typing import Any, Optional

from loguru import logger

from app.core.config import settings
from app.services.chroma_manager import ChromaManager
from app.services.document_parser.base import ParseResult
from app.services.embedding.gitee_client import GiteeEmbeddingClient


class EmbeddingService:
    """Embedding 高层服务。

    提供文档分块 → 向量化 → ChromaDB 存储的一站式能力，
    以及语义搜索功能。
    """

    def __init__(
        self,
        embedding_client: Optional[GiteeEmbeddingClient] = None,
        chroma_manager: Optional[ChromaManager] = None,
    ):
        """初始化 Embedding 服务。

        Args:
            embedding_client: Gitee AI Embedding 客户端
            chroma_manager: ChromaDB 管理器
        """
        self.embedding_client = embedding_client or GiteeEmbeddingClient()
        self.chroma_manager = chroma_manager or ChromaManager()

        # 确保 ChromaDB 已初始化
        try:
            _ = self.chroma_manager.text_collection
        except RuntimeError:
            self.chroma_manager.initialize()

    def _get_project_collection_name(self, project_id: uuid.UUID) -> str:
        """获取指定项目的 ChromaDB 集合名称。

        Args:
            project_id: 项目 ID

        Returns:
            str: 集合名称
        """
        return f"project_{project_id}_documents"

    def chunk_text(
        self,
        parse_result: ParseResult,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        """将解析结果按段落+滑动窗口分块。

        Args:
            parse_result: 文档解析结果
            chunk_size: 每块的字符数（默认从 config 读取）
            chunk_overlap: 重叠字符数（默认从 config 读取）

        Returns:
            list[dict]: 分块结果列表，每块包含:
                - text: 块文本
                - page_num: 来源页码
                - chunk_index: 块序号
        """
        chunk_size = chunk_size or settings.CHUNK_SIZE
        chunk_overlap = chunk_overlap or settings.CHUNK_OVERLAP

        chunks: list[dict[str, Any]] = []
        chunk_index = 0

        for page in parse_result.pages:
            text = page.text.strip()
            if not text:
                continue

            # 对长文本使用滑动窗口分块
            if len(text) > chunk_size:
                start = 0
                while start < len(text):
                    end = start + chunk_size
                    chunk_text = text[start:end]

                    chunks.append({
                        "text": chunk_text,
                        "page_num": page.page_num,
                        "chunk_index": chunk_index,
                        "text_preview": chunk_text[:50].replace("\n", " "),
                    })
                    chunk_index += 1

                    # 滑动窗口
                    start += chunk_size - chunk_overlap
                    if end >= len(text):
                        break
            else:
                # 短文本直接作为一个块
                chunks.append({
                    "text": text,
                    "page_num": page.page_num,
                    "chunk_index": chunk_index,
                    "text_preview": text[:50].replace("\n", " "),
                })
                chunk_index += 1

        # 如果没有任何文本块，添加一个空的占位块
        if not chunks:
            logger.warning(f"文档 '{parse_result.file_name}' 未提取到文本，添加占位块")
            chunks.append({
                "text": parse_result.full_text or f"[空文档: {parse_result.file_name}]",
                "page_num": 0,
                "chunk_index": 0,
                "text_preview": "[空文档]",
            })

        logger.info(
            f"文档分块完成: {len(chunks)} 块, "
            f"chunk_size={chunk_size}, overlap={chunk_overlap}"
        )
        return chunks

    def store_document_vectors(
        self,
        project_id: uuid.UUID,
        doc_id: uuid.UUID,
        parse_result: ParseResult,
    ) -> int:
        """将文档解析结果分块、向量化并存入 ChromaDB。

        Args:
            project_id: 项目 ID
            doc_id: 文档 ID
            parse_result: 文档解析结果

        Returns:
            int: 成功存储的向量数量
        """
        # 1. 分块
        chunks = self.chunk_text(parse_result)
        if not chunks:
            logger.warning(f"文档 {doc_id} 分块结果为空，跳过向量化")
            return 0

        # 2. 提取文本列表
        texts = [chunk["text"] for chunk in chunks]

        # 3. 向量化
        logger.info(f"开始向量化 {len(texts)} 个文本块...")
        embeddings = self.embedding_client.embed_batch(texts)

        # 4. 过滤向量化失败的块
        valid_chunks = []
        valid_embeddings = []
        for chunk, emb in zip(chunks, embeddings):
            if emb and len(emb) > 0:
                valid_chunks.append(chunk)
                valid_embeddings.append(emb)

        if not valid_chunks:
            logger.error(f"文档 {doc_id} 所有文本块向量化失败")
            return 0

        # 5. 存入 ChromaDB
        try:
            collection_name = self._get_project_collection_name(project_id)
            collection = self.chroma_manager.client.get_or_create_collection(
                name=collection_name,
                metadata={
                    "hnsw:space": settings.CHROMA_DISTANCE_FN,
                    "project_id": str(project_id),
                    "description": f"项目 {project_id} 的文档向量集合",
                },
            )

            ids = [f"{doc_id}_chunk_{c['chunk_index']}" for c in valid_chunks]
            metadatas = [
                {
                    "doc_id": str(doc_id),
                    "page_num": c["page_num"],
                    "chunk_index": c["chunk_index"],
                    "text_preview": c["text_preview"],
                }
                for c in valid_chunks
            ]

            collection.add(
                ids=ids,
                embeddings=valid_embeddings,
                metadatas=metadatas,
                documents=[c["text"] for c in valid_chunks],
            )

            stored_count = len(valid_chunks)
            logger.info(
                f"向量存储成功: 项目={project_id}, 文档={doc_id}, "
                f"共 {stored_count} 条向量"
            )
            return stored_count

        except Exception as exc:
            logger.error(f"ChromaDB 向量存储失败: {exc!s}")
            return 0

    def search_similar(
        self,
        query_text: str,
        project_id: uuid.UUID,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """语义搜索与查询文本相似的文档片段。

        Args:
            query_text: 查询文本
            project_id: 项目 ID（限定搜索范围）
            top_k: 返回的 top-K 结果数

        Returns:
            list[dict]: 相似结果列表，每项包含:
                - doc_id: 文档 ID
                - text: 片段文本
                - page_num: 页码
                - chunk_index: 块序号
                - similarity: 相似度分数
                - text_preview: 文本预览
        """
        # 1. 查询文本向量化
        query_embedding = self.embedding_client.embed_text(query_text)
        if not query_embedding:
            logger.error("查询文本向量化失败")
            return []

        # 2. 在项目集合中搜索
        try:
            collection_name = self._get_project_collection_name(project_id)
            collection = self.chroma_manager.client.get_collection(
                name=collection_name
            )

            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=min(top_k, 100),
                include=["metadatas", "documents", "distances"],
            )

            # 3. 格式化结果
            formatted_results: list[dict[str, Any]] = []
            if results["ids"] and results["ids"][0]:
                for i, doc_id_full in enumerate(results["ids"][0]):
                    metadata = results["metadatas"][0][i] if results["metadatas"] else {}
                    distance = results["distances"][0][i] if results["distances"] else 0.0

                    # 将余弦距离转换为相似度分数
                    similarity = max(0.0, 1.0 - distance) * 100

                    formatted_results.append({
                        "doc_id": metadata.get("doc_id", ""),
                        "text": results["documents"][0][i] if results["documents"] else "",
                        "page_num": metadata.get("page_num", 0),
                        "chunk_index": metadata.get("chunk_index", 0),
                        "similarity": round(similarity, 2),
                        "text_preview": metadata.get("text_preview", ""),
                    })

            logger.info(
                f"语义搜索完成: 查询='{query_text[:30]}...', "
                f"项目={project_id}, 结果={len(formatted_results)} 条"
            )
            return formatted_results

        except Exception as exc:
            logger.error(f"ChromaDB 语义搜索失败: {exc!s}")
            return []

    def delete_document_vectors(
        self,
        project_id: uuid.UUID,
        doc_id: uuid.UUID,
    ) -> bool:
        """删除指定文档的所有向量。

        Args:
            project_id: 项目 ID
            doc_id: 文档 ID

        Returns:
            bool: 是否成功删除
        """
        try:
            collection_name = self._get_project_collection_name(project_id)
            collection = self.chroma_manager.client.get_collection(
                name=collection_name
            )

            # 查询该文档的所有向量 ID
            results = collection.get(
                where={"doc_id": str(doc_id)},
                include=[],
            )

            if results["ids"]:
                collection.delete(ids=results["ids"])
                logger.info(
                    f"删除文档向量: 项目={project_id}, 文档={doc_id}, "
                    f"共 {len(results['ids'])} 条"
                )
            return True

        except Exception as exc:
            logger.warning(f"删除文档向量失败: {exc!s}")
            return False

    def delete_project_vectors(
        self,
        project_id: uuid.UUID,
    ) -> bool:
        """删除指定项目的所有向量集合。

        Args:
            project_id: 项目 ID

        Returns:
            bool: 是否成功删除
        """
        try:
            collection_name = self._get_project_collection_name(project_id)
            self.chroma_manager.client.delete_collection(collection_name)
            logger.info(f"删除项目向量集合: 项目={project_id}")
            return True
        except Exception as exc:
            logger.warning(f"删除项目向量集合失败: {exc!s}")
            return False
