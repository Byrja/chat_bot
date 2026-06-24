import random

from bot.db import get_conn


def add_quote(
    db_path: str,
    chat_id: int,
    source_message_id: int | None,
    author_tg_user_id: int | None,
    author_label: str,
    quote_text: str,
    added_by_tg_user_id: int | None,
) -> int:
    conn = get_conn(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO quotes (chat_id, source_message_id, author_tg_user_id, author_label, quote_text, added_by_tg_user_id)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (chat_id, source_message_id, author_tg_user_id, author_label, quote_text.strip(), added_by_tg_user_id),
    )
    qid = int(cur.lastrowid)
    conn.commit()
    conn.close()
    return qid


def random_quote(db_path: str, chat_id: int):
    conn = get_conn(db_path)
    cur = conn.cursor()
    cur.execute(
        "SELECT id, author_label, quote_text, source_message_id, created_at FROM quotes WHERE chat_id = ?",
        (chat_id,),
    )
    rows = cur.fetchall()
    conn.close()
    if not rows:
        return None
    return random.choice(rows)


def latest_quote(db_path: str, chat_id: int):
    conn = get_conn(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, author_label, quote_text, source_message_id, created_at
        FROM quotes
        WHERE chat_id = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (chat_id,),
    )
    row = cur.fetchone()
    conn.close()
    return row


def list_quotes(db_path: str, chat_id: int, limit: int = 20):
    conn = get_conn(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, author_label, quote_text, source_message_id, created_at
        FROM quotes
        WHERE chat_id = ?
        ORDER BY id DESC
        LIMIT ?
        """,
        (chat_id, limit),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def get_quote_by_id(db_path: str, quote_id: int, chat_id: int):
    conn = get_conn(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, author_label, quote_text, source_message_id, created_at
        FROM quotes
        WHERE id = ? AND chat_id = ?
        """,
        (quote_id, chat_id),
    )
    row = cur.fetchone()
    conn.close()
    return row


def delete_quote(db_path: str, quote_id: int, chat_id: int) -> bool:
    conn = get_conn(db_path)
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM quotes WHERE id = ? AND chat_id = ?",
        (quote_id, chat_id),
    )
    deleted = cur.rowcount > 0
    conn.commit()
    conn.close()
    return deleted
