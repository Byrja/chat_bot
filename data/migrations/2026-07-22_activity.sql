-- Migration: harden activity counter (apply to data/md4.db on a fresh DB or after restoring a pre-2026-07-22 backup).
-- 1) msg_type column (default 'text') so track_message_activity can store what kind of message was counted.
-- 2) message_id column + UNIQUE INDEX for (chat_id, message_id) so re-delivered Telegram Updates after
--    restart do not double-count (bump_message_activity catches IntegrityError and returns).
-- Idempotent: uses IF NOT EXISTS where supported; rerun safely.

-- 1) member_messages.msg_type
ALTER TABLE member_messages ADD COLUMN msg_type TEXT DEFAULT 'text';

-- 2) member_messages.message_id + UNIQUE INDEX
ALTER TABLE member_messages ADD COLUMN message_id INTEGER;

CREATE INDEX IF NOT EXISTS idx_member_messages_msgid
    ON member_messages(chat_id, message_id);

CREATE UNIQUE INDEX IF NOT EXISTS idx_member_messages_unique_msgid
    ON member_messages(chat_id, message_id)
    WHERE message_id IS NOT NULL;

-- Verification (run manually after migration):
--   SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_member%';
--   Expected: idx_member_messages_msgid, idx_member_messages_unique_msgid
