from datetime import datetime
import time

from telegram import ChatPermissions, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from bot.config import Settings
from bot.db import get_conn
from bot.repositories.profile import get_birthdate, set_birthdate
from bot.services.rbac import effective_role, has_permission


def _settings(context: ContextTypes.DEFAULT_TYPE) -> Settings:
    return context.application.bot_data["settings"]


def _menu_kb(update: Update, context: ContextTypes.DEFAULT_TYPE, issuer_id: int) -> InlineKeyboardMarkup:
    s = _settings(context)

    rows = [
        [
            InlineKeyboardButton("📊 Статистика", callback_data=f"menu:stats:{issuer_id}"),
            InlineKeyboardButton("👥 Актив", callback_data=f"menu:activity:{issuer_id}"),
        ],
        [InlineKeyboardButton("💬 Топ пар", callback_data=f"menu:pairs:{issuer_id}"), InlineKeyboardButton("📆 Топ недели", callback_data=f"menu:week:{issuer_id}")],
        [InlineKeyboardButton("📣 Хипиш", callback_data=f"menu:fun_hipish:{issuer_id}")],
        [InlineKeyboardButton("🎭 Развлечения", callback_data=f"menu:fun:{issuer_id}")],
        [InlineKeyboardButton("⚙️ Настройки", callback_data=f"menu:settings:{issuer_id}")],
    ]

    if has_permission(s, s.sqlite_path, issuer_id, "warn"):
        rows.append([InlineKeyboardButton("🛡 Модерация", callback_data=f"menu:mod:{issuer_id}")])

    return InlineKeyboardMarkup(rows)


def _back_kb(issuer_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ В меню", callback_data=f"menu:home:{issuer_id}")]])


async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message or (update.callback_query.message if update.callback_query else None)
    if not msg or not update.effective_user:
        return

    issuer_id = update.effective_user.id
    text = "MD4 меню\nВыбери действие:"
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=_menu_kb(update, context, issuer_id))
    else:
        await msg.reply_text(text, reply_markup=_menu_kb(update, context, issuer_id))


