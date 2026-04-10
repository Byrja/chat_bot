from datetime import datetime, timedelta, timezone

from telegram import ChatPermissions, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from bot.config import Settings
from bot.repositories.sanctions import add_sanction
from bot.services.rbac import has_permission


def _settings(context: ContextTypes.DEFAULT_TYPE) -> Settings:
    return context.application.bot_data.get("settings") or context.application.settings


async def mod_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_user:
        return

    s = _settings(context)
    if not has_permission(s, s.sqlite_path, update.effective_user.id, "warn"):
        await update.message.reply_text("Недостаточно прав")
        return

    if not update.message.reply_to_message or not update.message.reply_to_message.from_user:
        await update.message.reply_text("Используй /mod ответом на сообщение пользователя")
        return

    target = update.message.reply_to_message.from_user
    if target.is_bot:
        await update.message.reply_text("Нельзя модерировать бота")
        return

    issuer_id = update.effective_user.id
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("⚠️ warn", callback_data=f"modquickask:warn:{target.id}:{issuer_id}")],
        [InlineKeyboardButton("🔇 mute 30m", callback_data=f"modquickask:mute30:{target.id}:{issuer_id}")],
        [InlineKeyboardButton("⛔ ban", callback_data=f"modquickask:ban:{target.id}:{issuer_id}")],
    ])
    await update.message.reply_text(f"Мод-панель для {target.id}", reply_markup=kb)


def _reason_label(key: str) -> str:
    return {
        "spam": "спам",
        "abuse": "оскорбления",
        "offtopic": "оффтоп",
        "other": "другое",
    }.get(key, "другое")


async def mod_quick_ask_reason(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not update.effective_user:
        return
    await query.answer()

    parts = (query.data or "").split(":")
    if len(parts) != 4:
        return
    action = parts[1]
    target_id = parts[2]
    issuer_id = parts[3]

    if str(update.effective_user.id) != issuer_id:
        await query.answer("Эта панель не для тебя", show_alert=True)
        return

    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Спам", callback_data=f"modquick:{action}:{target_id}:{issuer_id}:spam"),
            InlineKeyboardButton("Оскорбления", callback_data=f"modquick:{action}:{target_id}:{issuer_id}:abuse"),
        ],
        [
            InlineKeyboardButton("Оффтоп", callback_data=f"modquick:{action}:{target_id}:{issuer_id}:offtopic"),
            InlineKeyboardButton("Другое", callback_data=f"modquick:{action}:{target_id}:{issuer_id}:other"),
        ],
    ])
    await query.edit_message_text(f"Выбери причину для действия {action}:", reply_markup=kb)


async def mod_quick_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not update.effective_user or not update.effective_chat:
        return
    await query.answer()

    s = _settings(context)
    if not has_permission(s, s.sqlite_path, update.effective_user.id, "warn"):
        await query.answer("Недостаточно прав", show_alert=True)
        return

    parts = (query.data or "").split(":")
    if len(parts) != 5:
        return
    action = parts[1]
    reason_key = parts[4]
    try:
        target_id = int(parts[2])
        issuer_id = int(parts[3])
    except Exception:
        await query.edit_message_text("Некорректный target")
        return

    if update.effective_user.id != issuer_id:
        await query.answer("Эта панель не для тебя", show_alert=True)
        return

    reason = f"quick panel: {_reason_label(reason_key)}"

    if action == "warn":
        add_sanction(s.sqlite_path, target_id, "warn", update.effective_user.id, reason=reason)
        await query.edit_message_text(f"⚠️ Warn выдан {target_id}\nПричина: {_reason_label(reason_key)}")
        return

    if action == "mute30":
        until_dt = datetime.now(timezone.utc) + timedelta(minutes=30)
        try:
            await context.bot.restrict_chat_member(
                chat_id=update.effective_chat.id,
                user_id=target_id,
                permissions=ChatPermissions(can_send_messages=False),
                until_date=until_dt,
            )
        except Exception as e:
            await query.edit_message_text(f"Не удалось выдать мут: {e}")
            return
        add_sanction(s.sqlite_path, target_id, "mute", update.effective_user.id, reason=reason, until_at=until_dt.isoformat())
        await query.edit_message_text(f"🔇 Mute 30m выдан {target_id}\nПричина: {_reason_label(reason_key)}")
        return

    if action == "ban":
        try:
            await context.bot.ban_chat_member(chat_id=update.effective_chat.id, user_id=target_id, revoke_messages=False)
        except Exception as e:
            await query.edit_message_text(f"Не удалось выдать бан: {e}")
            return
        add_sanction(s.sqlite_path, target_id, "ban", update.effective_user.id, reason=reason)
        await query.edit_message_text(f"⛔ Ban выдан {target_id}\nПричина: {_reason_label(reason_key)}")
        return
