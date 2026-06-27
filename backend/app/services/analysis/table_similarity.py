"""
表格相似度分析引擎。
从解析结果中提取表格结构，计算跨文档表格的相似度。
"""
from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any, Optional, Callable, Awaitable

from loguru import logger
from sqlalchemy import select

from app.models.analysis import SimilarityResult
from app.models.project import BidDocument


def _jaccard_sets(set1: set, set2: set) -> float:
    """计算两个集合的 Jaccard 相似度。"""
    if not set1 or not set2:
        return 0.0
    inter = set1 & set2
    union = set1 | set2
    return len(inter) / len(union) if union else 0.0


def _flatten_cells(table_data: list[list[str]]) -> set[str]:
    """将表格数据展平为单元格字符串集合。"""
    cells: set[str] = set()
    for row in table_data:
        for cell in row:
            stripped = str(cell).strip()
            if stripped:
                cells.add(stripped)
    return cells


def compare_table_pair(
    table_a: list[list[str]], table_b: list[list[str]],
) -> dict[str, float]:
    """比较两个表格的相似度。

    综合比较：表头相似度、结构相似度、单元格内容相似度。

    Args:
        table_a: 表格A的数据
        table_b: 表格B的数据

    Returns:
        dict: {header_sim, structure_sim, content_sim, overall}
    """
    if not table_a or not table_b:
        return {"header_sim": 0.0, "structure_sim": 0.0, "content_sim": 0.0, "overall": 0.0}

    # 1. 表头相似度
    header_a = {str(c).strip() for c in table_a[0]}
    header_b = {str(c).strip() for c in table_b[0]}
    header_sim = _jaccard_sets(header_a, header_b)

    # 2. 结构相似度（行列数匹配）
    rows_a, cols_a = len(table_a), max((len(r) for r in table_a), default=0)
    rows_b, cols_b = len(table_b), max((len(r) for r in table_b), default=0)

    row_ratio = min(rows_a, rows_b) / max(rows_a, rows_b, 1)
    col_ratio = min(cols_a, cols_b) / max(cols_a, cols_b, 1)
    structure_sim = row_ratio * 0.5 + col_ratio * 0.5

    # 3. 单元格内容相似度
    cells_a = _flatten_cells(table_a)
    cells_b = _flatten_cells(table_b)
    content_sim = _jaccard_sets(cells_a, cells_b)

    # 融合评分
    overall = header_sim * 0.4 + structure_sim * 0.2 + content_sim * 0.4

    return {
        "header_sim": round(header_sim, 4),
        "structure_sim": round(structure_sim, 4),
        "content_sim": round(content_sim, 4),
        "overall": round(overall, 4),
    }


def compute_document_table_similarity(
    tables_a: list[dict], tables_b: list[dict],
) -> float:
    """计算两个文档之间的整体表格相似度。

    对每对表格找最佳匹配，取相似度平均值。

    Args:
        tables_a: 文档A的表格列表（含 data 字段）
        tables_b: 文档B的表格列表（含 data 字段）

    Returns:
        float: 表格相似度 (0.0 - 1.0)
    """
    if not tables_a or not tables_b:
        return 0.0

    scores: list[float] = []
    for ta in tables_a:
        data_a = ta.get("data", [])
        if not data_a or len(data_a) < 2:
            continue
        best_score = 0.0
        for tb in tables_b:
            data_b = tb.get("data", [])
            if not data_b or len(data_b) < 2:
                continue
            result = compare_table_pair(data_a, data_b)
            if result["overall"] > best_score:
                best_score = result["overall"]
        if best_score > 0:
            scores.append(best_score)

    if not scores:
        return 0.0

    return sum(scores) / len(scores)


async def analyze_table_similarity(
    project_id: uuid.UUID,
    analysis_task_id: uuid.UUID,
    db_session_factory,
    on_progress: Optional[Callable[[int], Awaitable[None]]] = None,
) -> int:
    """分析项目文档间的表格相似度。

    从 BidDocument.extracted_tables 读取已保存的表格数据，
    对每对文档进行表格相似度计算并更新 SimilarityResult。

    Args:
        project_id: 项目ID
        analysis_task_id: 分析任务ID
        db_session_factory: 数据库会话工厂

    Returns:
        int: 更新的结果数量
    """
    logger.info(f"开始表格相似度分析: project={project_id}")

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
                logger.info("文档数量不足，跳过表格相似度分析")
                return 0

            # 收集每个文档的表格数据
            doc_tables: dict[str, list[dict]] = {}
            for doc in documents:
                tables = []
                if doc.extracted_tables and isinstance(doc.extracted_tables, list):
                    tables = doc.extracted_tables
                doc_tables[str(doc.id)] = tables
                if tables:
                    logger.debug(f"文档 {doc.filename}: {len(tables)} 个表格")

            total_tables = sum(len(t) for t in doc_tables.values())
            if total_tables == 0:
                logger.info(
                    "文档中无表格数据（请在文档解析后重新分析），"
                    "跳过表格相似度分析"
                )
                return 0

            # 两两比较并更新 SimilarityResult
            updated_count = 0
            doc_ids = list(doc_tables.keys())
            total_pairs = len(doc_ids) * (len(doc_ids) - 1) // 2
            pair_count = 0

            from app.models.analysis import SimilarityResult as SimResultModel
            from sqlalchemy import or_

            for i in range(len(doc_ids)):
                for j in range(i + 1, len(doc_ids)):
                    pair_count += 1
                    doc_a = doc_ids[i]
                    doc_b = doc_ids[j]

                    table_score = compute_document_table_similarity(
                        doc_tables.get(doc_a, []),
                        doc_tables.get(doc_b, []),
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
                        existing.table_similarity = Decimal(
                            str(round(table_score * 100, 2))
                        )
                        updated_count += 1

                    if on_progress and pair_count % max(1, total_pairs // 10) == 0:
                        try:
                            await on_progress(pair_count)
                        except Exception:
                            pass

            await db.commit()
            logger.info(
                f"表格相似度分析完成: 更新 {updated_count} 条记录"
            )
            return updated_count

    except Exception as exc:
        logger.error(f"表格相似度分析失败: {exc!s}")
        return 0
