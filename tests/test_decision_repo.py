import sqlite3

from bot.db import init_db
from bot.repositories.applications import get_or_create_draft_application, set_decision, submit_application, upsert_user


def test_set_decision_only_from_submitted(tmp_path):
    db_file = tmp_path / "md4_decision.db"
    init_db(str(db_file))
    upsert_user(str(db_file), 42, "u42", "U42")

    app_id = get_or_create_draft_application(str(db_file), 42)
    assert set_decision(str(db_file), app_id, "approved", 1) is False

    assert submit_application(str(db_file), app_id) is True
    assert set_decision(str(db_file), app_id, "rejected", 1, "test reason") is True
    assert set_decision(str(db_file), app_id, "approved", 1) is False

    conn = sqlite3.connect(db_file)
    cur = conn.cursor()
    cur.execute("SELECT status, reject_reason FROM applications WHERE id = ?", (app_id,))
    status, reason = cur.fetchone()
    conn.close()

    assert status == "rejected"
    assert reason == "test reason"
