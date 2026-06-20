"""
文本相似度分析引擎。
使用 Cosine 和 Jaccard 相似度计算文档间的相似度。
"""

from __future__ import annotations

import math
import uuid
from decimal import Decimal
from typing import Any, Optional

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.analysis import SimilarityResult
from app.services.analysis.models import (
    DocumentSimilarityReport,
    SimilarityPair,
)


def compute_cosine_similarity(vec1, vec2) -> float:
    """计算两个向量的余弦相似度。

    Args:
        vec1: 向量A
        vec2: 向量B

    Returns:
        float: 余弦相似度 (0.0 - 1.0)
    """
    if vec1 is None or vec2 is None:
        return 0.0
    if len(vec1) == 0 or len(vec2) == 0:
        return 0.0

    if len(vec1) != len(vec2):
        logger.warning(
            f"向量维度不匹配: {len(vec1)} vs {len(vec2)}，将截断至较短者"
        )
        min_len = min(len(vec1), len(vec2))
        vec1 = vec1[:min_len]
        vec2 = vec2[:min_len]

    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    norm_a = math.sqrt(sum(a * a for a in vec1))
    norm_b = math.sqrt(sum(b * b for b in vec2))

    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0

    return dot_product / (norm_a * norm_b)


def compute_jaccard_similarity(text1: str, text2: str) -> float:
    """计算两段文本的 Jaccard 相似度（基于字符集合交集）。

    Args:
        text1: 文本A
        text2: 文本B

    Returns:
        float: Jaccard 相似度 (0.0 - 1.0)
    """
    if not text1 or not text2:
        return 0.0

    set1 = set(text1)
    set2 = set(text2)

    intersection = set1 & set2
    union = set1 | set2

    if len(union) == 0:
        return 0.0

    return len(intersection) / len(union)


def compute_ngram_jaccard(text1: str, text2: str, n: int = 3) -> float:
    """计算两段文本的 n-gram Jaccard 相似度。

    适合技术规格等需要比较专业术语和结构的文本。

    Args:
        text1: 文本A
        text2: 文本B
        n: n-gram 大小

    Returns:
        float: n-gram Jaccard 相似度 (0.0 - 1.0)
    """
    if not text1 or not text2:
        return 0.0

    def _ngrams(text: str, n: int) -> set[str]:
        text = text.replace(" ", "").replace("\n", "").replace("\r", "")
        if len(text) < n:
            return {text}
        return {text[i : i + n] for i in range(len(text) - n + 1)}

    ngrams1 = _ngrams(text1, n)
    ngrams2 = _ngrams(text2, n)

    intersection = ngrams1 & ngrams2
    union = ngrams1 | ngrams2

    if not union:
        return 0.0

    return len(intersection) / len(union)


def compute_chunk_level_similarity(
    chunks_a: list[dict[str, Any]],
    chunks_b: list[dict[str, Any]],
    threshold: float = 0.8,
) -> list[SimilarityPair]:
    """计算两个文档的所有文本块之间的成对相似度。

    Args:
        chunks_a: 文档A的文本块列表
        chunks_b: 文档B的文本块列表
        threshold: 相似度阈值，低于此值的结果将被过滤

    Returns:
        list[SimilarityPair]: 相似度对列表（已按分数降序排列）
    """
    pairs: list[SimilarityPair] = []

    for ca in chunks_a:
        vec_a = ca.get("embedding", [])
        text_a = ca.get("text", "")
        doc_id_a = ca.get("doc_id", "")

        for cb in chunks_b:
            vec_b = cb.get("embedding", [])
            text_b = cb.get("text", "")
            doc_id_b = cb.get("doc_id", "")

            # 跳过同一文档的比较
            if doc_id_a == doc_id_b:
                continue

            # 使用余弦相似度（基于向量）
            score = compute_cosine_similarity(vec_a, vec_b)

            # 补充 Jaccard 相似度作为补充
            jaccard = compute_ngram_jaccard(text_a, text_b)
            score = max(score, jaccard * 0.7)  # 融合评分

            if score >= threshold:
                pairs.append(
                    SimilarityPair(
                        doc_id_1=doc_id_a,
                        chunk_1=text_a,
                        doc_id_2=doc_id_b,
                        chunk_2=text_b,
                        score=score,
                    )
                )

    # 按分数降序排列
    pairs.sort(key=lambda p: p.score, reverse=True)
    return pairs


def aggregate_document_similarity(
    pairs: list[SimilarityPair],
) -> list[DocumentSimilarityReport]:
    """将 chunk 级相似度聚合成文档级报告。

    Args:
        pairs: 所有相似度对

    Returns:
        list[DocumentSimilarityReport]: 文档级报告列表
    """
    from collections import defaultdict

    # 按文档对聚合
    doc_pairs: dict[tuple[str, str], list[SimilarityPair]] = defaultdict(list)
    for pair in pairs:
        key = tuple(sorted([pair.doc_id_1, pair.doc_id_2]))
        doc_pairs[key].append(pair)

    reports: list[DocumentSimilarityReport] = []
    for (doc1, doc2), doc_pairs_list in doc_pairs.items():
        # 整体分数 = 取 top-K 的平均值（避免大量低分拉低总分）
        top_k = min(10, len(doc_pairs_list))
        top_scores = [p.score for p in doc_pairs_list[:top_k]]
        overall_score = sum(top_scores) / len(top_scores) if top_scores else 0.0

        # 高相似度片段数（score > 0.9）
        high_count = sum(1 for p in doc_pairs_list if p.score > 0.9)

        reports.append(
            DocumentSimilarityReport(
                doc_id_1=doc1,
                doc_id_2=doc2,
                overall_score=overall_score,
                high_similarity_pairs=high_count,
                pairs=doc_pairs_list[:50],  # 最多保留50条
            )
        )

    # 按整体分数降序排列
    reports.sort(key=lambda r: r.overall_score, reverse=True)
    return reports


