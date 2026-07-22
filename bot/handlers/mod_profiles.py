import html
from datetime import datetime, timezone

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from bot.config import Settings
from bot.repositories.applications import get_latest_application_for_user
from bot.repositories.moderation import (
    add_note,
    count_warns,
    get_member_summary,
    get_role,
    list_members_for_mod,
    list_notes,
)
from bot.repositories.roles import set_role
from bot.repositories.sanctions import add_sanction, list_warns_for_user
from bot.services.formatting import human_date
from bot.services.rbac import is_chat_admin_cmd
from bot.services.timeparse import parse_mute_duration

# --- state keys for conversation-like input via bot_data ---
# We don't use ConversationHandler here; instead we set a pending action
# keyed by admin user id and expect the next text message in the chat to be the reason.

_PENDING_MOD_ACTION = "pending_mod_action"

_ROLE_RU = {
    "admin": "Админ",
    "old": "Олд",
    "trusted": "Проверенный",
    "newbie": "Новичок",
    "lava": "Токсичная лава",
}


class _RoleMap:
    ORDER = ["admin", "old", "trusted", "newbie", "lava"]


def _settings(context: ContextTypes.DEFAULT_TYPE) -> Settings:
    return context.application.bot_data.get("settings") or context.application.settings


def _settings_sqlite(context: ContextTypes.DEFAULT_TYPE) -> str:
    return _settings(context).sqlite_path


def _main_chat_id(context: ContextTypes.DEFAULT_TYPE) -> int:
    return _settings(context).main_chat_id


def _admin_ids(context: ContextTypes.DEFAULT_TYPE) -> set[int]:
    return set(_settings(context).admin_user_ids)


def _user_link_html(uid: int, first_name: str, username: str) -> str:
    label = (first_name or username or f"User {uid}").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f'<a href="tg://user?id={uid}">{label}</a>'


def _profile_text(context: ContextTypes.DEFAULT_TYPE, uid: int, summary: dict | None, role: str, warn_count: int, app: tuple | None = None) -> str:
    s = summary or {}
    link = _user_link_html(uid, s.get("first_name", ""), s.get("username", ""))
    lines = [
        f"👤 Профиль: {link}",
        "───────────────────",
        f"ID: <code>{uid}</code>",
    ]
    if s.get('username'):
        lines.append(f"Username: @{s.get('username')}")
    lines.append(f"Имя: {s.get('first_name', '—')}")
    lines.append(f"Роль: {_ROLE_RU.get(role, role)}")
    lines.append(f"Сообщений: {s.get('msg_count', 0)}")
    lines.append(f"Последнее сообщение: {human_date(s.get('last_message_at'))}")
    lines.append(f"Предупреждений: {warn_count}")
    if app:
        app_id, status, answers = app
        status_ru = {"draft": "черновик", "submitted": "на модерации", "approved": "одобрена", "rejected": "отклонена"}.get(status, status)
        lines.append("")
        lines.append(f"🧾 Анкета #{app_id} — {status_ru}")
        if answers:
            for key in ["name", "district", "age", "hobby", "alcohol", "availability", "tg_handle"]:
                val = answers.get(key)
                if val:
                    lines.append(f"{_answer_label(key)}: {html.escape(val)}")
    return "\n".join(lines)


def _answer_label(key: str) -> str:
    return {
        "name": "Имя",
        "district": "Район",
        "age": "Возраст",
        "hobby": "Хобби",
        "alcohol": "Алкоголь",
        "availability": "Свободное время",
        "tg_handle": "TG",
    }.get(key, key)


