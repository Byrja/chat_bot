from bot.db import get_conn

_VALID = {"admin", "old", "trusted", "newbie", "lava"}


def get_role(db_path: str, tg_user_id: int) -> str:
    conn = get_conn(db_path)
    cur = conn.cursor()
    cur.execute("SELECT role FROM member_roles WHERE tg_user_id = ?", (tg_user_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return "newbie"
    role = str(row[0])
    return role if role in _VALID else "newbie"


def set_role(db_path: str, tg_user_id: int, role: str, assigned_by_tg_user_id: int | None = None) -> bool:
    if role not in _VALID:
        return False
    conn = get_conn(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO member_roles (tg_user_id, role, assigned_by_tg_user_id, updated_at)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(tg_user_id)
        DO UPDATE SET
            role=excluded.role,
            assigned_by_tg_user_id=excluded.assigned_by_tg_user_id,
            updated_at=CURRENT_TIMESTAMP
        """,
        (tg_user_id, role, assigned_by_tg_user_id),
    )
    conn.commit()
    conn.close()
    return True
