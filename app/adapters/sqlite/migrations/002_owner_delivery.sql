ALTER TABLE owner_inbox ADD COLUMN delivery_status TEXT NOT NULL DEFAULT 'pending';
ALTER TABLE owner_inbox ADD COLUMN delivery_attempted_at TEXT;
