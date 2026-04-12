from telegram import ChatMemberUpdated, Update
from telegram.ext import ContextTypes

from bot.config import Settings
from bot.db import get_conn


def _settings(context: ContextTypes.DEFAULT_TYPE) -> Settings:
    return context.application.bot_data.get("settings") or context.application.settings


def _display_name(user) -> str:
    if not user:
        return "участник"
    return user.first_name or (f"@{user.username}" if user.username else str(user.id))


def _was_member(status: str) -> bool:
    return status in {"member", "administrator", "creator", "restricted"}


def _is_member(status: str) -> bool:
    return status in {"member", "administrator", "creator", "restricted"}


def _latest_application_summary(db_path: str, tg_user_id: int) -> tuple[str, str]:
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
        return ("нет", "Анкета не заполнена")

    app_id, status = int(row[0]), str(row[1])
    cur.execute(
        "SELECT question_code, answer_text FROM application_answers WHERE application_id = ? ORDER BY position ASC",
        (app_id,),
    )
    answers = {str(r[0]): str(r[1]) for r in cur.fetchall()}
    conn.close()

    name = answers.get("name", "—")
    district = answers.get("district", "—")
    age = answers.get("age", "—")
    return (
        status,
        f"ID: {app_id}\nИмя: {name}\nРайон: {district}\nВозраст: {age}",
    )


async def member_status_event(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cmu: ChatMemberUpdated | None = update.chat_member
    if not cmu:
        return

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
        await context.bot.send_message(chat_id=s.main_chat_id, text=f"👋 Добро пожаловать, {who}!")

        status, summary = _latest_application_summary(s.sqlite_path, user.id)
        status_ru = {
            "draft": "черновик",
            "submitted": "на модерации",
            "approved": "одобрена",
            "rejected": "отклонена",
        }.get(status, status)
        text = (
            "🧾 Анкета участника\n"
            "───────────────────\n"
            f"Пользователь: {who} ({user.id})\n"
            f"Статус анкеты: {status_ru}\n"
            f"{summary}\n\n"
            "Заполнить/обновить анкету: в личке бота /start"
        )
        kwargs = {}
        if s.main_questionnaires_thread_id:
            kwargs["message_thread_id"] = s.main_questionnaires_thread_id
        await context.bot.send_message(chat_id=s.main_chat_id, text=text, **kwargs)
        return

    if just_left:
        who = _display_name(user)
        await context.bot.send_message(chat_id=s.main_chat_id, text=f"👋 {who}, удачи! Если что — возвращайся.")
