from telegram import Update
from telegram.ext import ContextTypes

from bot.config import Settings
from bot.repositories.roles import get_role, set_role

_VALID = {"admin", "old", "trusted", "newbie", "lava"}
_ROLE_RU = {
    "admin": "Админ",
    "old": "Олд",
    "trusted": "Проверенный",
    "newbie": "Новичок",
    "lava": "Токсичная лава",
}
_NUM_MAP = {
    "1": "admin",
    "2": "old",
    "3": "trusted",
    "4": "newbie",
    "5": "lava",
}


def _settings(context: ContextTypes.DEFAULT_TYPE) -> Settings:
    return context.application.bot_data.get("settings") or context.application.settings


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
        await update.message.reply_text("Используй /role <admin|old|trusted|newbie|lava> ответом на сообщение пользователя")
        return

    if not context.args:
        await update.message.reply_text("Укажи роль: 1|2|3|4|5 (или admin|old|trusted|newbie|lava)")
        return

    raw = (context.args[0] or "").strip().lower()
    role = _NUM_MAP.get(raw, raw)
    if role not in _VALID:
        await update.message.reply_text("Неизвестная роль. Доступно: 1=admin, 2=old, 3=trusted, 4=newbie, 5=lava")
        return

    target = update.message.reply_to_message.from_user
    s = _settings(context)
    ok = set_role(s.sqlite_path, target.id, role, assigned_by_tg_user_id=update.effective_user.id)
    if not ok:
        await update.message.reply_text("Не удалось сохранить роль")
        return

    await update.message.reply_text(f"Роль для {target.id} обновлена: {_ROLE_RU.get(role, role)}")


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
    label = target.first_name or (f"@{target.username}" if target.username else str(target.id))
    await update.message.reply_text(f"Пользователь: {label}\nРоль: {_ROLE_RU.get(role, role)}")