async def menu_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not update.effective_user or not update.effective_chat:
        return
    await query.answer()

    parts = (query.data or "").split(":")
    if len(parts) != 3:
        return
    action = parts[1]
    try:
        issuer_id = int(parts[2])
    except Exception:
        return

    if update.effective_user.id != issuer_id:
        await query.answer("Это меню не для тебя", show_alert=True)
        return

    s = _settings(context)
    uid = update.effective_user.id

    if action == "home":
        await show_menu(update, context)
        return

    if action == "stats":
        conn = get_conn(s.sqlite_path)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM applications WHERE tg_user_id = ?", (uid,))
        apps = int(cur.fetchone()[0] or 0)
        cur.execute("SELECT COUNT(*) FROM applications WHERE tg_user_id = ? AND status='approved'", (uid,))
        approved = int(cur.fetchone()[0] or 0)
        cur.execute(
            "SELECT msg_count, last_message_at FROM member_activity WHERE chat_id = ? AND tg_user_id = ?",
            (s.main_chat_id, uid),
        )
        r = cur.fetchone()
        conn.close()
        msg_count = int(r[0]) if r else 0
        last_at = r[1] if r else None
        role = effective_role(s, s.sqlite_path, uid)

        await query.edit_message_text(
            "📊 Твоя статистика\n"
            "───────────────────\n"
            f"Роль: {role}\n"
            f"Анкет подано: {apps}\n"
            f"Одобрено: {approved}\n"
            f"Сообщений в чате: {msg_count}\n"
            f"Последнее сообщение: {last_at or '—'}",
            reply_markup=_back_kb(issuer_id),
        )
        return

    if action == "pairs":
        conn = get_conn(s.sqlite_path)
        cur = conn.cursor()
        cur.execute(
            """
            SELECT from_tg_user_id, to_tg_user_id, pair_count, last_reply_at
            FROM reply_pairs
            WHERE chat_id = ?
            ORDER BY pair_count DESC, datetime(last_reply_at) DESC
            LIMIT 10
            """,
            (s.main_chat_id,),
        )
        rows = cur.fetchall()

        if not rows:
            conn.close()
            text = "Пока нет данных по топ-парам (нужны reply-сообщения)."
        else:
            uids = set()
            for fr, to, _, _ in rows:
                uids.add(int(fr))
                uids.add(int(to))

            labels = {uid: str(uid) for uid in uids}
            for uid in uids:
                cur.execute(
                    "SELECT COALESCE(username,''), COALESCE(first_name,'') FROM member_activity WHERE chat_id = ? AND tg_user_id = ? ORDER BY updated_at DESC LIMIT 1",
                    (s.main_chat_id, uid),
                )
                r = cur.fetchone()
                if r:
                    uname, fname = r
                    labels[uid] = f"@{uname}" if uname else (fname or str(uid))
            conn.close()

            lines = ["💬 Топ пар (по reply)", "───────────────────"]
            for i, (fuid, tuid, cnt, last_at) in enumerate(rows, 1):
                lines.append(f"{i}. {labels.get(int(fuid), fuid)} → {labels.get(int(tuid), tuid)} | {cnt} | {last_at or '—'}")
            text = "\n".join(lines)

        await query.edit_message_text(text, reply_markup=_back_kb(issuer_id))
        return

    if action == "week":
        conn = get_conn(s.sqlite_path)
        cur = conn.cursor()
        cur.execute(
            """
            SELECT mm.tg_user_id,
                   COUNT(*) as c,
                   MAX(mm.created_at) as last_at,
                   COALESCE(ma.username, ''),
                   COALESCE(ma.first_name, '')
            FROM member_messages mm
            LEFT JOIN member_activity ma
              ON ma.chat_id = mm.chat_id AND ma.tg_user_id = mm.tg_user_id
            WHERE mm.chat_id = ?
              AND datetime(mm.created_at) >= datetime('now', '-7 days')
            GROUP BY mm.tg_user_id, ma.username, ma.first_name
            ORDER BY c DESC, datetime(last_at) DESC
            LIMIT 10
            """,
            (s.main_chat_id,),
        )
        rows = cur.fetchall()
        conn.close()

        if not rows:
            text = "Пока нет данных за последние 7 дней."
        else:
            lines = ["📆 Топ недели (7 дней)", "───────────────────"]
            for i, (uid2, cnt, last_at, username, first_name) in enumerate(rows, 1):
                label = f"@{username}" if username else (first_name or str(uid2))
                lines.append(f"{i}. {label} — {cnt} | {last_at or '—'}")
            text = "\n".join(lines)

        await query.edit_message_text(text, reply_markup=_back_kb(issuer_id))
        return

    if action == "activity":
        conn = get_conn(s.sqlite_path)
        cur = conn.cursor()
        cur.execute(
            """
            SELECT COALESCE(username,''), COALESCE(first_name,''), msg_count, last_message_at
            FROM member_activity
            WHERE chat_id = ?
            ORDER BY msg_count DESC, datetime(last_message_at) DESC
            LIMIT 10
            """,
            (s.main_chat_id,),
        )
        rows = cur.fetchall()
        conn.close()

        if not rows:
            text = "Пока нет данных по активности."
        else:
            lines = ["👥 Топ активности", "───────────────────"]
            for i, (username, first_name, cnt, last_at) in enumerate(rows, 1):
                label = f"@{username}" if username else (first_name or "user")
                lines.append(f"{i}. {label} — {cnt} | {last_at or '—'}")
            text = "\n".join(lines)

        await query.edit_message_text(text, reply_markup=_back_kb(issuer_id))
        return

    if action == "fun":
        await query.edit_message_text(
            "🎭 Развлечения\nПока доступен раздел общения и активности.",
            reply_markup=_back_kb(issuer_id),
        )
        return

    if action == "fun_hipish":
        key = f"hipish_last_ts:{update.effective_chat.id}"
        now = time.time()
        last = float(context.application.bot_data.get(key, 0.0) or 0.0)
        cooldown = 3600
        if now - last < cooldown:
            left_min = int((cooldown - (now - last)) // 60) + 1
            await query.edit_message_text(
                f"/hipish можно вызывать не чаще 1 раза в час. Осталось ~{left_min} мин.",
                reply_markup=_back_kb(issuer_id),
            )
            return

        usernames: list[str] = []
        missing = 0
        try:
            admins = await context.bot.get_chat_administrators(update.effective_chat.id)
            for a in admins:
                u = a.user
                if not u or u.is_bot:
                    continue
                if u.username:
                    usernames.append(f"@{u.username}")
                else:
                    missing += 1
        except Exception:
            pass

        usernames = sorted(set(usernames))
        if not usernames:
            text = "Не нашёл админов с @username"
        else:
            text = "Хипиш! " + " ".join(usernames)
            if missing:
                text += f"\n(и ещё {missing} админ(ов) без @username)"

        await query.edit_message_text(text, reply_markup=_back_kb(issuer_id))
        context.application.bot_data[key] = now
        return

    if action == "settings":
        b = get_birthdate(s.sqlite_path, uid)
        btxt = f"{b[0]:02d}.{b[1]:02d}" if b else "не задана"
        role = effective_role(s, s.sqlite_path, uid)

        conn = get_conn(s.sqlite_path)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM applications WHERE tg_user_id = ?", (uid,))
        apps_total = int(cur.fetchone()[0] or 0)
        cur.execute("SELECT COUNT(*) FROM applications WHERE tg_user_id = ? AND status='approved'", (uid,))
        apps_approved = int(cur.fetchone()[0] or 0)
        cur.execute(
            "SELECT status, COALESCE(submitted_at, created_at) FROM applications WHERE tg_user_id = ? ORDER BY id DESC LIMIT 1",
            (uid,),
        )
        last = cur.fetchone()
        conn.close()
        last_status = last[0] if last else "—"
        last_dt = last[1] if last else "—"

        await query.edit_message_text(
            "⚙️ Твой профиль и настройки\n"
            "───────────────────\n"
            f"Роль: {role}\n"
            f"Дата рождения: {btxt}\n"
            f"Анкет подано: {apps_total}\n"
            f"Одобрено: {apps_approved}\n"
            f"Последняя анкета: {last_status} ({last_dt})\n\n"
            "Выбери действие:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔇 Самомут 15 мин", callback_data=f"menu:settings_muteme15:{issuer_id}")],
                [InlineKeyboardButton("🎂 Указать дату рождения", callback_data=f"menu:settings_bday:{issuer_id}")],
                [InlineKeyboardButton("📝 Редактировать анкету", callback_data=f"menu:settings_editform:{issuer_id}")],
                [InlineKeyboardButton("🚪 Kick me", callback_data=f"menu:settings_kick_confirm:{issuer_id}")],
                [InlineKeyboardButton("⬅️ В меню", callback_data=f"menu:home:{issuer_id}")],
            ]),
        )
        return

    if action == "settings_muteme15":
        try:
            await context.bot.restrict_chat_member(
                chat_id=update.effective_chat.id,
                user_id=uid,
                permissions=ChatPermissions(can_send_messages=False),
                until_date=datetime.utcnow().timestamp() + 15 * 60,
            )
            await query.edit_message_text("Самомут на 15 минут активирован", reply_markup=_back_kb(issuer_id))
        except Exception as e:
            await query.edit_message_text(f"Не удалось выдать самомут: {e}", reply_markup=_back_kb(issuer_id))
        return

    if action == "settings_bday":
        context.user_data["await_birthdate_issuer"] = issuer_id
        await query.edit_message_text(
            "Введи дату рождения в формате ДД.ММ (например 05.11)",
            reply_markup=_back_kb(issuer_id),
        )
        return

    if action == "settings_editform":
        await query.edit_message_text(
            "Чтобы обновить свою анкету, просто нажми /start и пройди заново.",
            reply_markup=_back_kb(issuer_id),
        )
        return

    if action == "settings_kick_confirm":
        await query.edit_message_text(
            "Ты точно хочешь сам себя кикнуть из чата?",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Да, кикни меня", callback_data=f"menu:settings_kick_do:{issuer_id}")],
                [InlineKeyboardButton("⬅️ Назад", callback_data=f"menu:settings:{issuer_id}")],
            ]),
        )
        return

    if action == "settings_kick_do":
        speech = (
            "🎭 Великий выход…\n"
            "Ты уходишь как легенда этого чата.\n"
            "Пусть дорога будет мемной, а вайб — вечным."
        )
        await query.edit_message_text(speech)
        try:
            await context.bot.ban_chat_member(chat_id=update.effective_chat.id, user_id=uid, revoke_messages=False)
            await context.bot.unban_chat_member(chat_id=update.effective_chat.id, user_id=uid, only_if_banned=True)
        except Exception:
            pass
        return

    if action == "mod":
        if not has_permission(s, s.sqlite_path, uid, "warn"):
            await query.edit_message_text("Недостаточно прав", reply_markup=_back_kb(issuer_id))
            return
        await query.edit_message_text(
            "🛡 Модерация\n"
            "Команды (reply на пользователя):\n"
            "/mod — кнопочная панель\n"
            "/warn причина\n"
            "/mute 30 причина\n"
            "/ban причина",
            reply_markup=_back_kb(issuer_id),
        )
        return

    await show_menu(update, context)
