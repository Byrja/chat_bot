from bot.db import get_conn


def upsert_user(db_path: str, tg_user_id: int, username: str | None, first_name: str | None) -> None:
    conn = get_conn(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO users (tg_user_id, username, first_name)
        VALUES (?, ?, ?)
        ON CONFLICT(tg_user_id) DO UPDATE SET
            username=excluded.username,
            first_name=excluded.first_name
        """,
        (tg_user_id, username or None, first_name or None),
    )
    conn.commit()
    conn.close()


def get_or_create_draft_application(db_path: str, tg_user_id: int) -> int:
    conn = get_conn(db_path)
    cur = conn.cursor()
    cur.execute(
        "SELECT id FROM applications WHERE tg_user_id = ? AND status = 'draft' ORDER BY id DESC LIMIT 1",
        (tg_user_id,),
    )
    row = cur.fetchone()
    if row:
        conn.close()
        return int(row[0])

    cur.execute("INSERT INTO applications (tg_user_id, status) VALUES (?, 'draft')", (tg_user_id,))
    app_id = int(cur.lastrowid)
    conn.commit()
    conn.close()
    return app_id


def save_answer(db_path: str, application_id: int, question_code: str, answer_text: str, position: int) -> None:
    conn = get_conn(db_path)
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM application_answers WHERE application_id = ? AND question_code = ?",
        (application_id, question_code),
    )
    cur.execute(
        """
        INSERT INTO application_answers (application_id, question_code, answer_text, position)
        VALUES (?, ?, ?, ?)
        """,
        (application_id, question_code, answer_text.strip(), position),
    )
    conn.commit()
    conn.close()
