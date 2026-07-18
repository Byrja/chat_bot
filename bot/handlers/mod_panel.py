from datetime import datetime, timedelta, timezone

from telegram import ChatPermissions, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from bot.config import Settings
from bot.db import get_conn
from bot.repositories.sanctions import add_sanction
from bot.services.rbac import is_chat_admin_cmd


def _settings(context: ContextTypes.DEFAULT_TYPE) -> Settings:
    return context.application.bot_data.get("settings") or context.application.settings


def _user_label_for_mod(user) -> str:
    """Имя для отображения в интерфейсе модерации."""
    if user.first_name:
        return user.first_name
    if user.username:
        return f"@{user.username}"
    return f"User {user.id}"


def _uid_to_label(db_path: str, chat_id: int, uid: int) -> str:
    """Получить имя пользователя из БД по tg_user_id."""
    conn = get_conn(db_path)
    cur = conn.cursor()
    cur.execute(
        "SELECT COALESCE(username,''), COALESCE(first_name,'') FROM member_activity WHERE chat_id = ? AND tg_user_id = ? ORDER BY updated_at DESC LIMIT 1",
        (chat_id, uid),
    )
    row = cur.fetchone()
    conn.close()
    if row:
        u, f = row
        if f:
            return f
        if u:
            return f"@{u}"
    return f"User {uid}"


async def mod_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_user or not update.effective_chat:
        return

    if not await is_chat_admin_cmd(context, update.effective_chat.id, update.effective_user.id):
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
    await update.message.reply_text(
        f"Мод-панель для {_user_label_for_mod(target)}",
        parse_mode="HTML",
        reply_markup=kb,
    )


def _reason_label(key: str) -> str:
    return {
        "spam": "спам",
        "abuse": "оскорбления",
        "offtopic": "оффтоп",
        "other": "другое",
    }.get(key, "другое")


def _action_label(action: str) -> str:
    return {
        "warn": "⚠️ warn",
        "mute30": "🔇 mute 30m",
        "ban": "⛔ ban",
    }.get(action, action)


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
        [InlineKeyboardButton("❌ Отмена", callback_data=f"modcancel:{target_id}:{issuer_id}")],
    ])
    await query.edit_message_text(f"Выбери причину для действия {_action_label(action)}:", reply_markup=kb)


async def mod_cancel_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not update.effective_user:
        return
    await query.answer()
    parts = (query.data or "").split(":")
    if len(parts) != 3:
        return
    try:
        target_id = int(parts[1])
        issuer_id = int(parts[2])
    except ValueError:
        await query.edit_message_text("Некорректные данные")
        return
    if update.effective_user.id != issuer_id:
        await query.answer("Эта панель не для тебя", show_alert=True)
        return
    await query.edit_message_text("❌ Модерация отменена")


async def mod_quick_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not update.effective_user or not update.effective_chat:
        return
    await query.answer()

    if not await is_chat_admin_cmd(context, update.effective_chat.id, update.effective_user.id):
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

    s = _settings(context)
    reason = f"quick panel: {_reason_label(reason_key)}"

    if action == "warn":
        add_sanction(s.sqlite_path, target_id, "warn", update.effective_user.id, reason=reason)
        label = _uid_to_label(s.sqlite_path, update.effective_chat.id, target_id)
        await query.edit_message_text(f"⚠️ Warn выдан {label}\nПричина: {_reason_label(reason_key)}")
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
        label = _uid_to_label(s.sqlite_path, update.effective_chat.id, target_id)
        await query.edit_message_text(f"🔇 Mute 30m выдан {label}\nПричина: {_reason_label(reason_key)}")
        return

    if action == "ban":
        try:
            await context.bot.ban_chat_member(chat_id=update.effective_chat.id, user_id=target_id, revoke_messages=False)
        except Exception as e:
            await query.edit_message_text(f"Не удалось выдать бан: {e}")
            return
        add_sanction(s.sqlite_path, target_id, "ban", update.effective_user.id, reason=reason)
        label = _uid_to_label(s.sqlite_path, update.effective_chat.id, target_id)
        await query.edit_message_text(f"⛔ Ban выдан {label}\nПричина: {_reason_label(reason_key)}")
        return
