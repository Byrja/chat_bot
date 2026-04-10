from telegram import Update
from telegram.ext import ContextTypes

from bot.config import Settings
from bot.repositories.activity import get_top_week_activity


def _settings(context: ContextTypes.DEFAULT_TYPE) -> Settings:
    return context.application.bot_data["settings"]


async def show_top_week(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message or (update.callback_query.message if update.callback_query else None)
    if not msg or not update.effective_chat:
        return

    s = _settings(context)
    rows = get_top_week_activity(s.sqlite_path, update.effective_chat.id, limit=10)
    if not rows:
        text = "Пока нет данных за последние 7 дней."
    else:
        lines = ["📆 Топ ноулайферов (7 дней)", "───────────────────"]
        for i, (uid, cnt, last_at, username, first_name) in enumerate(rows, 1):
            label = f"@{username}" if username else (first_name or str(uid))
            lines.append(f"{i}. {label} — {cnt} | {last_at or '—'}")
        text = "\n".join(lines)

    if update.callback_query:
        await update.callback_query.edit_message_text(text)
    else:
        await msg.reply_text(text)
