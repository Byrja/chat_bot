import sqlite3

from bot.db import init_db
from bot.repositories.applications import get_or_create_draft_application, submit_application, upsert_user


def test_submit_application_changes_status(tmp_path):
    db_file = tmp_path / "md4_submit.db"
    init_db(str(db_file))
    upsert_user(str(db_file), 1, "u", "f")
    app_id = get_or_create_draft_application(str(db_file), 1)

    assert submit_application(str(db_file), app_id) is True
    assert submit_application(str(db_file), app_id) is False

    conn = sqlite3.connect(db_file)
    cur = conn.cursor()
    cur.execute("SELECT status, submitted_at FROM applications WHERE id = ?", (app_id,))
    status, submitted_at = cur.fetchone()
    conn.close()

    assert status == "submitted"
    assert submitted_at is not None
