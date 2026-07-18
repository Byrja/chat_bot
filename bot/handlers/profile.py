from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from bot.config import Settings
from bot.db import get_conn
from bot.services.formatting import human_date

_ROLE_RU = {
    "admin": "Админ",
    "old": "Олд",
    "trusted": "Проверенный",
    "newbie": "Новичок",
    "lava": "Токсичная лава",
}


def _settings(context: ContextTypes.DEFAULT_TYPE) -> Settings:
    return context.application.bot_data.get("settings") or context.application.settings


def _user_label(user) -> str:
    if user.first_name:
        return user.first_name
    if user.username:
        return f"@{user.username}"
    return str(user.id)


def _tg_link(uid: int, name: str) -> str:
    return f'<a href="tg://user?id={uid}">{name}</a>'


def _format_date(dt_str) -> str:
    """Deprecated: use human_date() from formatting.py instead."""
    return human_date(dt_str)


async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /profile — показать профиль участника.
    Reply на сообщение пользователя → профиль этого пользователя.
    Без reply → профиль текущего пользователя.
    """
    if not update.message or not update.effective_chat:
        return

    s = _settings(context)
    chat_id = update.effective_chat.id

    # Определить target
    if update.message.reply_to_message and update.message.reply_to_message.from_user:
        target = update.message.reply_to_message.from_user
    elif update.effective_user:
        target = update.effective_user
    else:
        return

    uid = target.id
    label = _user_label(target)
    link = _tg_link(uid, label)

    # 1. Role
    from bot.repositories.roles import get_role
    from bot.services.rbac import effective_role
    role = effective_role(s, s.sqlite_path, uid)

    # 2. Activity
    conn = get_conn(s.sqlite_path)
    cur = conn.cursor()

    # member_activity (msg_count + last)
    cur.execute(
        "SELECT msg_count, last_message_at FROM member_activity WHERE chat_id = ? AND tg_user_id = ?",
        (chat_id, uid),
    )
    act = cur.fetchone()
    msg_count = int(act[0]) if act else 0
    last_message = act[1] if act else None

    # first message
    cur.execute(
        "SELECT MIN(created_at) FROM member_messages WHERE chat_id = ? AND tg_user_id = ?",
        (chat_id, uid),
    )
    first_row = cur.fetchone()
    first_message = first_row[0] if first_row and first_row[0] else None

    # days in chat
    days_in_chat = None
    if first_message:
        try:
            from datetime import datetime
            dt = datetime.fromisoformat(first_message).replace(tzinfo=None)
            delta = datetime.now() - dt
            days_in_chat = delta.days
        except Exception:
            pass

    # 3. Sanctions
    cur.execute(
        "SELECT COUNT(*) FROM sanctions WHERE target_tg_user_id = ? AND action = 'warn'",
        (uid,),
    )
    warn_count = int(cur.fetchone()[0])

    # Current mute
    cur.execute(
        "SELECT until_at FROM sanctions WHERE target_tg_user_id = ? AND action = 'mute' AND until_at IS NOT NULL AND until_at > datetime('now')",
        (uid,),
    )
    active_mute = cur.fetchone()

    # Current ban
    cur.execute(
        "SELECT id FROM sanctions WHERE target_tg_user_id = ? AND action = 'ban'",
        (uid,),
    )
    active_ban = cur.fetchone()

    # 4. Karma
    cur.execute(
        "SELECT score FROM karma_scores WHERE chat_id = ? AND tg_user_id = ?",
        (chat_id, uid),
    )
    karma_row = cur.fetchone()
    karma = int(karma_row[0]) if karma_row else 0

    # 5. Application status
    cur.execute(
        "SELECT id, status, submitted_at, reject_reason FROM applications WHERE tg_user_id = ? ORDER BY id DESC LIMIT 1",
        (uid,),
    )
    app = cur.fetchone()
    app_id = int(app[0]) if app else None
    app_status = str(app[1]) if app else None
    app_reject = str(app[3]) if app and app[3] else None

    # 6. Birthday
    cur.execute(
        "SELECT birth_day, birth_month FROM member_profiles WHERE tg_user_id = ?",
        (uid,),
    )
    bp = cur.fetchone()
    bday = None
    if bp and bp[0] and bp[1]:
        bday = f"{int(bp[0])}.{int(bp[1])}"

    # 7. Friends & goats
    cur.execute(
        "SELECT COUNT(*) FROM friendships WHERE chat_id = ? AND status = 'accepted' AND ((user_a = ? AND user_b != ?) OR (user_b = ? AND user_a != ?))",
        (chat_id, uid, uid, uid, uid),
    )
    friend_count = int(cur.fetchone()[0])

    cur.execute(
        "SELECT COUNT(*) FROM goats WHERE chat_id = ? AND to_tg_user_id = ?",
        (chat_id, uid),
    )
    goat_count = int(cur.fetchone()[0])

    # 8. Active bottle game
    cur.execute(
        "SELECT COUNT(*) FROM bottle_games WHERE active = 1 AND finished_at IS NULL AND tg_user_id = ? LIMIT 1",
        (uid,),
    )
    active_bottle = cur.fetchone()[0] > 0

    conn.close()

    # Build text
    lines = [f"👤 <b>{link}</b>"]
    lines.append(f"🎭 Роль: {_ROLE_RU.get(role, role)}")
    lines.append("")
    lines.append("📊 Активность в чате:")
    lines.append(f"   Сообщений: {msg_count}")
    lines.append(f"   Первое сообщение: {human_date(first_message)}")
    lines.append(f"   Последнее сообщение: {human_date(last_message)}")
    if days_in_chat is not None:
        lines.append(f"   Дней в чате: {days_in_chat}")
    lines.append("")
    lines.append(f"⚖️ Карма: {karma}")
    lines.append(f"👥 Друзей: {friend_count}  😈 Козлов: {goat_count}")
    lines.append(f"⚠️ Предупреждения: {warn_count}")

    if active_mute:
        lines.append(f"🔇 Мут до: {human_date(active_mute[0])}")
    if active_ban:
        lines.append("🚫 В бане")

    if app:
        status_map = {"submitted": "📝 На рассмотрении", "approved": "✅ Одобрена", "rejected": "❌ Отклонена"}
        status_label = status_map.get(app_status, app_status)
        lines.append(f"📋 Анкета: {status_label}")
        if app_reject:
            lines.append(f"   Отклонена: {app_reject}")

    if bday:
        lines.append(f"🎂 День рождения: {bday}")

    if active_bottle:
        lines.append("🍾 Играл(а) в бутылочку (сейчас)")

    # Inline keyboard
    buttons = []
    if app_id:
        buttons.append([InlineKeyboardButton("📋 Анкета", callback_data=f"profile_app:{uid}")])
    if warn_count > 0 or active_mute or active_ban:
        buttons.append([InlineKeyboardButton("📜 История санкций", callback_data=f"profile_sanctions:{uid}")])
    if label:
        buttons.append([InlineKeyboardButton(f"🔍 {label}", url=f"tg://user?id={uid}")])
    if update.effective_user and uid == update.effective_user.id:
        buttons.append([InlineKeyboardButton("⬅️ В меню", callback_data=f"menu:home:{uid}")])

    reply_markup = InlineKeyboardMarkup(buttons) if buttons else None

    text = "\n".join(lines)
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=reply_markup)
