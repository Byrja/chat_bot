from datetime import datetime, timezone

from bot.db import get_conn


def reset_drama(db_path: str, chat_id: int, by_user_id: int | None = None) -> None:
    conn = get_conn(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO drama_counter (chat_id, last_reset_at, updated_by_tg_user_id, updated_at)
        VALUES (?, CURRENT_TIMESTAMP, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(chat_id)
        DO UPDATE SET
            last_reset_at=CURRENT_TIMESTAMP,
            updated_by_tg_user_id=excluded.updated_by_tg_user_id,
            updated_at=CURRENT_TIMESTAMP
        """,
        (chat_id, by_user_id),
    )
    conn.commit()
    conn.close()


def get_days_without_drama(db_path: str, chat_id: int) -> int:
    conn = get_conn(db_path)
    cur = conn.cursor()
    cur.execute("SELECT last_reset_at FROM drama_counter WHERE chat_id = ?", (chat_id,))
    row = cur.fetchone()
    conn.close()
    if not row or not row[0]:
        return 0
    dt = datetime.fromisoformat(str(row[0]).replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    delta = now - dt
    return max(0, delta.days)
