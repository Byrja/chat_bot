from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from bot.config import Settings
from bot.db import get_conn
from bot.repositories.karma import apply_karma
from bot.repositories.social import (
    create_bottle_game,
    get_friend_foe_stats,
    get_friend_foe_top,
    pick_bottle_pair,
    resolve_bottle_game,
)
from bot.services.rbac import has_permission


def _settings(context: ContextTypes.DEFAULT_TYPE) -> Settings:
    return context.application.bot_data["settings"]


def _label(db_path: str, chat_id: int, uid: int) -> str:
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
        if u:
            return f"@{u}"
        if f:
            return f
    return str(uid)


async def friend_foe_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_chat or not update.effective_user:
        return
    s = _settings(context)
    st = get_friend_foe_stats(s.sqlite_path, update.effective_chat.id, update.effective_user.id)
    await update.message.reply_text(
        "⚖️ Friend/Foe статистика\n"
        "───────────────────\n"
        f"Карма: {st['karma']}\n"
        f"Плюсов получено: {st['plus_count']}\n"
        f"Минусов получено: {st['minus_count']}"
    )


async def friend_foe_top(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_chat:
        return
    s = _settings(context)
    pos, neg = get_friend_foe_top(s.sqlite_path, update.effective_chat.id, limit=3)

    lines = ["👥 Friend/Foe топ", "───────────────────", "🤝 Друзья:"]
    if pos:
        for i, (uid, score) in enumerate(pos, 1):
            lines.append(f"{i}. {_label(s.sqlite_path, update.effective_chat.id, int(uid))} — {int(score)}")
    else:
        lines.append("—")

    lines.append("")
    lines.append("😈 Козлы:")
    if neg:
        for i, (uid, score) in enumerate(neg, 1):
            lines.append(f"{i}. {_label(s.sqlite_path, update.effective_chat.id, int(uid))} — {int(score)}")
    else:
        lines.append("—")

    await update.message.reply_text("\n".join(lines))


async def bottle_game(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_chat or not update.effective_user:
        return
    s = _settings(context)
    pair = pick_bottle_pair(s.sqlite_path, update.effective_chat.id)
    if not pair:
        await update.message.reply_text("Нужно хотя бы 2 активных участника для бутылочки")
        return

    actor_uid, partner_uid = pair
    gid = create_bottle_game(s.sqlite_path, update.effective_chat.id, actor_uid, partner_uid, update.effective_user.id)

    actor = _label(s.sqlite_path, update.effective_chat.id, actor_uid)
    partner = _label(s.sqlite_path, update.effective_chat.id, partner_uid)

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Выполнено (+10)", callback_data=f"bottle:done:{gid}:{actor_uid}")],
        [InlineKeyboardButton("❌ Не выполнено (-10)", callback_data=f"bottle:fail:{gid}:{actor_uid}")],
    ])
    await update.message.reply_text(
        f"🍾 Бутылочка крутится...\n"
        f"{actor} выполняет задание от {partner}.\n"
        f"Отметьте результат:",
        reply_markup=kb,
    )


async def bottle_result_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not update.effective_user or not update.effective_chat:
        return
    await query.answer()

    parts = (query.data or "").split(":")
    if len(parts) != 4:
        return
    action, gid_s, actor_s = parts[1], parts[2], parts[3]
    try:
        gid = int(gid_s)
        actor_uid = int(actor_s)
    except Exception:
        return

    s = _settings(context)
    is_admin = has_permission(s, s.sqlite_path, update.effective_user.id, "warn")
    if update.effective_user.id not in {actor_uid} and not is_admin:
        await query.answer("Отметить может только исполнитель или админ", show_alert=True)
        return

    resolved = resolve_bottle_game(s.sqlite_path, gid, "done" if action == "done" else "fail")
    if not resolved:
        await query.edit_message_text("Эта игра уже закрыта или недоступна")
        return

    actor_uid_db, _partner_uid = resolved
    delta = 10 if action == "done" else -10
    apply_karma(s.sqlite_path, update.effective_chat.id, 0, actor_uid_db, delta, reason="bottle_game")

    actor = _label(s.sqlite_path, update.effective_chat.id, actor_uid_db)
    if delta > 0:
        await query.edit_message_text(f"✅ Задание выполнено. {actor} получает +10 кармы")
    else:
        await query.edit_message_text(f"❌ Задание провалено. {actor} получает -10 кармы")
