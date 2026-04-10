from telegram import Update
from telegram.ext import ContextTypes

from bot.config import Settings
from bot.repositories.sanctions import add_sanction


def _settings(context: ContextTypes.DEFAULT_TYPE) -> Settings:
    return context.application.bot_data["settings"]


def _is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user = update.effective_user
    if not user:
        return False
    return user.id in _settings(context).admin_user_ids


async def warn_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    if not _is_admin(update, context):
        await update.message.reply_text("Недостаточно прав")
        return

    if not update.message.reply_to_message or not update.message.reply_to_message.from_user:
        await update.message.reply_text("Используй /warn ответом на сообщение пользователя")
        return

    target = update.message.reply_to_message.from_user
    if target.is_bot:
        await update.message.reply_text("Нельзя выдать предупреждение боту")
        return

    reason = " ".join(context.args).strip() if context.args else None
    s = _settings(context)
    add_sanction(
        s.sqlite_path,
        target_tg_user_id=target.id,
        action="warn",
        issued_by_tg_user_id=update.effective_user.id,
        reason=reason,
        until_at=None,
    )

    text = f"⚠️ Предупреждение выдано пользователю {target.id}"
    if reason:
        text += f"\nПричина: {reason}"
    await update.message.reply_text(text)

    try:
        dm = "Тебе выдано предупреждение администратором."
        if reason:
            dm += f"\nПричина: {reason}"
        await context.bot.send_message(chat_id=target.id, text=dm)
    except Exception:
        pass
