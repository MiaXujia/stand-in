"""私密记忆 → 受控情境标签；自由文本原文和 hint 不进模型。"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import date

from app.core.models import MemoryItem, Situation, Visibility

_CAUTION = "⚠️ 你不知道具体原因，也不许猜，不许问“你是不是因为……”。"
_GUIDANCE = {"压力期": "语气放轻，少开玩笑，不追问原因。"}


def labels(items: Iterable[MemoryItem], *, today: date) -> list[Situation]:
    chosen: dict[str, Situation] = {}
    for item in items:
        if item.visibility is not Visibility.PRIVATE or item.situation not in _GUIDANCE:
            continue
        if item.expires_at is not None and item.expires_at < today:
            continue
        current = chosen.get(item.situation)
        if current is None or (
            item.since is not None and (current.since is None or item.since > current.since)
        ):
            chosen[item.situation] = Situation(label=item.situation, since=item.since)
    ordered = sorted(
        chosen.values(),
        key=lambda s: (s.since is not None, s.since or date.min),
        reverse=True,
    )
    return ordered[:2]


def render(situations: Sequence[Situation]) -> str:
    if not situations:
        return ""
    lines = [f"她现在处于「{s.label}」。{_GUIDANCE[s.label]}" for s in situations if s.label in _GUIDANCE]
    if not lines:
        return ""
    lines.append(_CAUTION)
    return "\n".join(lines)
