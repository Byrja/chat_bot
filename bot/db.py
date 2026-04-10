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
