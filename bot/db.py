import sqlite3
from pathlib import Path


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tg_user_id INTEGER UNIQUE NOT NULL,
    username TEXT,
    first_name TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tg_user_id INTEGER NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('draft','submitted','approved','rejected')) DEFAULT 'draft',
    submitted_at DATETIME,
    decided_at DATETIME,
    decided_by_admin_id INTEGER,
    reject_reason TEXT,
    invite_link TEXT,
    invite_expires_at DATETIME,
    invite_uses_limit INTEGER NOT NULL DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS application_answers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id INTEGER NOT NULL,
    question_code TEXT NOT NULL,
    answer_text TEXT NOT NULL,
    position INTEGER NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS moderation_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    actor_tg_user_id INTEGER,
    meta_json TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sanctions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_tg_user_id INTEGER NOT NULL,
    action TEXT NOT NULL CHECK(action IN ('warn','mute','ban')),
    reason TEXT,
    until_at DATETIME,
    issued_by_tg_user_id INTEGER NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_applications_user_created
ON applications(tg_user_id, created_at);

CREATE INDEX IF NOT EXISTS idx_answers_app_position
ON application_answers(application_id, position);

CREATE TABLE IF NOT EXISTS member_activity (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    tg_user_id INTEGER NOT NULL,
    username TEXT,
    first_name TEXT,
    msg_count INTEGER NOT NULL DEFAULT 0,
    last_message_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(chat_id, tg_user_id)
);

CREATE INDEX IF NOT EXISTS idx_member_activity_chat_msgcount
ON member_activity(chat_id, msg_count DESC);

CREATE TABLE IF NOT EXISTS member_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    tg_user_id INTEGER NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_member_messages_chat_created
ON member_messages(chat_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_member_messages_chat_user_created
ON member_messages(chat_id, tg_user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS reply_pairs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    from_tg_user_id INTEGER NOT NULL,
    to_tg_user_id INTEGER NOT NULL,
    pair_count INTEGER NOT NULL DEFAULT 0,
    last_reply_at DATETIME,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(chat_id, from_tg_user_id, to_tg_user_id)
);

CREATE INDEX IF NOT EXISTS idx_reply_pairs_chat_count
ON reply_pairs(chat_id, pair_count DESC);

CREATE TABLE IF NOT EXISTS member_roles (
    tg_user_id INTEGER PRIMARY KEY,
    role TEXT NOT NULL CHECK(role IN ('admin','old','trusted','newbie')) DEFAULT 'newbie',
    assigned_by_tg_user_id INTEGER,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS member_profiles (
    tg_user_id INTEGER PRIMARY KEY,
    birth_day INTEGER,
    birth_month INTEGER,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS birthday_notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tg_user_id INTEGER NOT NULL,
    event_type TEXT NOT NULL CHECK(event_type IN ('week_before','today')),
    event_date TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tg_user_id, event_type, event_date)
);

CREATE TABLE IF NOT EXISTS quotes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    source_message_id INTEGER,
    author_tg_user_id INTEGER,
    author_label TEXT,
    quote_text TEXT NOT NULL,
    added_by_tg_user_id INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_quotes_chat_created
ON quotes(chat_id, created_at DESC);

CREATE TABLE IF NOT EXISTS drama_counter (
    chat_id INTEGER PRIMARY KEY,
    last_reset_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_by_tg_user_id INTEGER,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS karma_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    tg_user_id INTEGER NOT NULL,
    score INTEGER NOT NULL DEFAULT 0,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(chat_id, tg_user_id)
);

CREATE TABLE IF NOT EXISTS karma_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    from_tg_user_id INTEGER NOT NULL,
    to_tg_user_id INTEGER NOT NULL,
    delta INTEGER NOT NULL,
    reason TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS bottle_games (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    actor_tg_user_id INTEGER NOT NULL,
    partner_tg_user_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','done','fail')),
    created_by_tg_user_id INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    resolved_at DATETIME
);
"""


def ensure_parent(db_path: str) -> None:
    Path(db_path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)


def get_conn(db_path: str) -> sqlite3.Connection:
    ensure_parent(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str) -> None:
    conn = get_conn(db_path)
    try:
        conn.executescript(SCHEMA_SQL)
        conn.commit()
    finally:
        conn.close()
