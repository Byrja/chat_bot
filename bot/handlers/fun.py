from datetime import datetime, timedelta, timezone

from telegram import ChatPermissions, Update
from telegram.ext import ContextTypes

from bot.config import Settings


def _settings(context: ContextTypes.DEFAULT_TYPE) -> Settings:
    return context.application.bot_data["settings"]


def _parse_minutes(raw: str | None) -> int:
    if not raw:
        return 30
    s = raw.strip()
    if not s.isdigit():
        return 30
    v = int(s)
    if v < 1:
        return 1
    if v > 1440:
        return 1440
    return v


async def mute_me(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_chat or not update.effective_user:
        return

    minutes = _parse_minutes(context.args[0] if context.args else None)
    until_dt = datetime.now(timezone.utc) + timedelta(minutes=minutes)

    try:
        await context.bot.restrict_chat_member(
            chat_id=update.effective_chat.id,
            user_id=update.effective_user.id,
            permissions=ChatPermissions(can_send_messages=False),
            until_date=until_dt,
        )
        await update.message.reply_text(f"Ок, самозамут на {minutes} мин 🫡")
    except Exception as e:
        await update.message.reply_text(f"Не удалось выдать self-mute: {e}")


async def hipish(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_chat:
        return

    s = _settings(context)
    ids: set[int] = set(s.admin_user_ids)

    try:
        admins = await context.bot.get_chat_administrators(update.effective_chat.id)
        for a in admins:
            u = a.user
            if u and not u.is_bot:
                ids.add(u.id)
    except Exception:
        pass

    if not ids:
        await update.message.reply_text("Админы не найдены")
        return

    mentions = [f'<a href="tg://user?id={uid}">admin:{uid}</a>' for uid in sorted(ids)]
    await update.message.reply_text("Хипиш! " + " ".join(mentions), parse_mode="HTML")
