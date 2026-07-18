from bot.db import get_conn


def list_members_for_mod(db_path: str, chat_id: int, limit: int = 200):
    """Список участников чата для модераторской панели."""
    conn = get_conn(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT tg_user_id, COALESCE(username, ''), COALESCE(first_name, ''), msg_count, last_message_at
        FROM member_activity
        WHERE chat_id = ?
        ORDER BY first_name COLLATE NOCASE ASC, username COLLATE NOCASE ASC
        LIMIT ?
        """,
        (chat_id, limit),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def get_member_summary(db_path: str, chat_id: int, tg_user_id: int) -> dict | None:
    conn = get_conn(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT tg_user_id, COALESCE(username, '') as username, COALESCE(first_name, '') as first_name,
               msg_count, last_message_at, created_at
        FROM member_activity
        WHERE chat_id = ? AND tg_user_id = ?
        LIMIT 1
        """,
        (chat_id, tg_user_id),
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    return dict(row)


def list_notes(db_path: str, target_tg_user_id: int, limit: int = 20) -> list[dict]:
    conn = get_conn(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, author_tg_user_id, note_text, created_at
        FROM member_notes
        WHERE target_tg_user_id = ?
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (target_tg_user_id, limit),
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def add_note(db_path: str, target_tg_user_id: int, author_tg_user_id: int, note_text: str) -> int:
    conn = get_conn(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO member_notes (target_tg_user_id, author_tg_user_id, note_text, created_at, updated_at)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """,
        (target_tg_user_id, author_tg_user_id, note_text),
    )
    note_id = cur.lastrowid
    conn.commit()
    conn.close()
    return note_id


def delete_note(db_path: str, note_id: int) -> bool:
    conn = get_conn(db_path)
    cur = conn.cursor()
    cur.execute("DELETE FROM member_notes WHERE id = ?", (note_id,))
    deleted = cur.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


def count_warns(db_path: str, target_tg_user_id: int) -> int:
    from bot.repositories.sanctions import count_warns as _count_warns
    return _count_warns(db_path, target_tg_user_id)


def get_role(db_path: str, tg_user_id: int) -> str | None:
    from bot.repositories.roles import get_role as _get_role
    return _get_role(db_path, tg_user_id)
