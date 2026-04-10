from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from bot.config import Settings
from bot.db import get_conn
from bot.repositories.karma import apply_karma
from bot.repositories.social import (
    create_bottle_game,
    get_friend_foe_stats,
    get_friend_foe_top,
    resolve_bottle_game,
)
from bot.services.llm_client import complete_text, llm_enabled
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
    msg = update.message or (update.callback_query.message if update.callback_query else None)
    if not msg or not update.effective_chat or not update.effective_user:
        return
    s = _settings(context)
    st = get_friend_foe_stats(s.sqlite_path, update.effective_chat.id, update.effective_user.id)
    text = (
        "⚖️ Friend/Foe статистика\n"
        "───────────────────\n"
        f"Карма: {st['karma']}\n"
        f"Плюсов получено: {st['plus_count']}\n"
        f"Минусов получено: {st['minus_count']}"
    )
    if update.callback_query:
        await update.callback_query.edit_message_text(text)
    else:
        await msg.reply_text(text)


async def friend_foe_top(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message or (update.callback_query.message if update.callback_query else None)
    if not msg or not update.effective_chat:
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

    text = "\n".join(lines)
    if update.callback_query:
        await update.callback_query.edit_message_text(text)
    else:
        await msg.reply_text(text)


def _fallback_bottle_task(actor: str, partner: str) -> str:
    tasks = [
        f"{actor} говорит {partner} три честных комплимента.",
        f"{actor} придумывает мини-челлендж на сутки для себя и {partner}.",
        f"{actor} кидает трек для {partner} и пишет почему именно он.",
        f"{actor} отправляет мем про вас двоих с подписью.",
    ]
    import random

    return random.choice(tasks)


def _gen_bottle_task(actor: str, partner: str) -> str:
    if llm_enabled():
        prompt = (
            f"Придумай одно короткое веселое задание для игры в бутылочку. "
            f"Участники: {actor} и {partner}. Формат 1-2 предложения, без токсичности и 18+"
        )
        txt = complete_text(prompt, max_tokens=80, temperature=0.9)
        if txt:
            return txt
    return _fallback_bottle_task(actor, partner)


async def bottle_game(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message or (update.callback_query.message if update.callback_query else None)
    if not msg or not update.effective_chat or not update.effective_user:
        return
    s = _settings(context)

    key = f"bottle_last_ts:{update.effective_chat.id}"
    import time
    now = time.time()
    last = float(context.application.bot_data.get(key, 0.0) or 0.0)
    if now - last < 300:
        left = int((300 - (now - last)) // 60) + 1
        text = f"🍾 Бутылочку можно запускать раз в 5 минут. Осталось ~{left} мин."
        if update.callback_query:
            await update.callback_query.edit_message_text(text)
        else:
            await msg.reply_text(text)
        return

    actor_uid = update.effective_user.id
    actor = _label(s.sqlite_path, update.effective_chat.id, actor_uid)

    lobby_key = f"bottle_lobby:{update.effective_chat.id}"
    context.application.bot_data[lobby_key] = {"actor_uid": actor_uid, "started_at": now}
    context.application.bot_data[key] = now

    kb = InlineKeyboardMarkup(
        [[InlineKeyboardButton("🎮 Играть", callback_data=f"bottlejoin:{update.effective_chat.id}:{actor_uid}")]]
    )
    text = f"🍾 Бутылочка запущена {actor}.\nКто хочет быть вторым игроком — жми «Играть»."
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=kb)
    else:
        await msg.reply_text(text, reply_markup=kb)


async def bottle_join_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not update.effective_user or not update.effective_chat:
        return
    await query.answer()

    parts = (query.data or "").split(":")
    if len(parts) != 3:
        return
    actor_uid = int(parts[2])
    joiner_uid = update.effective_user.id
    if joiner_uid == actor_uid:
        await query.answer("Нужен второй участник", show_alert=True)
        return

    lobby_key = f"bottle_lobby:{update.effective_chat.id}"
    lobby = context.application.bot_data.get(lobby_key)
    if not lobby or int(lobby.get("actor_uid", 0)) != actor_uid:
        await query.answer("Игра уже закрыта", show_alert=True)
        return

    # close lobby immediately (first click wins)
    context.application.bot_data.pop(lobby_key, None)

    s = _settings(context)
    gid = create_bottle_game(s.sqlite_path, update.effective_chat.id, actor_uid, joiner_uid, actor_uid)
    actor = _label(s.sqlite_path, update.effective_chat.id, actor_uid)
    partner = _label(s.sqlite_path, update.effective_chat.id, joiner_uid)
    task = _gen_bottle_task(actor, partner)

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Выполнено (+10)", callback_data=f"bottle:done:{gid}:{actor_uid}")],
        [InlineKeyboardButton("❌ Не выполнено (-10)", callback_data=f"bottle:fail:{gid}:{actor_uid}")],
    ])
    await query.edit_message_text(
        f"🍾 Пара найдена: {actor} и {partner}\n\nЗадание:\n{task}\n\nОтметьте результат:",
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
