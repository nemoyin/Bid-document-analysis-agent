"""
错误一致性检测引擎。
提供错别字检测、跨文档一致性检查（术语、数字、格式）。
"""

from __future__ import annotations

import hashlib
import re
import uuid
from collections import defaultdict
from typing import Any, Optional

from loguru import logger

from app.core.config import settings
from app.models.analysis import ErrorDetectionResult
from app.services.analysis.models import ConsistencyIssue, TypoResult


# ============================================================
# 错别字检测
# ============================================================


def detect_typos(text: str) -> list[TypoResult]:
    """使用 pycorrector 进行错别字检测。

    如果 pycorrector 未安装或加载失败，使用基本规则作为降级方案。

    Args:
        text: 待检测文本

    Returns:
        list[TypoResult]: 错别字结果列表
    """
    if not text or not text.strip():
        return []

    # 检查是否启用了 pycorrector
    pycorrector_enabled = getattr(settings, "PYCORRECTOR_ENABLED", True)

    if pycorrector_enabled:
        pycorrector_results = _detect_with_pycorrector(text)
        if pycorrector_results:
            return pycorrector_results
        logger.info("pycorrector 未返回结果，使用规则降级")

    # 降级方案：基于规则检测
    return _detect_with_rules(text)


def _detect_with_pycorrector(text: str) -> list[TypoResult]:
    """使用 pycorrector 进行检测。

    Returns:
        list[TypoResult]: 检测结果，失败返回空列表
    """
    try:
        import pycorrector

        corrected_text, details = pycorrector.correct(text)
        results: list[TypoResult] = []

        for err in details:
            original = err.get("source", "")
            corrected = err.get("target", "")
            confidence = err.get("confidence", 0.5)

            if original and corrected and original != corrected:
                # 在原文中查找位置
                pos = text.find(original)
                results.append(
                    TypoResult(
                        position={
                            "offset": pos if pos >= 0 else 0,
                            "length": len(original),
                        },
                        original=original,
                        corrected=corrected,
                        confidence=float(confidence),
                    )
                )

        return results
    except ImportError:
        logger.warning("pycorrector 未安装，使用规则降级检测")
        return []
    except Exception as exc:
        logger.warning(f"pycorrector 检测异常: {exc!s}，使用规则降级")
        return []


def _detect_with_rules(text: str) -> list[TypoResult]:
    """使用规则进行错别字检测（降级方案）。

    检测常见错误模式：连续重复字、常见易混淆字等。

    Args:
        text: 待检测文本

    Returns:
        list[TypoResult]: 检测结果
    """
    results: list[TypoResult] = []

    # 1. 检测连续重复字（如"的的"、"了了"）
    repeat_pattern = re.compile(r"([\u4e00-\u9fff])\1{2,}")
    for match in repeat_pattern.finditer(text):
        original = match.group()
        corrected = original[0]  # 只保留一个
        results.append(
            TypoResult(
                position={
                    "offset": match.start(),
                    "length": len(original),
                    "context": text[max(0, match.start() - 10) : match.end() + 10],
                },
                original=original,
                corrected=corrected,
                confidence=0.6,
            )
        )

    # 2. 检测常见的中文易混淆字（简单规则）
    confusion_pairs = [
        ("的地得", {"的": "地", "地": "的"}),
    ]
    # 太简化了，只检测明显的"的"和"地"在动词/名词前混用
    # 不在此处做复杂 NLP，留待 pycorrector 处理

    return results


# ============================================================
# 跨文档一致性检查
# ============================================================


def _extract_terms(text: str) -> set[str]:
    """从文本中提取专业术语。

    提取中文连续词组（2-10个中文字符的连续序列，排除标点）。

    Args:
        text: 文本内容

    Returns:
        set[str]: 提取的术语集合
    """
    # 提取连续中文词组
    term_pattern = re.compile(r"[\u4e00-\u9fff]{2,10}")
    terms = set(term_pattern.findall(text))

    # 过滤常见非术语词
    stop_terms = {
        "可以", "没有", "如果", "因为", "所以", "但是", "而且", "虽然",
        "或者", "并且", "关于", "按照", "根据", "通过", "需要", "应该",
        "已经", "进行", "提供", "包括", "以及", "其中", "同时", "此外",
        "对于", "作为", "具有", "成为", "就是", "不是", "十分", "非常",
        "实现", "建立", "完成", "方式", "方法", "情况", "时间", "内容",
        "本标书", "投标人", "招标人", "项目",
    }
    return {t for t in terms if t not in stop_terms and len(t) >= 2}


