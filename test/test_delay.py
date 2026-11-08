from __future__ import annotations

import random
from datetime import datetime

from app.core.delay import plan

NOON = datetime(2026, 10, 25, 12, 0)
NIGHT = datetime(2026, 10, 25, 23, 30)


def test_parts_follow_lines_and_delays() -> None:
    parts = plan("嗯\n我在\n你说", now=NOON, rng=random.Random(1))
    assert [p.text for p in parts] == ["嗯", "我在", "你说"]
    assert 2000 <= parts[0].delay_ms <= 8000
    assert all(800 <= p.delay_ms <= 2000 for p in parts[1:])


def test_night_first_delay_is_longer() -> None:
    parts = plan("嗯", now=NIGHT, rng=random.Random(1))
    assert 5000 <= parts[0].delay_ms <= 15000


def test_merges_when_too_many_parts() -> None:
    parts = plan("一\n二\n三\n四\n五\n六", now=NOON, rng=random.Random(1))
    assert len(parts) == 4


def test_long_line_is_split_under_limit() -> None:
    text = "。".join(["今天上班真的好累啊"] * 40) + "。"
    parts = plan(text, now=NOON, rng=random.Random(1))
    assert len(parts) >= 2
    assert all(len(p.text) <= 220 for p in parts)


def test_blank_input_returns_empty() -> None:
    assert plan("  \n ", now=NOON, rng=random.Random(1)) == []
