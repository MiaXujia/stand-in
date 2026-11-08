-- 001 · 初始表结构
-- 时间戳统一存 UTC ISO8601；day 用本地日期（Asia/Shanghai）

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    role TEXT NOT NULL CHECK (role IN ('her', 'him')),
    mode TEXT NOT NULL CHECK (mode IN ('reply', 'proactive')),
    text TEXT NOT NULL,
    parts_json TEXT,
    task_id TEXT,
    prompt_version TEXT,
    tokens_in INTEGER NOT NULL DEFAULT 0,
    tokens_out INTEGER NOT NULL DEFAULT 0,
    client_msg_id TEXT,
    created_at TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_messages_client_msg ON messages (client_msg_id);
CREATE INDEX IF NOT EXISTS ix_messages_created ON messages (created_at);

CREATE TABLE IF NOT EXISTS proactive_log (
    day TEXT NOT NULL,
    task_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('reserved', 'sent', 'failed')),
    reason_code TEXT,
    text TEXT,
    at TEXT NOT NULL,
    PRIMARY KEY (day, task_id)
);

CREATE TABLE IF NOT EXISTS send_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    day TEXT NOT NULL,
    task_id TEXT NOT NULL,
    reason_code TEXT,
    detail TEXT NOT NULL DEFAULT '',
    at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_send_log_day ON send_log (day);

CREATE TABLE IF NOT EXISTS app_state (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS owner_inbox (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,
    body TEXT NOT NULL,
    at TEXT NOT NULL,
    read_at TEXT
);
