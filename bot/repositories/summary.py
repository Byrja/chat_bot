from bot.db import get_conn


def get_last_text_messages(db_path: str, chat_id: int, limit: int = 50) -> list[dict]:
    """Вернуть последние N текстовых сообщений из чата (chronological order)."""
    conn = get_conn(db_path)
    conn.row_factory = lambda c, r: {col[0]: r[idx] for idx, col in enumerate(c.description)}
    cur = conn.cursor()
    cur.execute(
        """
        SELECT mm.tg_user_id, ma.first_name, mm.text, mm.created_at
        FROM member_messages mm
        LEFT JOIN member_activity ma
          ON ma.chat_id = mm.chat_id AND ma.tg_user_id = mm.tg_user_id
        WHERE mm.chat_id = ? AND mm.msg_type = 'text' AND mm.text IS NOT NULL AND mm.text != ''
        ORDER BY mm.created_at DESC
        LIMIT ?
        """,
        (chat_id, limit),
    )
    rows = list(cur.fetchall())
    conn.close()
    rows.reverse()  # chronological order for summary
    return rows


def can_use_summary(db_path: str, tg_user_id: int, max_per_day: int = 3) -> bool:
    conn = get_conn(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT COUNT(*) FROM summary_usage
        WHERE tg_user_id = ? AND datetime(used_at) >= datetime('now', '-1 day')
        """,
        (tg_user_id,),
    )
    count = int(cur.fetchone()[0])
    conn.close()
    return count < max_per_day


def remaining_summary_uses(db_path: str, tg_user_id: int, max_per_day: int = 3) -> int:
    conn = get_conn(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT COUNT(*) FROM summary_usage
        WHERE tg_user_id = ? AND datetime(used_at) >= datetime('now', '-1 day')
        """,
        (tg_user_id,),
    )
    count = int(cur.fetchone()[0])
    conn.close()
    return max(0, max_per_day - count)


def log_summary_usage(db_path: str, tg_user_id: int) -> None:
    conn = get_conn(db_path)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO summary_usage (tg_user_id, used_at) VALUES (?, CURRENT_TIMESTAMP)",
        (tg_user_id,),
    )
    conn.commit()
    conn.close()
