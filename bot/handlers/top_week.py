from telegram import Update
from telegram.ext import ContextTypes

from bot.config import Settings
from bot.repositories.activity import get_top_week_activity, get_today_activity, count_today_messages


def _settings(context: ContextTypes.DEFAULT_TYPE) -> Settings:
    return context.application.bot_data.get("settings") or context.application.settings


async def show_top_week(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message or (update.callback_query.message if update.callback_query else None)
    if not msg or not update.effective_chat:
        return

    s = _settings(context)
    rows = get_top_week_activity(s.sqlite_path, update.effective_chat.id, limit=10)
    if not rows:
        text = "Пока нет данных за последние 7 дней."
    else:
        lines = ["📆 Топ самых активных (7 дней)", "───────────────────"]
        for i, (uid, cnt, last_at, username, first_name) in enumerate(rows, 1):
            label = first_name or username or str(uid)
            lines.append(f"{i}. {label} — {cnt} | {last_at or '—'}")
        text = "\n".join(lines)

    if update.callback_query:
        await update.callback_query.edit_message_text(text)
    else:
        await msg.reply_text(text)


async def show_today_top(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message or (update.callback_query.message if update.callback_query else None)
    if not msg or not update.effective_chat:
        return

    s = _settings(context)
    rows = get_today_activity(s.sqlite_path, update.effective_chat.id, limit=10)
    total = count_today_messages(s.sqlite_path, update.effective_chat.id)
    if not rows:
        text = "Пока нет данных за последние 24 часа."
    else:
        lines = ["📊 Топ самых активных (за сутки)", "───────────────────"]
        for i, (uid, cnt, last_at, username, first_name) in enumerate(rows, 1):
            label = first_name or username or str(uid)
            lines.append(f"{i}. {label} — {cnt} сообщений")
        lines.append(f"\n💬 Всего сообщений за сутки: {total}")
        text = "\n".join(lines)

    if update.callback_query:
        await update.callback_query.edit_message_text(text)
    else:
        await msg.reply_text(text)
