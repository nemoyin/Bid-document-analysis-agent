"""
模板复用分析引擎。
检测不同标书是否使用了相同的文档模板（样式/布局/节/标题）。
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any, Callable, Awaitable, Optional

from loguru import logger
from sqlalchemy import or_, select

from app.models.analysis import SimilarityResult, TemplateReuseResult
from app.models.project import BidDocument


# ── DOCX 模板特征提取 ────────────────────────────────────────────────

def extract_docx_template_features(file_path: str) -> dict[str, Any]:
    """从 DOCX 提取模板级特征。

    Returns:
        dict: {
            styles: {style_name: {font_name, font_size, bold, italic}},
            layout: {margin_top, margin_bottom, margin_left, margin_right},
            sections: [{type, orientation}],
            heading_structure: [{text, level}],
        }
    """
    try:
        from docx import Document
        from docx.shared import Inches
        from docx.oxml.ns import qn

        doc = Document(file_path)

        # 1. 样式特征
        styles: dict[str, dict] = {}
        for style in doc.styles:
            if style.type is not None and style.type.name == "PARAGRAPH":
                try:
                    font = style.font
                    pf = style.paragraph_format
                    styles[style.name or ""] = {
                        "font_name": str(font.name) if font.name else "",
                        "font_size": float(font.size.pt) if font.size else 0,
                        "bold": bool(font.bold),
                        "italic": bool(font.italic),
                    }
                except Exception:
                    continue

        # 2. 布局特征（取第一节的页边距）
        layout: dict[str, float] = {}
        if doc.sections:
            sec = doc.sections[0]
            layout = {
                "margin_top": round(sec.top_margin.inches, 2) if sec.top_margin else 0,
                "margin_bottom": round(sec.bottom_margin.inches, 2) if sec.bottom_margin else 0,
                "margin_left": round(sec.left_margin.inches, 2) if sec.left_margin else 0,
                "margin_right": round(sec.right_margin.inches, 2) if sec.right_margin else 0,
            }

        # 3. 节结构
        sections: list[dict] = []
        for sec in doc.sections:
            sections.append({
                "type": str(sec.start_type) if sec.start_type else "unknown",
                "orientation": str(sec.orientation) if sec.orientation else "portrait",
            })

        # 4. 标题结构（复用 structure_similarity）
        from app.services.analysis.structure_similarity import extract_headings
        full_text = "\n".join(p.text for p in doc.paragraphs)
        heading_structure = extract_headings(full_text)

        return {
            "styles": styles,
            "layout": layout,
            "sections": sections,
            "heading_structure": heading_structure,
        }

    except Exception as exc:
        logger.warning(f"提取 DOCX 模板特征失败: {file_path!r} — {exc!s}")
        return {"styles": {}, "layout": {}, "sections": [], "heading_structure": []}


def extract_pdf_template_features(file_path: str) -> dict[str, Any]:
    """从 PDF 提取模板级特征。

    Returns:
        dict: {fonts: set[str], layout: {width, height}, heading_structure: [...]}
    """
    try:
        import fitz  # PyMuPDF

        doc = fitz.open(file_path)
        fonts: set[str] = set()
        page_boxes: list[dict] = []

        for page in doc:
            page_boxes.append({
                "width": round(page.rect.width, 1),
                "height": round(page.rect.height, 1),
            })
            try:
                for b in page.get_fonts():
                    fonts.add(b[3] if len(b) > 3 else "")
            except Exception:
                pass

        # 标题提取
        full_text = ""
        for page in doc:
            full_text += page.get_text()
        from app.services.analysis.structure_similarity import extract_headings
        heading_structure = extract_headings(full_text)

        doc.close()
        return {
            "fonts": sorted(fonts),
            "layout": page_boxes[0] if page_boxes else {},
            "sections": [],
            "heading_structure": heading_structure,
        }

    except ImportError:
        logger.debug("PyMuPDF 未安装，使用 pdfplumber 提取 PDF 模板特征")
        return _extract_pdf_features_pdfplumber(file_path)
    except Exception as exc:
        logger.warning(f"提取 PDF 模板特征失败: {file_path!r} — {exc!s}")
        return {"fonts": [], "layout": {}, "sections": [], "heading_structure": []}


def _extract_pdf_features_pdfplumber(file_path: str) -> dict[str, Any]:
    """pdfplumber 备选方案。"""
    try:
        import pdfplumber

        with pdfplumber.open(file_path) as pdf:
            boxes = []
            full_text = ""
            for page in pdf.pages:
                boxes.append({"width": round(page.width, 1), "height": round(page.height, 1)})
                full_text += (page.extract_text() or "")

            from app.services.analysis.structure_similarity import extract_headings
            return {
                "fonts": [],
                "layout": boxes[0] if boxes else {},
                "sections": [],
                "heading_structure": extract_headings(full_text),
            }
    except Exception as exc:
        logger.warning(f"pdfplumber 提取失败: {exc!s}")
        return {"fonts": [], "layout": {}, "sections": [], "heading_structure": []}


# ── 特征比对 ──────────────────────────────────────────────────────────

def _style_jaccard(styles_a: dict, styles_b: dict) -> float:
    """计算样式特征的 Jaccard 相似度（基于 font_name+font_size+bold 三元组）。"""
    if not styles_a or not styles_b:
        return 0.0

    def _to_tuples(sd: dict) -> set[tuple]:
        return {
            (v.get("font_name", ""), v.get("font_size", 0), v.get("bold", False))
            for v in sd.values()
            if v
        }

    ta = _to_tuples(styles_a)
    tb = _to_tuples(styles_b)
    if not ta and not tb:
        return 1.0
    inter = ta & tb
    union = ta | tb
    return len(inter) / len(union) if union else 0.0


def _layout_similarity(la: dict, lb: dict, tolerance: float = 0.1) -> float:
    """比较页边距布局（±tolerance 英寸内视为匹配）。"""
    keys = ["margin_top", "margin_bottom", "margin_left", "margin_right"]
    match_count = 0
    total_keys = 0
    for k in keys:
        va = la.get(k, -999)
        vb = lb.get(k, -999)
        if va == -999 or vb == -999:
            continue
        total_keys += 1
        if abs(va - vb) <= tolerance:
            match_count += 1
    return match_count / total_keys if total_keys > 0 else 0.0


def _section_similarity(sa: list, sb: list) -> float:
    """比较节结构的 LCS 相似度。"""
    if not sa and not sb:
        return 1.0
    types_a = [s.get("type", "") for s in sa]
    types_b = [s.get("type", "") for s in sb]
    from app.services.analysis.structure_similarity import _lcs_length
    lcs = _lcs_length(types_a, types_b)
    max_len = max(len(types_a), len(types_b))
    return lcs / max_len if max_len > 0 else 0.0


def compare_template_features(
    features_a: dict[str, Any],
    features_b: dict[str, Any],
) -> dict[str, float]:
    """比对两个文档的模板特征。

    Args:
        features_a: 文档A的模板特征
        features_b: 文档B的模板特征

    Returns:
        dict: {
            reuse_score, style_match_score, layout_match_score,
            heading_match_score, section_match_score,
        }
    """
    if not features_a and not features_b:
        return {
            "reuse_score": 0.0, "style_match_score": 0.0,
            "layout_match_score": 0.0, "heading_match_score": 0.0,
            "section_match_score": 0.0,
        }

    style_sim = _style_jaccard(
        features_a.get("styles", {}),
        features_b.get("styles", {}),
    )
    layout_sim = _layout_similarity(
        features_a.get("layout", {}),
        features_b.get("layout", {}),
    )
    section_sim = _section_similarity(
        features_a.get("sections", []),
        features_b.get("sections", []),
    )

    # 标题匹配（复用已有函数）
    from app.services.analysis.structure_similarity import compare_heading_sequences
    heading_sim = compare_heading_sequences(
        features_a.get("heading_structure", []),
        features_b.get("heading_structure", []),
    )

    # 加权融合
    reuse = (
        style_sim * 0.4
        + layout_sim * 0.3
        + heading_sim * 0.2
        + section_sim * 0.1
    )

    return {
        "reuse_score": round(min(max(reuse, 0.0), 1.0), 4),
        "style_match_score": round(style_sim, 4),
        "layout_match_score": round(layout_sim, 4),
        "heading_match_score": round(heading_sim, 4),
        "section_match_score": round(section_sim, 4),
    }


# ── 编排器兼容入口 ────────────────────────────────────────────────────

async def analyze_template_reuse(
    project_id: uuid.UUID,
    analysis_task_id: uuid.UUID,
    db_session_factory,
    on_progress: Optional[Callable[[int], Awaitable[None]]] = None,
) -> int:
    """分析项目文档间的模板复用度。

    Args:
        project_id: 项目ID
        analysis_task_id: 分析任务ID
        db_session_factory: 数据库会话工厂

    Returns:
        int: 创建的 TemplateReuseResult 数量
    """
    logger.info(f"开始模板复用分析: project={project_id}")

    try:
        async with db_session_factory() as db:
            result = await db.execute(
                select(BidDocument).where(
                    BidDocument.project_id == str(project_id),
                    BidDocument.parse_status == "completed",
                )
            )
            documents = result.scalars().all()

            if len(documents) < 2:
                logger.info("文档数量不足，跳过模板复用分析")
                return 0

            created_count = 0
            doc_ids = [str(d.id) for d in documents]
            doc_paths = {str(d.id): d.file_path for d in documents}
            total_pairs = len(doc_ids) * (len(doc_ids) - 1) // 2
            pair_count = 0

            for i in range(len(doc_ids)):
                for j in range(i + 1, len(doc_ids)):
                    pair_count += 1
                    doc_a = doc_ids[i]
                    doc_b = doc_ids[j]

                    # 根据文件类型提取特征
                    path_a = doc_paths.get(doc_a, "")
                    path_b = doc_paths.get(doc_b, "")

                    if path_a.endswith(".docx") and path_b.endswith(".docx"):
                        fa = extract_docx_template_features(path_a)
                        fb = extract_docx_template_features(path_b)
                    elif path_a.endswith(".pdf") and path_b.endswith(".pdf"):
                        fa = extract_pdf_template_features(path_a)
                        fb = extract_pdf_template_features(path_b)
                    else:
                        # 不同类型文件无法直接比对模板
                        fa = fb = {}

                    comparison = compare_template_features(fa, fb)

                    # 创建 TemplateReuseResult
                    db_result = TemplateReuseResult(
                        id=str(uuid.uuid4()),
                        task_id=str(analysis_task_id),
                        doc1_id=doc_a,
                        doc2_id=doc_b,
                        reuse_score=Decimal(str(round(comparison["reuse_score"] * 100, 2))),
                        style_match_score=Decimal(str(round(comparison["style_match_score"] * 100, 2))),
                        layout_match_score=Decimal(str(round(comparison["layout_match_score"] * 100, 2))),
                        heading_match_score=Decimal(str(round(comparison["heading_match_score"] * 100, 2))),
                        section_match_score=Decimal(str(round(comparison["section_match_score"] * 100, 2))),
                        details={
                            "styles_a_count": len(fa.get("styles", {})),
                            "styles_b_count": len(fb.get("styles", {})),
                            "comparison": comparison,
                        },
                    )
                    db.add(db_result)
                    created_count += 1

                    if on_progress and pair_count % max(1, total_pairs // 10) == 0:
                        try:
                            await on_progress(pair_count)
                        except Exception:
                            pass

            await db.commit()
            logger.info(f"模板复用分析完成: 创建 {created_count} 条记录")
            return created_count

    except Exception as exc:
        logger.error(f"模板复用分析失败: {exc!s}")
        return 0