def _profile_markup(uid: int, issuer_id: int, current_role: str) -> InlineKeyboardMarkup:
    rows = []
    # role cycling buttons
    idx = _RoleMap.ORDER.index(current_role) if current_role in _RoleMap.ORDER else 3
    prev_role = _RoleMap.ORDER[(idx - 1) % len(_RoleMap.ORDER)]
    next_role = _RoleMap.ORDER[(idx + 1) % len(_RoleMap.ORDER)]
    rows.append([
        InlineKeyboardButton(f"⬅️ {_ROLE_RU[prev_role]}", callback_data=f"modprofile:role:{uid}:{issuer_id}:{prev_role}"),
        InlineKeyboardButton(f"{_ROLE_RU[next_role]} ➡️", callback_data=f"modprofile:role:{uid}:{issuer_id}:{next_role}"),
    ])
    rows.append([
        InlineKeyboardButton("⚠️ Варн", callback_data=f"modprofile:warnask:{uid}:{issuer_id}"),
        InlineKeyboardButton("🔇 Мут", callback_data=f"modprofile:muteask:{uid}:{issuer_id}"),
        InlineKeyboardButton("⛔ Бан", callback_data=f"modprofile:banask:{uid}:{issuer_id}"),
    ])
    rows.append([
        InlineKeyboardButton("📝 Заметки", callback_data=f"modprofile:notes:{uid}:{issuer_id}"),
        InlineKeyboardButton("➕ Добавить заметку", callback_data=f"modprofile:noteask:{uid}:{issuer_id}"),
    ])
    rows.append([
        InlineKeyboardButton("⬅️ К списку", callback_data=f"modprofile:list:{issuer_id}:0"),
        InlineKeyboardButton("⬅️ В меню", callback_data=f"menu:mod:{issuer_id}"),
    ])
    return InlineKeyboardMarkup(rows)


def _members_page_markup(members: list, issuer_id: int, page: int, per_page: int) -> InlineKeyboardMarkup:
    start = page * per_page
    end = start + per_page
    page_members = members[start:end]
    rows = []
    for uid, username, first_name, _msg_count, _last_at in page_members:
        label = (first_name or username or f"User {uid}").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        rows.append([InlineKeyboardButton(label, callback_data=f"modprofile:view:{uid}:{issuer_id}")])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"modprofile:list:{issuer_id}:{page - 1}"))
    if end < len(members):
        nav.append(InlineKeyboardButton("Вперёд ➡️", callback_data=f"modprofile:list:{issuer_id}:{page + 1}"))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton("⬅️ В меню", callback_data=f"menu:mod:{issuer_id}")])
    return InlineKeyboardMarkup(rows)


