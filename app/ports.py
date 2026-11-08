"""协议层：services 只认这些 Protocol，换实现不改业务代码。"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from datetime import date, datetime
from typing import Protocol

from app.config import Task  # noqa: F401  (供类型引用)
from app.core.models import (
    Completion,
    DeliveryStatus,
    MemoryItem,
    Mode,
    PersonaCard,
    StoredMessage,
    TurnSnapshot,
)


class ChatModel(Protocol):
    def complete(
        self,
        messages: Sequence[dict[str, str]],
        *,
        temperature: float = 0.9,
        max_tokens: int = 400,
    ) -> Completion: ...

    def stream(
        self,
        messages: Sequence[dict[str, str]],
        *,
        temperature: float = 0.9,
        max_tokens: int = 400,
    ) -> Iterator[str]: ...


class MemoryStore(Protocol):
    def chat_items(self) -> Sequence[MemoryItem]: ...
    def private_items(self) -> Sequence[MemoryItem]: ...
    def write(self, kind: str, items: Sequence[MemoryItem]) -> None: ...


class PersonaSource(Protocol):
    def load(self) -> PersonaCard: ...


class MessageRepo(Protocol):
    def add_her(
        self, text: str, *, client_msg_id: str | None, now: datetime
    ) -> tuple[int, bool]: ...

    def add_him(
        self,
        text: str,
        *,
        parts: Sequence[str],
        mode: Mode,
        prompt_version: str | None,
        task_id: str | None,
        usage: Completion | None,
        now: datetime,
    ) -> int: ...

    def recent(self, limit: int = 12) -> Sequence[StoredMessage]: ...
    def since(self, after_id: int, limit: int = 200) -> Sequence[StoredMessage]: ...
    def her_replied_since(self, dt: datetime) -> bool: ...
class TurnRepo(Protocol):
    def start(self, text: str, *, client_msg_id: str | None, now: datetime) -> tuple[TurnSnapshot, bool]: ...
    def by_client_id(self, client_msg_id: str) -> TurnSnapshot | None: ...
    def by_id(self, turn_id: str) -> TurnSnapshot | None: ...
    def commit(
        self,
        turn_id: str,
        *,
        parts: Sequence[str],
        fixed: bool,
        prompt_version: str | None,
        usage: Completion | None,
        now: datetime,
    ) -> int: ...
    def fail(self, turn_id: str, error_code: str, *, now: datetime) -> None: ...
    def recover_incomplete(self, *, now: datetime) -> int: ...


class StateRepo(Protocol):
    def get(self, key: str, default: str | None = None) -> str | None: ...
    def set(self, key: str, value: str, *, now: datetime) -> None: ...
    def muted_until(self, *, now: datetime) -> datetime | None: ...
    def snoozed_until(self, *, now: datetime) -> datetime | None: ...


class ProactiveRepo(Protocol):
    def sent_today(self, day: date) -> set[str]: ...
    def count_today(self, day: date) -> int: ...
    def last_at(self) -> datetime | None: ...
    def reserve_and_send(
        self,
        *,
        day: date,
        task_id: str,
        text: str,
        now: datetime,
        prompt_version: str | None = None,
    ) -> bool: ...


class SendLogRepo(Protocol):
    def log(
        self,
        *,
        day: date,
        task_id: str,
        reason_code: str | None,
        detail: str = "",
        now: datetime,
    ) -> None: ...


class InboxRepo(Protocol):
    def add(self, *, kind: str, body: str, now: datetime) -> int: ...
    def set_delivery_status(self, message_id: int, status: DeliveryStatus, *, now: datetime) -> None: ...
    def unread(self, limit: int = 50) -> Sequence[dict[str, object]]: ...
    def mark_read(self, ids: Sequence[int]) -> None: ...


class Notifier(Protocol):
    def notify(self, kind: str, text: str) -> DeliveryStatus: ...
