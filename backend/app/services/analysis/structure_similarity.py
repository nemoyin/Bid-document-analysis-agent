"""
目录结构相似度分析引擎。
提取文档的标题/章节结构，比较文档间的结构相似度。
"""
from __future__ import annotations

import re
import uuid
from collections import defaultdict
from decimal import Decimal
from typing import Any, Optional, Callable, Awaitable

from loguru import logger
from sqlalchemy import select

from app.core.config import settings
from app.models.analysis import SimilarityResult
from app.models.project import BidDocument


# 中文标书常见标题模式
HEADING_PATTERNS = [
    # 第X章 / 第X节
    re.compile(r'^第[一二三四五六七八九十\d]+[章节]', re.MULTILINE),
    # 数字编号: 1. / 1.1 / 1.1.1
    re.compile(r'^\d+(?:\.\d+)*\s+\S', re.MULTILINE),
    # 中文数字编号: 一、/ （一）/ (一)
    re.compile(r'^[（(]?[一二三四五六七八九十]+[）)]?\s*[、,]?\s*\S', re.MULTILINE),
    # 投标书常见章节名
    re.compile(r'^(投标函|法定代表人|授权书|公司概况|项目组织|技术方案|质量保证|工期|安全|售后服务|附件|报价|商务|技术)'),
]


def extract_headings(text: str) -> list[dict[str, Any]]:
    """从文档文本中提取章节标题。

    Args:
        text: 文档全文

    Returns:
        list[dict]: 标题列表，每个包含 {text, level, line_number}
    """
    lines = text.split('\n')
    headings: list[dict[str, Any]] = []

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or len(stripped) > 80:
            continue

        # 检查是否匹配标题模式
        for pattern in HEADING_PATTERNS:
            if pattern.match(stripped):
                # 粗略判断层级：以缩进和编号深度判断
                level = 1
                if stripped.startswith((' ', '\t', '（', '(')):
                    level = 2
                if re.match(r'^\d+\.\d+\.\d+', stripped):
                    level = 3
                elif re.match(r'^\d+\.\d+', stripped):
                    level = 2

                headings.append({
                    "text": stripped[:60],  # 截断过长标题
                    "level": level,
                    "line_number": i,
                })
                break

    return headings


def compare_heading_sequences(
    headings_a: list[dict], headings_b: list[dict],
) -> float:
    """比较两个文档的标题序列相似度。

    综合比较标题文本相似度和结构序列匹配度。

    Args:
        headings_a: 文档A的标题序列
        headings_b: 文档B的标题序列

    Returns:
        float: 结构相似度 (0.0 - 1.0)
    """
    if not headings_a or not headings_b:
        return 0.0

    # 1. 标题文本相似度（Jaccard + 公共子序列）
    texts_a = {h["text"] for h in headings_a}
    texts_b = {h["text"] for h in headings_b}
    intersection = texts_a & texts_b
    union = texts_a | texts_b
    text_sim = len(intersection) / len(union) if union else 0.0

    # 2. 结构序列相似度（编辑距离归一化）
    levels_a = [h["level"] for h in headings_a]
    levels_b = [h["level"] for h in headings_b]
    lcs_len = _lcs_length(levels_a, levels_b)
    max_len = max(len(levels_a), len(levels_b))
    seq_sim = lcs_len / max_len if max_len > 0 else 0.0

    # 3. 标题数量相似度
    count_sim = min(len(headings_a), len(headings_b)) / max(len(headings_a), len(headings_b), 1)

    # 融合评分
    return text_sim * 0.5 + seq_sim * 0.3 + count_sim * 0.2


def _lcs_length(a: list, b: list) -> int:
    """计算两个序列的最长公共子序列长度（DP 优化空间版）。"""
    if not a or not b:
        return 0
    prev = [0] * (len(b) + 1)
    for i in range(1, len(a) + 1):
        curr = [0] * (len(b) + 1)
        for j in range(1, len(b) + 1):
            if a[i - 1] == b[j - 1]:
                curr[j] = prev[j - 1] + 1
            else:
                curr[j] = max(prev[j], curr[j - 1])
        prev = curr
    return prev[len(b)]


async def analyze_structure_similarity(
    project_id: uuid.UUID,
    analysis_task_id: uuid.UUID,
    db_session_factory,
    on_progress: Optional[Callable[[int], Awaitable[None]]] = None,
) -> int:
    """分析项目文档间的目录结构相似度。

    Args:
        project_id: 项目ID
        analysis_task_id: 分析任务ID
        db_session_factory: 数据库会话工厂

    Returns:
        int: 更新的结果数量
    """
    logger.info(f"开始目录结构相似度分析: project={project_id}")

    try:
        async with db_session_factory() as db:
            # 获取项目所有文档
            result = await db.execute(
                select(BidDocument).where(
                    BidDocument.project_id == project_id,
                    BidDocument.parse_status == "completed",
                )
            )
            documents = result.scalars().all()

            if len(documents) < 2:
                logger.info("文档数量不足，跳过目录结构分析")
                return 0

            # 提取每个文档的标题结构
            doc_headings: dict[str, list[dict]] = {}
            for doc in documents:
                if doc.content_text:
                    headings = extract_headings(doc.content_text)
                    doc_headings[str(doc.id)] = headings
                    logger.debug(f"文档 {doc.filename}: 提取到 {len(headings)} 个标题")

            # 两两比较
            updated_count = 0
            doc_ids = list(doc_headings.keys())
            total_pairs = len(doc_ids) * (len(doc_ids) - 1) // 2
            pair_count = 0

            # 查找已有的相似度记录并更新
            from app.models.analysis import SimilarityResult as SimResultModel
            from sqlalchemy import or_

            for i in range(len(doc_ids)):
                for j in range(i + 1, len(doc_ids)):
                    pair_count += 1
                    doc_a = doc_ids[i]
                    doc_b = doc_ids[j]

                    structure_score = compare_heading_sequences(
                        doc_headings.get(doc_a, []),
                        doc_headings.get(doc_b, []),
                    )

                    # 查找相似度记录（doc ID 顺序无关）
                    query = select(SimResultModel).where(
                        SimResultModel.task_id == str(analysis_task_id),
                        or_(
                            (SimResultModel.doc1_id == doc_a) & (SimResultModel.doc2_id == doc_b),
                            (SimResultModel.doc1_id == doc_b) & (SimResultModel.doc2_id == doc_a),
                        ),
                    )
                    exec_result = await db.execute(query)
                    existing = exec_result.scalar_one_or_none()

                    if existing:
                        existing.structure_similarity = Decimal(
                            str(round(structure_score * 100, 2))
                        )
                        updated_count += 1

                    # 每完成一对，上报进度（每10%触发一次以减少DB写入）
                    if on_progress and pair_count % max(1, total_pairs // 10) == 0:
                        try:
                            await on_progress(pair_count)
                        except Exception:
                            pass

            await db.commit()
            logger.info(
                f"目录结构相似度分析完成: 更新 {updated_count} 条记录"
            )
            return updated_count

    except Exception as exc:
        logger.error(f"目录结构相似度分析失败: {exc!s}")
        return 0
