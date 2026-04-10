from telegram import Update
from telegram.ext import ContextTypes

from bot.config import Settings
from bot.repositories.activity import bump_message_activity, get_top_activity


def _settings(context: ContextTypes.DEFAULT_TYPE) -> Settings:
    return context.application.bot_data["settings"]


def _is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user = update.effective_user
    if not user:
        return False
    return user.id in _settings(context).admin_user_ids


async def track_message_activity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_chat or not update.effective_user:
        return
    # Track only main chat activity (as requested for participant leaderboard)
    s = _settings(context)
    if update.effective_chat.id != s.main_chat_id:
        return

    msg = update.effective_message
    if not msg:
        return
    # Ignore service/system updates and commands
    if msg.text and msg.text.startswith("/"):
        return

    bump_message_activity(
        s.sqlite_path,
        chat_id=update.effective_chat.id,
        tg_user_id=update.effective_user.id,
        username=update.effective_user.username,
        first_name=update.effective_user.first_name,
    )


async def show_activity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_chat:
        return
    if not _is_admin(update, context):
        await update.message.reply_text("Недостаточно прав")
        return

    s = _settings(context)
    rows = get_top_activity(s.sqlite_path, chat_id=update.effective_chat.id, limit=30)
    if not rows:
        await update.message.reply_text("Пока нет данных по активности (счётчик начался после деплоя).")
        return

    lines = ["📈 Топ активности (по сообщениям)", "───────────────────"]
    for i, (uid, username, first_name, cnt, last_at) in enumerate(rows, 1):
        label = f"@{username}" if username else (first_name or str(uid))
        lines.append(f"{i}. {label} — {cnt} сообщений | последнее: {last_at or '—'}")

    await update.message.reply_text("\n".join(lines))
