import sqlite3

from bot.db import init_db
from bot.repositories.applications import get_or_create_draft_application, save_answer, upsert_user


def test_save_answer_replaces_previous(tmp_path):
    db_file = tmp_path / "md4_repo.db"
    init_db(str(db_file))

    upsert_user(str(db_file), 1, "user", "Name")
    app_id = get_or_create_draft_application(str(db_file), 1)
    save_answer(str(db_file), app_id, "name", "Alex", 1)
    save_answer(str(db_file), app_id, "name", "Sasha", 1)

    conn = sqlite3.connect(db_file)
    cur = conn.cursor()
    cur.execute("SELECT answer_text FROM application_answers WHERE application_id = ? AND question_code = 'name'", (app_id,))
    rows = cur.fetchall()
    conn.close()

    assert len(rows) == 1
    assert rows[0][0] == "Sasha"
