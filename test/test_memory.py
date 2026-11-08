from __future__ import annotations

from datetime import date

from app.adapters.files.memory import FileMemoryStore
from app.core import scoring
from app.core.models import MemoryItem

TODAY = date(2026, 10, 25)


def test_chat_items_exclude_private(workspace) -> None:
    store = FileMemoryStore(workspace / "memory")
    chat = store.chat_items()
    private = store.private_items()
    assert [item.id for item in chat] == ["food-001"]
    assert [item.id for item in private] == ["st-001"]
    assert all(item.visibility.value == "chat" for item in chat)


def test_select_finds_by_tag_and_text(workspace) -> None:
    store = FileMemoryStore(workspace / "memory")
    hits = scoring.select("中午吃啥，不吃香菜", store.chat_items(), today=TODAY)
    assert hits and hits[0].item.id == "food-001"


def test_select_returns_empty_below_threshold(workspace) -> None:
    store = FileMemoryStore(workspace / "memory")
    assert scoring.select("显卡驱动怎么装", store.chat_items(), today=TODAY) == []


def test_expired_items_are_ignored() -> None:
    items = [
        MemoryItem(
            id="stale",
            text="在准备答辩",
            tags=("工作",),
            expires_at=date(2026, 9, 1),
        )
    ]
    assert scoring.select("答辩准备得怎么样", items, today=TODAY) == []


def test_write_is_atomic_and_reloadable(workspace) -> None:
    store = FileMemoryStore(workspace / "memory")
    store.write("bit", [MemoryItem(id="bit-1", text="加班叫上山", tags=("加班",))])
    reloaded = FileMemoryStore(workspace / "memory")
    assert "bit-1" in [item.id for item in reloaded.chat_items()]
    assert not (workspace / "memory" / "bits.json.tmp").exists()
