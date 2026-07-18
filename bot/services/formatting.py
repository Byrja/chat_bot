"""Shared formatting helpers for bot output.

Single source of truth for user-link HTML, human-readable dates, and the
"back to menu" keyboard. Keep this file small and stable — every handler
in bot/handlers/ imports from here.
"""
from __future__ import annotations

import html
from datetime import datetime, timezone
from typing import Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


# --- User links ----------------------------------------------------------

def user_link_from_parts(first_name: str, username: str, uid: int) -> str:
    """HTML tg://user?id=UID link from raw DB fields (username, first_name, uid).

    Returns `<a href="tg://user?id=UID">display_name</a>`.
    """
    name = first_name or (f"@{username}" if username else f"User {uid}")
    name = html.escape(name)
    return f'<a href="tg://user?id={uid}">{name}</a>'


def user_link_from_user(user) -> str:
    """HTML tg://user?id=UID link from a telegram.User object.

    Returns `—` if user is None.
    """
    if not user:
        return "—"
    name = user.username or user.first_name or str(user.id)
    name = html.escape(name)
    return f'<a href="tg://user?id={user.id}">{name}</a>'


def user_label_from_user(user) -> str:
    """Plain text display name from telegram.User (no HTML)."""
    if not user:
        return "unknown"
    return user.first_name or (f"@{user.username}" if user.username else str(user.id))


def user_link_from_db(db_path: str, uid: int, chat_id: Optional[int] = None) -> str:
    """Look up the latest username/first_name for uid and return HTML link.

    If chat_id is given, restricts lookup to that chat; otherwise picks the
    most recently updated row across all chats.
    """
    from bot.db import get_conn

    conn = get_conn(db_path)
    cur = conn.cursor()
    try:
        if chat_id is not None:
            cur.execute(
                "SELECT COALESCE(username, ''), COALESCE(first_name, '') "
                "FROM member_activity WHERE chat_id = ? AND tg_user_id = ? "
                "ORDER BY updated_at DESC LIMIT 1",
                (chat_id, uid),
            )
        else:
            cur.execute(
                "SELECT COALESCE(username, ''), COALESCE(first_name, '') "
                "FROM member_activity WHERE tg_user_id = ? "
                "ORDER BY updated_at DESC LIMIT 1",
                (uid,),
            )
        row = cur.fetchone()
    finally:
        conn.close()

    if row:
        username, first_name = (str(row[0] or ""), str(row[1] or ""))
    else:
        username, first_name = "", ""
    name = f"@{username}" if username else (first_name or f"User {uid}")
    name = html.escape(name)
    return f'<a href="tg://user?id={uid}">{name}</a>'


def fetch_names_bulk(db_path: str, chat_id: int, uids: list[int]) -> dict[int, tuple[str, str]]:
    """Return {uid: (username, first_name)} for a batch of uids (single query)."""
    if not uids:
        return {}
    from bot.db import get_conn

    placeholders = ",".join("?" * len(uids))
    conn = get_conn(db_path)
    cur = conn.cursor()
    try:
        cur.execute(
            f"SELECT tg_user_id, COALESCE(username, ''), COALESCE(first_name, '') "
            f"FROM member_activity WHERE chat_id = ? AND tg_user_id IN ({placeholders}) "
            f"ORDER BY updated_at DESC",
            (chat_id, *uids),
        )
        rows = cur.fetchall()
    finally:
        conn.close()

    # Keep only the most recent row per uid (rows are already ordered DESC).
    out: dict[int, tuple[str, str]] = {}
    for uid, username, first_name in rows:
        uid_i = int(uid)
        if uid_i not in out:
            out[uid_i] = (str(username or ""), str(first_name or ""))
    for u in uids:
        out.setdefault(u, ("", ""))
    return out


# --- Date / time formatting ---------------------------------------------

def human_date(dt_str: str | None) -> str:
    """'сегодня' / 'вчера' / '3 дн. назад' / '15.07'.

    Accepts ISO 8601 strings. Returns `никогда` for None/empty.
    """
    if not dt_str:
        return "никогда"
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return dt_str
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    delta = now - dt
    if delta.days < 0:
        return "будущее"
    if delta.days == 0:
        return f"сегодня в {dt.strftime('%H:%M')}"
    if delta.days == 1:
        return f"вчера в {dt.strftime('%H:%M')}"
    if delta.days < 7:
        return f"{delta.days} дн. назад"
    return dt.strftime("%d.%m")


def is_valid_name(first_name: str, username: str) -> bool:
    """Reject empty, zero-width, all-whitespace names."""
    name = (first_name or "").strip()
    if not name:
        name = (username or "").strip().lstrip("@")
    if not name:
        return False
    cleaned = "".join(ch for ch in name if (ch.isprintable() and not ch.isspace()) or ch in " -")
    return len(cleaned) > 0


def days_silent(last_at: str | None) -> str:
    """'3 дня молчания' / '5 дней молчания' / empty if recent."""
    if not last_at:
        return ""
    try:
        dt = datetime.fromisoformat(last_at.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    days = (now - dt).days
    if days < 1:
        return ""
    if days == 1:
        return "1 день молчания"
    if days < 5:
        return f"{days} дня молчания"
    return f"{days} дней молчания"


# --- Action / reason labels ---------------------------------------------

ACTION_LABEL = {
    "warn": "⚠️ warn",
    "mute30": "🔇 mute 30m",
    "ban": "⛔ ban",
}

REASON_LABEL = {
    "spam": "спам",
    "abuse": "оскорбления",
    "offtopic": "оффтоп",
    "other": "другое",
}


def action_label(action: str) -> str:
    return ACTION_LABEL.get(action, action)


def reason_label(reason_key: str) -> str:
    return REASON_LABEL.get(reason_key, "другое")


# --- Common keyboards ----------------------------------------------------

def back_to_menu_kb(issuer_id: int) -> InlineKeyboardMarkup:
    """Single '⬅️ В меню' button bound to issuer_id."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ В меню", callback_data=f"menu:home:{issuer_id}")]
    ])


def back_to_menu_kb_any() -> InlineKeyboardMarkup:
    """Back button with issuer_id=0 — used for direct command flows."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ В меню", callback_data="menu:home:0")]
    ])
