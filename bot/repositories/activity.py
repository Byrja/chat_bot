from bot.db import get_conn


def get_top_week_activity(db_path: str, chat_id: int, limit: int = 20):
    conn = get_conn(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT mm.tg_user_id,
               COUNT(*) as c,
               MAX(mm.created_at) as last_at,
               COALESCE(ma.username, ''),
               COALESCE(ma.first_name, '')
        FROM member_messages mm
        LEFT JOIN member_activity ma
          ON ma.chat_id = mm.chat_id AND ma.tg_user_id = mm.tg_user_id
        WHERE mm.chat_id = ?
          AND datetime(mm.created_at) >= datetime('now', '-7 days')
        GROUP BY mm.tg_user_id, ma.username, ma.first_name
        ORDER BY c DESC, datetime(last_at) DESC
        LIMIT ?
        """,
        (chat_id, limit),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def bump_message_activity(
    db_path: str,
    chat_id: int,
    tg_user_id: int,
    username: str | None,
    first_name: str | None,
) -> None:
    conn = get_conn(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO member_activity (chat_id, tg_user_id, username, first_name, msg_count, last_message_at, updated_at)
        VALUES (?, ?, ?, ?, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ON CONFLICT(chat_id, tg_user_id)
        DO UPDATE SET
            username=excluded.username,
            first_name=excluded.first_name,
            msg_count=member_activity.msg_count + 1,
            last_message_at=CURRENT_TIMESTAMP,
            updated_at=CURRENT_TIMESTAMP
        """,
        (chat_id, tg_user_id, username or None, first_name or None),
    )
    cur.execute(
        "INSERT INTO member_messages (chat_id, tg_user_id) VALUES (?, ?)",
        (chat_id, tg_user_id),
    )
    conn.commit()
    conn.close()


def get_top_activity(db_path: str, chat_id: int, limit: int = 20):
    conn = get_conn(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT tg_user_id, COALESCE(username, ''), COALESCE(first_name, ''), msg_count, last_message_at
        FROM member_activity
        WHERE chat_id = ?
        ORDER BY msg_count DESC, datetime(last_message_at) DESC
        LIMIT ?
        """,
        (chat_id, limit),
    )
    rows = cur.fetchall()
    conn.close()
    return rows
