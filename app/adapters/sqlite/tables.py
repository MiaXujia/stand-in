"""SQLAlchemy Core 表定义（只在 sqlite 适配器内部使用）。"""

from __future__ import annotations

from sqlalchemy import Column, Integer, MetaData, Table, Text

metadata = MetaData()

messages = Table(
    "messages",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("role", Text, nullable=False),
    Column("mode", Text, nullable=False),
    Column("text", Text, nullable=False),
    Column("parts_json", Text),
    Column("task_id", Text),
    Column("prompt_version", Text),
    Column("tokens_in", Integer, nullable=False, server_default="0"),
    Column("tokens_out", Integer, nullable=False, server_default="0"),
    Column("client_msg_id", Text),
    Column("turn_id", Text),
    Column("created_at", Text, nullable=False),
)

turns = Table(
    "turns",
    metadata,
    Column("turn_id", Text, primary_key=True),
    Column("client_msg_id", Text, nullable=False),
    Column("status", Text, nullable=False),
    Column("input_message_id", Integer),
    Column("output_message_id", Integer),
    Column("error_code", Text),
    Column("fixed", Integer, nullable=False, server_default="0"),
    Column("created_at", Text, nullable=False),
    Column("updated_at", Text, nullable=False),
)

proactive_log = Table(
    "proactive_log",
    metadata,
    Column("day", Text, primary_key=True),
    Column("task_id", Text, primary_key=True),
    Column("status", Text, nullable=False),
    Column("reason_code", Text),
    Column("text", Text),
    Column("at", Text, nullable=False),
)

send_log = Table(
    "send_log",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("day", Text, nullable=False),
    Column("task_id", Text, nullable=False),
    Column("reason_code", Text),
    Column("detail", Text, nullable=False, server_default=""),
    Column("at", Text, nullable=False),
)

app_state = Table(
    "app_state",
    metadata,
    Column("key", Text, primary_key=True),
    Column("value", Text, nullable=False),
    Column("updated_at", Text, nullable=False),
)

owner_inbox = Table(
    "owner_inbox",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("kind", Text, nullable=False),
    Column("body", Text, nullable=False),
    Column("at", Text, nullable=False),
    Column("read_at", Text),
    Column("delivery_status", Text, nullable=False, server_default="pending"),
    Column("delivery_attempted_at", Text),
)
