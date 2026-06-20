"""
内部数据结构定义
提供分析引擎使用的数据类。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class SimilarityPair:
    """文本相似度对。

    Attributes:
        doc_id_1: 文档A ID
        chunk_1: 文档A的文本块
        doc_id_2: 文档B ID
        chunk_2: 文档B的文本块
        score: 相似度分数 (0.0 - 1.0)
    """

    doc_id_1: str
    chunk_1: str
    doc_id_2: str
    chunk_2: str
    score: float


@dataclass
class DocumentSimilarityReport:
    """文档级相似度报告。

    Attributes:
        doc_id_1: 文档A ID
        doc_id_2: 文档B ID
        overall_score: 整体相似度 (0.0 - 1.0)
        high_similarity_pairs: 高相似度片段数
        pairs: 详细相似对列表（最多保留 top-K）
    """

    doc_id_1: str
    doc_id_2: str
    overall_score: float
    high_similarity_pairs: int
    pairs: list[SimilarityPair] = field(default_factory=list)


@dataclass
class TypoResult:
    """错别字检测结果。

    Attributes:
        position: 错误位置 {page, paragraph, offset}
        original: 原始错误文本
        corrected: 建议修正文本
        confidence: 置信度 (0.0 - 1.0)
    """

    position: dict[str, Any]
    original: str
    corrected: str
    confidence: float


@dataclass
class ConsistencyIssue:
    """一致性检查问题。

    Attributes:
        issue_type: 问题类型: TERM / NUMBER / FORMAT
        documents: 涉及的文档ID列表
        description: 问题描述
        severity: 严重程度: low / medium / high
    """

    issue_type: str  # TERM, NUMBER, FORMAT
    documents: list[str]
    description: str
    severity: str  # low, medium, high
