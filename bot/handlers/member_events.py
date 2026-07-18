from telegram import ChatMemberUpdated, Update
from telegram.ext import ContextTypes

from bot.config import Settings
from bot.db import get_conn
from bot.repositories.activity import ensure_member, update_member_name
from bot.services.formatting import user_link_from_user
from bot.services.rbac import invalidate_chat_admins


def _settings(context: ContextTypes.DEFAULT_TYPE) -> Settings:
    return context.application.bot_data.get("settings") or context.application.settings


def _display_name(user) -> str:
    if not user:
        return "участник"
    return user.first_name or (f"@{user.username}" if user.username else str(user.id))


def _tg_handle(user_id: int | str | None, username: str | None = None, saved: str | None = None) -> str:
    if username:
        return f"@{username}"
    saved = (saved or "").strip()
    if saved.startswith("@"):
        return saved
    if saved and user_id is not None and saved != str(user_id):
        return saved
    return "—"


def _was_member(status: str) -> bool:
    return status in {"member", "administrator", "creator", "restricted"}


def _is_member(status: str) -> bool:
    return status in {"member", "administrator", "creator", "restricted"}


def _latest_application_packet(db_path: str, tg_user_id: int) -> tuple[int, str, dict[str, str]] | None:
    conn = get_conn(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, status FROM applications
        WHERE tg_user_id = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (tg_user_id,),
    )
    row = cur.fetchone()
    if not row:
        conn.close()
        return None

    app_id, status = int(row[0]), str(row[1])
    cur.execute(
        "SELECT question_code, answer_text FROM application_answers WHERE application_id = ? ORDER BY position ASC",
        (app_id,),
    )
    answers = {str(r[0]): str(r[1]) for r in cur.fetchall()}
    conn.close()
    return (app_id, status, answers)


async def member_status_event(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cmu: ChatMemberUpdated | None = update.chat_member
    if not cmu:
        return

    # Любое изменение статуса участника (promote/demote/leave/kick/join)
    # инвалидирует кэш Telegram-админов, чтобы следующий is_chat_admin_cmd
    # подтянул свежий список без ожидания TTL 5 мин.
    invalidate_chat_admins(context, cmu.chat.id)

    s = _settings(context)
    chat = cmu.chat
    if not chat or chat.id != s.main_chat_id:
        return

    old_status = cmu.old_chat_member.status
    new_status = cmu.new_chat_member.status
    user = cmu.new_chat_member.user
    if not user or user.is_bot:
        return

    just_joined = (not _was_member(old_status)) and _is_member(new_status)
    just_left = _was_member(old_status) and (new_status in {"left", "kicked"})

    if just_joined:
        who = _display_name(user)
        await context.bot.send_message(chat_id=s.main_chat_id, text=f"👋 Добро пожаловать, {user_link_from_user(user)}!", parse_mode="HTML")
        ensure_member(s.sqlite_path, chat.id, user.id, user.username, user.first_name)

        packet = _latest_application_packet(s.sqlite_path, user.id)
        if packet:
            _, _, answers = packet
            name_from_app = answers.get('name')
            if name_from_app and name_from_app.strip():
                update_member_name(s.sqlite_path, chat.id, user.id, name_from_app.strip())
        kwargs = {}
        if s.main_questionnaires_thread_id:
            kwargs["message_thread_id"] = s.main_questionnaires_thread_id

        if not packet:
            await context.bot.send_message(
                chat_id=s.main_chat_id,
                text=(
                    "🧾 Анкета участника\n"
                    "───────────────────\n"
                    f"Пользователь: {user_link_from_user(user)}\n"
                    "Анкета не заполнена\n\n"
                    "Заполнить/обновить анкету: в личке бота /start"
                ),
                parse_mode="HTML",
                **kwargs,
            )
            return

        app_id, status, answers = packet
        status_ru = {
            "draft": "черновик",
            "submitted": "на модерации",
            "approved": "одобрена",
            "rejected": "отклонена",
        }.get(status, status)
        tg = _tg_handle(user.id, user.username, answers.get("tg_handle"))
        text = (
            "🧾 Анкета участника\n"
            "───────────────────\n"
            f"Application ID: {app_id}\n"
            f"User: {tg}\n"
            f"Статус: {status_ru}\n"
            f"Имя: {answers.get('name', '—')}\n"
            f"Район: {answers.get('district', '—')}\n"
            f"Возраст: {answers.get('age', '—')}\n"
            f"Хобби: {answers.get('hobby', '—')}\n"
            f"Алкоголь: {answers.get('alcohol', '—')}\n"
            f"Свободное время: {answers.get('availability', '—')}"
        )
        photo_id = answers.get("photo_file_id")
        if photo_id:
            await context.bot.send_photo(chat_id=s.main_chat_id, photo=photo_id, caption=text, parse_mode="HTML", **kwargs)
        else:
            await context.bot.send_message(chat_id=s.main_chat_id, text=text, parse_mode="HTML", **kwargs)
        return

    if just_left:
        who = _display_name(user)
        await context.bot.send_message(chat_id=s.main_chat_id, text=f"👋 {user_link_from_user(user)}, удачи! Если что — возвращайся.", parse_mode="HTML")
