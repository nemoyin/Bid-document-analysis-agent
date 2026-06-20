"""
分析任务编排器。
协调文本相似度、图片相似度、错误检测三大分析引擎，
管理分析任务的整个生命周期。
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional, ClassVar

from loguru import logger
from sqlalchemy import select

from app.core.config import settings
from app.models.analysis import AnalysisTask
from app.schemas.common import RiskLevel


# 配置文件路径
_CONFIG_FILE: ClassVar[Path] = Path(settings.ROOT_DIR) / "data" / "analysis_config.json"


def _load_analysis_config() -> dict:
    """读取持久化的分析配置，如果文件不存在则使用代码默认值。"""
    defaults = {
        "text_similarity_weight": settings.TEXT_SIMILARITY_WEIGHT,
        "structure_similarity_weight": settings.STRUCTURE_SIMILARITY_WEIGHT,
        "image_similarity_weight": settings.IMAGE_SIMILARITY_WEIGHT,
        "table_similarity_weight": settings.TABLE_SIMILARITY_WEIGHT,
        "error_consistency_weight": settings.ERROR_CONSISTENCY_WEIGHT,
        "metadata_consistency_weight": settings.METADATA_CONSISTENCY_WEIGHT,
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

    def calculate_risk_score(
        self,
        text_score: float,
        structure_score: float,
        image_score: float,
        table_score: float,
        error_score: float,
        metadata_score: float,
    ) -> float:
        """计算综合风险评分（6维度，PRD REQ-016）。

        公式 (权重和为 1.0，对应满分 100 分):
            text(30%) + structure(15%) + image(15%)
            + table(10%) + error(20%) + metadata(10%)

        Args:
            text_score: 文本相似度评分 (0.0 - 1.0)
            structure_score: 目录结构相似度评分 (0.0 - 1.0)
            image_score: 图片相似度评分 (0.0 - 1.0)
            table_score: 表格相似度评分 (0.0 - 1.0)
            error_score: 错误一致性评分 (0.0 - 1.0)
            metadata_score: 元数据一致性评分 (0.0 - 1.0)

        Returns:
            float: 综合风险评分 (0.0 - 1.0)
        """
        cfg = _load_analysis_config()
        tw = cfg.get("text_similarity_weight", 0.30)
        sw = cfg.get("structure_similarity_weight", 0.15)
        iw = cfg.get("image_similarity_weight", 0.15)
        tbw = cfg.get("table_similarity_weight", 0.10)
        ew = cfg.get("error_consistency_weight", 0.20)
        mw = cfg.get("metadata_consistency_weight", 0.10)

        risk = (
            text_score * tw
            + structure_score * sw
            + image_score * iw
            + table_score * tbw
            + error_score * ew
            + metadata_score * mw
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
        logger.info(f"[阶段0/5] 任务初始化完成")

        # ---- 阶段1：文档解析（调用 T03 的解析器，如果文档尚未解析） ----
        await self._update_task_status(task_id, "analyzing", progress=5)
        try:
            await self._ensure_documents_parsed(project_id)
        except Exception as exc:
            logger.warning(f"[阶段1/5] 文档解析准备异常: {exc!s}")
        logger.info(f"[阶段1/5] 文档解析准备完成")

        # ---- 阶段2：Embedding + ChromaDB 向量化 ----
        await self._update_task_status(task_id, "analyzing", progress=15)
        try:
            await self._ensure_embeddings(project_id)
        except Exception as exc:
            logger.warning(f"[阶段2/5] 向量化异常: {exc!s}")
        logger.info(f"[阶段2/5] 向量化完成")

        # ---- 阶段3：文本相似度分析 ----
        await self._update_task_status(task_id, "analyzing", progress=20)
        text_result_count = 0
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
                )
                result["text_similarity_count"] = text_result_count
        except Exception as exc:
            logger.error(f"[阶段3/6] 文本相似度分析失败: {exc!s}")
        logger.info(
            f"[阶段3/6] 文本相似度分析完成: {text_result_count} 条结果"
        )

        # ---- 阶段4：目录结构相似度分析 ----
        await self._update_task_status(task_id, "analyzing", progress=35)
        structure_result_count = 0
        try:
            from app.services.analysis.structure_similarity import (
                analyze_structure_similarity,
            )
            structure_result_count = await analyze_structure_similarity(
                project_id=project_id,
                analysis_task_id=task_id,
                db_session_factory=self.db_session_factory,
            )
            result["structure_similarity_count"] = structure_result_count
        except Exception as exc:
            logger.error(f"[阶段4/6] 目录结构相似度分析失败: {exc!s}")
        logger.info(
            f"[阶段4/6] 目录结构相似度分析完成: {structure_result_count} 条结果"
        )

        # ---- 阶段5：图片相似度分析 ----
        await self._update_task_status(task_id, "analyzing", progress=50)
        image_result_count = 0
        try:
            from app.services.analysis.image_similarity import analyze_image_similarity

            image_result_count = await analyze_image_similarity(
                project_id=project_id,
                analysis_task_id=task_id,
                db_session_factory=self.db_session_factory,
            )
            result["image_similarity_count"] = image_result_count
        except Exception as exc:
            logger.error(f"[阶段5/6] 图片相似度分析失败: {exc!s}")
        logger.info(
            f"[阶段5/6] 图片相似度分析完成: {image_result_count} 条结果"
        )

        # ---- 阶段6：表格相似度分析 ----
        await self._update_task_status(task_id, "analyzing", progress=60)
        table_result_count = 0
        try:
            from app.services.analysis.table_similarity import (
                analyze_table_similarity,
            )
            table_result_count = await analyze_table_similarity(
                project_id=project_id,
                analysis_task_id=task_id,
                db_session_factory=self.db_session_factory,
            )
            result["table_similarity_count"] = table_result_count
        except Exception as exc:
            logger.error(f"[阶段6/6] 表格相似度分析失败: {exc!s}")
        logger.info(
            f"[阶段6/6] 表格相似度分析完成: {table_result_count} 条结果"
        )

        # ---- 阶段7：错误检测分析 ----
        await self._update_task_status(task_id, "analyzing", progress=75)
        error_result_count = 0
        try:
            from app.services.analysis.error_detection import analyze_errors

            error_result_count = await analyze_errors(
                project_id=project_id,
                analysis_task_id=task_id,
                db_session_factory=self.db_session_factory,
            )
            result["error_detection_count"] = error_result_count
        except Exception as exc:
            logger.error(f"[阶段7/6] 错误检测分析失败: {exc!s}")
        logger.info(
            f"[阶段7/6] 错误检测分析完成: {error_result_count} 条结果"
        )

        # ---- 阶段8：元数据一致性分析 ----
        await self._update_task_status(task_id, "analyzing", progress=85)
        metadata_result_count = 0
        try:
            from app.services.analysis.metadata_consistency import (
                analyze_metadata_consistency,
            )
            metadata_result_count = await analyze_metadata_consistency(
                project_id=project_id,
                analysis_task_id=task_id,
                db_session_factory=self.db_session_factory,
            )
            result["metadata_consistency_count"] = metadata_result_count
        except Exception as exc:
            logger.error(f"[阶段8/6] 元数据一致性分析失败: {exc!s}")
        logger.info(
            f"[阶段8/6] 元数据一致性分析完成: {metadata_result_count} 条结果"
        )

        # ---- 阶段9：综合评分 ----
        await self._update_task_status(task_id, "analyzing", progress=92)

        # 计算各维度评分（6维度）
        text_score = await self._compute_text_score(task_id)
        structure_score = await self._compute_structure_score(task_id)
        image_score = self._compute_image_score(image_result_count)
        table_score = await self._compute_table_score(task_id)
        error_score = self._compute_error_score(error_result_count)
        metadata_score = await self._compute_metadata_score(task_id)
        combined_score = self.calculate_risk_score(
            text_score, structure_score, image_score,
            table_score, error_score, metadata_score,
        )
        risk_level = self.risk_to_level(combined_score)

        result["text_score"] = round(text_score, 4)
        result["structure_score"] = round(structure_score, 4)
        result["image_score"] = round(image_score, 4)
        result["table_score"] = round(table_score, 4)
        result["error_score"] = round(error_score, 4)
        result["metadata_score"] = round(metadata_score, 4)
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
                    task.completed_at = datetime.now(timezone.utc)
                    # 6维度评分写入 error_message 字段（JSON 格式）
                    import json as _json
                    task.error_message = _json.dumps({
                        "text_score": round(text_score, 4),
                        "structure_score": round(structure_score, 4),
                        "image_score": round(image_score, 4),
                        "table_score": round(table_score, 4),
                        "error_score": round(error_score, 4),
                        "metadata_score": round(metadata_score, 4),
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