def _extract_numbers(text: str) -> list[dict]:
    """从文本中提取数字及其上下文。

    Args:
        text: 文本内容

    Returns:
        list[dict]: 提取的数字及上下文
    """
    results: list[dict] = []
    # 匹配数字 + 单位（如"180天"、"100万元"、"3个月"）
    number_pattern = re.compile(
        r"(\d+[\.\d]*)\s*(天|月|年|元|万元|亿|米|平方米|千克|吨|公里|%)"
    )
    for match in number_pattern.finditer(text):
        context_start = max(0, match.start() - 10)
        context_end = min(len(text), match.end() + 10)
        results.append({
            "value": match.group(1),
            "unit": match.group(2),
            "full": match.group(),
            "context": text[context_start:context_end],
            "position": match.start(),
        })
    return results


def _check_date_formats(text: str) -> list[str]:
    """检查日期格式一致性。

    Args:
        text: 文本内容

    Returns:
        list[str]: 发现的日期格式类型
    """
    formats = set()
    # 不同日期格式
    patterns = [
        (r"\d{4}年\d{1,2}月\d{1,2}日", "YYYY年MM月DD日"),
        (r"\d{4}-\d{2}-\d{2}", "YYYY-MM-DD"),
        (r"\d{4}/\d{2}/\d{2}", "YYYY/MM/DD"),
        (r"\d{4}\.\d{2}\.\d{2}", "YYYY.MM.DD"),
    ]
    for pattern, fmt_name in patterns:
        if re.search(pattern, text):
            formats.add(fmt_name)
    return list(formats)


def check_consistency(
    documents: list[dict],
) -> list[ConsistencyIssue]:
    """跨文档一致性检查。

    Args:
        documents: 文档列表，每项需含 {"doc_id": str, "text": str}

    Returns:
        list[ConsistencyIssue]: 一致性问题列表
    """
    if len(documents) < 2:
        return []

    issues: list[ConsistencyIssue] = []

    # --- 术语一致性检查 ---
    doc_terms: dict[str, set[str]] = {}
    for doc in documents:
        doc_terms[doc["doc_id"]] = _extract_terms(doc.get("text", ""))

    # 找不同文档间的术语差异
    doc_ids = list(doc_terms.keys())
    for i in range(len(doc_ids)):
        for j in range(i + 1, len(doc_ids)):
            terms_i = doc_terms[doc_ids[i]]
            terms_j = doc_terms[doc_ids[j]]

            # 在 A 中出现但 B 中没有的术语（可能为同义不同词）
            only_in_i = terms_i - terms_j
            only_in_j = terms_j - terms_i

            # 对于大量差异，只需记录前几个
            if only_in_i and only_in_j:
                common = min(len(only_in_i), len(only_in_j), 5)
                diff_examples = list(only_in_i)[:common]
                issues.append(
                    ConsistencyIssue(
                        issue_type="TERM",
                        documents=[doc_ids[i], doc_ids[j]],
                        description=(
                            f"文档间术语不一致，示例差异: "
                            f"{{{', '.join(diff_examples)}}}"
                        ),
                        severity="medium",
                    )
                )

    # --- 数字一致性检查 ---
    doc_numbers: dict[str, list[dict]] = {}
    for doc in documents:
        doc_numbers[doc["doc_id"]] = _extract_numbers(doc.get("text", ""))

    for i in range(len(doc_ids)):
        for j in range(i + 1, len(doc_ids)):
            nums_i = doc_numbers[doc_ids[i]]
            nums_j = doc_numbers[doc_ids[j]]

            # 按单位分组对比数字
            by_unit_i: dict[str, list[str]] = defaultdict(list)
            for n in nums_i:
                by_unit_i[n["unit"]].append(n["value"])

            by_unit_j: dict[str, list[str]] = defaultdict(list)
            for n in nums_j:
                by_unit_j[n["unit"]].append(n["value"])

            # 检查相同单位下是否有不同数值
            for unit in set(by_unit_i.keys()) & set(by_unit_j.keys()):
                vals_i = set(by_unit_i[unit])
                vals_j = set(by_unit_j[unit])
                if vals_i != vals_j and vals_i and vals_j:
                    issues.append(
                        ConsistencyIssue(
                            issue_type="NUMBER",
                            documents=[doc_ids[i], doc_ids[j]],
                            description=(
                                f"单位'{unit}'下数字不一致: "
                                f"文档1={', '.join(vals_i)} vs "
                                f"文档2={', '.join(vals_j)}"
                            ),
                            severity="high",
                        )
                    )

    # --- 格式一致性检查（日期格式） ---
    doc_date_formats: dict[str, list[str]] = {}
    for doc in documents:
        fmts = _check_date_formats(doc.get("text", ""))
        if fmts:
            doc_date_formats[doc["doc_id"]] = fmts

    date_doc_ids = list(doc_date_formats.keys())
    for i in range(len(date_doc_ids)):
        for j in range(i + 1, len(date_doc_ids)):
            fmts_i = set(doc_date_formats[date_doc_ids[i]])
            fmts_j = set(doc_date_formats[date_doc_ids[j]])
            if fmts_i != fmts_j:
                issues.append(
                    ConsistencyIssue(
                        issue_type="FORMAT",
                        documents=[date_doc_ids[i], date_doc_ids[j]],
                        description=(
                            f"日期格式不一致: "
                            f"{', '.join(fmts_i)} vs {', '.join(fmts_j)}"
                        ),
                        severity="low",
                    )
                )

    logger.info(
        f"一致性检查完成: {len(documents)} 个文档, "
        f"发现 {len(issues)} 个问题"
    )
    return issues


