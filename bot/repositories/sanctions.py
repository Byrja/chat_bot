import json

from bot.db import get_conn


def add_sanction(
    db_path: str,
    target_tg_user_id: int,
    action: str,
    issued_by_tg_user_id: int,
    reason: str | None = None,
    until_at: str | None = None,
) -> int:
    conn = get_conn(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO sanctions (target_tg_user_id, action, reason, until_at, issued_by_tg_user_id)
        VALUES (?, ?, ?, ?, ?)
        """,
        (target_tg_user_id, action, reason, until_at, issued_by_tg_user_id),
    )
    sanction_id = int(cur.lastrowid)

    cur.execute(
        """
        INSERT INTO moderation_events (application_id, action, actor_tg_user_id, meta_json)
        VALUES (?, ?, ?, ?)
        """,
        (
            0,
            f"sanction_{action}",
            issued_by_tg_user_id,
            json.dumps(
                {
                    "target_tg_user_id": target_tg_user_id,
                    "reason": reason,
                    "until_at": until_at,
                    "sanction_id": sanction_id,
                },
                ensure_ascii=False,
            ),
        ),
    )

    conn.commit()
    conn.close()
    return sanction_id
