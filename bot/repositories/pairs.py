from bot.db import get_conn


def bump_reply_pair(db_path: str, chat_id: int, from_uid: int, to_uid: int) -> None:
    if from_uid == to_uid:
        return
    conn = get_conn(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO reply_pairs (chat_id, from_tg_user_id, to_tg_user_id, pair_count, last_reply_at, updated_at)
        VALUES (?, ?, ?, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ON CONFLICT(chat_id, from_tg_user_id, to_tg_user_id)
        DO UPDATE SET
            pair_count=reply_pairs.pair_count + 1,
            last_reply_at=CURRENT_TIMESTAMP,
            updated_at=CURRENT_TIMESTAMP
        """,
        (chat_id, from_uid, to_uid),
    )
    conn.commit()
    conn.close()


def get_top_pairs(db_path: str, chat_id: int, limit: int = 10, since_days: int | None = None):
    conn = get_conn(db_path)
    cur = conn.cursor()
    if since_days is None:
        cur.execute(
            """
            SELECT from_tg_user_id, to_tg_user_id, pair_count, last_reply_at
            FROM reply_pairs
            WHERE chat_id = ?
            ORDER BY pair_count DESC, datetime(last_reply_at) DESC
            LIMIT ?
            """,
            (chat_id, limit),
        )
        rows = cur.fetchall()
        conn.close()
        return rows

    # Recalculate for recent window from message-level replies (derived from pair last update)
    cur.execute(
        """
        SELECT from_tg_user_id, to_tg_user_id, pair_count, last_reply_at
        FROM reply_pairs
        WHERE chat_id = ?
          AND datetime(last_reply_at) >= datetime('now', ?)
        ORDER BY pair_count DESC, datetime(last_reply_at) DESC
        LIMIT ?
        """,
        (chat_id, f"-{since_days} days", limit),
    )
    rows = cur.fetchall()
    conn.close()
    return rows
