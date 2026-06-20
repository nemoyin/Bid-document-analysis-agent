"""
文档解析器工厂类。
根据文件扩展名自动选择合适的文档解析器。
"""

from __future__ import annotations

from loguru import logger

from app.services.document_parser.base import BaseDocumentParser
from app.services.document_parser.docx_parser import DocxParser
from app.services.document_parser.pdf_parser import PdfParser


class ParserFactory:
    """文档解析器工厂。

    根据文件扩展名自动选择并创建对应的解析器实例。
    支持 PDF 和 DOCX 格式，未来可扩展支持 xlsx 等格式。
    """

    _parsers: dict[str, type[BaseDocumentParser]] = {
        ".pdf": PdfParser,
        ".docx": DocxParser,
        ".doc": DocxParser,  # 仅支持 OOXML .docx; 旧版 .doc 需先转换为 .docx
    }

    @classmethod
    def register_parser(
        cls, extension: str, parser_class: type[BaseDocumentParser]
    ) -> None:
        """注册新的文档解析器。

        Args:
            extension: 文件扩展名（如 ".xlsx"）
            parser_class: 解析器类
        """
        ext = extension.lower()
        if not ext.startswith("."):
            ext = f".{ext}"
        cls._parsers[ext] = parser_class
        logger.info(f"注册解析器: {ext} -> {parser_class.__name__}")

    @classmethod
    def get_parser(cls, file_path: str) -> BaseDocumentParser:
        """根据文件路径获取对应的文档解析器。

        Args:
            file_path: 文档文件路径

        Returns:
            BaseDocumentParser: 对应的解析器实例

        Raises:
            ValueError: 不支持的文件格式
        """
        import os

        _, ext = os.path.splitext(file_path)
        ext = ext.lower()

        parser_class = cls._parsers.get(ext)
        if parser_class is None:
            supported = ", ".join(cls._parsers.keys())
            raise ValueError(
                f"不支持的文件格式 '{ext}'，支持格式: {supported}"
            )

        logger.debug(f"选择解析器: {ext} -> {parser_class.__name__}")
        return parser_class()

    @classmethod
    def parse(cls, file_path: str) -> "ParseResult":
        """解析文档的便捷方法（获取解析器并解析一步完成）。

        Args:
            file_path: 文档文件路径

        Returns:
            ParseResult: 解析结果
        """
        from app.services.document_parser.base import ParseResult

        parser = cls.get_parser(file_path)
        return parser.parse(file_path)

    @classmethod
    def supported_extensions(cls) -> list[str]:
        """获取支持的扩展名列表。

        Returns:
            list[str]: 支持的扩展名列表
        """
        return list(cls._parsers.keys())
