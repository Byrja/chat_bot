import sqlite3

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
    msg_type: str = "text",
    message_id: int | None = None,
    text: str | None = None,
) -> None:
    conn = get_conn(db_path)
    cur = conn.cursor()
    # Сначала пробуем вставить строку в member_messages — UNIQUE INDEX защищает
    # от дублей Telegram-Update'ов (если бот получит один и тот же message_id
    # дважды — например, после рестарта).
    try:
        cur.execute(
            """
            INSERT INTO member_messages (chat_id, tg_user_id, msg_type, message_id, text)
            VALUES (?, ?, ?, ?, ?)
            """,
            (chat_id, tg_user_id, msg_type, message_id, text),
        )
    except sqlite3.IntegrityError:
        # Этот message_id уже записан (дубль от Telegram после рестарта) — выходим,
        # не инкрементируя msg_count. Иначе бот бы считал одно сообщение дважды.
        conn.rollback()
        conn.close()
        return

    # Только если новая строка реально добавлена — инкрементируем счётчик.
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


def get_asleep_activity(db_path: str, chat_id: int, limit: int = 20):
    """Пользователи, которые дольше всех не пишут (last_message_at самый старый)."""
    conn = get_conn(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT tg_user_id, COALESCE(username, ''), COALESCE(first_name, ''), msg_count, last_message_at
        FROM member_activity
        WHERE chat_id = ?
          AND last_message_at IS NOT NULL
        ORDER BY datetime(last_message_at) ASC
        LIMIT ?
        """,
        (chat_id, limit),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def get_today_activity(db_path: str, chat_id: int, limit: int = 20):
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
          AND datetime(mm.created_at) >= datetime('now', '-1 day')
        GROUP BY mm.tg_user_id, ma.username, ma.first_name
        ORDER BY c DESC, datetime(last_at) DESC
        LIMIT ?
        """,
        (chat_id, limit),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def count_today_messages(db_path: str, chat_id: int) -> int:
    conn = get_conn(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT COUNT(*) FROM member_messages
        WHERE chat_id = ?
          AND datetime(created_at) >= datetime('now', '-1 day')
        """,
        (chat_id,),
    )
    row = cur.fetchone()
    conn.close()
    return row[0] if row else 0


def get_activity_members(db_path: str, chat_id: int):
    conn = get_conn(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT tg_user_id, COALESCE(username, ''), COALESCE(first_name, '')
        FROM member_activity
        WHERE chat_id = ?
        ORDER BY msg_count DESC
        """,
        (chat_id,),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def ensure_member(db_path: str, chat_id: int, tg_user_id: int, username: str | None, first_name: str | None) -> None:
    conn = get_conn(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO member_activity (chat_id, tg_user_id, username, first_name, msg_count, last_message_at, updated_at)
        VALUES (?, ?, ?, ?, 0, NULL, CURRENT_TIMESTAMP)
        ON CONFLICT(chat_id, tg_user_id)
        DO UPDATE SET
            username=excluded.username,
            first_name=excluded.first_name,
            updated_at=CURRENT_TIMESTAMP
        WHERE excluded.username IS NOT NULL OR excluded.first_name IS NOT NULL
        """,
        (chat_id, tg_user_id, username or None, first_name or None),
    )
    conn.commit()
    conn.close()


def update_member_name(db_path: str, chat_id: int, tg_user_id: int, first_name: str) -> None:
    conn = get_conn(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE member_activity
        SET first_name = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE chat_id = ? AND tg_user_id = ?
        """,
        (first_name, chat_id, tg_user_id),
    )
    conn.commit()
    conn.close()
