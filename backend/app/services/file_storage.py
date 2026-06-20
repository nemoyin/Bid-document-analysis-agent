"""
文件存储服务。
管理上传文件的保存、组织和删除。
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import BinaryIO, Optional

from loguru import logger

from app.core.config import settings


class FileStorageService:
    """文件存储服务。

    将上传的文件按 {UPLOAD_DIR}/{project_id}/{document_id}/{filename}
    的目录结构进行组织存储。
    """

    def __init__(self, upload_dir: Optional[str] = None):
        """初始化文件存储服务。

        Args:
            upload_dir: 上传根目录，默认从 config 读取
        """
        self.upload_dir = Path(upload_dir or settings.UPLOAD_DIR)
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    def get_project_dir(self, project_id: uuid.UUID) -> Path:
        """获取项目上传目录。

        Args:
            project_id: 项目 ID

        Returns:
            Path: 项目上传目录路径
        """
        project_dir = self.upload_dir / str(project_id)
        project_dir.mkdir(parents=True, exist_ok=True)
        return project_dir

    def get_document_dir(
        self, project_id: uuid.UUID, document_id: uuid.UUID
    ) -> Path:
        """获取文档上传目录。

        Args:
            project_id: 项目 ID
            document_id: 文档 ID

        Returns:
            Path: 文档上传目录路径
        """
        doc_dir = self.get_project_dir(project_id) / str(document_id)
        doc_dir.mkdir(parents=True, exist_ok=True)
        return doc_dir

    def save_file(
        self,
        project_id: uuid.UUID,
        document_id: uuid.UUID,
        filename: str,
        file_content: bytes | BinaryIO,
    ) -> str:
        """保存上传文件。

        Args:
            project_id: 项目 ID
            document_id: 文档 ID
            filename: 原始文件名（用于保持）
            file_content: 文件内容（bytes 或文件对象）
            max_size: 最大文件大小（默认从 config 读取）

        Returns:
            str: 保存后的文件绝对路径

        Raises:
            ValueError: 文件类型不允许或文件过大
        """
        # 验证文件扩展名
        _, ext = os.path.splitext(filename)
        ext = ext.lower()
        allowed = settings.ALLOWED_EXTENSIONS
        if ext not in allowed:
            raise ValueError(
                f"不支持的文件类型 '{ext}'，允许类型: {', '.join(allowed)}"
            )

        # 确保唯一文件名（避免冲突）
        doc_dir = self.get_document_dir(project_id, document_id)
        file_path = doc_dir / filename

        # 如果文件已存在，添加时间戳后缀
        if file_path.exists():
            name_stem = file_path.stem
            file_path = doc_dir / f"{name_stem}_{uuid.uuid4().hex[:8]}{ext}"

        # 写入文件
        if isinstance(file_content, bytes):
            file_path.write_bytes(file_content)
        else:
            with open(file_path, "wb") as f:
                chunk = file_content.read(1024 * 1024)  # 1MB chunks
                while chunk:
                    f.write(chunk)
                    chunk = file_content.read(1024 * 1024)

        abs_path = str(file_path.absolute())
        file_size = file_path.stat().st_size

        logger.info(
            f"文件保存成功: {filename} ({file_size} bytes), "
            f"路径: {abs_path}"
        )
        return abs_path

    def delete_file(self, file_path: str) -> bool:
        """删除文件。

        Args:
            file_path: 文件路径

        Returns:
            bool: 是否成功删除
        """
        try:
            path = Path(file_path)
            if path.exists() and path.is_file():
                path.unlink()
                logger.info(f"文件已删除: {file_path}")
                return True
            logger.warning(f"文件不存在: {file_path}")
            return False
        except Exception as exc:
            logger.error(f"文件删除失败: {file_path}, 错误: {exc!s}")
            return False

    def delete_document_files(
        self, project_id: uuid.UUID, document_id: uuid.UUID
    ) -> bool:
        """删除文档的所有文件。

        Args:
            project_id: 项目 ID
            document_id: 文档 ID

        Returns:
            bool: 是否成功删除
        """
        import shutil

        try:
            doc_dir = self.get_document_dir(project_id, document_id)
            if doc_dir.exists():
                shutil.rmtree(doc_dir)
                logger.info(f"文档目录已删除: {doc_dir}")
                return True
            return True
        except Exception as exc:
            logger.error(f"文档目录删除失败: {exc!s}")
            return False

    def delete_project_files(self, project_id: uuid.UUID) -> bool:
        """删除项目的所有文件。

        Args:
            project_id: 项目 ID

        Returns:
            bool: 是否成功删除
        """
        import shutil

        try:
            project_dir = self.get_project_dir(project_id)
            if project_dir.exists():
                shutil.rmtree(project_dir)
                logger.info(f"项目文件目录已删除: {project_dir}")
                return True
            return True
        except Exception as exc:
            logger.error(f"项目文件目录删除失败: {exc!s}")
            return False

    def get_file_size(self, file_path: str) -> int:
        """获取文件大小。

        Args:
            file_path: 文件路径

        Returns:
            int: 文件大小（bytes），文件不存在返回 -1
        """
        try:
            return Path(file_path).stat().st_size
        except (OSError, FileNotFoundError):
            return -1

    def file_exists(self, file_path: str) -> bool:
        """检查文件是否存在。

        Args:
            file_path: 文件路径

        Returns:
            bool: 是否存在
        """
        return Path(file_path).exists() and Path(file_path).is_file()
