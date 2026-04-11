from bot.db import get_conn


def _pair(a: int, b: int) -> tuple[int, int]:
    return (a, b) if a < b else (b, a)


def create_friend_request(db_path: str, chat_id: int, from_uid: int, to_uid: int) -> int | None:
    if from_uid == to_uid:
        return None
    a, b = _pair(from_uid, to_uid)
    conn = get_conn(db_path)
    cur = conn.cursor()
    cur.execute("SELECT id, status FROM friendships WHERE chat_id = ? AND user_a = ? AND user_b = ?", (chat_id, a, b))
    row = cur.fetchone()
    if row:
        fid, status = int(row[0]), str(row[1])
        conn.close()
        if status == "accepted":
            return 0
        return fid

    cur.execute(
        """
        INSERT INTO friendships (chat_id, user_a, user_b, status, pending_from)
        VALUES (?, ?, ?, 'pending', ?)
        """,
        (chat_id, a, b, from_uid),
    )
    fid = int(cur.lastrowid)
    conn.commit()
    conn.close()
    return fid


def accept_friend_request(db_path: str, friendship_id: int, accepter_uid: int) -> bool:
    conn = get_conn(db_path)
    cur = conn.cursor()
    cur.execute(
        "SELECT user_a, user_b, status, pending_from FROM friendships WHERE id = ?",
        (friendship_id,),
    )
    row = cur.fetchone()
    if not row:
        conn.close()
        return False
    ua, ub, status, pending_from = int(row[0]), int(row[1]), str(row[2]), int(row[3])
    if status != "pending":
        conn.close()
        return False
    if accepter_uid not in {ua, ub} or accepter_uid == pending_from:
        conn.close()
        return False

    cur.execute(
        "UPDATE friendships SET status='accepted', accepted_at=CURRENT_TIMESTAMP WHERE id = ? AND status='pending'",
        (friendship_id,),
    )
    ok = cur.rowcount > 0
    conn.commit()
    conn.close()
    return ok


def add_goat(db_path: str, chat_id: int, from_uid: int, to_uid: int) -> bool:
    if from_uid == to_uid:
        return False
    conn = get_conn(db_path)
    cur = conn.cursor()
    cur.execute(
        "INSERT OR IGNORE INTO goats (chat_id, from_tg_user_id, to_tg_user_id) VALUES (?, ?, ?)",
        (chat_id, from_uid, to_uid),
    )
    ok = cur.rowcount > 0
    conn.commit()
    conn.close()
    return ok


def relation_stats(db_path: str, chat_id: int, uid: int) -> dict:
    conn = get_conn(db_path)
    cur = conn.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM friendships WHERE chat_id = ? AND status='accepted' AND (user_a = ? OR user_b = ?)",
        (chat_id, uid, uid),
    )
    friends = int(cur.fetchone()[0] or 0)
    cur.execute("SELECT COUNT(*) FROM goats WHERE chat_id = ? AND from_tg_user_id = ?", (chat_id, uid))
    goats_out = int(cur.fetchone()[0] or 0)
    cur.execute("SELECT COUNT(*) FROM goats WHERE chat_id = ? AND to_tg_user_id = ?", (chat_id, uid))
    goats_in = int(cur.fetchone()[0] or 0)
    conn.close()
    return {"friends": friends, "goats_out": goats_out, "goats_in": goats_in}
