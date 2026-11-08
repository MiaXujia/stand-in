from __future__ import annotations

from datetime import datetime

from app.core import prompt
from app.core.models import FewShot, MemoryHit, MemoryItem, PersonaCard

NOW = datetime(2026, 10, 25, 12, 0)


def _card(**overrides) -> PersonaCard:
    base = dict(
        identity="我叫阿哲。\n{{MODE}}",
        style="连发 2–4 条，每条 5–15 字。",
        banned=("多喝热水", "随便"),
        fewshots=(),
        missing=(),
    )
    base.update(overrides)
    return PersonaCard(**base)


def test_sections_order_and_no_placeholder() -> None:
    bundle = prompt.build_reply(
        card=_card(), hits=(), situations=(), history=(), now=NOW, query="今天好累"
    )
    system = bundle.messages[0]["content"]
    assert "{{" not in system
    headings = [line for line in system.splitlines() if line.startswith("## ")]
    assert headings[:2] == ["## 身份", "## 说话规则"]
    assert headings[-1] == "## 绝不"
    assert bundle.version


def test_version_changes_with_persona_not_with_memory() -> None:
    hit = MemoryHit(item=MemoryItem(id="x", text="不吃香菜"), score=0.9)
    a = prompt.build_reply(card=_card(), hits=(), situations=(), history=(), now=NOW)
    b = prompt.build_reply(card=_card(), hits=(hit,), situations=(), history=(), now=NOW)
    assert a.version == b.version
    c = prompt.build_reply(card=_card(style="每条 1 个字。"), hits=(), situations=(), history=(), now=NOW)
    assert c.version != a.version


def test_fewshot_selection_prefers_matching_scene() -> None:
    shots = (
        FewShot(tags=("吃饭",), her="中午吃什么", me=("你想吃啥",)),
        FewShot(tags=("累", "工作"), her="今天好累啊", me=("谁惹你了",)),
    )
    bundle = prompt.build_reply(
        card=_card(fewshots=shots), hits=(), situations=(), history=(), now=NOW, query="今天加班好累"
    )
    assert "谁惹你了" in bundle.messages[0]["content"]


def test_history_maps_roles() -> None:
    from app.core.models import Mode, StoredMessage

    history = (
        StoredMessage(id=1, role="her", mode=Mode.REPLY, text="在吗", parts=("在吗",), created_at=NOW),
        StoredMessage(id=2, role="him", mode=Mode.REPLY, text="在\n怎么了", parts=("在", "怎么了"), created_at=NOW),
    )
    bundle = prompt.build_reply(card=_card(), hits=(), situations=(), history=history, now=NOW)
    roles = [m["role"] for m in bundle.messages]
    assert roles == ["system", "user", "assistant"]
    assert bundle.messages[-1]["content"] == "在\n怎么了"
