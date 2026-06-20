"""
Gitee AI Embedding API 客户端。
封装 Gitee AI 的文本向量化 API 调用，支持单条和批量向量化。
API Key 从 config 中读取，不硬编码。
"""

from __future__ import annotations

import asyncio
import time
from typing import Optional

import httpx
from loguru import logger

from app.core.config import settings


class GiteeEmbeddingClient:
    """Gitee AI Embedding API 客户端。

    使用 Gitee AI 的 Qwen3-Embedding-8B 模型进行文本向量化。
    支持单条嵌入和批量嵌入，具备指数退避重试机制。
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[int] = None,
        max_retries: Optional[int] = None,
    ):
        """初始化 Embedding 客户端。

        Args:
            api_key: Gitee AI API Key，默认从 config 读取
            base_url: API 基础 URL，默认从 config 读取
            model: 模型名称，默认从 config 读取
            timeout: 请求超时秒数，默认从 config 读取
            max_retries: 最大重试次数，默认从 config 读取
        """
        self.api_key = api_key or settings.GITEE_AI_API_KEY
        self.base_url = base_url or settings.GITEE_AI_BASE_URL
        self.model = model or settings.GITEE_AI_MODEL
        self.timeout = timeout or settings.GITEE_AI_TIMEOUT
        self.max_retries = max_retries or settings.GITEE_AI_MAX_RETRIES

        if not self.api_key:
            logger.warning("GITEE_AI_API_KEY 未配置，Embedding 服务将无法正常工作")

        # 构建 Embedding API 端点
        # Gitee AI OpenAI-compatible endpoint: POST {base_url}/embeddings
        self._embed_url = f"{self.base_url}/embeddings"

    def _build_headers(self) -> dict[str, str]:
        """构建请求头。

        Returns:
            dict: 包含 Authorization 的请求头
        """
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _build_payload(self, input_text: str | list[str]) -> dict:
        """构建请求体。

        Args:
            input_text: 单条文本或文本列表

        Returns:
            dict: 请求体
        """
        return {
            "model": self.model,
            "input": input_text,
        }

    def embed_text(self, text: str) -> list[float]:
        """将单条文本向量化。

        Args:
            text: 待向量化的文本

        Returns:
            list[float]: 向量数组，失败时返回空列表
        """
        if not text or not text.strip():
            logger.warning("输入文本为空，返回空向量")
            return []

        if not self.api_key:
            logger.error("API Key 未配置，无法调用 Embedding API")
            return []

        for attempt in range(1, self.max_retries + 1):
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    response = client.post(
                        self._embed_url,
                        headers=self._build_headers(),
                        json=self._build_payload(text),
                    )

                if response.status_code == 200:
                    data = response.json()
                    embedding = data["data"][0]["embedding"]
                    logger.debug(
                        f"Embedding 成功: 输入长度={len(text)}, "
                        f"向量维度={len(embedding)}"
                    )
                    return embedding

                logger.warning(
                    f"Embedding API 返回非200状态码: {response.status_code}, "
                    f"响应: {response.text[:200]}"
                )

            except httpx.TimeoutException:
                logger.warning(
                    f"Embedding API 超时 (尝试 {attempt}/{self.max_retries})"
                )
            except httpx.RequestError as exc:
                logger.warning(
                    f"Embedding API 请求失败 (尝试 {attempt}/{self.max_retries}): "
                    f"{exc!s}"
                )
            except (KeyError, IndexError, ValueError) as exc:
                logger.error(f"Embedding API 响应解析失败: {exc!s}")
                return []

            # 指数退避重试
            if attempt < self.max_retries:
                wait_time = 2 ** attempt
                logger.info(f"等待 {wait_time}s 后重试...")
                time.sleep(wait_time)

        logger.error(f"Embedding API 调用失败，已重试 {self.max_retries} 次")
        return []

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """批量将多条文本向量化。

        Args:
            texts: 待向量化的文本列表

        Returns:
            list[list[float]]: 向量数组列表，失败项对应空列表
        """
        if not texts:
            return []

        # 过滤空文本
        valid_texts = [t for t in texts if t and t.strip()]
        if not valid_texts:
            logger.warning("所有输入文本均为空，返回空结果")
            return [[] for _ in texts]

        if not self.api_key:
            logger.error("API Key 未配置，无法调用 Embedding API")
            return [[] for _ in texts]

        for attempt in range(1, self.max_retries + 1):
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    response = client.post(
                        self._embed_url,
                        headers=self._build_headers(),
                        json=self._build_payload(valid_texts),
                    )

                if response.status_code == 200:
                    data = response.json()
                    # 按输入顺序排序结果
                    embedding_map = {
                        item["index"]: item["embedding"]
                        for item in data["data"]
                    }
                    results = [
                        embedding_map.get(i, [])
                        for i in range(len(valid_texts))
                    ]
                    logger.info(
                        f"批量 Embedding 成功: {len(valid_texts)} 条, "
                        f"向量维度={len(results[0]) if results else 0}"
                    )
                    return results

                logger.warning(
                    f"批量 Embedding API 返回非200状态码: {response.status_code}, "
                    f"响应: {response.text[:200]}"
                )

            except httpx.TimeoutException:
                logger.warning(
                    f"批量 Embedding API 超时 (尝试 {attempt}/{self.max_retries})"
                )
            except httpx.RequestError as exc:
                logger.warning(
                    f"批量 Embedding API 请求失败 "
                    f"(尝试 {attempt}/{self.max_retries}): {exc!s}"
                )
            except (KeyError, IndexError, ValueError) as exc:
                logger.error(f"批量 Embedding API 响应解析失败: {exc!s}")
                return [[] for _ in texts]

            # 指数退避
            if attempt < self.max_retries:
                wait_time = 2 ** attempt
                logger.info(f"等待 {wait_time}s 后重试...")
                time.sleep(wait_time)

        logger.error(f"批量 Embedding API 调用失败，已重试 {self.max_retries} 次")
        return [[] for _ in texts]

    async def embed_text_async(self, text: str) -> list[float]:
        """异步将单条文本向量化。

        Args:
            text: 待向量化的文本

        Returns:
            list[float]: 向量数组，失败时返回空列表
        """
        if not text or not text.strip():
            return []

        if not self.api_key:
            logger.error("API Key 未配置")
            return []

        for attempt in range(1, self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        self._embed_url,
                        headers=self._build_headers(),
                        json=self._build_payload(text),
                    )

                if response.status_code == 200:
                    data = response.json()
                    return data["data"][0]["embedding"]

                logger.warning(
                    f"异步 Embedding API 非200: {response.status_code}"
                )

            except (httpx.TimeoutException, httpx.RequestError) as exc:
                logger.warning(
                    f"异步 Embedding API 失败 "
                    f"(尝试 {attempt}/{self.max_retries}): {exc!s}"
                )
            except (KeyError, IndexError, ValueError) as exc:
                logger.error(f"异步 Embedding 响应解析失败: {exc!s}")
                return []

            if attempt < self.max_retries:
                await asyncio.sleep(2 ** attempt)

        return []

    async def embed_batch_async(self, texts: list[str]) -> list[list[float]]:
        """异步批量向量化。

        Args:
            texts: 文本列表

        Returns:
            list[list[float]]: 向量列表
        """
        if not texts:
            return []

        valid_texts = [t for t in texts if t and t.strip()]
        if not valid_texts:
            return [[] for _ in texts]

        if not self.api_key:
            logger.error("API Key 未配置")
            return [[] for _ in texts]

        for attempt in range(1, self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        self._embed_url,
                        headers=self._build_headers(),
                        json=self._build_payload(valid_texts),
                    )

                if response.status_code == 200:
                    data = response.json()
                    embedding_map = {
                        item["index"]: item["embedding"]
                        for item in data["data"]
                    }
                    return [
                        embedding_map.get(i, [])
                        for i in range(len(valid_texts))
                    ]

            except (httpx.TimeoutException, httpx.RequestError) as exc:
                logger.warning(
                    f"异步批量 Embedding 失败 "
                    f"(尝试 {attempt}/{self.max_retries}): {exc!s}"
                )
            except (KeyError, IndexError, ValueError) as exc:
                logger.error(f"异步批量 Embedding 解析失败: {exc!s}")
                return [[] for _ in texts]

            if attempt < self.max_retries:
                await asyncio.sleep(2 ** attempt)

        return [[] for _ in texts]
