from __future__ import annotations

import sqlite3

from app.adapters.sqlite import MIGRATIONS_DIR
from app.adapters.sqlite.engine import make_engine
from app.adapters.sqlite.migrate import migrate


def test_existing_owner_inbox_survives_delivery_status_upgrade(tmp_path) -> None:
    db_path = tmp_path / "old.db"
    with sqlite3.connect(db_path) as conn:
        conn.executescript((MIGRATIONS_DIR / "001_init.sql").read_text(encoding="utf-8"))
        conn.execute("PRAGMA user_version = 1")
        conn.execute(
            "INSERT INTO owner_inbox (kind, body, at) VALUES (?, ?, ?)",
            ("crisis", "原有记录", "2026-10-25T04:00:00+00:00"),
        )
        conn.execute(
            "INSERT INTO messages (role, mode, text, parts_json, created_at) VALUES (?, ?, ?, ?, ?)",
            ("her", "reply", "旧消息", '["旧消息"]', "2026-10-25T04:01:00+00:00"),
        )

    engine = make_engine(db_path)
    assert migrate(engine, MIGRATIONS_DIR) == 3
    with engine.connect() as conn:
        row = conn.exec_driver_sql(
            "SELECT kind, body, delivery_status FROM owner_inbox"
        ).one()
    assert tuple(row) == ("crisis", "原有记录", "pending")
    with engine.connect() as conn:
        old_message = conn.exec_driver_sql("SELECT text, turn_id FROM messages").one()
    assert tuple(old_message) == ("旧消息", None)
