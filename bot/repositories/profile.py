from bot.db import get_conn


def set_birthdate(db_path: str, tg_user_id: int, day: int, month: int) -> None:
    conn = get_conn(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO member_profiles (tg_user_id, birth_day, birth_month, updated_at)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(tg_user_id)
        DO UPDATE SET birth_day=excluded.birth_day, birth_month=excluded.birth_month, updated_at=CURRENT_TIMESTAMP
        """,
        (tg_user_id, day, month),
    )
    conn.commit()
    conn.close()


def get_birthdate(db_path: str, tg_user_id: int) -> tuple[int, int] | None:
    conn = get_conn(db_path)
    cur = conn.cursor()
    cur.execute("SELECT birth_day, birth_month FROM member_profiles WHERE tg_user_id = ?", (tg_user_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    return int(row[0]), int(row[1])
