"""SQLite 仓储实现：只做 SQL，不做业务判断。时间戳统一 UTC ISO8601。"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import UTC, date, datetime
from uuid import uuid4

from sqlalchemy import func, select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from app.adapters.sqlite.tables import (
    app_state,
    messages,
    owner_inbox,
    proactive_log,
    send_log,
    turns,
)
from app.core.errors import TurnConflict
from app.core.models import (
    Completion,
    DeliveryStatus,
    Mode,
    StoredMessage,
    TurnSnapshot,
    TurnStatus,
)


def _utc(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()


def _parse(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def _inserted_id(result) -> int:  # noqa: ANN001
    primary_key = result.inserted_primary_key
    if not primary_key:
        raise RuntimeError("insert 没有返回主键")
    return int(primary_key[0])


def _to_message(row) -> StoredMessage:  # noqa: ANN001
    parts = tuple(json.loads(row.parts_json)) if row.parts_json else (row.text,)
    return StoredMessage(
        id=int(row.id),
        role=row.role,
        mode=Mode(row.mode),
        text=row.text,
        parts=parts,
        created_at=_parse(row.created_at) or datetime.now(UTC),
        turn_id=row.turn_id,
    )


def _to_turn(conn, row) -> TurnSnapshot:  # noqa: ANN001
    input_row = conn.execute(
        select(messages.c.text).where(messages.c.id == row.input_message_id)
    ).one()
    parts: tuple[str, ...] = ()
    if row.output_message_id is not None:
        output_row = conn.execute(
            select(messages.c.parts_json, messages.c.text).where(
                messages.c.id == row.output_message_id
            )
        ).one()
        parts = tuple(json.loads(output_row.parts_json)) if output_row.parts_json else (output_row.text,)
    return TurnSnapshot(
        turn_id=row.turn_id,
        client_msg_id=row.client_msg_id,
        status=TurnStatus(row.status),
        text=input_row.text,
        input_message_id=row.input_message_id,
        output_message_id=row.output_message_id,
        error_code=row.error_code,
        fixed=bool(row.fixed),
        parts=parts,
    )


class SqliteTurnRepo:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def start(
        self, text: str, *, client_msg_id: str | None, now: datetime
    ) -> tuple[TurnSnapshot, bool]:
        client_id = client_msg_id or uuid4().hex
        turn_id = uuid4().hex
        with self._engine.begin() as conn:
            legacy = conn.execute(
                select(messages.c.id).where(
                    messages.c.client_msg_id == client_id, messages.c.turn_id.is_(None)
                )
            ).first()
            if legacy is not None:
                raise TurnConflict("client_msg_id belongs to a legacy message")
            inserted = conn.execute(
                sqlite_insert(turns)
                .values(
                    turn_id=turn_id,
                    client_msg_id=client_id,
                    status=TurnStatus.GENERATING.value,
                    created_at=_utc(now),
                    updated_at=_utc(now),
                )
                .on_conflict_do_nothing(index_elements=[turns.c.client_msg_id])
            ).rowcount
            if inserted:
                result = conn.execute(
                    messages.insert().values(
                        role="her",
                        mode=Mode.REPLY.value,
                        text=text,
                        parts_json=json.dumps([text], ensure_ascii=False),
                        client_msg_id=client_id,
                        turn_id=turn_id,
                        created_at=_utc(now),
                    )
                )
                conn.execute(
                    update(turns)
                    .where(turns.c.turn_id == turn_id)
                    .values(input_message_id=_inserted_id(result))
                )
            else:
                row = conn.execute(
                    select(turns).where(turns.c.client_msg_id == client_id)
                ).one()
                turn_id = row.turn_id
            row = conn.execute(select(turns).where(turns.c.turn_id == turn_id)).one()
            snapshot = _to_turn(conn, row)
            if snapshot.text != text:
                raise TurnConflict("client_msg_id was reused with different text")
            return snapshot, bool(inserted)

    def by_client_id(self, client_msg_id: str) -> TurnSnapshot | None:
        with self._engine.connect() as conn:
            row = conn.execute(
                select(turns).where(turns.c.client_msg_id == client_msg_id)
            ).first()
            return _to_turn(conn, row) if row else None

    def by_id(self, turn_id: str) -> TurnSnapshot | None:
        with self._engine.connect() as conn:
            row = conn.execute(select(turns).where(turns.c.turn_id == turn_id)).first()
            return _to_turn(conn, row) if row else None

    def commit(
        self,
        turn_id: str,
        *,
        parts: Sequence[str],
        fixed: bool,
        prompt_version: str | None,
        usage: Completion | None,
        now: datetime,
    ) -> int:
        with self._engine.begin() as conn:
            row = conn.execute(select(turns).where(turns.c.turn_id == turn_id)).one()
            if row.status != TurnStatus.GENERATING.value or row.output_message_id is not None:
                raise TurnConflict("turn is not generating")
            result = conn.execute(
                messages.insert().values(
                    role="him",
                    mode=Mode.REPLY.value,
                    text="\n".join(parts),
                    parts_json=json.dumps(list(parts), ensure_ascii=False),
                    turn_id=turn_id,
                    prompt_version=prompt_version,
                    tokens_in=usage.tokens_in if usage else 0,
                    tokens_out=usage.tokens_out if usage else 0,
                    created_at=_utc(now),
                )
            )
            message_id = _inserted_id(result)
            conn.execute(
                update(turns)
                .where(turns.c.turn_id == turn_id)
                .values(
                    status=TurnStatus.COMMITTED.value,
                    output_message_id=message_id,
                    fixed=int(fixed),
                    updated_at=_utc(now),
                )
            )
            return message_id

    def fail(self, turn_id: str, error_code: str, *, now: datetime) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                update(turns)
                .where(turns.c.turn_id == turn_id, turns.c.status == TurnStatus.GENERATING.value)
                .values(status=TurnStatus.FAILED.value, error_code=error_code, updated_at=_utc(now))
            )

    def recover_incomplete(self, *, now: datetime) -> int:
        with self._engine.begin() as conn:
            result = conn.execute(
                update(turns)
                .where(turns.c.status == TurnStatus.GENERATING.value)
                .values(
                    status=TurnStatus.FAILED.value,
                    error_code="interrupted",
                    updated_at=_utc(now),
                )
            )
            return result.rowcount or 0


class SqliteMessageRepo:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def add_her(
        self, text: str, *, client_msg_id: str | None, now: datetime
    ) -> tuple[int, bool]:
        values = {
            "role": "her",
            "mode": Mode.REPLY.value,
            "text": text,
            "parts_json": json.dumps([text], ensure_ascii=False),
            "client_msg_id": client_msg_id,
            "created_at": _utc(now),
        }
        with self._engine.begin() as conn:
            if client_msg_id:
                existing = conn.execute(
                    select(messages.c.id).where(messages.c.client_msg_id == client_msg_id)
                ).scalar_one_or_none()
                if existing is not None:
                    return int(existing), False
            try:
                result = conn.execute(messages.insert().values(**values))
            except IntegrityError:
                existing = conn.execute(
                    select(messages.c.id).where(messages.c.client_msg_id == client_msg_id)
                ).scalar_one()
                return int(existing), False
            return _inserted_id(result), True

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
    ) -> int:
        with self._engine.begin() as conn:
            result = conn.execute(
                messages.insert().values(
                    role="him",
                    mode=mode.value,
                    text=text,
                    parts_json=json.dumps(list(parts), ensure_ascii=False),
                    task_id=task_id,
                    prompt_version=prompt_version,
                    tokens_in=usage.tokens_in if usage else 0,
                    tokens_out=usage.tokens_out if usage else 0,
                    created_at=_utc(now),
                )
            )
            return _inserted_id(result)

    def recent(self, limit: int = 12) -> list[StoredMessage]:
        with self._engine.connect() as conn:
            rows = conn.execute(
                select(messages).order_by(messages.c.id.desc()).limit(limit)
            ).all()
        return [_to_message(row) for row in reversed(rows)]

    def since(self, after_id: int, limit: int = 200) -> list[StoredMessage]:
        with self._engine.connect() as conn:
            rows = conn.execute(
                select(messages)
                .where(messages.c.id > after_id)
                .order_by(messages.c.id.asc())
                .limit(limit)
            ).all()
        return [_to_message(row) for row in rows]

    def her_replied_since(self, dt: datetime) -> bool:
        with self._engine.connect() as conn:
            count = conn.execute(
                select(func.count())
                .select_from(messages)
                .where(messages.c.role == "her", messages.c.created_at > _utc(dt))
            ).scalar_one()
        return int(count) > 0

class SqliteProactiveRepo:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def sent_today(self, day: date) -> set[str]:
        with self._engine.connect() as conn:
            rows = conn.execute(
                select(proactive_log.c.task_id).where(
                    proactive_log.c.day == day.isoformat(),
                    proactive_log.c.status == "sent",
                )
            ).all()
        return {str(row.task_id) for row in rows}

    def count_today(self, day: date) -> int:
        with self._engine.connect() as conn:
            count = conn.execute(
                select(func.count())
                .select_from(proactive_log)
                .where(
                    proactive_log.c.day == day.isoformat(),
                    proactive_log.c.status == "sent",
                )
            ).scalar_one()
        return int(count)

    def last_at(self) -> datetime | None:
        with self._engine.connect() as conn:
            value = conn.execute(
                select(func.max(proactive_log.c.at)).where(proactive_log.c.status == "sent")
            ).scalar_one_or_none()
        return _parse(value)

    def reserve_and_send(
        self,
        *,
        day: date,
        task_id: str,
        text: str,
        now: datetime,
        prompt_version: str | None = None,
    ) -> bool:
        day_str = day.isoformat()
        with self._engine.begin() as conn:
            exists = conn.execute(
                select(proactive_log.c.task_id).where(
                    proactive_log.c.day == day_str, proactive_log.c.task_id == task_id
                )
            ).first()
            if exists:
                return False
            conn.execute(
                proactive_log.insert().values(
                    day=day_str,
                    task_id=task_id,
                    status="reserved",
                    text=text,
                    at=_utc(now),
                )
            )
            conn.execute(
                messages.insert().values(
                    role="him",
                    mode=Mode.PROACTIVE.value,
                    text=text,
                    parts_json=json.dumps([text], ensure_ascii=False),
                    task_id=task_id,
                    prompt_version=prompt_version,
                    created_at=_utc(now),
                )
            )
            conn.execute(
                update(proactive_log)
                .where(proactive_log.c.day == day_str, proactive_log.c.task_id == task_id)
                .values(status="sent")
            )
        return True


class SqliteStateRepo:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def get(self, key: str, default: str | None = None) -> str | None:
        with self._engine.connect() as conn:
            value = conn.execute(
                select(app_state.c.value).where(app_state.c.key == key)
            ).scalar_one_or_none()
        return str(value) if value is not None else default

    def set(self, key: str, value: str, *, now: datetime) -> None:
        with self._engine.begin() as conn:
            changed = conn.execute(
                update(app_state)
                .where(app_state.c.key == key)
                .values(value=value, updated_at=_utc(now))
            ).rowcount
            if not changed:
                conn.execute(
                    app_state.insert().values(key=key, value=value, updated_at=_utc(now))
                )

    def muted_until(self, *, now: datetime) -> datetime | None:
        parsed = _parse(self.get("muted_until"))
        return parsed if parsed and parsed > now else None

    def snoozed_until(self, *, now: datetime) -> datetime | None:
        parsed = _parse(self.get("snoozed_until"))
        return parsed if parsed and parsed > now else None


class SqliteSendLogRepo:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def log(
        self,
        *,
        day: date,
        task_id: str,
        reason_code: str | None,
        detail: str = "",
        now: datetime,
    ) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                send_log.insert().values(
                    day=day.isoformat(),
                    task_id=task_id,
                    reason_code=reason_code,
                    detail=detail,
                    at=_utc(now),
                )
            )


class SqliteInboxRepo:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def add(self, *, kind: str, body: str, now: datetime) -> int:
        with self._engine.begin() as conn:
            result = conn.execute(
                owner_inbox.insert().values(kind=kind, body=body, at=_utc(now))
            )
            return _inserted_id(result)

    def set_delivery_status(self, message_id: int, status: DeliveryStatus, *, now: datetime) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                update(owner_inbox)
                .where(owner_inbox.c.id == message_id)
                .values(delivery_status=status.value, delivery_attempted_at=_utc(now))
            )

    def unread(self, limit: int = 50) -> list[dict[str, object]]:
        with self._engine.connect() as conn:
            rows = conn.execute(
                select(owner_inbox)
                .where(owner_inbox.c.read_at.is_(None))
                .order_by(owner_inbox.c.id.desc())
                .limit(limit)
            ).all()
        return [
            {
                "id": row.id,
                "kind": row.kind,
                "body": row.body,
                "at": row.at,
                "delivery_status": row.delivery_status,
                "delivery_attempted_at": row.delivery_attempted_at,
            }
            for row in rows
        ]

    def mark_read(self, ids: Sequence[int]) -> None:
        if not ids:
            return
        with self._engine.begin() as conn:
            conn.execute(
                update(owner_inbox)
                .where(owner_inbox.c.id.in_(list(ids)))
                .values(read_at=datetime.now(UTC).isoformat())
            )
