"""
分析引擎模块
提供文本相似度、目录结构相似度、图片相似度、表格相似度、错误检测、元数据一致性六大分析引擎及编排器。
"""

from app.services.analysis.analysis_orchestrator import AnalysisOrchestrator
from app.services.analysis.text_similarity import (
    compute_cosine_similarity,
    compute_jaccard_similarity,
    analyze_text_similarity,
    compute_project_similarity_matrix,
)
from app.services.analysis.structure_similarity import (
    extract_headings,
    compare_heading_sequences,
    analyze_structure_similarity,
)
from app.services.analysis.image_similarity import (
    compute_phash,
    compute_dhash,
    compute_ahash,
    hamming_distance,
    compute_fusion_score,
    analyze_image_similarity,
)
from app.services.analysis.table_similarity import (
    compare_table_pair,
    compute_document_table_similarity,
    analyze_table_similarity,
)
from app.services.analysis.error_detection import (
    detect_typos,
    check_consistency,
    analyze_errors,
)
from app.services.analysis.metadata_consistency import (
    compare_metadata,
    analyze_metadata_consistency,
)
from app.services.analysis.models import (
    SimilarityPair,
    DocumentSimilarityReport,
    TypoResult,
    ConsistencyIssue,
)

__all__ = [
    "AnalysisOrchestrator",
    "compute_cosine_similarity",
    "compute_jaccard_similarity",
    "analyze_text_similarity",
    "compute_project_similarity_matrix",
    "extract_headings",
    "compare_heading_sequences",
    "analyze_structure_similarity",
    "compute_phash",
    "compute_dhash",
    "compute_ahash",
    "hamming_distance",
    "compute_fusion_score",
    "analyze_image_similarity",
    "compare_table_pair",
    "compute_document_table_similarity",
    "analyze_table_similarity",
    "detect_typos",
    "check_consistency",
    "analyze_errors",
    "compare_metadata",
    "analyze_metadata_consistency",
    "SimilarityPair",
    "DocumentSimilarityReport",
    "TypoResult",
    "ConsistencyIssue",
]
