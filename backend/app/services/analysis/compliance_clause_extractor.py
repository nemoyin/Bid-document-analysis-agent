"""条款结构化提取引擎 — 粗拆(规则) + 精拆(LLM)"""
from __future__ import annotations

import json as _json
import re
from typing import Any

from app.core.compliance_config import get_active_clause_types

# 中文招标文件常见章节边界模式
_CHAPTER_PATTERNS = [
    re.compile(r'^第[一二三四五六七八九十\d]+章'),   # 第X章
    re.compile(r'^第[一二三四五六七八九十\d]+节'),   # 第X节
    re.compile(r'^[一二三四五六七八九十]+[、，]'),   # 一、
    re.compile(r'^\d+[\.\、]'),                     # 1. / 1、
]


def coarse_split(text: str) -> list[dict[str, Any]]:
    """按章节/编号将招标文件全文切分为段落块。

    Args:
        text: 招标文件全文

    Returns:
        list[dict]: [{"title": "章节标题", "content": "段落内容", "start_line": 0}, ...]
    """
    if not text or not text.strip():
        return []

    lines = text.split('\n')
    if len(lines) <= 3:
        return [{"title": "全文", "content": text, "start_line": 0}]

    # 找出章节边界行
    boundaries: list[int] = []
    boundary_titles: list[str] = []

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or len(stripped) > 100:
            continue
        for pattern in _CHAPTER_PATTERNS:
            if pattern.match(stripped):
                boundaries.append(i)
                boundary_titles.append(stripped[:80])
                break

    # 无章节边界 → 整个文档作为一个块
    if len(boundaries) <= 1:
        return [{"title": "全文", "content": text, "start_line": 0}]

    # 按边界切分
    chunks: list[dict[str, Any]] = []
    for idx in range(len(boundaries)):
        start = boundaries[idx]
        end = boundaries[idx + 1] if idx + 1 < len(boundaries) else len(lines)
        chunk_text = '\n'.join(lines[start:end]).strip()
        if chunk_text:
            chunks.append({
                "title": boundary_titles[idx],
                "content": chunk_text,
                "start_line": start,
            })

    return chunks


def build_extraction_prompt(chunk_text: str, clause_types: list[dict]) -> str:
    """构建 LLM 条款提取 prompt。

    Args:
        chunk_text: 粗拆后的段落块文本
        clause_types: 启用的条款类型列表 [{"id": "...", "label": "..."}]

    Returns:
        str: LLM prompt
    """
    type_list = "\n".join(
        f"- {t['id']}: {t['label']}" for t in clause_types
    )
    return f"""你是一名招投标文件结构化分析专家。请从以下招标文件段落中提取所有独立的资格/要求条款。

支持的条款类型：
{type_list}

对于每个条款，提取：
1. type: 条款类型ID (从上述列表选择最匹配的)
2. original_text: 条款原文（精确摘录）
3. location: 章节/小节信息（如可识别）
4. params: 结构化关键参数（按条款类型动态变化，例如：
   - 资格条件类：资质等级、证书名称、注册资本
   - 业绩要求类：项目数量、合同金额、年限
   - 技术要求类：品牌、型号、技术参数
   - 时间节点类：天数、时间类型（发售期/澄清期/投标期）
   - 评分标准类：分值、客观/主观标识
   - 合同条款类：金额、比例、期限
   ）

段落原文：
---
{chunk_text[:3000]}
---

请以 JSON 格式输出：{{"clauses": [...]}}。如果段落中没有可提取的条款，返回 {{"clauses": []}}。"""


async def _call_llm_chat(prompt: str) -> str:
    """调用 Gitee AI Chat Completion API。"""
    import httpx
    from app.core.config import settings

    url = f"{settings.GITEE_AI_BASE_URL}/chat/completions"
    headers = {"Authorization": f"Bearer {settings.GITEE_AI_API_KEY}"}
    payload = {
        "model": "Qwen3-32B",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 2000,
    }
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]


def _parse_llm_response(raw: str) -> list[dict]:
    """解析 LLM 返回的结构化条款列表。"""
    try:
        text = raw.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1])
        data = _json.loads(text)
        return data.get("clauses", [])
    except (_json.JSONDecodeError, KeyError):
        return []


async def extract_clauses_async(
    text: str,
    clause_types: list[dict] | None = None,
) -> list[dict[str, Any]]:
    """从招标文件全文异步提取条款卡片列表。

    Args:
        text: 招标文件全文
        clause_types: 启用的条款类型列表，默认从配置读取

    Returns:
        list[dict]: 条款卡片列表
    """
    if clause_types is None:
        clause_types = get_active_clause_types()

    if not clause_types:
        return []

    chunks = coarse_split(text)
    all_clauses: list[dict] = []

    for chunk in chunks:
        prompt = build_extraction_prompt(chunk["content"], clause_types)
        try:
            raw = await _call_llm_chat(prompt)
        except Exception:
            continue

        parsed = _parse_llm_response(raw)
        for clause in parsed:
            clause.setdefault("location", {"chapter": chunk["title"]})
        all_clauses.extend(parsed)

    return all_clauses
