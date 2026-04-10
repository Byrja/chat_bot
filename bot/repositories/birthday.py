from datetime import date, timedelta

from bot.db import get_conn


def _next_birthday(d: int, m: int, today: date) -> date:
    year = today.year
    try_date = date(year, m, d)
    if try_date < today:
        try_date = date(year + 1, m, d)
    return try_date


def get_birthdays_for_offset(db_path: str, offset_days: int):
    today = date.today()
    target = today + timedelta(days=offset_days)

    conn = get_conn(db_path)
    cur = conn.cursor()
    cur.execute("SELECT tg_user_id, birth_day, birth_month FROM member_profiles")
    rows = cur.fetchall()
    out = []
    for uid, day, month in rows:
        try:
            nb = _next_birthday(int(day), int(month), today)
        except Exception:
            continue
        if nb == target:
            out.append((int(uid), int(day), int(month)))
    conn.close()
    return out, target.isoformat()


def was_notified(db_path: str, tg_user_id: int, event_type: str, event_date: str) -> bool:
    conn = get_conn(db_path)
    cur = conn.cursor()
    cur.execute(
        "SELECT 1 FROM birthday_notifications WHERE tg_user_id = ? AND event_type = ? AND event_date = ?",
        (tg_user_id, event_type, event_date),
    )
    row = cur.fetchone()
    conn.close()
    return row is not None


def mark_notified(db_path: str, tg_user_id: int, event_type: str, event_date: str) -> None:
    conn = get_conn(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT OR IGNORE INTO birthday_notifications (tg_user_id, event_type, event_date)
        VALUES (?, ?, ?)
        """,
        (tg_user_id, event_type, event_date),
    )
    conn.commit()
    conn.close()


def get_user_label(db_path: str, chat_id: int, tg_user_id: int) -> str:
    conn = get_conn(db_path)
    cur = conn.cursor()
    cur.execute(
        "SELECT COALESCE(username,''), COALESCE(first_name,'') FROM member_activity WHERE chat_id = ? AND tg_user_id = ? ORDER BY updated_at DESC LIMIT 1",
        (chat_id, tg_user_id),
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        return str(tg_user_id)
    uname, fname = row
    return f"@{uname}" if uname else (fname or str(tg_user_id))
