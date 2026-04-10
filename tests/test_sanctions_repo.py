import sqlite3

from bot.db import init_db
from bot.repositories.sanctions import add_sanction


def test_add_warn_sanction_logs_both_tables(tmp_path):
    db_file = tmp_path / "md4_sanctions.db"
    init_db(str(db_file))

    sid = add_sanction(
        str(db_file),
        target_tg_user_id=100,
        action="warn",
        issued_by_tg_user_id=200,
        reason="spam",
        until_at=None,
    )
    assert sid > 0

    conn = sqlite3.connect(db_file)
    cur = conn.cursor()
    cur.execute("SELECT action, reason, issued_by_tg_user_id FROM sanctions WHERE id = ?", (sid,))
    row = cur.fetchone()
    assert row == ("warn", "spam", 200)

    cur.execute("SELECT action, actor_tg_user_id FROM moderation_events ORDER BY id DESC LIMIT 1")
    ev = cur.fetchone()
    conn.close()
    assert ev == ("sanction_warn", 200)
