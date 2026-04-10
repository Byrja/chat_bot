from telegram import Update
from telegram.ext import ContextTypes

from bot.config import Settings
from bot.repositories.roles import get_role, set_role

_VALID = {"admin", "old", "trusted", "newbie"}


def _settings(context: ContextTypes.DEFAULT_TYPE) -> Settings:
    return context.application.bot_data["settings"]


def _is_env_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user = update.effective_user
    if not user:
        return False
    return user.id in _settings(context).admin_user_ids


async def set_role_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_user:
        return
    if not _is_env_admin(update, context):
        await update.message.reply_text("Недостаточно прав")
        return

    if not update.message.reply_to_message or not update.message.reply_to_message.from_user:
        await update.message.reply_text("Используй /role <admin|old|trusted|newbie> ответом на сообщение пользователя")
        return

    if not context.args:
        await update.message.reply_text("Укажи роль: admin|old|trusted|newbie")
        return

    role = (context.args[0] or "").strip().lower()
    if role not in _VALID:
        await update.message.reply_text("Неизвестная роль. Доступно: admin|old|trusted|newbie")
        return

    target = update.message.reply_to_message.from_user
    s = _settings(context)
    ok = set_role(s.sqlite_path, target.id, role, assigned_by_tg_user_id=update.effective_user.id)
    if not ok:
        await update.message.reply_text("Не удалось сохранить роль")
        return

    await update.message.reply_text(f"Роль для {target.id} обновлена: {role}")


async def whois_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    s = _settings(context)

    if update.message.reply_to_message and update.message.reply_to_message.from_user:
        target = update.message.reply_to_message.from_user
    elif update.effective_user:
        target = update.effective_user
    else:
        return

    role = "admin" if target.id in s.admin_user_ids else get_role(s.sqlite_path, target.id)
    label = f"@{target.username}" if target.username else str(target.id)
    await update.message.reply_text(f"Пользователь {label}\nРоль: {role}")
