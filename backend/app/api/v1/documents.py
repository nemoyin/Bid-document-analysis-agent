"""
文档上传与解析 API 路由。
提供文档上传、解析触发和状态查询接口。
"""

from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.models.project import BidDocument, Project
from app.schemas.common import ApiResponse
from app.schemas.project import BidDocumentResponse
from app.services.document_parser.parser_factory import ParserFactory
from app.services.embedding.embedding_service import EmbeddingService
from app.services.file_storage import FileStorageService

router = APIRouter(prefix="/projects/{project_id}/documents")

file_storage = FileStorageService()


async def _get_project_or_error(
    project_id: str, db: AsyncSession
) -> Project:
    """获取项目，不存在则抛出 HTTP 异常。"""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    return project


async def _get_document_or_error(
    project_id: str, doc_id: str, db: AsyncSession
) -> BidDocument:
    """获取文档，不存在则抛出 HTTP 异常。"""
    result = await db.execute(
        select(BidDocument).where(
            BidDocument.id == doc_id,
            BidDocument.project_id == project_id,
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    return doc


async def _run_parse_background(
    project_id: str,
    doc_id: str,
    file_path: str,
    db_session_factory,
) -> None:
    """后台执行文档解析。

    Args:
        project_id: 项目 ID
        doc_id: 文档 ID
        file_path: 文件路径
        db_session_factory: 数据库会话工厂
    """
    try:
        async with db_session_factory() as db:
            doc = await _get_document_or_error(project_id, doc_id, db)

            # 更新文档状态为"解析中"
            doc.status = "parsing"
            doc.parse_status = "processing"
            await db.flush()

            # 解析文档
            parser = ParserFactory.get_parser(file_path)
            parse_result = parser.parse(file_path)

            # 更新文档信息
            doc.content_text = parse_result.full_text
            doc.page_count = len(parse_result.pages) if parse_result.pages else None
            doc.status = "parsed"
            doc.parse_status = "completed"
            doc.parsed_at = datetime.utcnow()

            # 保存提取的图片到磁盘，并记录元数据
            if parse_result.images:
                saved_images = []
                for img in parse_result.images:
                    img_filename = f"image_{img.image_hash}.{img.image_ext or 'png'}"
                    img_dir = Path(doc.file_path).parent / "images"
                    img_dir.mkdir(parents=True, exist_ok=True)
                    img_path = img_dir / img_filename
                    img_path.write_bytes(img.image_data)
                    saved_images.append({
                        "path": str(img_path.absolute()),
                        "hash": img.image_hash,
                        "page_num": img.page_num,
                        "ext": img.image_ext or "png",
                    })
                doc.extracted_images = saved_images
                logger.info(f"图片保存完成: {len(saved_images)} 张 -> {img_dir}")

            # 保存提取的表格数据
            if parse_result.pages:
                saved_tables = []
                for page in parse_result.pages:
                    if page.tables:
                        for table in page.tables:
                            if table and len(table) >= 2:  # 至少包含表头和一行数据
                                saved_tables.append({
                                    "page_num": page.page_num,
                                    "rows": len(table),
                                    "cols": max(len(row) for row in table) if table else 0,
                                    "header": table[0] if table else [],
                                    "data": table,
                                })
                if saved_tables:
                    doc.extracted_tables = saved_tables
                    logger.info(f"表格保存完成: {len(saved_tables)} 个表格")

            await db.flush()

            # 将解析结果向量化并存入 ChromaDB
            try:
                embedding_service = EmbeddingService()
                vector_count = embedding_service.store_document_vectors(
                    project_id=project_id,
                    doc_id=doc_id,
                    parse_result=parse_result,
                )
                logger.info(
                    f"文档向量化完成: doc_id={doc_id}, vectors={vector_count}"
                )
            except Exception as exc:
                logger.error(f"文档向量化存储失败: {exc!s}")

            await db.commit()
            logger.info(f"文档解析完成: doc_id={doc_id}, pages={len(parse_result.pages)}")

    except Exception as exc:
        logger.error(f"文档解析失败: doc_id={doc_id}, error={exc!s}")
        try:
            async with db_session_factory() as db:
                doc = await _get_document_or_error(project_id, doc_id, db)
                doc.status = "failed"
                doc.parse_status = "failed"
                await db.commit()
        except Exception:
            pass


# ============================================================
# 文档上传
# ============================================================


@router.post("/upload", response_model=ApiResponse[BidDocumentResponse])
async def upload_document(
    project_id: str,
    file: UploadFile = File(..., description="文档文件（PDF/DOCX/DOC/XLSX）"),
    db: AsyncSession = Depends(get_db),
):
    """上传投标文档。

    将文件保存到文件存储，并在数据库中创建文档记录。
    上传后文档状态为 'uploaded'，需要手动触发解析。
    """
    # 验证项目存在
    project = await _get_project_or_error(project_id, db)

    # 验证文件名
    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名不能为空")

    # 验证文件扩展名
    from pathlib import Path as FilePath
    ext = FilePath(file.filename).suffix.lower()
    if ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件类型 '{ext}'，允许类型: {', '.join(settings.ALLOWED_EXTENSIONS)}",
        )

    # 读取文件内容
    file_content = await file.read()
    if len(file_content) > settings.MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"文件过大（{len(file_content)} bytes），最大允许 {settings.MAX_FILE_SIZE} bytes",
        )

    # 创建文档记录
    doc_id = str(uuid.uuid4())
    doc = BidDocument(
        id=doc_id,
        project_id=project_id,
        filename=file.filename,
        file_type=ext.lstrip("."),
        file_size=len(file_content),
        status="uploaded",
    )
    db.add(doc)

    # 保存文件
    try:
        file_path = file_storage.save_file(
            project_id=project_id,
            document_id=doc_id,
            filename=file.filename,
            file_content=file_content,
        )
        doc.file_path = file_path
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # 更新项目文档计数
    project.file_count += 1

    await db.flush()
    await db.refresh(doc)

    logger.info(
        f"文档上传成功: project={project_id}, doc={doc_id}, "
        f"file={file.filename} ({len(file_content)} bytes)"
    )

    return ApiResponse.success(
        data=BidDocumentResponse.model_validate(doc),
        message="文档上传成功",
    )


