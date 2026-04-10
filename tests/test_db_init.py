import sqlite3

from bot.db import init_db


def test_init_db_creates_tables(tmp_path):
    db_file = tmp_path / "md4_test.db"
    init_db(str(db_file))

    conn = sqlite3.connect(db_file)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {r[0] for r in cur.fetchall()}
    conn.close()

    assert "users" in tables
    assert "applications" in tables
    assert "application_answers" in tables
    assert "moderation_events" in tables
    assert "sanctions" in tables