async def mod_profile_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.data or not update.effective_user:
        return
    await query.answer()

    if not await is_chat_admin_cmd(context, update.effective_chat.id, update.effective_user.id):
        await query.answer("Недостаточно прав", show_alert=True)
        return

    parts = query.data.split(":")
    if len(parts) < 2:
        return

    action = parts[1]
    s = _settings(context)
    issuer_id = update.effective_user.id

    try:
        if action == "list":
            page = int(parts[3]) if len(parts) > 3 else 0
            members = list_members_for_mod(s.sqlite_path, s.main_chat_id)
            if not members:
                await query.edit_message_text(
                    "Пока нет участников в базе.",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ В меню", callback_data=f"menu:mod:{issuer_id}")]]),
                )
                return
            text = f"👤 Профили участников ({len(members)}):"
            await query.edit_message_text(
                text,
                reply_markup=_members_page_markup(members, issuer_id, page, per_page=10),
            )
            return

        if action == "view":
            uid = int(parts[2])
            summary = get_member_summary(s.sqlite_path, s.main_chat_id, uid)
            role = get_role(s.sqlite_path, uid)
            warn_count = count_warns(s.sqlite_path, uid)
            app = get_latest_application_for_user(s.sqlite_path, uid)
            text = _profile_text(context, uid, summary, role, warn_count, app=app)
            await query.edit_message_text(
                text,
                parse_mode="HTML",
                reply_markup=_profile_markup(uid, issuer_id, role),
            )
            return

        if action == "role":
            uid = int(parts[2])
            new_role = parts[4]
            set_role(s.sqlite_path, uid, new_role, assigned_by_tg_user_id=issuer_id)
            summary = get_member_summary(s.sqlite_path, s.main_chat_id, uid)
            warn_count = count_warns(s.sqlite_path, uid)
            app = get_latest_application_for_user(s.sqlite_path, uid)
            text = _profile_text(context, uid, summary, new_role, warn_count, app=app)
            await query.edit_message_text(
                text,
                parse_mode="HTML",
                reply_markup=_profile_markup(uid, issuer_id, new_role),
            )
            return

        if action == "warnask":
            uid = int(parts[2])
            # set pending action; next text message in this chat from admin = reason
            context.bot_data.setdefault(_PENDING_MOD_ACTION, {})[issuer_id] = {"type": "warn", "target": uid, "chat_id": update.effective_chat.id}
            target_link = _user_link_html(uid, "", "")
            await query.edit_message_text(
                f"⚠️ Варн для {target_link}.\nНапиши причину в этот чат (или /cancel для отмены):",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Отмена", callback_data=f"modprofile:view:{uid}:{issuer_id}")]]),
            )
            return

        if action == "muteask":
            uid = int(parts[2])
            summary = get_member_summary(s.sqlite_path, s.main_chat_id, uid)
            target_link = _user_link_html(uid, summary.get("first_name", ""), summary.get("username", ""))
            durations = [
                ("30 мин", "30"), ("1 час", "1h"), ("6 часов", "6h"),
                ("1 день", "1d"), ("7 дней", "7d"),
            ]
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton(label, callback_data=f"modprofile:mute:{uid}:{issuer_id}:{dur}")]
                for label, dur in durations
            ] + [[InlineKeyboardButton("⬅️ К профилю", callback_data=f"modprofile:view:{uid}:{issuer_id}")]])
            await query.edit_message_text(
                f"🔇 Выбери длительность мута для {target_link}:",
                parse_mode="HTML",
                reply_markup=kb,
            )
            return

        if action == "mute":
            uid = int(parts[2])
            duration_text = parts[4] if len(parts) > 4 else "30"
            await _apply_mute(update, context, uid, duration_text)
            return

        if action == "banask":
            uid = int(parts[2])
            context.bot_data.setdefault(_PENDING_MOD_ACTION, {})[issuer_id] = {"type": "ban", "target": uid, "chat_id": update.effective_chat.id}
            target_link = _user_link_html(uid, "", "")
            await query.edit_message_text(
                f"⛔ Бан для {target_link}.\nНапиши причину в этот чат (или /cancel для отмены):",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Отмена", callback_data=f"modprofile:view:{uid}:{issuer_id}")]]),
            )
            return

        if action == "notes":
            uid = int(parts[2])
            notes = list_notes(s.sqlite_path, uid)
            target_link = _user_link_html(uid, "", "")
            if not notes:
                text = f"📝 Заметки {target_link}\n───────────────────\nПока нет заметок."
            else:
                lines = [f"📝 Заметки {target_link}", "───────────────────"]
                for note in notes:
                    dt = human_date(note["created_at"])
                    lines.append(f"#{note['id']} | {dt} | от {note['author_tg_user_id']}\n{html.escape(note['note_text'])}")
                text = "\n\n".join(lines)
            await query.edit_message_text(
                text,
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("➕ Добавить заметку", callback_data=f"modprofile:noteask:{uid}:{issuer_id}")],
                    [InlineKeyboardButton("⬅️ К профилю", callback_data=f"modprofile:view:{uid}:{issuer_id}")],
                ]),
            )
            return

        if action == "noteask":
            uid = int(parts[2])
            context.bot_data.setdefault(_PENDING_MOD_ACTION, {})[issuer_id] = {"type": "note", "target": uid, "chat_id": update.effective_chat.id}
            target_link = _user_link_html(uid, "", "")
            await query.edit_message_text(
                f"📝 Заметка для {target_link}.\nНапиши текст заметки в этот чат (или /cancel для отмены):",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Отмена", callback_data=f"modprofile:view:{uid}:{issuer_id}")]]),
            )
            return

    except (ValueError, IndexError) as e:
        await query.edit_message_text(f"Ошибка обработки: {e}")
        return


async def _apply_mute(update: Update, context: ContextTypes.DEFAULT_TYPE, target_id: int, duration_text: str) -> None:
    from telegram import ChatPermissions
    s = _settings(context)
    until = parse_mute_duration(duration_text)
    try:
        permissions = ChatPermissions(can_send_messages=False)
        if until:
            await context.bot.restrict_chat_member(
                chat_id=s.main_chat_id,
                user_id=target_id,
                permissions=permissions,
                until_date=until,
            )
        else:
            await context.bot.restrict_chat_member(
                chat_id=s.main_chat_id,
                user_id=target_id,
                permissions=permissions,
            )
    except Exception as e:
        target_link = _user_link_html(target_id, "", "")
        await update.callback_query.edit_message_text(f"Не удалось выдать мут {target_link}: {e}", parse_mode="HTML")
        return

    add_sanction(
        s.sqlite_path,
        target_tg_user_id=target_id,
        action="mute",
        issued_by_tg_user_id=update.effective_user.id,
        reason=f"Мут {duration_text} из панели профиля",
        until_at=until.isoformat() if until else None,
    )
    target_link = _user_link_html(target_id, "", "")
    await update.callback_query.edit_message_text(
        f"🔇 Мут {duration_text} выдан пользователю {target_link}",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ К профилю", callback_data=f"modprofile:view:{target_id}:{update.effective_user.id}")]]),
    )