# ============================================================
# 触发解析
# ============================================================


@router.post(
    "/{doc_id}/parse",
    response_model=ApiResponse[BidDocumentResponse],
)
async def trigger_parse(
    project_id: str,
    doc_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """触发文档解析。

    在后台执行文档解析 + 向量化存储。
    返回文档当前信息，解析状态会异步更新。
    """
    doc = await _get_document_or_error(project_id, doc_id, db)

    if doc.status == "parsing":
        raise HTTPException(status_code=409, detail="文档正在解析中")

    if doc.status == "parsed" and doc.parse_status == "completed":
        raise HTTPException(status_code=409, detail="文档已经解析完成")

    if not doc.file_path:
        raise HTTPException(status_code=400, detail="文档文件路径不存在")

    # 验证文件存在
    file_path_obj = Path(doc.file_path)
    if not file_path_obj.exists():
        raise HTTPException(status_code=400, detail="文档文件在磁盘上不存在")

    # 在后台执行解析
    from app.db.session import async_session_factory

    background_tasks.add_task(
        _run_parse_background,
        project_id=project_id,
        doc_id=doc_id,
        file_path=doc.file_path,
        db_session_factory=async_session_factory,
    )

    logger.info(f"文档解析已触发: doc_id={doc_id}, file={doc.filename}")

    return ApiResponse.success(
        data=BidDocumentResponse.model_validate(doc),
        message="文档解析已触发，请通过状态接口查询进度",
    )


# ============================================================
# 查询解析状态
# ============================================================


@router.get(
    "/{doc_id}/parse-status",
    response_model=ApiResponse[BidDocumentResponse],
)
async def get_parse_status(
    project_id: str,
    doc_id: str,
    db: AsyncSession = Depends(get_db),
):
    """查询文档解析状态。"""
    doc = await _get_document_or_error(project_id, doc_id, db)

    return ApiResponse.success(
        data=BidDocumentResponse.model_validate(doc),
        message="查询成功",
    )