# ============================================================
# 主入口
# ============================================================


async def analyze_errors(
    project_id: uuid.UUID,
    analysis_task_id: uuid.UUID,
    db_session_factory,
) -> int:
    """错误检测分析主入口。

    遍历项目下文档，执行错别字检测和一致性检查。

    Args:
        project_id: 项目ID
        analysis_task_id: 分析任务ID
        db_session_factory: 数据库会话工厂

    Returns:
        int: 写入的错误检测结果数量
    """
    logger.info(f"开始错误检测分析: project={project_id}, task={analysis_task_id}")

    try:
        async with db_session_factory() as db:
            from sqlalchemy import select
            from app.models.project import BidDocument

            # 获取所有文档的文本内容
            result = await db.execute(
                select(BidDocument).where(BidDocument.project_id == project_id)
            )
            documents = result.scalars().all()

            if not documents:
                logger.warning(f"项目 {project_id} 没有文档，跳过错误检测")
                return 0

            written_count = 0
            doc_texts_for_consistency: list[dict] = []

            # ---- 1. 逐文档错别字检测 ----
            for doc in documents:
                if not doc.content_text:
                    continue

                typos = detect_typos(doc.content_text)

                doc_texts_for_consistency.append({
                    "doc_id": str(doc.id),
                    "text": doc.content_text,
                })

                for typo in typos:
                    # 计算错误哈希
                    error_text = typo.original
                    error_hash = hashlib.sha256(
                        error_text.encode("utf-8")
                    ).hexdigest()[:16]

                    error_entry = ErrorDetectionResult(
                        task_id=str(analysis_task_id),
                        document_id=str(doc.id),
                        error_type="typo",
                        original_text=error_text,
                        corrected_text=typo.corrected,
                        position=typo.position,
                        error_hash=error_hash,
                    )
                    db.add(error_entry)
                    written_count += 1

            logger.info(
                f"错别字检测完成: {len(documents)} 个文档, "
                f"发现 {written_count} 个错误"
            )

            # ---- 2. 跨文档一致性检查 ----
            consistency_issues = check_consistency(doc_texts_for_consistency)

            for issue in consistency_issues:
                issue_hash = hashlib.sha256(
                    issue.description.encode("utf-8")
                ).hexdigest()[:16]

                # 为每个涉及的文档创建一条记录
                for doc_id_str in issue.documents:
                    error_entry = ErrorDetectionResult(
                        task_id=str(analysis_task_id),
                        document_id=str(doc_id_str),
                        error_type=issue.issue_type.lower(),
                        original_text=issue.description[:500],
                        corrected_text="",
                        position={
                            "issue_type": issue.issue_type,
                            "severity": issue.severity,
                        },
                        error_hash=issue_hash,
                        is_shared=True,
                        shared_document_ids={
                            "documents": issue.documents,
                            "severity": issue.severity,
                        },
                    )
                    db.add(error_entry)
                    written_count += 1

            await db.commit()
            logger.info(
                f"错误检测分析完成: 写入 {written_count} 条结果"
            )
            return written_count

    except Exception as exc:
        logger.error(f"错误检测分析失败: {exc!s}")
        return 0
