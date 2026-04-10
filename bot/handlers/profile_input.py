import re

from telegram import Update
from telegram.ext import ContextTypes

from bot.config import Settings
from bot.repositories.profile import set_birthdate


def _settings(context: ContextTypes.DEFAULT_TYPE) -> Settings:
    return context.application.bot_data["settings"]


async def capture_birthdate_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_user:
        return

    issuer = context.user_data.get("await_birthdate_issuer")
    if not issuer:
        return
    if update.effective_user.id != int(issuer):
        return

    text = (update.message.text or "").strip()
    m = re.match(r"^(\d{1,2})\.(\d{1,2})$", text)
    if not m:
        await update.message.reply_text("Формат неверный. Используй ДД.ММ")
        return

    day = int(m.group(1))
    month = int(m.group(2))
    if not (1 <= month <= 12 and 1 <= day <= 31):
        await update.message.reply_text("Некорректная дата")
        return

    s = _settings(context)
    set_birthdate(s.sqlite_path, update.effective_user.id, day, month)
    context.user_data.pop("await_birthdate_issuer", None)
    await update.message.reply_text(f"Дата рождения сохранена: {day:02d}.{month:02d}")
