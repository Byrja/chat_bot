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
from bot.services.rbac import has_permission


def _settings(context: ContextTypes.DEFAULT_TYPE) -> Settings:
    return context.application.bot_data.get("settings") or context.application.settings


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
        issuer = None
        if update.callback_query.data:
            parts = update.callback_query.data.split(":")
            if len(parts) == 3 and parts[0] == "menu":
                issuer = parts[2]
        back = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data=f"menu:social:{issuer}")]]) if issuer else None
        await update.callback_query.edit_message_text(text, reply_markup=back)
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
        issuer = None
        if update.callback_query.data:
            parts = update.callback_query.data.split(":")
            if len(parts) == 3 and parts[0] == "menu":
                issuer = parts[2]
        back = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data=f"menu:social:{issuer}")]]) if issuer else None
        await update.callback_query.edit_message_text(text, reply_markup=back)
    else:
        await msg.reply_text(text)


def _fallback_bottle_task(actor: str, partner: str, third: str | None = None, mode: str = "hard") -> str:
    import random

    third = third or "третьего"
    light = [
        f"🎙 {actor}: голосовое 10–15 сек с 2 комплиментами для {partner}.",
        f"📸 {actor}: фото самого странного предмета дома + подпись в 1 фразе.",
        f"✍️ {actor}: напиши {partner} 3 факта, за что его ценит чат.",
        f"🎵 {actor}: отправь трек для {partner} и объясни выбор одним предложением.",
        f"🙂 {actor}: придумай {partner} добрую кличку дня (до 3 слов).",
        f"🧩 {actor}: задай {partner} лёгкую загадку в 1 сообщении.",
        f"📹 {actor}: кружок 10 сек «я рад, что {partner} в чате».",
    ]
    hard = [
        f"🎥 {actor}: запиши кружок 10–15 сек «как будто стоишь на голове» и передай эстафету {partner}.",
        f"🎙 {actor}: отправь голосовое со скороговоркой без запинки. {partner} оценивает: прошёл/не прошёл.",
        f"📸 {actor}: сфоткай самое грязное место в квартире и подпиши «мой угол позора».",
        f"😂 {actor}: прожарь {partner} в 2 фразах так, чтобы было обидно и смешно одновременно.",
        f"🎯 {actor}: придумай {partner} микро-челлендж на 1 сообщение и добейся выполнения прямо в чате.",
        f"📹 {actor}: кружок «моё лицо, когда {partner} пишет 'ща приду' и не приходит».",
        f"🤝 {actor}: выбери рандомно {third} и скажи ему комплимент так, чтобы чат не поверил.",
        f"🎙 {actor}: в голосовом 15 сек объясни, почему {partner} — красный флаг, но твой любимый.",
        f"📸 {actor}: покажи свой «угол силы» дома и подпиши, почему там рождаются тупые идеи.",
        f"✍️ {actor}: напиши 2 строки рэпа про {partner} и его чат-вайб.",
        f"🎭 {actor}: отыграй в кружке «я пытаюсь не отвечать {partner}, но не могу».",
        f"🧪 {actor}: придумай мини-тест для {partner} на 1 вопрос и вынеси вердикт сразу.",
    ]
    savage = [
        f"🧨 {actor}: в голосовом 20 сек выскажи {partner} весь накопившийся под*ёб (без семьи/реальных травм).",
        f"🎙 {actor}: голосовым скажи 3 причины, почему {partner} токсик, но любим чатом.",
        f"💀 {actor}: прожарь {partner} в 3 панчлайнах так, чтобы чат заорал.",
        f"🎭 {actor}: кружок «как выглядит {partner}, когда врёт «я уже выехал»».",
        f"📸 {actor}: фото «место, где умерла моя дисциплина» + подпись «посвящается {partner}"",
        f"⚡ {actor}: 7 слов о {partner}: 3 хороших, 3 плохих, 1 беспощадная правда.",
        f"🃏 {actor}: кидай мем + подпись «когда {partner} врывается в чат после тишины».",
        f"🧠 {actor}: придумай для {partner} кличку дня и обоснуй в одной жёсткой фразе.",
        f"🤝 {actor}: выбери {third} и устрой мини-баттл «кто лучше прожарит {partner}» (по 1 фразе).",
        f"🎙 {actor}: голосовым озвучь «топ-3 косяка {partner} за неделю» и закончи фразой «но ты всё равно наш».",
        f"📹 {actor}: кружок «прокурор чата» — за 15 сек вынеси приговор {partner} за токсичность.",
        f"✍️ {actor}: напиши {partner} ультиматум из 2 пунктов и «штраф» за невыполнение (в шуточном формате).",
        f"📸 {actor}: покажи предмет, который лучше всего символизирует {partner}, и добей подписью в 1 жёсткой строке.",
        f"🎙 {actor}: зачитай скороговорку на максимальной скорости. Если запнулся — сам себя прожарь в 1 фразе.",
        f"🧷 {actor}: напиши 2 правды и 1 ложь про {partner}; чат решает, что ложь.",
    ]

    pool = hard
    if mode == "light":
        pool = light
    elif mode == "savage":
        pool = savage

    return random.choice(pool)


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

    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🙂 Лайт", callback_data=f"bottlemode:light:{update.effective_chat.id}:{actor_uid}"),
            InlineKeyboardButton("😈 Жёстко", callback_data=f"bottlemode:hard:{update.effective_chat.id}:{actor_uid}"),
            InlineKeyboardButton("💀 Отбитый", callback_data=f"bottlemode:savage:{update.effective_chat.id}:{actor_uid}"),
        ]
    ])
    text = f"🍾 {actor} запускает бутылочку. Выбери режим задания:"
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

    # Optional third participant from current chat activity
    conn = get_conn(s.sqlite_path)
    cur = conn.cursor()
    cur.execute(
        "SELECT tg_user_id FROM member_activity WHERE chat_id = ? ORDER BY RANDOM() LIMIT 20",
        (update.effective_chat.id,),
    )
    pool = [int(r[0]) for r in cur.fetchall()]
    conn.close()
    third_uid = None
    for u in pool:
        if u not in {actor_uid, joiner_uid}:
            third_uid = u
            break
    third = _label(s.sqlite_path, update.effective_chat.id, third_uid) if third_uid else None

    mode = str(lobby.get("mode", "hard")) if lobby else "hard"
    task = _fallback_bottle_task(actor, partner, third=third, mode=mode)

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
