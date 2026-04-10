from bot.db import get_conn


def count_submitted_today(db_path: str, tg_user_id: int) -> int:
    conn = get_conn(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT COUNT(*)
        FROM applications
        WHERE tg_user_id = ?
          AND status IN ('submitted','approved','rejected')
          AND date(COALESCE(submitted_at, created_at)) = date('now')
        """,
        (tg_user_id,),
    )
    n = int(cur.fetchone()[0] or 0)
    conn.close()
    return n


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


def set_decision(db_path: str, application_id: int, status: str, decided_by_admin_id: int, reject_reason: str | None = None) -> bool:
    if status not in {"approved", "rejected"}:
        return False
    conn = get_conn(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE applications
        SET status=?, decided_at=CURRENT_TIMESTAMP, decided_by_admin_id=?, reject_reason=?, updated_at=CURRENT_TIMESTAMP
        WHERE id = ? AND status = 'submitted'
        """,
        (status, decided_by_admin_id, reject_reason, application_id),
    )
    changed = cur.rowcount > 0
    conn.commit()
    conn.close()
    return changed


def get_application_owner(db_path: str, application_id: int) -> int | None:
    conn = get_conn(db_path)
    cur = conn.cursor()
    cur.execute("SELECT tg_user_id FROM applications WHERE id = ?", (application_id,))
    row = cur.fetchone()
    conn.close()
    return int(row[0]) if row else None


def submit_application(db_path: str, application_id: int) -> bool:
    conn = get_conn(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE applications
        SET status='submitted', submitted_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP
        WHERE id = ? AND status = 'draft'
        """,
        (application_id,),
    )
    changed = cur.rowcount > 0
    conn.commit()
    conn.close()
    return changed


def get_application_for_admin(db_path: str, application_id: int) -> tuple[int, dict[str, str]] | None:
    owner = get_application_owner(db_path, application_id)
    if owner is None:
        return None
    return owner, get_answers_map(db_path, application_id)


def get_answers_map(db_path: str, application_id: int) -> dict[str, str]:
    conn = get_conn(db_path)
    cur = conn.cursor()
    cur.execute(
        "SELECT question_code, answer_text FROM application_answers WHERE application_id = ? ORDER BY position ASC",
        (application_id,),
    )
    rows = cur.fetchall()
    conn.close()
    return {str(r[0]): str(r[1]) for r in rows}


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
