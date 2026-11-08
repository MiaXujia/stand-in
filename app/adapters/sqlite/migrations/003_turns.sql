CREATE TABLE IF NOT EXISTS turns (
    turn_id TEXT PRIMARY KEY,
    client_msg_id TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL CHECK (status IN ('generating', 'committed', 'failed')),
    input_message_id INTEGER,
    output_message_id INTEGER,
    error_code TEXT,
    fixed INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

ALTER TABLE messages ADD COLUMN turn_id TEXT;
CREATE INDEX IF NOT EXISTS ix_messages_turn ON messages (turn_id);
CREATE UNIQUE INDEX IF NOT EXISTS ux_messages_turn_reply
    ON messages (turn_id) WHERE role = 'him' AND turn_id IS NOT NULL;
