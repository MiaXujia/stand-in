"""记忆文件实现：profile / events / promises / bits + private。

- private.json 只由 private_items() 暴露；chat_items() 连读都不读它。
- 写文件用临时文件 + os.replace，避免半截 JSON。
- 用 mtime 做热更新，改了文件下一轮就生效。
"""

from __future__ import annotations

import json
import os
from collections.abc import Sequence
from datetime import UTC, date, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from app.core.models import MemoryItem, MemoryKind, Visibility

FILES: dict[str, str] = {
    "profile": "profile.json",
    "event": "events.json",
    "promise": "promises.json",
    "bit": "bits.json",
    "private": "private.json",
}
CHAT_KINDS: tuple[str, ...] = ("profile", "event", "promise", "bit")


class _ItemModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="ignore")

    id: str
    text: str
    tags: list[str] = []
    visibility: str = "chat"
    updated_at: date | None = None
    expires_at: date | None = None
    due: date | None = None
    annual: bool = False
    situation: str | None = None
    since: date | None = None
    hint: str = ""


def _mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


class FileMemoryStore:
    def __init__(self, directory: Path) -> None:
        self._dir = Path(directory)
        self._chat: tuple[MemoryItem, ...] = ()
        self._private: tuple[MemoryItem, ...] = ()
        self._stamp: tuple[tuple[str, float], ...] | None = None

    # ---- 读 ----
    def _current_stamp(self) -> tuple[tuple[str, float], ...]:
        return tuple(sorted((name, _mtime(self._dir / name)) for name in FILES.values()))

    def _load_file(self, path: Path, kind: MemoryKind) -> list[MemoryItem]:
        if not path.exists():
            return []
        data = json.loads(path.read_text(encoding="utf-8"))
        raw = data.get("items", []) if isinstance(data, dict) else data
        items: list[MemoryItem] = []
        for entry in raw:
            model = _ItemModel.model_validate(entry)
            visibility = (
                Visibility.PRIVATE if kind == "private" else Visibility(model.visibility)
            )
            items.append(
                MemoryItem(
                    id=model.id,
                    text=model.text,
                    kind=kind,
                    tags=tuple(model.tags),
                    visibility=visibility,
                    updated_at=model.updated_at,
                    expires_at=model.expires_at,
                    due=model.due,
                    annual=model.annual,
                    situation=model.situation,
                    since=model.since,
                    hint=model.hint,
                )
            )
        return items

    def refresh(self) -> None:
        stamp = self._current_stamp()
        if stamp == self._stamp:
            return
        chat: list[MemoryItem] = []
        for kind in CHAT_KINDS:
            chat.extend(self._load_file(self._dir / FILES[kind], kind))  # type: ignore[arg-type]
        private = self._load_file(self._dir / FILES["private"], "private")
        self._chat = tuple(chat)
        self._private = tuple(private)
        self._stamp = stamp

    def chat_items(self) -> Sequence[MemoryItem]:
        self.refresh()
        return tuple(i for i in self._chat if i.visibility is Visibility.CHAT)

    def private_items(self) -> Sequence[MemoryItem]:
        self.refresh()
        return self._private

    # ---- 写 ----
    def write(self, kind: str, items: Sequence[MemoryItem]) -> None:
        path = self._dir / FILES[kind]
        payload: dict = {}
        if path.exists():
            try:
                existing = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(existing, dict):
                    payload = existing
            except json.JSONDecodeError:
                payload = {}
        payload["items"] = [
            _ItemModel(
                id=item.id,
                text=item.text,
                tags=list(item.tags),
                visibility=item.visibility.value,
                updated_at=item.updated_at,
                expires_at=item.expires_at,
                due=item.due,
                annual=item.annual,
                situation=item.situation,
                since=item.since,
                hint=item.hint,
            ).model_dump(mode="json", by_alias=True, exclude_none=True)
            for item in items
        ]
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, path)
        self._stamp = None


def today_utc() -> date:
    return datetime.now(UTC).date()
