from telegram import ChatPermissions, Update
from telegram.ext import ContextTypes

from bot.config import Settings
from bot.repositories.sanctions import add_sanction
from bot.services.rbac import has_permission
from bot.services.timeparse import parse_mute_duration


def _settings(context: ContextTypes.DEFAULT_TYPE) -> Settings:
    return context.application.bot_data["settings"]


def _can(update: Update, context: ContextTypes.DEFAULT_TYPE, command: str) -> bool:
    user = update.effective_user
    if not user:
        return False
    s = _settings(context)
    return has_permission(s, s.sqlite_path, user.id, command)


async def mute_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_chat:
        return
    if not _can(update, context, "mute"):
        await update.message.reply_text("Недостаточно прав")
        return

    if not update.message.reply_to_message or not update.message.reply_to_message.from_user:
        await update.message.reply_text("Используй /mute ответом на сообщение пользователя")
        return

    if not context.args:
        await update.message.reply_text("Формат: /mute 30 причина (минуты, можно также 30m/2h/1d)")
        return

    target = update.message.reply_to_message.from_user
    if target.is_bot:
        await update.message.reply_text("Нельзя выдать мут боту")
        return

    until_dt = parse_mute_duration(context.args[0])
    if until_dt is None:
        await update.message.reply_text("Некорректная длительность. Используй: 30 (мин), 30m, 2h, 1d")
        return
    reason = " ".join(context.args[1:]).strip() or None

    s = _settings(context)
    try:
        await context.bot.restrict_chat_member(
            chat_id=update.effective_chat.id,
            user_id=target.id,
            permissions=ChatPermissions(can_send_messages=False),
            until_date=until_dt,
        )
    except Exception as e:
        await update.message.reply_text(f"Не удалось выдать мут: {e}")
        return

    add_sanction(
        s.sqlite_path,
        target_tg_user_id=target.id,
        action="mute",
        issued_by_tg_user_id=update.effective_user.id,
        reason=reason,
        until_at=until_dt.isoformat(),
    )

    txt = f"🔇 Мут выдан пользователю {target.id} до {until_dt.strftime('%Y-%m-%d %H:%M UTC')}"
    if reason:
        txt += f"\nПричина: {reason}"
    await update.message.reply_text(txt)


async def ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_chat:
        return
    if not _can(update, context, "ban"):
        await update.message.reply_text("Недостаточно прав")
        return

    if not update.message.reply_to_message or not update.message.reply_to_message.from_user:
        await update.message.reply_text("Используй /ban ответом на сообщение пользователя")
        return

    target = update.message.reply_to_message.from_user
    if target.is_bot:
        await update.message.reply_text("Нельзя забанить бота")
        return

    reason = " ".join(context.args).strip() if context.args else None

    s = _settings(context)
    try:
        await context.bot.ban_chat_member(
            chat_id=update.effective_chat.id,
            user_id=target.id,
            revoke_messages=False,
        )
    except Exception as e:
        await update.message.reply_text(f"Не удалось выдать бан: {e}")
        return

    add_sanction(
        s.sqlite_path,
        target_tg_user_id=target.id,
        action="ban",
        issued_by_tg_user_id=update.effective_user.id,
        reason=reason,
        until_at=None,
    )

    text = f"⛔ Бан выдан пользователю {target.id}"
    if reason:
        text += f"\nПричина: {reason}"
    await update.message.reply_text(text)


async def warn_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    if not _can(update, context, "warn"):
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
