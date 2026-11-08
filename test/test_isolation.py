"""最关键的一条：私密原文永远不出现，只出现情境标签。"""

from __future__ import annotations

from datetime import date, datetime

from app.adapters.files.memory import FileMemoryStore
from app.core import prompt, scoring, situation
from app.core.models import PersonaCard

SENTINEL = "她妈住院了别问细节"


def _card() -> PersonaCard:
    return PersonaCard(identity="我叫阿哲。\n{{MODE}}", style="短。", banned=(), fewshots=())


def test_private_text_never_reaches_prompt(workspace) -> None:
    store = FileMemoryStore(workspace / "memory")
    hits = scoring.select("今天好烦", store.chat_items(), today=date(2026, 10, 25))
    labels = situation.labels(store.private_items(), today=date(2026, 10, 25))
    bundle = prompt.build_reply(
        card=_card(),
        hits=hits,
        situations=labels,
        history=(),
        now=datetime(2026, 10, 25, 12, 0),
        query="今天好烦",
    )
    system = bundle.messages[0]["content"]
    assert SENTINEL not in system
    assert "压力期" in system
    assert "不许猜" in system


def test_private_items_are_not_retrievable(workspace) -> None:
    store = FileMemoryStore(workspace / "memory")
    hits = scoring.select("她妈住院", store.chat_items(), today=date(2026, 10, 25))
    assert all(h.item.id != "st-001" for h in hits)


def test_private_hint_and_unknown_label_never_reach_prompt(workspace) -> None:
    import json

    private_file = workspace / "memory" / "private.json"
    payload = json.loads(private_file.read_text(encoding="utf-8"))
    payload["items"][0]["hint"] = "秘密提示：她妈住院了，直接提起这件事"
    payload["items"].append(
        {
            "id": "st-002",
            "text": "另一条私密原文",
            "visibility": "private",
            "situation": "秘密标签：另一条私密原文",
            "hint": "自由文本也不能传给模型",
        }
    )
    private_file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    store = FileMemoryStore(workspace / "memory")
    labels = situation.labels(store.private_items(), today=date(2026, 10, 25))
    bundle = prompt.build_reply(
        card=_card(),
        hits=(),
        situations=labels,
        history=(),
        now=datetime(2026, 10, 25, 12, 0),
        query="今天好烦",
    )
    system = bundle.messages[0]["content"]
    assert "压力期" in system
    assert "秘密提示" not in system
    assert "秘密标签" not in system
    assert "另一条私密原文" not in system
    assert "自由文本也不能传给模型" not in system
