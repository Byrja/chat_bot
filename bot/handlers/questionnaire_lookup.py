import re

from telegram import Update
from telegram.ext import ContextTypes

from bot.config import Settings
from bot.db import get_conn


def _settings(context: ContextTypes.DEFAULT_TYPE) -> Settings:
    return context.application.bot_data.get("settings") or context.application.settings


def _extract_username(text: str) -> str | None:
    m = re.match(r"(?is)^\s*анкета\s+@?([a-zA-Z0-9_]{3,})\s*$", text or "")
    if not m:
        return None
    return m.group(1).lower()


def _fetch_latest_application_by_username(db_path: str, username: str):
    conn = get_conn(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT a.id, a.status, u.tg_user_id, COALESCE(u.username, ''), COALESCE(u.first_name, '')
        FROM applications a
        JOIN users u ON u.tg_user_id = a.tg_user_id
        WHERE lower(COALESCE(u.username, '')) = ?
          AND a.status != 'draft'
        ORDER BY a.id DESC
        LIMIT 1
        """,
        (username.lower(),),
    )
    row = cur.fetchone()
    if not row:
        conn.close()
        return None

    app_id, status, tg_user_id, uname, first_name = row
    cur.execute(
        "SELECT question_code, answer_text FROM application_answers WHERE application_id = ? ORDER BY position ASC",
        (app_id,),
    )
    answers = {r[0]: r[1] for r in cur.fetchall()}
    conn.close()
    return {
        "app_id": int(app_id),
        "status": str(status),
        "tg_user_id": int(tg_user_id),
        "username": str(uname),
        "first_name": str(first_name),
        "answers": answers,
    }


async def questionnaire_lookup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return

    username = _extract_username(update.message.text)
    if not username:
        return

    s = _settings(context)
    data = _fetch_latest_application_by_username(s.sqlite_path, username)
    if not data:
        await update.message.reply_text(f"Анкета для @{username} не найдена")
        return

    a = data["answers"]
    text = (
        "🧾 Анкета участника\n"
        "───────────────────\n"
        f"User: @{data['username']} ({data['tg_user_id']})\n"
        f"Статус: {data['status']}\n"
        f"Имя: {a.get('name', '—')}\n"
        f"Район: {a.get('district', '—')}\n"
        f"Возраст: {a.get('age', '—')}\n"
        f"Хобби: {a.get('hobby', '—')}\n"
        f"Алкоголь: {a.get('alcohol', '—')}\n"
        f"Свободное время: {a.get('availability', '—')}"
    )

    photo_id = a.get("photo_file_id")
    if photo_id:
        await update.message.reply_photo(photo=photo_id, caption=text)
    else:
        await update.message.reply_text(text)
