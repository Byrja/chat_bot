from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from bot.config import Settings


def _settings(context: ContextTypes.DEFAULT_TYPE) -> Settings:
    return context.application.bot_data.get("settings") or context.application.settings


async def bottle_mode_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not update.effective_user or not update.effective_chat:
        return
    parts = (query.data or "").split(":")
    if len(parts) != 4:
        return
    mode, chat_id_s, actor_s = parts[1], parts[2], parts[3]
    if mode not in {"light", "hard", "savage"}:
        return

    actor_uid = int(actor_s)

    key = f"bottle_last_ts:{update.effective_chat.id}"
    import time
    now = time.time()

    lobby_key = f"bottle_lobby:{update.effective_chat.id}"
    lobby = context.application.bot_data.get(lobby_key)
    if lobby and lobby.get("mode"):
        await query.answer("Режим уже выбран", show_alert=True)
        return

    context.application.bot_data[key] = now
    context.application.bot_data[lobby_key] = {"actor_uid": actor_uid, "started_at": now, "mode": mode}

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎮 Играть", callback_data=f"bottlejoin:{update.effective_chat.id}:{actor_uid}")],
        [InlineKeyboardButton("❌ Отмена", callback_data=f"bottlecancel:{update.effective_chat.id}:{actor_uid}")],
    ])
    mode_label = {"light": "Лайт", "hard": "Жёстко", "savage": "Отбитый"}[mode]
    await query.edit_message_text(
        f"Режим: {mode_label}. Кто хочет быть вторым игроком — жми «Играть».",
        reply_markup=kb,
    )


async def bottle_cancel_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not update.effective_user or not update.effective_chat:
        return
    parts = (query.data or "").split(":")
    if len(parts) != 3:
        await query.answer()
        return
    try:
        actor_uid = int(parts[2])
    except ValueError:
        await query.answer("Некорректные данные", show_alert=True)
        return
    if update.effective_user.id != actor_uid:
        await query.answer("Отменить может только инициатор", show_alert=True)
        return
    lobby_key = f"bottle_lobby:{update.effective_chat.id}"
    context.application.bot_data.pop(lobby_key, None)
    await query.edit_message_text("🍾 Бутылочка отменена.")
