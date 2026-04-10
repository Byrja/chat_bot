from telegram import Update
from telegram.ext import ContextTypes

from bot.config import Settings
from bot.repositories.drama import get_days_without_drama, reset_drama
from bot.services.rbac import has_permission


def _settings(context: ContextTypes.DEFAULT_TYPE) -> Settings:
    return context.application.bot_data.get("settings") or context.application.settings


async def days_without_drama(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message or (update.callback_query.message if update.callback_query else None)
    if not msg or not update.effective_chat:
        return

    s = _settings(context)
    days = get_days_without_drama(s.sqlite_path, update.effective_chat.id)
    text = f"🕊 Дней без драмы: {days}"
    if update.callback_query:
        await update.callback_query.edit_message_text(text)
    else:
        await msg.reply_text(text)


async def drama_reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_user or not update.effective_chat:
        return

    s = _settings(context)
    if not has_permission(s, s.sqlite_path, update.effective_user.id, "warn"):
        await update.message.reply_text("Недостаточно прав")
        return

    reset_drama(s.sqlite_path, update.effective_chat.id, update.effective_user.id)
    await update.message.reply_text("💥 Счётчик драмы сброшен")
