import random

from bot.db import get_conn
from bot.repositories.karma import get_karma, top_karma


def get_friend_foe_stats(db_path: str, chat_id: int, tg_user_id: int) -> dict:
    conn = get_conn(db_path)
    cur = conn.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM karma_events WHERE chat_id = ? AND to_tg_user_id = ? AND delta > 0",
        (chat_id, tg_user_id),
    )
    plus_count = int(cur.fetchone()[0] or 0)
    cur.execute(
        "SELECT COUNT(*) FROM karma_events WHERE chat_id = ? AND to_tg_user_id = ? AND delta < 0",
        (chat_id, tg_user_id),
    )
    minus_count = int(cur.fetchone()[0] or 0)
    conn.close()
    return {
        "karma": get_karma(db_path, chat_id, tg_user_id),
        "plus_count": plus_count,
        "minus_count": minus_count,
    }


def get_friend_foe_top(db_path: str, chat_id: int, limit: int = 3):
    pos, neg = top_karma(db_path, chat_id, limit=limit)
    return pos, neg


def pick_bottle_pair(db_path: str, chat_id: int) -> tuple[int, int] | None:
    conn = get_conn(db_path)
    cur = conn.cursor()
    cur.execute(
        "SELECT tg_user_id FROM member_activity WHERE chat_id = ? ORDER BY msg_count DESC LIMIT 50",
        (chat_id,),
    )
    users = [int(r[0]) for r in cur.fetchall()]
    conn.close()
    users = list(dict.fromkeys(users))
    if len(users) < 2:
        return None
    actor, partner = random.sample(users, 2)
    return actor, partner


def create_bottle_game(db_path: str, chat_id: int, actor_uid: int, partner_uid: int, created_by_uid: int | None) -> int:
    conn = get_conn(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO bottle_games (chat_id, actor_tg_user_id, partner_tg_user_id, status, created_by_tg_user_id)
        VALUES (?, ?, ?, 'pending', ?)
        """,
        (chat_id, actor_uid, partner_uid, created_by_uid),
    )
    gid = int(cur.lastrowid)
    conn.commit()
    conn.close()
    return gid


def resolve_bottle_game(db_path: str, game_id: int, new_status: str) -> tuple[int, int] | None:
    if new_status not in {"done", "fail"}:
        return None
    conn = get_conn(db_path)
    cur = conn.cursor()
    cur.execute("SELECT actor_tg_user_id, partner_tg_user_id, status FROM bottle_games WHERE id = ?", (game_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return None
    actor_uid, partner_uid, status = int(row[0]), int(row[1]), str(row[2])
    if status != "pending":
        conn.close()
        return None

    cur.execute(
        "UPDATE bottle_games SET status = ?, resolved_at = CURRENT_TIMESTAMP WHERE id = ? AND status = 'pending'",
        (new_status, game_id),
    )
    changed = cur.rowcount > 0
    conn.commit()
    conn.close()
    if not changed:
        return None
    return actor_uid, partner_uid
