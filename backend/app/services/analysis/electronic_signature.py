"""
电子标书特征检测引擎。
检测不同标书的电子证据一致性（创建者、软件、IP、MAC），
识别围串标的直接电子证据（L1 级证据）。
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any, Callable, Awaitable, Optional

from loguru import logger
from sqlalchemy import or_, select

from app.models.analysis import ElectronicSignatureResult
from app.models.project import BidDocument


# ── 电子签名提取 ──────────────────────────────────────────────────────

def extract_electronic_signatures(
    file_metadata: dict[str, Any],
    upload_ip: str | None,
) -> dict[str, Any]:
    """从文档元数据和上传记录提取电子签名特征。

    Args:
        file_metadata: 文档解析时提取的元数据字典
        upload_ip: 上传时的客户端IP（可空）

    Returns:
        dict: {
            creator_id, software, ip_address, mac_address,
            created_time, modified_time, revision_count,
        }
    """
    metadata = file_metadata or {}

    # 创建者ID（优先 author，其次 last_modified_by）
    creator_id = (
        str(metadata.get("author", "")).strip()
        or str(metadata.get("last_modified_by", "")).strip()
    )

    # 编辑软件（优先 creator/producer）
    software = (
        str(metadata.get("creator", "")).strip()
        or str(metadata.get("producer", "")).strip()
    )

    # IP地址
    ip_address = str(upload_ip).strip() if upload_ip else None

    # MAC地址（仅当文档中嵌入了自定义属性时可用，一般不可获取）
    mac_address = None
    if metadata.get("mac_address"):
        mac_address = str(metadata["mac_address"]).strip()

    return {
        "creator_id": creator_id,
        "software": software,
        "ip_address": ip_address,
        "mac_address": mac_address,
        "created_time": str(metadata.get("created", "")).strip(),
        "modified_time": str(metadata.get("modified", "")).strip(),
        "revision_count": metadata.get("revision"),
    }


# ── 电子签名比对 ──────────────────────────────────────────────────────

# 各维度原始权重
_SIGNATURE_WEIGHTS = {
    "mac": 0.40,       # MAC地址匹配 → 同一台电脑（最强证据）
    "ip": 0.25,        # IP地址匹配 → 同一网络/组织
    "creator": 0.20,   # 创建者匹配 → 同一人编辑
    "software": 0.15,  # 软件匹配 → 同款工具
}


def _ip_same_subnet(ip_a: str, ip_b: str) -> bool:
    """判断两个IP是否在同一 /24 子网（C类）。"""
    try:
        parts_a = ip_a.split(".")
        parts_b = ip_b.split(".")
        if len(parts_a) != 4 or len(parts_b) != 4:
            return ip_a == ip_b  # 非标准IP退化为精确匹配
        # 比较前3段（/24子网掩码）
        return parts_a[:3] == parts_b[:3]
    except Exception:
        return ip_a == ip_b


def compare_electronic_signatures(
    sig_a: dict[str, Any],
    sig_b: dict[str, Any],
) -> dict[str, Any]:
    """比对两份标书的电子签名特征。

    Args:
        sig_a: 文档A的电子签名
        sig_b: 文档B的电子签名

    Returns:
        dict: {
            signature_score, mac_match, ip_match,
            creator_match, software_match,
            matched_items, details,
        }
    """
    # 逐项比对
    mac_match = None
    if sig_a.get("mac_address") and sig_b.get("mac_address"):
        mac_match = sig_a["mac_address"].lower() == sig_b["mac_address"].lower()

    ip_match = None
    if sig_a.get("ip_address") and sig_b.get("ip_address"):
        ip_match = _ip_same_subnet(sig_a["ip_address"], sig_b["ip_address"])

    creator_match = None
    ca = sig_a.get("creator_id", "").strip().lower()
    cb = sig_b.get("creator_id", "").strip().lower()
    if ca and cb:
        creator_match = ca == cb

    software_match = None
    sa = sig_a.get("software", "").strip().lower()
    sb = sig_b.get("software", "").strip().lower()
    if sa and sb:
        software_match = sa == sb

    # 收集匹配项
    matched_items: list[str] = []
    if mac_match is True:
        matched_items.append("mac")
    if ip_match is True:
        matched_items.append("ip")
    if creator_match is True:
        matched_items.append("creator")
    if software_match is True:
        matched_items.append("software")

    # 确定可用维度和权重
    available_checks = {
        "mac": mac_match is not None,
        "ip": ip_match is not None,
        "creator": creator_match is not None,
        "software": software_match is not None,
    }

    # 权重重分配：不可用维度的权重按比例分配给可用维度
    available_weight = sum(
        _SIGNATURE_WEIGHTS[k] for k, v in available_checks.items() if v
    )

    if available_weight == 0:
        return {
            "signature_score": 0.0,
            "mac_match": mac_match,
            "ip_match": ip_match,
            "creator_match": creator_match,
            "software_match": software_match,
            "matched_items": [],
            "details": {"available_checks": available_checks},
        }

    # 计算加权得分
    score = 0.0
    for check_key, matched in [
        ("mac", mac_match),
        ("ip", ip_match),
        ("creator", creator_match),
        ("software", software_match),
    ]:
        if matched and available_checks[check_key]:
            score += _SIGNATURE_WEIGHTS[check_key] / available_weight

    return {
        "signature_score": round(min(max(score, 0.0), 1.0), 4),
        "mac_match": mac_match,
        "ip_match": ip_match,
        "creator_match": creator_match,
        "software_match": software_match,
        "matched_items": matched_items,
        "details": {
            "available_checks": available_checks,
            "sig_a": {
                "creator_id": sig_a.get("creator_id", ""),
                "software": sig_a.get("software", ""),
                "ip_address": sig_a.get("ip_address"),
                "mac_address": sig_a.get("mac_address"),
            },
            "sig_b": {
                "creator_id": sig_b.get("creator_id", ""),
                "software": sig_b.get("software", ""),
                "ip_address": sig_b.get("ip_address"),
                "mac_address": sig_b.get("mac_address"),
            },
        },
    }


# ── 编排器兼容入口 ────────────────────────────────────────────────────

async def analyze_electronic_signature(
    project_id: uuid.UUID,
    analysis_task_id: uuid.UUID,
    db_session_factory,
    on_progress: Optional[Callable[[int], Awaitable[None]]] = None,
) -> int:
    """分析项目文档间的电子标书特征一致性。

    从 BidDocument.file_metadata 提取创建者/软件/时间特征，
    从 BidDocument.upload_ip 提取IP特征，对每对文档进行比对。

    Args:
        project_id: 项目ID
        analysis_task_id: 分析任务ID
        db_session_factory: 数据库会话工厂

    Returns:
        int: 创建的 ElectronicSignatureResult 数量
    """
    logger.info(f"开始电子标书特征检测: project={project_id}")

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
                logger.info("文档数量不足，跳过电子标书特征检测")
                return 0

            created_count = 0
            doc_ids = [str(d.id) for d in documents]
            total_pairs = len(doc_ids) * (len(doc_ids) - 1) // 2
            pair_count = 0

            for i in range(len(doc_ids)):
                for j in range(i + 1, len(doc_ids)):
                    pair_count += 1
                    doc_a = doc_ids[i]
                    doc_b = doc_ids[j]

                    # 查找文档元数据
                    doc_a_obj = next((d for d in documents if str(d.id) == doc_a), None)
                    doc_b_obj = next((d for d in documents if str(d.id) == doc_b), None)

                    sig_a = extract_electronic_signatures(
                        doc_a_obj.file_metadata if doc_a_obj else {},
                        getattr(doc_a_obj, "upload_ip", None),
                    )
                    sig_b = extract_electronic_signatures(
                        doc_b_obj.file_metadata if doc_b_obj else {},
                        getattr(doc_b_obj, "upload_ip", None),
                    )

                    comparison = compare_electronic_signatures(sig_a, sig_b)

                    # 创建结果记录
                    db_result = ElectronicSignatureResult(
                        id=str(uuid.uuid4()),
                        task_id=str(analysis_task_id),
                        doc1_id=doc_a,
                        doc2_id=doc_b,
                        signature_score=Decimal(
                            str(round(comparison["signature_score"] * 100, 2))
                        ),
                        mac_match=comparison["mac_match"],
                        ip_match=comparison["ip_match"],
                        creator_match=comparison["creator_match"],
                        software_match=comparison["software_match"],
                        details=comparison["details"],
                    )
                    db.add(db_result)
                    created_count += 1

                    if on_progress and pair_count % max(1, total_pairs // 10) == 0:
                        try:
                            await on_progress(pair_count)
                        except Exception:
                            pass

            await db.commit()
            logger.info(f"电子标书特征检测完成: 创建 {created_count} 条记录")
            return created_count

    except Exception as exc:
        logger.error(f"电子标书特征检测失败: {exc!s}")
        return 0
