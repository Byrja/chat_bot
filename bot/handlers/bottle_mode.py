from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from bot.config import Settings


def _settings(context: ContextTypes.DEFAULT_TYPE) -> Settings:
    return context.application.bot_data.get("settings") or context.application.settings


async def bottle_mode_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not update.effective_user or not update.effective_chat:
        return
    await query.answer()

    parts = (query.data or "").split(":")
    if len(parts) != 4:
        return
    mode, chat_id_s, actor_s = parts[1], parts[2], parts[3]
    if mode not in {"light", "hard", "savage"}:
        return

    actor_uid = int(actor_s)
    if update.effective_user.id != actor_uid:
        await query.answer("Режим выбирает тот, кто запустил бутылочку", show_alert=True)
        return

    key = f"bottle_last_ts:{update.effective_chat.id}"
    import time
    now = time.time()
    context.application.bot_data[key] = now

    lobby_key = f"bottle_lobby:{update.effective_chat.id}"
    context.application.bot_data[lobby_key] = {"actor_uid": actor_uid, "started_at": now, "mode": mode}

    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🎮 Играть", callback_data=f"bottlejoin:{update.effective_chat.id}:{actor_uid}")]])
    mode_label = {"light": "Лайт", "hard": "Жёстко", "savage": "Отбитый"}[mode]
    await query.edit_message_text(
        f"Режим: {mode_label}. Кто хочет быть вторым игроком — жми «Играть».",
        reply_markup=kb,
    )
