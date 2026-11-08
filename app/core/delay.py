"""分条与播放延迟。纯函数：时间、随机源都由参数传入。"""

from __future__ import annotations

import random
import re
from datetime import datetime

from app.core.models import DelayLimits, DelayPart

_SPLIT = re.compile(r"(?<=[。！？!?])")
_PUNCT_TAIL = "。！？!?…~，,、；;：: \t"


def _clean(line: str) -> str:
    line = line.strip()
    line = re.sub(r"^[-*•·\d]+[.、)）]?\s*", "", line)  # 去列表符号
    line = line.replace("**", "").replace("__", "")
    return line.strip(_PUNCT_TAIL) if len(line) > 2 else line.strip()


def _chunk(text: str, limits: DelayLimits) -> list[str]:
    if len(text) <= limits.max_chars:
        return [text]
    pieces = [p for p in _SPLIT.split(text) if p.strip()]
    if len(pieces) <= 1:
        return [text[: limits.max_chars - 1] + "…"]
    out: list[str] = []
    buf = ""
    for piece in pieces:
        if len(buf) + len(piece) <= 90:
            buf += piece
        else:
            if buf:
                out.append(buf)
            buf = piece
    if buf:
        out.append(buf)
    return [p[: limits.max_chars - 1] + "…" if len(p) > limits.max_chars else p for p in out]


def plan(
    text: str,
    *,
    now: datetime,
    rng: random.Random,
    limits: DelayLimits | None = None,
) -> list[DelayPart]:
    limits = limits or DelayLimits()
    lines = [c for c in (_clean(x) for x in text.splitlines()) if c]
    if not lines:
        return []

    parts: list[str] = []
    for line in lines:
        parts.extend(_chunk(line, limits))
    if len(parts) > limits.max_parts:
        head = parts[: limits.max_parts - 1]
        tail = "".join(parts[limits.max_parts - 1 :])
        parts = [*head, tail[: limits.max_chars - 1] + ("…" if len(tail) > limits.max_chars else "")]

    is_night = now.hour >= limits.night_start or now.hour < limits.night_end
    first = rng.randint(*(limits.night_ms if is_night else limits.first_ms))
    gap = rng.randint(*limits.gap_ms)
    return [
        DelayPart(text=part, delay_ms=first if i == 0 else gap)
        for i, part in enumerate(parts)
    ]
