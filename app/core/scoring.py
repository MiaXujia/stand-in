"""中文 bigram 相关度：检索、少样本挑选、主动消息去重共用。纯函数。"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable, Sequence
from datetime import date

from app.core.models import MemoryHit, MemoryItem, Visibility

_ASCII = re.compile(r"[a-z0-9]+")
_CJK = re.compile(r"[\u4e00-\u9fff]")


def tokens(text: str) -> set[str]:
    lowered = text.lower()
    out: set[str] = set(_ASCII.findall(lowered))
    chars = _CJK.findall(lowered)
    out |= set(chars)
    out |= {a + b for a, b in zip(chars, chars[1:], strict=False)}
    return out


def _overlap(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / math.sqrt(len(a) * len(b))


def similarity(a: str, b: str) -> float:
    """0–1，越长越像；用于主动消息去重。"""
    return round(min(1.0, _overlap(tokens(a), tokens(b))), 4)


def score(query: str, item: MemoryItem) -> float:
    q = tokens(query)
    if not q:
        return 0.0
    body = _overlap(q, tokens(item.text))
    tags = 0.0
    if item.tags:
        tag_tokens: set[str] = set()
        for tag in item.tags:
            tag_tokens |= tokens(tag)
        tags = _overlap(q, tag_tokens)
    return round(min(1.0, 0.8 * body + 0.5 * tags), 4)


def is_active(item: MemoryItem, today: date) -> bool:
    return item.expires_at is None or item.expires_at >= today


def select(
    query: str,
    items: Iterable[MemoryItem],
    *,
    k: int = 4,
    min_score: float = 0.12,
    today: date | None = None,
) -> list[MemoryHit]:
    """只接受 chat 可见的条目；空结果是好结果（宁可不提，也别乱提）。"""
    today = today or date.today()
    hits: list[MemoryHit] = []
    for item in items:
        if item.visibility is not Visibility.CHAT or not is_active(item, today):
            continue
        s = score(query, item)
        if s < min_score:
            continue
        why = tuple(t for t in item.tags if tokens(t) & tokens(query))[:3]
        hits.append(MemoryHit(item=item, score=s, why=why))
    hits.sort(key=lambda h: h.score, reverse=True)
    return hits[:k]


def pick_fewshots(query: str, shots: Sequence, k: int = 6) -> list:
    """按场景挑几条示例，避免把整份 fewshot 塞进 prompt。"""
    if not shots:
        return []
    ranked = sorted(
        shots,
        key=lambda fs: similarity(query, " ".join((*fs.tags, fs.her))),
        reverse=True,
    )
    return ranked[:k]
