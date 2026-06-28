"""
分析任务编排器。
协调文本相似度、图片相似度、错误检测三大分析引擎，
管理分析任务的整个生命周期。
支持6维度细粒度进度追踪。
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional, ClassVar

import copy

from loguru import logger
from sqlalchemy import select, func as sa_func
from sqlalchemy.orm.attributes import flag_modified

from app.core.config import settings
from app.models.analysis import AnalysisTask
from app.schemas.common import RiskLevel
# 配置文件路径
_CONFIG_FILE: ClassVar[Path] = Path(settings.ROOT_DIR) / "data" / "analysis_config.json"

# 8维度元数据 (V1.1)：key, 显示名, 权重, 预计每对比秒数
DIMENSIONS: ClassVar[list[dict[str, Any]]] = [
    {"key": "text_similarity",        "weight": 0.25, "seconds_per": 5},
    {"key": "structure_similarity",   "weight": 0.10, "seconds_per": 3},
    {"key": "image_similarity",       "weight": 0.12, "seconds_per": 8},
    {"key": "table_similarity",       "weight": 0.08, "seconds_per": 5},
    {"key": "error_consistency",      "weight": 0.15, "seconds_per": 10},
    {"key": "metadata_consistency",   "weight": 0.08, "seconds_per": 3},
    {"key": "template_reuse",         "weight": 0.10, "seconds_per": 8},
    {"key": "electronic_signature",   "weight": 0.12, "seconds_per": 3},
]
def _load_analysis_config() -> dict:
    """读取持久化的分析配置，如果文件不存在则使用代码默认值。"""
    defaults = {
        "text_similarity_weight": settings.TEXT_SIMILARITY_WEIGHT,
        "structure_similarity_weight": settings.STRUCTURE_SIMILARITY_WEIGHT,
        "image_similarity_weight": settings.IMAGE_SIMILARITY_WEIGHT,
        "table_similarity_weight": settings.TABLE_SIMILARITY_WEIGHT,
        "error_consistency_weight": settings.ERROR_CONSISTENCY_WEIGHT,
        "metadata_consistency_weight": settings.METADATA_CONSISTENCY_WEIGHT,
        "template_reuse_weight": 0.10,
        "electronic_signature_weight": 0.12,
        "risk_low": settings.RISK_LEVEL_LOW,
        "risk_medium": settings.RISK_LEVEL_MEDIUM,
        "risk_high": settings.RISK_LEVEL_HIGH,
    }
    if _CONFIG_FILE.exists():
        try:
            with open(_CONFIG_FILE, encoding="utf-8") as f:
                persisted = json.load(f)
                defaults.update({k: v for k, v in persisted.items() if k in defaults})
        except (json.JSONDecodeError, OSError):
            pass
    return defaults
class AnalysisOrchestrator:
    """分析任务编排器。

    协调多阶段分析流程，管理任务状态和进度更新。
    """

    def __init__(self, db_session_factory):
        """初始化编排器。

        Args:
            db_session_factory: 数据库会话工厂
        """
        self.db_session_factory = db_session_factory

    async def _update_task_status(
        self, task_id: uuid.UUID, status: str, progress: int = 0,
        error_message: Optional[str] = None,
    ) -> None:
        """更新分析任务状态。

        Args:
            task_id: 任务ID
            status: 新状态
            progress: 进度百分比
            error_message: 错误信息（可选）
        """
        try:
            async with self.db_session_factory() as db:
                result = await db.execute(
                    select(AnalysisTask).where(AnalysisTask.id == task_id)
                )
                task = result.scalar_one_or_none()
                if task:
                    task.status = status
                    task.progress = progress
                    if error_message:
                        task.error_message = error_message
                    if status == "analyzing":
                        task.started_at = datetime.now(timezone.utc)
                    elif status in ("completed", "failed"):
                        task.completed_at = datetime.now(timezone.utc)
                    await db.commit()
        except Exception as exc:
            logger.error(f"更新任务状态失败: {exc!s}")

    async def _update_progress_detail(
        self,
        task_id: uuid.UUID,
        progress_detail: dict[str, Any],
    ) -> None:
        """更新分析任务的详细进度信息。

        Args:
            task_id: 任务ID
            progress_detail: 进度详情 dict，会与现有 progress_detail 合并
        """
        try:
            async with self.db_session_factory() as db:
                result = await db.execute(
                    select(AnalysisTask).where(AnalysisTask.id == task_id)
                )
                task = result.scalar_one_or_none()
                if not task:
                    return

                # 合并 progress_detail（深拷贝确保 SQLAlchemy 检测到变更）
                existing = copy.deepcopy(task.progress_detail) if task.progress_detail else {}
                existing.update(progress_detail)
                task.progress_detail = existing
                flag_modified(task, "progress_detail")

                # 同步更新独立列
                if "completed_comparisons" in progress_detail:
                    task.completed_comparisons = progress_detail["completed_comparisons"]
                if "issues_found" in progress_detail:
                    task.issues_found = progress_detail["issues_found"]
                if "estimated_seconds" in progress_detail:
                    task.estimated_seconds = progress_detail["estimated_seconds"]
                if "total_comparisons" in progress_detail:
                    task.total_comparisons = progress_detail["total_comparisons"]

                # 计算新的加权进度
                weighted = self._calculate_weighted_progress(existing)
                task.progress = weighted

                await db.commit()
        except Exception as exc:
            logger.error(f"更新进度详情失败: {exc!s}")

    @staticmethod
    def _calculate_weighted_progress(detail: dict) -> int:
        """根据6维度完成度计算加权总进度百分比，并同步 overall_progress。

        Args:
            detail: progress_detail JSON

        Returns:
            int: 0-100 的进度百分比
        """
        if not detail:
            return 0

        dims = detail.get("dimensions", {})
        if not dims:
            return detail.get("overall_progress", 0)

        total_weighted = 0.0
        total_weight = 0.0
        for dim in DIMENSIONS:
            key = dim["key"]
            weight = dim["weight"]
            total_weight += weight
            dim_info = dims.get(key, {})
            status = dim_info.get("status", "pending")
            if status == "completed":
                total_weighted += weight
            elif status == "running":
                completed = dim_info.get("completed", 0)
                total = dim_info.get("total", 1)
                if total > 0:
                    total_weighted += weight * (completed / total)

        if total_weight == 0:
            return 0
        result = int(total_weighted / total_weight * 100)
        # 同步 overall_progress 字段，保持与顶层 progress 一致
        detail["overall_progress"] = result
        return result

    @staticmethod
    def _calculate_eta(detail: dict) -> int:
        """根据剩余对比计算预计剩余秒数。

        公式: Σ(剩余对比数 × 维度耗时秒数) for each pending/running dimension

        Args:
            detail: progress_detail JSON

        Returns:
            int: 预计剩余秒数
        """
        dims = detail.get("dimensions", {})
        total_eta = 0
        for dim in DIMENSIONS:
            key = dim["key"]
            dim_info = dims.get(key, {})
            if not dim_info:
                continue
            status = dim_info.get("status", "pending")
            if status == "completed":
                continue
            total = dim_info.get("total", 0)
            completed = dim_info.get("completed", 0)
            remaining = max(0, total - completed)
            total_eta += remaining * dim["seconds_per"]
        return total_eta

    async def _update_dimension_status(
        self,
        task_id: uuid.UUID,
        dim_key: str,
        status: str,
        completed: int = 0,
    ) -> None:
        """更新单个维度的状态，并刷新 issues_found / ETA / 加权进度。

        Args:
            task_id: 任务ID
            dim_key: 维度 key (见 DIMENSIONS)
            status: "running" | "completed"
            completed: 已完成的对比数
        """
        try:
            async with self.db_session_factory() as db:
                result = await db.execute(
                    select(AnalysisTask).where(AnalysisTask.id == task_id)
                )
                task = result.scalar_one_or_none()
                if not task:
                    return

                # 深拷贝确保 SQLAlchemy 检测嵌套 dict 变更
                detail = copy.deepcopy(task.progress_detail) if task.progress_detail else {}
                dims = detail.get("dimensions", {})
                if dim_key not in dims:
                    dims[dim_key] = {"status": "pending", "completed": 0, "total": 1}

                dims[dim_key]["status"] = status
                if completed > 0:
                    dims[dim_key]["completed"] = completed
                # 如果 completed 没传但状态是 completed，设 completed=total
                if status == "completed" and dims[dim_key].get("completed", 0) == 0:
                    dims[dim_key]["completed"] = dims[dim_key].get("total", 0)

                detail["dimensions"] = dims
                if status == "running":
                    detail["current_dimension"] = dim_key

                task.progress_detail = detail
                flag_modified(task, "progress_detail")
                task.progress = self._calculate_weighted_progress(detail)
                task.estimated_seconds = self._calculate_eta(detail)

                # 累计已完成对比数
                total_completed = sum(
                    d.get("completed", 0) for d in dims.values()
                    if d.get("status") == "completed"
                )
                task.completed_comparisons = total_completed

                # 实时刷新 issues_found
                task.issues_found = await self._count_issues_so_far(task_id, db=db)

                task.progress_detail = detail
                flag_modified(task, "progress_detail")

                await db.commit()
        except Exception as exc:
            logger.error(f"更新维度状态失败: {exc!s}")

    async def _increment_dimension_progress(
        self,
        task_id: uuid.UUID,
        dim_key: str,
        increment: int = 1,
    ) -> None:
        """增量更新某个维度的已完成对比数（用于维度内细粒度进度上报）。

        与 _update_dimension_status 不同，此方法仅更新 completed 计数，
        不改变维度状态，适合在维度分析过程中频繁调用。

        Args:
            task_id: 任务ID
            dim_key: 维度 key
            increment: 增量（默认+1），调用方每完成一项对比调用一次
        """
        try:
            async with self.db_session_factory() as db:
                result = await db.execute(
                    select(AnalysisTask).where(AnalysisTask.id == task_id)
                )
                task = result.scalar_one_or_none()
                if not task:
                    return

                detail = copy.deepcopy(task.progress_detail) if task.progress_detail else {}
                dims = detail.get("dimensions", {})
                if dim_key not in dims:
                    dims[dim_key] = {"status": "running", "completed": 0, "total": 1}
                dims[dim_key]["completed"] = min(
                    dims[dim_key].get("completed", 0) + increment,
                    dims[dim_key].get("total", 1),
                )

                detail["dimensions"] = dims
                task.progress_detail = detail
                flag_modified(task, "progress_detail")
                task.progress = self._calculate_weighted_progress(detail)
                task.estimated_seconds = self._calculate_eta(detail)

                await db.commit()
        except Exception as exc:
            logger.warning(f"增量更新维度进度失败 ({dim_key}): {exc!s}")

    async def _count_issues_so_far(
        self, task_id: uuid.UUID, db=None
    ) -> int:
        """统计当前任务已发现的各类问题总数。"""
        total = 0
        try:
            from app.models.analysis import (
                SimilarityResult,
                ErrorDetectionResult,
                ImageSimilarityResult,
            )
            task_id_str = str(task_id)

            async def _query(session):
                nonlocal total
                sim_count = await session.execute(
                    select(sa_func.count(SimilarityResult.id)).where(
                        SimilarityResult.task_id == task_id_str,
                        SimilarityResult.full_text_similarity >= 80,
                    )
                )
                total += sim_count.scalar() or 0
                err_count = await session.execute(
                    select(sa_func.count(ErrorDetectionResult.id)).where(
                        ErrorDetectionResult.task_id == task_id_str,
                    )
                )
                total += err_count.scalar() or 0
                img_count = await session.execute(
                    select(sa_func.count(ImageSimilarityResult.id)).where(
                        ImageSimilarityResult.task_id == task_id_str,
                        ImageSimilarityResult.similar_image_id.isnot(None),
                    )
                )
                total += img_count.scalar() or 0

            if db is not None:
                await _query(db)
            else:
                async with self.db_session_factory() as session:
                    await _query(session)
        except Exception as exc:
            logger.warning(f"统计问题数失败: {exc!s}")
        return total

    def calculate_risk_score(
        self,
        text_score: float,
        structure_score: float,
        image_score: float,
        table_score: float,
        error_score: float,
        metadata_score: float,
        template_reuse_score: float = 0.0,
        electronic_signature_score: float = 0.0,
    ) -> float:
        """计算综合风险评分（V1.1：8维度）。

        公式 (权重和为 1.0，对应满分 100 分)

        Args:
            text_score: 文本相似度评分 (0.0 - 1.0)
            structure_score: 目录结构相似度评分 (0.0 - 1.0)
            image_score: 图片相似度评分 (0.0 - 1.0)
            table_score: 表格相似度评分 (0.0 - 1.0)
            error_score: 错误一致性评分 (0.0 - 1.0)
            metadata_score: 元数据一致性评分 (0.0 - 1.0)
            template_reuse_score: 模板复用评分 (0.0 - 1.0) [V1.1]
            electronic_signature_score: 电子签名评分 (0.0 - 1.0) [V1.1]

        Returns:
            float: 综合风险评分 (0.0 - 1.0)
        """
        cfg = _load_analysis_config()
        tw = cfg.get("text_similarity_weight", 0.25)
        sw = cfg.get("structure_similarity_weight", 0.10)
        iw = cfg.get("image_similarity_weight", 0.12)
        tbw = cfg.get("table_similarity_weight", 0.08)
        ew = cfg.get("error_consistency_weight", 0.15)
        mw = cfg.get("metadata_consistency_weight", 0.08)
        trw = cfg.get("template_reuse_weight", 0.10)
        esw = cfg.get("electronic_signature_weight", 0.12)

        risk = (
            text_score * tw
            + structure_score * sw
            + image_score * iw
            + table_score * tbw
            + error_score * ew
            + metadata_score * mw
            + template_reuse_score * trw
            + electronic_signature_score * esw
        )
        return min(max(risk, 0.0), 1.0)

    def risk_to_level(self, score: float) -> RiskLevel:
        """将风险分数映射到风险等级。

        Args:
            score: 风险评分 (0.0 - 1.0)

        Returns:
            RiskLevel: 风险等级
        """
        cfg = _load_analysis_config()
        low_threshold = cfg.get("risk_low", 0.3)
        medium_threshold = cfg.get("risk_medium", 0.6)
        high_threshold = cfg.get("risk_high", 0.85)

        if score >= high_threshold:
            return RiskLevel.CRITICAL
        elif score >= medium_threshold:
            return RiskLevel.HIGH
        elif score >= low_threshold:
            return RiskLevel.MODERATE
        return RiskLevel.LOW

    async def run_analysis(
        self,
        project_id: uuid.UUID,
        analysis_task_id: uuid.UUID,
    ) -> dict[str, Any]:
        """执行完整分析流程（主编排函数）。

        阶段：
        1. 初始化（pending→analyzing）
        2. 文本相似度分析 (0-35%)
        3. 图片相似度分析 (35-55%)
        4. 错误检测分析 (55-80%)
        5. 综合评分 (80-100%)

        Args:
            project_id: 项目ID
            analysis_task_id: 分析任务ID

        Returns:
            dict: 分析结果汇总
        """
        task_id = analysis_task_id
        logger.info(f"启动分析任务: task={task_id}, project={project_id}")

        result = {
            "task_id": str(task_id),
            "project_id": str(project_id),
            "text_similarity_count": 0,
            "image_similarity_count": 0,
            "error_detection_count": 0,
            "risk_score": 0.0,
            "risk_level": "LOW",
            "status": "running",
        }

        # ---- 阶段0：初始化 ----
        await self._update_task_status(task_id, "analyzing", progress=0)

        # 统计文档数，用于计算各维度总对比数
        doc_count = 0
        try:
            async with self.db_session_factory() as db:
                from app.models.project import BidDocument
                cnt_result = await db.execute(
                    select(sa_func.count(BidDocument.id)).where(
                        BidDocument.project_id == project_id
                    )
                )
                doc_count = cnt_result.scalar() or 0
        except Exception:
            doc_count = 1

        # 计算各维度总对比数
        doc_pairs = max(1, doc_count * (doc_count - 1) // 2)  # C(n,2)

        # 初始化6维度进度
        init_dimensions = {}
        total_comps = 0
        for dim in DIMENSIONS:
            key = dim["key"]
            if key in ("error_consistency",):
                total_dim = max(1, doc_count)
            elif key in ("image_similarity",):
                total_dim = max(1, doc_count * 3)  # 每文档估计提取3张图片
            else:
                total_dim = doc_pairs
            init_dimensions[key] = {"status": "pending", "completed": 0, "total": total_dim}
            total_comps += total_dim

        progress_detail_init = {
            "current_dimension": None,
            "dimensions": init_dimensions,
            "overall_progress": 0,
        }

        await self._update_progress_detail(task_id, {
            **progress_detail_init,
            "total_comparisons": total_comps,
            "estimated_seconds": self._calculate_eta(progress_detail_init),
        })
        logger.info(f"[阶段0/9] 6维度进度初始化: 总对比={total_comps}")

        # ---- 阶段1：文档解析（调用 T03 的解析器，如果文档尚未解析） ----
        await self._update_task_status(task_id, "analyzing", progress=5)
        try:
            await self._ensure_documents_parsed(project_id)
        except Exception as exc:
            logger.warning(f"[阶段1/9] 文档解析准备异常: {exc!s}")
        logger.info(f"[阶段1/9] 文档解析准备完成")

        # ---- 阶段2：Embedding + ChromaDB 向量化 ----
        await self._update_task_status(task_id, "analyzing", progress=15)
        try:
            await self._ensure_embeddings(project_id)
        except Exception as exc:
            logger.warning(f"[阶段2/9] 向量化异常: {exc!s}")
        logger.info(f"[阶段2/9] 向量化完成")

        # ---- 阶段3：文本相似度分析 ----
        await self._update_progress_detail(task_id, {
            "current_dimension": "text_similarity",
        })
        await self._update_dimension_status(task_id, "text_similarity", "running")
        text_result_count = 0

        _text_last_reported = [0]  # 闭包可变引用
        async def _on_text_progress(completed: int) -> None:
            """文本相似度维度内进度回调"""
            inc = completed - _text_last_reported[0]
            _text_last_reported[0] = completed
            if inc > 0:
                await self._increment_dimension_progress(
                    task_id, "text_similarity", increment=inc,
                )

        try:
            from app.services.analysis.text_similarity import analyze_text_similarity
            from app.services.chroma_manager import ChromaManager

            chroma_manager = ChromaManager()
            try:
                collection_name = f"project_{project_id}_documents"
                collection = chroma_manager.client.get_collection(
                    name=collection_name
                )
            except Exception:
                logger.warning(f"ChromaDB 集合 '{collection_name}' 不存在，跳过文本相似度分析")
                collection = None

            if collection:
                text_result_count = await analyze_text_similarity(
                    project_id=project_id,
                    analysis_task_id=task_id,
                    chroma_collection=collection,
                    db_session_factory=self.db_session_factory,
                    on_progress=_on_text_progress,
                )
                result["text_similarity_count"] = text_result_count
        except Exception as exc:
            logger.error(f"[阶段3/9] 文本相似度分析失败: {exc!s}")
        finally:
            await self._update_dimension_status(task_id, "text_similarity", "completed",
                completed=doc_pairs)
        logger.info(f"[阶段3/9] 文本相似度分析完成: {text_result_count} 条结果")

        # ---- 阶段4：目录结构相似度分析 ----
        await self._update_progress_detail(task_id, {
            "current_dimension": "structure_similarity",
        })
        await self._update_dimension_status(task_id, "structure_similarity", "running")
        structure_result_count = 0

        _struct_last_reported = [0]
        async def _on_structure_progress(completed: int) -> None:
            inc = completed - _struct_last_reported[0]
            _struct_last_reported[0] = completed
            if inc > 0:
                await self._increment_dimension_progress(
                    task_id, "structure_similarity", increment=inc,
                )

        try:
            from app.services.analysis.structure_similarity import (
                analyze_structure_similarity,
            )
            structure_result_count = await analyze_structure_similarity(
                project_id=project_id,
                analysis_task_id=task_id,
                db_session_factory=self.db_session_factory,
                on_progress=_on_structure_progress,
            )
            result["structure_similarity_count"] = structure_result_count
        except Exception as exc:
            logger.error(f"[阶段4/9] 目录结构相似度分析失败: {exc!s}")
        finally:
            await self._update_dimension_status(task_id, "structure_similarity", "completed",
                completed=doc_pairs)
        logger.info(f"[阶段4/9] 目录结构相似度分析完成: {structure_result_count} 条结果")

        # ---- 阶段5：图片相似度分析 ----
        await self._update_progress_detail(task_id, {
            "current_dimension": "image_similarity",
        })
        await self._update_dimension_status(task_id, "image_similarity", "running")
        image_result_count = 0

        _img_last_reported = [0]
        async def _on_image_progress(completed: int) -> None:
            inc = completed - _img_last_reported[0]
            _img_last_reported[0] = completed
            if inc > 0:
                await self._increment_dimension_progress(
                    task_id, "image_similarity", increment=inc,
                )

        try:
            from app.services.analysis.image_similarity import analyze_image_similarity

            image_result_count = await analyze_image_similarity(
                project_id=project_id,
                analysis_task_id=task_id,
                db_session_factory=self.db_session_factory,
                on_progress=_on_image_progress,
            )
            result["image_similarity_count"] = image_result_count
        except Exception as exc:
            logger.error(f"[阶段5/9] 图片相似度分析失败: {exc!s}")
        finally:
            img_total = max(1, doc_count * 3)
            await self._update_dimension_status(task_id, "image_similarity", "completed",
                completed=img_total)
        logger.info(f"[阶段5/9] 图片相似度分析完成: {image_result_count} 条结果")

        # ---- 阶段6：表格相似度分析 ----
        await self._update_progress_detail(task_id, {
            "current_dimension": "table_similarity",
        })
        await self._update_dimension_status(task_id, "table_similarity", "running")
        table_result_count = 0

        _tbl_last_reported = [0]
        async def _on_table_progress(completed: int) -> None:
            inc = completed - _tbl_last_reported[0]
            _tbl_last_reported[0] = completed
            if inc > 0:
                await self._increment_dimension_progress(
                    task_id, "table_similarity", increment=inc,
                )

        try:
            from app.services.analysis.table_similarity import (
                analyze_table_similarity,
            )
            table_result_count = await analyze_table_similarity(
                project_id=project_id,
                analysis_task_id=task_id,
                db_session_factory=self.db_session_factory,
                on_progress=_on_table_progress,
            )
            result["table_similarity_count"] = table_result_count
        except Exception as exc:
            logger.error(f"[阶段6/9] 表格相似度分析失败: {exc!s}")
        finally:
            await self._update_dimension_status(task_id, "table_similarity", "completed",
                completed=doc_pairs)
        logger.info(f"[阶段6/9] 表格相似度分析完成: {table_result_count} 条结果")

        # ---- 阶段7：错误检测分析 ----
        await self._update_progress_detail(task_id, {
            "current_dimension": "error_consistency",
        })
        await self._update_dimension_status(task_id, "error_consistency", "running")
        error_result_count = 0

        _err_last_reported = [0]
        async def _on_error_progress(completed: int) -> None:
            inc = completed - _err_last_reported[0]
            _err_last_reported[0] = completed
            if inc > 0:
                await self._increment_dimension_progress(
                    task_id, "error_consistency", increment=inc,
                )

        try:
            from app.services.analysis.error_detection import analyze_errors

            error_result_count = await analyze_errors(
                project_id=project_id,
                analysis_task_id=task_id,
                db_session_factory=self.db_session_factory,
                on_progress=_on_error_progress,
            )
            result["error_detection_count"] = error_result_count
        except Exception as exc:
            logger.error(f"[阶段7/9] 错误检测分析失败: {exc!s}")
        finally:
            err_total = max(1, doc_count)
            await self._update_dimension_status(task_id, "error_consistency", "completed",
                completed=err_total)
        logger.info(f"[阶段7/9] 错误检测分析完成: {error_result_count} 条结果")

        # ---- 阶段8：元数据一致性分析 ----
        await self._update_progress_detail(task_id, {
            "current_dimension": "metadata_consistency",
        })
        await self._update_dimension_status(task_id, "metadata_consistency", "running")
        metadata_result_count = 0

        _meta_last_reported = [0]
        async def _on_metadata_progress(completed: int) -> None:
            inc = completed - _meta_last_reported[0]
            _meta_last_reported[0] = completed
            if inc > 0:
                await self._increment_dimension_progress(
                    task_id, "metadata_consistency", increment=inc,
                )

        try:
            from app.services.analysis.metadata_consistency import (
                analyze_metadata_consistency,
            )
            metadata_result_count = await analyze_metadata_consistency(
                project_id=project_id,
                analysis_task_id=task_id,
                db_session_factory=self.db_session_factory,
                on_progress=_on_metadata_progress,
            )
            result["metadata_consistency_count"] = metadata_result_count
        except Exception as exc:
            logger.error(f"[阶段8/9] 元数据一致性分析失败: {exc!s}")
        finally:
            await self._update_dimension_status(task_id, "metadata_consistency", "completed",
                completed=doc_pairs)
        logger.info(f"[阶段8/10] 元数据一致性分析完成: {metadata_result_count} 条结果")

        # ---- 阶段8.1：模板复用分析 (V1.1) ----
        await self._update_progress_detail(task_id, {
            "current_dimension": "template_reuse",
        })
        await self._update_dimension_status(task_id, "template_reuse", "running")
        template_reuse_result_count = 0

        _tmpl_last_reported = [0]
        async def _on_template_reuse_progress(completed: int) -> None:
            inc = completed - _tmpl_last_reported[0]
            _tmpl_last_reported[0] = completed
            if inc > 0:
                await self._increment_dimension_progress(
                    task_id, "template_reuse", increment=inc,
                )

        try:
            from app.services.analysis.template_reuse import analyze_template_reuse
            template_reuse_result_count = await analyze_template_reuse(
                project_id=project_id,
                analysis_task_id=task_id,
                db_session_factory=self.db_session_factory,
                on_progress=_on_template_reuse_progress,
            )
            result["template_reuse_count"] = template_reuse_result_count
        except Exception as exc:
            logger.error(f"[阶段8.1/10] 模板复用分析失败: {exc!s}")
        finally:
            await self._update_dimension_status(task_id, "template_reuse", "completed",
                completed=doc_pairs)
        logger.info(f"[阶段8.1/10] 模板复用分析完成: {template_reuse_result_count} 条结果")

        # ---- 阶段8.2：电子标书特征检测 (V1.1) ----
        await self._update_progress_detail(task_id, {
            "current_dimension": "electronic_signature",
        })
        await self._update_dimension_status(task_id, "electronic_signature", "running")
        electronic_signature_result_count = 0

        _esig_last_reported = [0]
        async def _on_electronic_signature_progress(completed: int) -> None:
            inc = completed - _esig_last_reported[0]
            _esig_last_reported[0] = completed
            if inc > 0:
                await self._increment_dimension_progress(
                    task_id, "electronic_signature", increment=inc,
                )

        try:
            from app.services.analysis.electronic_signature import (
                analyze_electronic_signature,
            )
            electronic_signature_result_count = await analyze_electronic_signature(
                project_id=project_id,
                analysis_task_id=task_id,
                db_session_factory=self.db_session_factory,
                on_progress=_on_electronic_signature_progress,
            )
            result["electronic_signature_count"] = electronic_signature_result_count
        except Exception as exc:
            logger.error(f"[阶段8.2/10] 电子标书特征检测失败: {exc!s}")
        finally:
            await self._update_dimension_status(task_id, "electronic_signature", "completed",
                completed=doc_pairs)
        logger.info(
            f"[阶段8.2/10] 电子标书特征检测完成: {electronic_signature_result_count} 条结果"
        )

        # ---- 阶段9：综合评分 ----
        try:
            await self._update_progress_detail(task_id, {
                "current_dimension": None,
            })
        except Exception:
            pass  # 进度更新失败不影响最终评分

        # 计算各维度评分（V1.1：8维度）
        text_score = await self._compute_text_score(task_id)
        structure_score = await self._compute_structure_score(task_id)
        image_score = self._compute_image_score(image_result_count)
        table_score = await self._compute_table_score(task_id)
        error_score = self._compute_error_score(error_result_count)
        metadata_score = await self._compute_metadata_score(task_id)
        template_reuse_score = await self._compute_template_reuse_score(task_id)
        electronic_signature_score = await self._compute_electronic_signature_score(task_id)
        combined_score = self.calculate_risk_score(
            text_score, structure_score, image_score,
            table_score, error_score, metadata_score,
            template_reuse_score, electronic_signature_score,
        )
        risk_level = self.risk_to_level(combined_score)

        result["text_score"] = round(text_score, 4)
        result["structure_score"] = round(structure_score, 4)
        result["image_score"] = round(image_score, 4)
        result["table_score"] = round(table_score, 4)
        result["error_score"] = round(error_score, 4)
        result["metadata_score"] = round(metadata_score, 4)
        result["template_reuse_score"] = round(template_reuse_score, 4)
        result["electronic_signature_score"] = round(electronic_signature_score, 4)
        result["risk_score"] = round(combined_score, 4)
        result["risk_level"] = risk_level.value

        # 更新任务完成状态，写入维度评分
        try:
            async with self.db_session_factory() as db:
                task_result = await db.execute(
                    select(AnalysisTask).where(AnalysisTask.id == task_id)
                )
                task = task_result.scalar_one_or_none()
                if task:
                    task.status = "completed"
                    task.progress = 100
                    task.risk_score = Decimal(str(round(combined_score * 100, 2)))
                    task.risk_level = risk_level.value
                    now = datetime.now(timezone.utc)
                    task.completed_at = now
                    # 计算并持久化总耗时 (毫秒)
                    # 使用 timedelta 直接计算，避免 timestamp() 的时区陷阱
                    if task.started_at:
                        try:
                            started = task.started_at
                            # 确保是 UTC-aware：SQLite 可能丢失时区信息
                            if started.tzinfo is None:
                                from datetime import timezone as _tz
                                started = started.replace(tzinfo=_tz.utc)
                            # 使用 timedelta 直接计算，比 timestamp() 更可靠
                            task.total_duration_ms = int(
                                (now - started).total_seconds() * 1000
                            )
                        except Exception:
                            task.total_duration_ms = 0
                    # 8维度评分写入 error_message 字段（JSON 格式）[V1.1]
                    import json as _json
                    task.error_message = _json.dumps({
                        "text_score": round(text_score, 4),
                        "structure_score": round(structure_score, 4),
                        "image_score": round(image_score, 4),
                        "table_score": round(table_score, 4),
                        "error_score": round(error_score, 4),
                        "metadata_score": round(metadata_score, 4),
                        "template_reuse_score": round(template_reuse_score, 4),
                        "electronic_signature_score": round(electronic_signature_score, 4),
                    }, ensure_ascii=False)
                    # 同步更新项目的风险等级和评分
                    from app.models.project import Project
                    proj_result = await db.execute(
                        select(Project).where(Project.id == project_id)
                    )
                    project = proj_result.scalar_one_or_none()
                    if project:
                        project.risk_level = risk_level.value
                        project.average_score = Decimal(str(round(combined_score * 100, 2)))
                        # 同步更新项目文档计数
                        from sqlalchemy import func as sa_func
                        from app.models.project import BidDocument
                        cnt_result = await db.execute(
                            select(sa_func.count(BidDocument.id)).where(
                                BidDocument.project_id == project_id
                            )
                        )
                        project.file_count = cnt_result.scalar() or 0

                    await db.commit()
        except Exception as exc:
            logger.error(f"更新任务完成状态失败: {exc!s}")

        result["status"] = "completed"
        logger.info(
            f"分析任务完成: task={task_id}, "
            f"risk_score={combined_score:.2%}, "
            f"risk_level={risk_level.value}"
        )
        return result

    async def _ensure_documents_parsed(self, project_id: uuid.UUID) -> None:
        """确保项目下的文档已被解析。"""
        async with self.db_session_factory() as db:
            from app.models.project import BidDocument

            result = await db.execute(
                select(BidDocument).where(
                    BidDocument.project_id == project_id,
                )
            )
            docs = result.scalars().all()

            for doc in docs:
                if doc.parse_status in ("uploaded", "pending", "failed"):
                    logger.info(
                        f"文档 {doc.id} 尚未解析（状态: {doc.parse_status}），"
                        f"请先通过 upload/parse API 触发解析"
                    )

    async def _ensure_embeddings(self, project_id: uuid.UUID) -> None:
        """确保项目文档的向量已存在。"""
        from app.services.chroma_manager import ChromaManager

        chroma_manager = ChromaManager()
        try:
            collection_name = f"project_{project_id}_documents"
            collection = chroma_manager.client.get_collection(
                name=collection_name
            )
            count = collection.count()
            logger.info(f"ChromaDB 集合已有 {count} 条向量")
        except Exception:
            logger.info("ChromaDB 集合尚不存在（将在文本相似度阶段按需创建）")

    async def _compute_text_score(
        self, task_id: uuid.UUID
    ) -> float:
        """计算文本相似度评分。

        从 SimilarityResult 表读取实际的相似度值，
        取最高值作为文本相似度评分。

        Args:
            task_id: 分析任务ID

        Returns:
            float: 评分 (0.0 - 1.0)
        """
        try:
            from app.models.analysis import SimilarityResult
            from sqlalchemy import select, func as sa_func

            async with self.db_session_factory() as db:
                # 查出本任务所有相似度结果中的最高 full_text_similarity
                query = select(
                    sa_func.max(SimilarityResult.full_text_similarity)
                ).where(SimilarityResult.task_id == task_id)
                result = await db.execute(query)
                max_sim = result.scalar()
                if max_sim is not None:
                    val = float(max_sim) / 100.0  # DB 存的是 99.99，归一化到 0-1
                    return min(max(val, 0.0), 1.0)
                return 0.0
        except Exception as exc:
            logger.error(f"计算文本相似度评分失败: {exc!s}")
            return 0.0

    async def _compute_structure_score(
        self, task_id: uuid.UUID
    ) -> float:
        """计算目录结构相似度评分。

        从 SimilarityResult 表读取 structure_similarity，取最高值。

        Args:
            task_id: 分析任务ID

        Returns:
            float: 评分 (0.0 - 1.0)
        """
        try:
            from app.models.analysis import SimilarityResult
            from sqlalchemy import select, func as sa_func

            async with self.db_session_factory() as db:
                query = select(
                    sa_func.max(SimilarityResult.structure_similarity)
                ).where(SimilarityResult.task_id == task_id)
                result = await db.execute(query)
                max_val = result.scalar()
                if max_val is not None:
                    val = float(max_val) / 100.0
                    return min(max(val, 0.0), 1.0)
                return 0.0
        except Exception as exc:
            logger.error(f"计算目录结构相似度评分失败: {exc!s}")
            return 0.0

    async def _compute_table_score(
        self, task_id: uuid.UUID
    ) -> float:
        """计算表格相似度评分。

        从 SimilarityResult 表读取 table_similarity，取最高值。

        Args:
            task_id: 分析任务ID

        Returns:
            float: 评分 (0.0 - 1.0)
        """
        try:
            from app.models.analysis import SimilarityResult
            from sqlalchemy import select, func as sa_func

            async with self.db_session_factory() as db:
                query = select(
                    sa_func.max(SimilarityResult.table_similarity)
                ).where(SimilarityResult.task_id == task_id)
                result = await db.execute(query)
                max_val = result.scalar()
                if max_val is not None:
                    val = float(max_val) / 100.0
                    return min(max(val, 0.0), 1.0)
                return 0.0
        except Exception as exc:
            logger.error(f"计算表格相似度评分失败: {exc!s}")
            return 0.0

    async def _compute_metadata_score(
        self, task_id: uuid.UUID
    ) -> float:
        """计算元数据一致性评分。

        从 SimilarityResult 表读取 metadata_consistency，取最高值。

        Args:
            task_id: 分析任务ID

        Returns:
            float: 评分 (0.0 - 1.0)
        """
        try:
            from app.models.analysis import SimilarityResult
            from sqlalchemy import select, func as sa_func

            async with self.db_session_factory() as db:
                query = select(
                    sa_func.max(SimilarityResult.metadata_consistency)
                ).where(SimilarityResult.task_id == task_id)
                result = await db.execute(query)
                max_val = result.scalar()
                if max_val is not None:
                    val = float(max_val) / 100.0
                    return min(max(val, 0.0), 1.0)
                return 0.0
        except Exception as exc:
            logger.error(f"计算元数据一致性评分失败: {exc!s}")
            return 0.0

    async def _compute_template_reuse_score(
        self, task_id: uuid.UUID
    ) -> float:
        """计算模板复用评分 (V1.1)。

        从 TemplateReuseResult 表读取 reuse_score，取最高值。

        Args:
            task_id: 分析任务ID

        Returns:
            float: 评分 (0.0 - 1.0)
        """
        try:
            from app.models.analysis import TemplateReuseResult
            from sqlalchemy import select, func as sa_func

            async with self.db_session_factory() as db:
                query = select(
                    sa_func.max(TemplateReuseResult.reuse_score)
                ).where(TemplateReuseResult.task_id == task_id)
                result = await db.execute(query)
                max_val = result.scalar()
                if max_val is not None:
                    val = float(max_val) / 100.0
                    return min(max(val, 0.0), 1.0)
                return 0.0
        except Exception as exc:
            logger.error(f"计算模板复用评分失败: {exc!s}")
            return 0.0

    async def _compute_electronic_signature_score(
        self, task_id: uuid.UUID
    ) -> float:
        """计算电子标书特征评分 (V1.1)。

        从 ElectronicSignatureResult 表读取 signature_score，取最高值。

        Args:
            task_id: 分析任务ID

        Returns:
            float: 评分 (0.0 - 1.0)
        """
        try:
            from app.models.analysis import ElectronicSignatureResult
            from sqlalchemy import select, func as sa_func

            async with self.db_session_factory() as db:
                query = select(
                    sa_func.max(ElectronicSignatureResult.signature_score)
                ).where(ElectronicSignatureResult.task_id == task_id)
                result = await db.execute(query)
                max_val = result.scalar()
                if max_val is not None:
                    val = float(max_val) / 100.0
                    return min(max(val, 0.0), 1.0)
                return 0.0
        except Exception as exc:
            logger.error(f"计算电子标书特征评分失败: {exc!s}")
            return 0.0

    def _compute_image_score(self, result_count: int) -> float:
        """计算图片相似度评分。

        Args:
            result_count: 图片相似结果数

        Returns:
            float: 评分 (0.0 - 1.0)
        """
        if result_count == 0:
            return 0.0
        # 有相似图片时按数量估算
        return min(0.3 + result_count * 0.05, 0.9)

    def _compute_error_score(self, result_count: int) -> float:
        """计算错误一致性评分。

        Args:
            result_count: 错误检测结果数

        Returns:
            float: 评分 (0.0 - 1.0)
        """
        if result_count == 0:
            return 0.0
        # 大量一致的错误意味着更高风险
        return min(0.2 + result_count * 0.03, 0.85)

