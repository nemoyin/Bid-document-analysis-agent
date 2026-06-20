"""
元数据一致性分析引擎。
比对标书文件的元数据（作者、创建者、编辑软件等），
识别不同企业标书中的元数据异常一致现象。
"""
from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from loguru import logger
from sqlalchemy import select

from app.models.analysis import SimilarityResult
from app.models.project import BidDocument


# 需要比对的元数据字段
_METADATA_FIELDS = [
    "author",       # 作者
    "creator",      # 创建者（PDF producer）
    "producer",     # 生成软件
    "title",        # 标题
    "company",      # 公司（如果可提取）
    "last_modified_by",  # 最后修改者
]


def compare_metadata(
    meta_a: dict[str, Any], meta_b: dict[str, Any],
) -> dict[str, Any]:
    """比较两份文档的元数据一致性。

    Args:
        meta_a: 文档A的元数据
        meta_b: 文档B的元数据

    Returns:
        dict: {overall_score, matched_fields, details}
    """
    matched: list[str] = []
    details: list[dict] = []

    for field in _METADATA_FIELDS:
        val_a = str(meta_a.get(field, "")).strip().lower()
        val_b = str(meta_b.get(field, "")).strip().lower()

        if val_a and val_b and val_a == val_b:
            matched.append(field)
            details.append({
                "field": field,
                "value": meta_a.get(field, ""),
                "matched": True,
            })
        elif val_a or val_b:
            details.append({
                "field": field,
                "value_a": meta_a.get(field, ""),
                "value_b": meta_b.get(field, ""),
                "matched": False,
            })

    # 评分：匹配字段越多，元数据一致性越高 → 风险越高
    total_fields = len([d for d in details if d.get("value") or d.get("value_a")])
    if total_fields == 0:
        return {"overall_score": 0.0, "matched_fields": [], "details": details}

    # 不同字段的权重
    field_weights = {
        "author": 0.30,
        "creator": 0.20,
        "producer": 0.15,
        "title": 0.10,
        "company": 0.15,
        "last_modified_by": 0.10,
    }

    weighted_score = 0.0
    total_weight = 0.0
    for field in matched:
        w = field_weights.get(field, 0.1)
        weighted_score += w
        total_weight += w

    # 即使只有一个字段匹配（如author），也给出有意义的分数
    overall = weighted_score / max(total_weight, sum(field_weights.values()))

    return {
        "overall_score": round(overall, 4),
        "matched_fields": matched,
        "details": details,
    }


async def analyze_metadata_consistency(
    project_id: uuid.UUID,
    analysis_task_id: uuid.UUID,
    db_session_factory,
) -> int:
    """分析项目文档间的元数据一致性。

    从 BidDocument.file_metadata 读取解析时保存的元数据，
    对每对文档进行比对并更新 SimilarityResult。

    Args:
        project_id: 项目ID
        analysis_task_id: 分析任务ID
        db_session_factory: 数据库会话工厂

    Returns:
        int: 更新的结果数量
    """
    logger.info(f"开始元数据一致性分析: project={project_id}")

    try:
        async with db_session_factory() as db:
            result = await db.execute(
                select(BidDocument).where(
                    BidDocument.project_id == project_id,
                    BidDocument.parse_status == "completed",
                )
            )
            documents = result.scalars().all()

            if len(documents) < 2:
                logger.info("文档数量不足，跳过元数据一致性分析")
                return 0

            # 收集每个文档的元数据
            doc_metadata: dict[str, dict] = {}
            for doc in documents:
                if doc.file_metadata and isinstance(doc.file_metadata, dict):
                    doc_metadata[str(doc.id)] = doc.file_metadata
                else:
                    doc_metadata[str(doc.id)] = {}

            # 两两比较
            updated_count = 0
            doc_ids = list(doc_metadata.keys())

            from app.models.analysis import SimilarityResult as SimResultModel
            from sqlalchemy import or_

            for i in range(len(doc_ids)):
                for j in range(i + 1, len(doc_ids)):
                    doc_a = doc_ids[i]
                    doc_b = doc_ids[j]

                    comparison = compare_metadata(
                        doc_metadata.get(doc_a, {}),
                        doc_metadata.get(doc_b, {}),
                    )
                    meta_score = comparison["overall_score"]

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
                        existing.metadata_consistency = Decimal(
                            str(round(meta_score * 100, 2))
                        )
                        # 将元数据对比详情合并到 details JSON
                        if existing.details is None:
                            existing.details = {}
                        existing.details["metadata_comparison"] = comparison
                        updated_count += 1

            await db.commit()
            logger.info(
                f"元数据一致性分析完成: 更新 {updated_count} 条记录"
            )
            return updated_count

    except Exception as exc:
        logger.error(f"元数据一致性分析失败: {exc!s}")
        return 0
