"""
图片相似度分析引擎。
使用三哈希（pHash, dHash, aHash）融合计算图片相似度。
"""

from __future__ import annotations

import math
import uuid
from decimal import Decimal
from io import BytesIO
from typing import Any, Optional, Callable, Awaitable

from loguru import logger

from app.core.config import settings
from app.models.analysis import ImageSimilarityResult


def _compute_phash(pixels: list[int], width: int, height: int) -> str:
    """计算感知哈希（pHash）。

    基于离散余弦变换（DCT）的低频特征。

    Args:
        pixels: 像素值列表（灰度）
        width: 图片宽度
        height: 图片高度

    Returns:
        str: 64位二进制哈希字符串
    """
    # DCT (简化版：只计算部分低频系数)
    dct_size = 32
    if width < dct_size or height < dct_size:
        # 图片太小，降级到 dHash
        return _compute_dhash(pixels, width, height)

    # 缩放像素到 32x32 网格
    grid: list[list[float]] = [[0.0] * dct_size for _ in range(dct_size)]
    for y in range(dct_size):
        for x in range(dct_size):
            src_x = min(int(x * width / dct_size), width - 1)
            src_y = min(int(y * height / dct_size), height - 1)
            idx = src_y * width + src_x
            grid[y][x] = float(pixels[idx]) if idx < len(pixels) else 0.0

    # 计算 DCT 左上角 8x8 低频系数
    dct_coeff: list[list[float]] = [[0.0] * 8 for _ in range(8)]
    for u in range(8):
        for v in range(8):
            sum_val = 0.0
            for x in range(dct_size):
                for y in range(dct_size):
                    sum_val += grid[y][x] * math.cos(
                        (2 * x + 1) * u * math.pi / (2 * dct_size)
                    ) * math.cos((2 * y + 1) * v * math.pi / (2 * dct_size))
            dct_coeff[u][v] = sum_val

    # 取左上角 8x8，计算中位数，生成哈希
    coeffs = [dct_coeff[u][v] for u in range(8) for v in range(8)]
    median = sorted(coeffs)[len(coeffs) // 2]
    return "".join("1" if c > median else "0" for c in coeffs)


def _compute_dhash(pixels: list[int], width: int, height: int) -> str:
    """计算差异哈希（dHash）。

    基于相邻像素差异，对缩放和亮度变化鲁棒性好。

    Args:
        pixels: 像素值列表（灰度）
        width: 图片宽度
        height: 图片高度

    Returns:
        str: 64位二进制哈希字符串
    """
    # 缩放到 9x8
    grid_w, grid_h = 9, 8
    grid: list[list[float]] = [[0.0] * grid_w for _ in range(grid_h)]
    for y in range(grid_h):
        for x in range(grid_w):
            src_x = min(int(x * width / grid_w), width - 1)
            src_y = min(int(y * height / grid_h), height - 1)
            idx = src_y * width + src_x
            grid[y][x] = float(pixels[idx]) if idx < len(pixels) else 0.0

    # 比较相邻像素：左 > 右 → 1, 否则 0
    bits: list[str] = []
    for y in range(grid_h):
        for x in range(grid_w - 1):
            bits.append("1" if grid[y][x] > grid[y][x + 1] else "0")
    return "".join(bits)


def _compute_ahash(pixels: list[int], width: int, height: int) -> str:
    """计算平均哈希（aHash）。

    最简单的哈希方法，基于像素平均值比较。

    Args:
        pixels: 像素值列表（灰度）
        width: 图片宽度
        height: 图片高度

    Returns:
        str: 64位二进制哈希字符串
    """
    # 缩放到 8x8
    grid_w, grid_h = 8, 8
    values: list[float] = []
    for y in range(grid_h):
        for x in range(grid_w):
            src_x = min(int(x * width / grid_w), width - 1)
            src_y = min(int(y * height / grid_h), height - 1)
            idx = src_y * width + src_x
            values.append(float(pixels[idx]) if idx < len(pixels) else 0.0)

    avg = sum(values) / len(values)
    return "".join("1" if v > avg else "0" for v in values)


def _to_grayscale(image_bytes: bytes) -> tuple[list[int], int, int]:
    """将图片二进制数据转为灰度像素数组。

    Args:
        image_bytes: 图片二进制数据

    Returns:
        tuple: (像素数组, 宽度, 高度)
    """
    try:
        from PIL import Image
    except ImportError:
        logger.error("Pillow (PIL) 未安装，无法处理图片")
        return [], 0, 0

    try:
        img = Image.open(BytesIO(image_bytes))
        img = img.convert("L")  # 转为灰度
        return list(img.getdata()), img.width, img.height
    except Exception as exc:
        logger.error(f"图片转灰度失败: {exc!s}")
        return [], 0, 0


def compute_phash(image_bytes: bytes) -> str:
    """计算图片的感知哈希（pHash）。

    Args:
        image_bytes: 图片二进制数据

    Returns:
        str: pHash 哈希字符串
    """
    pixels, w, h = _to_grayscale(image_bytes)
    if not pixels:
        return ""
    return _compute_phash(pixels, w, h)


def compute_dhash(image_bytes: bytes) -> str:
    """计算图片的差异哈希（dHash）。

    Args:
        image_bytes: 图片二进制数据

    Returns:
        str: dHash 哈希字符串
    """
    pixels, w, h = _to_grayscale(image_bytes)
    if not pixels:
        return ""
    return _compute_dhash(pixels, w, h)


def compute_ahash(image_bytes: bytes) -> str:
    """计算图片的平均哈希（aHash）。

    Args:
        image_bytes: 图片二进制数据

    Returns:
        str: aHash 哈希字符串
    """
    pixels, w, h = _to_grayscale(image_bytes)
    if not pixels:
        return ""
    return _compute_ahash(pixels, w, h)


def hamming_distance(hash1: str, hash2: str) -> int:
    """计算两个哈希字符串的汉明距离。

    Args:
        hash1: 哈希字符串A
        hash2: 哈希字符串B

    Returns:
        int: 汉明距离（不同的位数）
    """
    if not hash1 or not hash2:
        return 64

    max_len = max(len(hash1), len(hash2))
    min_len = min(len(hash1), len(hash2))

    # 补齐较短者
    h1 = hash1.ljust(max_len, "0")
    h2 = hash2.ljust(max_len, "0")

    return sum(1 for a, b in zip(h1, h2) if a != b)


def compute_fusion_score(
    phash_dist: int, dhash_dist: int, ahash_dist: int
) -> float:
    """计算三哈希融合相似度分数。

    三哈希权重:
        pHash(感知): 0.4 — 对 JPEG 压缩、颜色变化鲁棒
        dHash(差异): 0.35 — 对缩放、亮度变化鲁棒
        aHash(平均): 0.25 — 简单快速，作为补充

    Args:
        phash_dist: pHash 汉明距离
        dhash_dist: dHash 汉明距离
        ahash_dist: aHash 汉明距离

    Returns:
        float: 融合相似度 (0.0 - 1.0)
    """
    # 汉明距离 0~64 → 相似度 1.0~0.0
    p_sim = max(0.0, 1.0 - phash_dist / 64.0)
    d_sim = max(0.0, 1.0 - dhash_dist / 64.0)
    a_sim = max(0.0, 1.0 - ahash_dist / 64.0)

    # 加权融合
    return p_sim * 0.4 + d_sim * 0.35 + a_sim * 0.25


async def analyze_image_similarity(
    project_id: uuid.UUID,
    analysis_task_id: uuid.UUID,
    db_session_factory,
    on_progress: Optional[Callable[[int], Awaitable[None]]] = None,
) -> int:
    """图片相似度分析主入口。

    遍历同项目下所有文档的图片，两两计算三哈希融合分数。

    Args:
        project_id: 项目ID
        analysis_task_id: 分析任务ID
        db_session_factory: 数据库会话工厂
        on_progress: 可选的进度回调，参数为已完成对比图片对数

    Returns:
        int: 写入的图片相似结果数量
    """
    logger.info(f"开始图片相似度分析: project={project_id}, task={analysis_task_id}")

    threshold = getattr(settings, "IMAGE_SIMILARITY_THRESHOLD", 0.85)

    try:
        async with db_session_factory() as db:
            from sqlalchemy import select
            from app.models.project import BidDocument

            # 获取项目下所有文档
            result = await db.execute(
                select(BidDocument).where(BidDocument.project_id == project_id)
            )
            documents = result.scalars().all()

            # 收集所有文档的图片
            all_images: list[dict] = []
            for doc in documents:
                if not doc.extracted_images:
                    continue
                images = doc.extracted_images if isinstance(doc.extracted_images, list) else []
                for img in images:
                    img["doc_id"] = str(doc.id)
                    all_images.append(img)

            if len(all_images) < 2:
                logger.warning(f"图片数量不足 {len(all_images)}，跳过图片相似度分析")
                return 0

            logger.info(f"共 {len(all_images)} 张图片待比对")

            # 两两比较
            written_count = 0
            total_img_pairs = len(all_images) * (len(all_images) - 1) // 2
            img_pair_count = 0
            for i in range(len(all_images)):
                for j in range(i + 1, len(all_images)):
                    img_i = all_images[i]
                    img_j = all_images[j]

                    # 跳过同一文档内的图片比较
                    if img_i["doc_id"] == img_j["doc_id"]:
                        continue

                    img_pair_count += 1

                    # 计算三哈希
                    try:
                        img_i_bytes = _load_image_bytes(img_i.get("path", ""))
                        img_j_bytes = _load_image_bytes(img_j.get("path", ""))

                        if not img_i_bytes or not img_j_bytes:
                            continue

                        phash_i = compute_phash(img_i_bytes)
                        phash_j = compute_phash(img_j_bytes)
                        dhash_i = compute_dhash(img_i_bytes)
                        dhash_j = compute_dhash(img_j_bytes)
                        ahash_i = compute_ahash(img_i_bytes)
                        ahash_j = compute_ahash(img_j_bytes)

                        phash_dist = hamming_distance(phash_i, phash_j)
                        dhash_dist = hamming_distance(dhash_i, dhash_j)
                        ahash_dist = hamming_distance(ahash_i, ahash_j)

                        fusion_score = compute_fusion_score(
                            phash_dist, dhash_dist, ahash_dist
                        )
                    except Exception as exc:
                        logger.warning(f"图片哈希计算失败: {exc!s}")
                        continue

                    if fusion_score >= threshold:
                        image_entry = ImageSimilarityResult(
                            task_id=str(analysis_task_id),
                            document_id=str(img_i["doc_id"]),
                            image_hash=img_i.get("hash", phash_i),
                            image_path=img_i.get("path", ""),
                            similar_image_path=img_j.get("path", ""),
                            page_number=img_i.get("page_num"),
                            hash_algorithm="fusion",
                            similar_image_id=str(img_j["doc_id"]),
                            similarity_score=Decimal(
                                str(round(fusion_score * 100, 2))
                            ),
                        )
                        db.add(image_entry)
                        written_count += 1

                    if on_progress and img_pair_count % max(1, total_img_pairs // 10) == 0:
                        try:
                            await on_progress(img_pair_count)
                        except Exception:
                            pass

            await db.commit()
            logger.info(
                f"图片相似度分析完成: 写入 {written_count} 条结果"
            )
            return written_count

    except Exception as exc:
        logger.error(f"图片相似度分析失败: {exc!s}")
        return 0


def _load_image_bytes(image_path: str) -> Optional[bytes]:
    """根据图片路径加载二进制数据。

    Args:
        image_path: 图片文件路径或 Base64 字符串

    Returns:
        Optional[bytes]: 图片二进制数据，失败返回 None
    """
    import os

    if not image_path:
        return None

    # 如果是文件路径
    if os.path.exists(image_path):
        try:
            with open(image_path, "rb") as f:
                return f.read()
        except Exception as exc:
            logger.warning(f"读取图片文件失败: {image_path}, {exc!s}")
            return None

    # 如果是相对路径，尝试在上传目录中查找
    upload_dir = settings.UPLOAD_DIR
    full_path = os.path.join(upload_dir, image_path)
    if os.path.exists(full_path):
        try:
            with open(full_path, "rb") as f:
                return f.read()
        except Exception:
            return None

    logger.warning(f"图片文件不存在: {image_path}")
    return None
