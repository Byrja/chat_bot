from bot.db import get_conn


def apply_karma(db_path: str, chat_id: int, from_uid: int, to_uid: int, delta: int, reason: str | None = None) -> None:
    conn = get_conn(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO karma_scores (chat_id, tg_user_id, score, updated_at)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(chat_id, tg_user_id)
        DO UPDATE SET score = karma_scores.score + excluded.score, updated_at=CURRENT_TIMESTAMP
        """,
        (chat_id, to_uid, delta),
    )
    cur.execute(
        """
        INSERT INTO karma_events (chat_id, from_tg_user_id, to_tg_user_id, delta, reason)
        VALUES (?, ?, ?, ?, ?)
        """,
        (chat_id, from_uid, to_uid, delta, reason),
    )
    conn.commit()
    conn.close()


def get_karma(db_path: str, chat_id: int, tg_user_id: int) -> int:
    conn = get_conn(db_path)
    cur = conn.cursor()
    cur.execute("SELECT score FROM karma_scores WHERE chat_id = ? AND tg_user_id = ?", (chat_id, tg_user_id))
    row = cur.fetchone()
    conn.close()
    return int(row[0]) if row else 0


def top_karma(db_path: str, chat_id: int, limit: int = 10):
    conn = get_conn(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT tg_user_id, score
        FROM karma_scores
        WHERE chat_id = ?
        ORDER BY score DESC, tg_user_id ASC
        LIMIT ?
        """,
        (chat_id, limit),
    )
    pos = cur.fetchall()

    cur.execute(
        """
        SELECT tg_user_id, score
        FROM karma_scores
        WHERE chat_id = ?
        ORDER BY score ASC, tg_user_id ASC
        LIMIT ?
        """,
        (chat_id, limit),
    )
    neg = cur.fetchall()

    conn.close()
    return pos, neg