async def analyze_text_similarity(
    project_id: uuid.UUID,
    analysis_task_id: uuid.UUID,
    chroma_collection: Any,
    db_session_factory,
) -> int:
    """文本相似度分析入口。

    从 ChromaDB 检索同一项目下所有文档的向量化分块，
    两两计算相似度，并将结果写入数据库。

    Args:
        project_id: 项目ID
        analysis_task_id: 分析任务ID
        chroma_collection: ChromaDB 集合实例
        db_session_factory: 数据库会话工厂

    Returns:
        int: 写入的相似度结果数量
    """
    logger.info(f"开始文本相似度分析: project={project_id}, task={analysis_task_id}")

    # 1. 从 ChromaDB 检索所有文档分块及其向量
    try:
        all_data = chroma_collection.get(
            include=["embeddings", "documents", "metadatas"]
        )
    except Exception as exc:
        logger.error(f"ChromaDB 检索失败: {exc!s}")
        return 0

    if not all_data or not all_data["ids"]:
        logger.warning(f"项目 {project_id} 在 ChromaDB 中没有文档分块")
        return 0

    logger.info(f"从 ChromaDB 检索到 {len(all_data['ids'])} 个文本块")

    # 2. 按文档分组
    from collections import defaultdict

    doc_chunks: dict[str, list[dict]] = defaultdict(list)
    for i, doc_id_full in enumerate(all_data["ids"]):
        metadata = all_data["metadatas"][i] if all_data["metadatas"] else {}
        doc_id = metadata.get("doc_id", "")
        doc_chunks[doc_id].append(
            {
                "doc_id": doc_id,
                "text": all_data["documents"][i] if all_data["documents"] else "",
                "embedding": all_data["embeddings"][i] if all_data["embeddings"] is not None else [],
                "chunk_index": metadata.get("chunk_index", 0),
                "page_num": metadata.get("page_num", 0),
            }
        )

    doc_ids = list(doc_chunks.keys())
    logger.info(f"按文档分组完成: {len(doc_ids)} 个文档")

    threshold = getattr(settings, "SIMILARITY_THRESHOLD", 0.8)

    # 3. 两两比较（避免重复比较）
    all_pairs: list[SimilarityPair] = []
    for i in range(len(doc_ids)):
        for j in range(i + 1, len(doc_ids)):
            chunks_a = doc_chunks[doc_ids[i]]
            chunks_b = doc_chunks[doc_ids[j]]
            pairs = compute_chunk_level_similarity(
                chunks_a, chunks_b, threshold=threshold
            )
            all_pairs.extend(pairs)

    logger.info(f"chunk 级相似度计算完成: {len(all_pairs)} 对")

    # 4. 聚合为文档级报告
    reports = aggregate_document_similarity(all_pairs)
    logger.info(f"文档级聚合完成: {len(reports)} 对文档")

    # 5. 写入数据库
    written_count = 0
    try:
        async with db_session_factory() as db:
            for report in reports:
                # 仅写入整体相似度 > threshold 的文档对
                if report.overall_score < threshold:
                    continue

                # 构建详细结果
                detail_pairs = [
                    {
                        "doc1_chunk": p.chunk_1[:200],
                        "doc2_chunk": p.chunk_2[:200],
                        "score": round(p.score, 4),
                    }
                    for p in report.pairs[:20]  # 最多保留20条
                ]

                similarity_entry = SimilarityResult(
                    task_id=str(analysis_task_id),
                    doc1_id=str(uuid.UUID(report.doc_id_1)),
                    doc2_id=str(uuid.UUID(report.doc_id_2)),
                    full_text_similarity=Decimal(str(round(report.overall_score * 100, 2))),
                    details={
                        "report_type": "text_similarity",
                        "total_pairs": len(report.pairs),
                        "high_similarity_pairs": report.high_similarity_pairs,
                        "top_pairs": detail_pairs,
                    },
                )
                db.add(similarity_entry)
                written_count += 1

            await db.commit()
            logger.info(
                f"文本相似度分析完成: 写入 {written_count} 条结果"
            )
    except Exception as exc:
        logger.error(f"文本相似度结果写入失败: {exc!s}")

    return written_count


async def compute_project_similarity_matrix(
    project_id: uuid.UUID, db: AsyncSession
) -> list[dict]:
    """计算并返回项目文档相似度矩阵。

    Args:
        project_id: 项目ID
        db: 数据库会话

    Returns:
        list[dict]: 相似度矩阵 (doc_id_1, doc_id_2, score)
    """
    from app.models.analysis import AnalysisTask, SimilarityResult

    # 获取最新的已完成分析任务
    result = await db.execute(
        select(AnalysisTask)
        .where(
            AnalysisTask.project_id == project_id,
            AnalysisTask.status == "completed",
        )
        .order_by(AnalysisTask.completed_at.desc())
        .limit(1)
    )
    task = result.scalar_one_or_none()
    if not task:
        return []

    # 获取该任务的相似度结果
    sim_result = await db.execute(
        select(SimilarityResult).where(SimilarityResult.task_id == task.id)
    )
    entries = sim_result.scalars().all()

    matrix = []
    for entry in entries:
        matrix.append(
            {
                "doc_id_1": str(entry.doc1_id),
                "doc_id_2": str(entry.doc2_id),
                "full_text_similarity": float(entry.full_text_similarity or 0),
                "technical_similarity": float(entry.technical_similarity or 0),
                "business_similarity": float(entry.business_similarity or 0),
            }
        )

    return matrix
