"""
PDF 文档解析器。
支持 PyMuPDF（优先）和 pdfplumber 两种引擎，提取文本、表格和图片。
"""

from __future__ import annotations

import hashlib
import io
import os
from typing import Optional

from loguru import logger

from app.services.document_parser.base import (
    BaseDocumentParser,
    ImageContent,
    PageContent,
    ParseResult,
)


class PdfParser(BaseDocumentParser):
    """PDF 文档解析器。

    使用 PyMuPDF（fitz）作为主要 PDF 解析引擎。
    使用 pdfplumber 辅助提取表格数据（表格提取更准确）。
    """

    def __init__(self, extract_images: bool = True, extract_tables: bool = True):
        """初始化 PDF 解析器。

        Args:
            extract_images: 是否提取图片
            extract_tables: 是否提取表格
        """
        self.extract_images = extract_images
        self.extract_tables = extract_tables

        # 惰性导入，避免未安装时报错
        self._fitz = None
        self._pdfplumber = None
        self._lazy_import()

    def _lazy_import(self) -> None:
        """惰性导入 PDF 解析库。"""
        try:
            import fitz  # PyMuPDF
            self._fitz = fitz
        except ImportError:
            logger.warning("PyMuPDF (fitz) 未安装，PDF 文本提取将不可用")
            try:
                import pdfplumber
                self._pdfplumber = pdfplumber
                logger.info("pdfplumber 可用，将作为 PDF 文本提取的备选")
            except ImportError:
                logger.warning("pdfplumber 也未安装，PDF 解析将完全不可用")

    def parse(self, file_path: str) -> ParseResult:
        """解析 PDF 文档。

        Args:
            file_path: PDF 文件路径

        Returns:
            ParseResult: 解析结果

        Raises:
            FileNotFoundError: 文件不存在
            ValueError: 解析失败
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"PDF 文件不存在: {file_path}")

        file_name = os.path.basename(file_path)

        # 优先使用 PyMuPDF
        if self._fitz:
            return self._parse_with_fitz(file_path, file_name)

        # 降级使用 pdfplumber
        if self._pdfplumber:
            return self._parse_with_pdfplumber(file_path, file_name)

        raise ValueError("未安装任何 PDF 解析库（需要 PyMuPDF 或 pdfplumber）")

    def _parse_with_fitz(self, file_path: str, file_name: str) -> ParseResult:
        """使用 PyMuPDF 解析 PDF。"""
        import fitz

        doc = fitz.open(file_path)
        pages: list[PageContent] = []
        images: list[ImageContent] = []

        metadata = {
            "file_name": file_name,
            "file_type": "pdf",
            "total_pages": len(doc),
            "title": doc.metadata.get("title", ""),
            "author": doc.metadata.get("author", ""),
            "subject": doc.metadata.get("subject", ""),
            "creator": doc.metadata.get("creator", ""),
            "producer": doc.metadata.get("producer", ""),
        }

        seen_hashes: set[str] = set()

        for page_num, page in enumerate(doc, start=1):
            page_text = page.get_text("text")

            # 提取表格（使用 find_tables）
            tables_data: list[list[list[str]]] = []
            if self.extract_tables:
                try:
                    tabs = page.find_tables()
                    for tab in tabs:
                        table_rows: list[list[str]] = []
                        for row in tab.extract():
                            table_rows.append(
                                [str(cell) if cell is not None else "" for cell in row]
                            )
                        if table_rows:
                            tables_data.append(table_rows)
                except Exception as exc:
                    logger.debug(f"PDF 第 {page_num} 页表格提取失败: {exc!s}")

            pages.append(
                PageContent(
                    page_num=page_num,
                    text=page_text,
                    tables=tables_data,
                )
            )

            # 提取图片
            if self.extract_images:
                try:
                    image_list = page.get_images(full=True)
                    for img_index, img in enumerate(image_list):
                        xref = img[0]
                        base_image = doc.extract_image(xref)
                        image_bytes = base_image["image"]
                        img_ext = base_image["ext"]

                        # 计算图片哈希（用于去重）
                        img_hash = hashlib.sha256(image_bytes).hexdigest()[:16]

                        # 去重：跳过已提取的相同图片
                        if img_hash in seen_hashes:
                            continue
                        seen_hashes.add(img_hash)

                        images.append(
                            ImageContent(
                                page_num=page_num,
                                image_data=image_bytes,
                                image_hash=img_hash,
                                image_ext=img_ext,
                            )
                        )
                except Exception as exc:
                    logger.debug(f"PDF 第 {page_num} 页图片提取失败: {exc!s}")

        doc.close()

        logger.info(
            f"PDF 解析完成: {file_name}, "
            f"共 {len(pages)} 页, {len(images)} 张图片"
        )

        return ParseResult(
            file_name=file_name,
            file_type="pdf",
            pages=pages,
            images=images,
            metadata=metadata,
        )

    def _parse_with_pdfplumber(self, file_path: str, file_name: str) -> ParseResult:
        """使用 pdfplumber 解析 PDF（备选方案）。"""
        import pdfplumber as plumber

        doc = plumber.open(file_path)
        pages: list[PageContent] = []
        images: list[ImageContent] = []

        metadata = {
            "file_name": file_name,
            "file_type": "pdf",
            "total_pages": len(doc.pages),
        }

        for page_num, page in enumerate(doc.pages, start=1):
            page_text = page.extract_text() or ""

            # 提取表格
            tables_data: list[list[list[str]]] = []
            if self.extract_tables:
                try:
                    tabs = page.extract_tables()
                    for tab in tabs:
                        if tab:
                            table_rows: list[list[str]] = [
                                [str(cell) if cell is not None else "" for cell in row]
                                for row in tab
                            ]
                            tables_data.append(table_rows)
                except Exception as exc:
                    logger.debug(f"pdfplumber 第 {page_num} 页表格提取失败: {exc!s}")

            pages.append(
                PageContent(
                    page_num=page_num,
                    text=page_text,
                    tables=tables_data,
                )
            )

        doc.close()

        logger.info(
            f"PDF (pdfplumber) 解析完成: {file_name}, "
            f"共 {len(pages)} 页"
        )

        return ParseResult(
            file_name=file_name,
            file_type="pdf",
            pages=pages,
            images=images,
            metadata=metadata,
        )
