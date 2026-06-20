"""
文档解析抽象基类与数据结构定义。
定义 ParseResult, PageContent, ImageContent 数据类及 BaseDocumentParser 抽象接口。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class PageContent:
    """页面内容数据结构。

    Attributes:
        page_num: 页码（从1开始）
        text: 该页的文本内容
        tables: 该页中的表格数据，每个表格为 List[List[str]]
    """

    page_num: int
    text: str
    tables: list[list[list[str]]] = field(default_factory=list)


@dataclass
class ImageContent:
    """图片内容数据结构。

    Attributes:
        page_num: 图片所在页码
        image_data: 图片的 PNG 二进制数据
        image_hash: 图片的 dhash 值（用于去重）
        image_ext: 图片扩展名
    """

    page_num: int
    image_data: bytes
    image_hash: str
    image_ext: str = "png"


@dataclass
class ParseResult:
    """文档解析结果。

    Attributes:
        file_name: 文件名
        file_type: 文件类型（如 pdf, docx）
        pages: 分页内容列表
        images: 提取的图片列表
        metadata: 文件元信息（页数、作者、创建时间等）
    """

    file_name: str
    file_type: str
    pages: list[PageContent] = field(default_factory=list)
    images: list[ImageContent] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def full_text(self) -> str:
        """获取所有页的拼接文本。"""
        return "\n".join(page.text for page in self.pages)


class BaseDocumentParser(ABC):
    """文档解析器抽象基类。

    所有具体的文档解析器（PDF、DOCX等）需继承此类，
    实现 parse 方法。
    """

    @abstractmethod
    def parse(self, file_path: str) -> ParseResult:
        """解析文档内容。

        Args:
            file_path: 文档文件路径

        Returns:
            ParseResult: 解析结果，包含文本、图片、表格、元数据

        Raises:
            FileNotFoundError: 文件不存在
            ValueError: 文件格式不支持或解析失败
        """
        ...