async def _apply_warn(update: Update, context: ContextTypes.DEFAULT_TYPE, target_id: int, reason: str) -> None:
    s = _settings(context)
    issuer_id = update.effective_user.id
    add_sanction(
        s.sqlite_path,
        target_tg_user_id=target_id,
        action="warn",
        issued_by_tg_user_id=issuer_id,
        reason=reason,
    )
    warn_count = count_warns(s.sqlite_path, target_id)
    target_link = _user_link_html(target_id, "", "")
    text = f"⚠️ Предупреждение выдано {target_link}.\nПричина: {reason}\nВсего предупреждений: {warn_count}"
    await update.message.reply_text(text, parse_mode="HTML")

    if warn_count >= 3:
        markup = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Да, кикнуть", callback_data=f"warnkick_yes_{target_id}"),
                InlineKeyboardButton("❌ Нет, отмена", callback_data=f"warnkick_no_{target_id}"),
            ]
        ])
        await update.message.reply_text(
            f"⚠️ У пользователя {target_link} уже {warn_count} предупреждений. Кикнуть?",
            parse_mode="HTML",
            reply_markup=markup,
        )


async def _apply_ban(update: Update, context: ContextTypes.DEFAULT_TYPE, target_id: int, reason: str) -> None:
    s = _settings(context)
    issuer_id = update.effective_user.id
    try:
        await context.bot.ban_chat_member(chat_id=s.main_chat_id, user_id=target_id, revoke_messages=False)
    except Exception as e:
        await update.message.reply_text(f"Не удалось выдать бан: {e}")
        return
    add_sanction(
        s.sqlite_path,
        target_tg_user_id=target_id,
        action="ban",
        issued_by_tg_user_id=issuer_id,
        reason=reason,
    )
    target_link = _user_link_html(target_id, "", "")
    text = f"⛔ Бан выдан {target_link}."
    if reason:
        text += f"\nПричина: {reason}"
    await update.message.reply_text(text, parse_mode="HTML")


async def _apply_note(update: Update, context: ContextTypes.DEFAULT_TYPE, target_id: int, note_text: str) -> None:
    s = _settings(context)
    issuer_id = update.effective_user.id
    note_id = add_note(s.sqlite_path, target_id, issuer_id, note_text)
    target_link = _user_link_html(target_id, "", "")
    await update.message.reply_text(
        f"📝 Заметка #{note_id} добавлена для {target_link}.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ К профилю", callback_data=f"modprofile:view:{target_id}:{issuer_id}")],
        ]),
    )


async def mod_profile_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles pending reason/note input from admin in the group chat."""
    if not update.message or not update.effective_user or not update.effective_chat:
        return
    issuer_id = update.effective_user.id
    pending = context.bot_data.get(_PENDING_MOD_ACTION, {}).get(issuer_id)
    if not pending:
        return
    if pending.get("chat_id") != update.effective_chat.id:
        return

    text = update.message.text or ""
    if text.strip().lower() == "/cancel":
        context.bot_data[_PENDING_MOD_ACTION].pop(issuer_id, None)
        await update.message.reply_text("Отменено.")
        return

    target_id = pending["target"]
    action_type = pending["type"]
    context.bot_data[_PENDING_MOD_ACTION].pop(issuer_id, None)

    if action_type == "warn":
        await _apply_warn(update, context, target_id, text.strip())
    elif action_type == "ban":
        await _apply_ban(update, context, target_id, text.strip())
    elif action_type == "note":
        await _apply_note(update, context, target_id, text.strip())


async def mod_profile_cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user:
        return
    issuer_id = update.effective_user.id
    if context.bot_data.get(_PENDING_MOD_ACTION, {}).pop(issuer_id, None):
        await update.message.reply_text("Отменено.")
    else:
        await update.message.reply_text("Нет активного действия.")
