from datetime import datetime, timezone

from telegram import Update
from telegram.ext import ContextTypes

from bot.config import Settings
from bot.repositories.activity import bump_message_activity, get_top_activity, get_asleep_activity, get_today_activity, count_today_messages, get_top_week_activity
from bot.repositories.pairs import bump_reply_pair, get_top_pairs
from bot.services.formatting import (
    days_silent,
    human_date,
    is_valid_name,
    user_link_from_parts,
)
from bot.services.rbac import has_permission


def _settings(context: ContextTypes.DEFAULT_TYPE) -> Settings:
    return context.application.bot_data.get("settings") or context.application.settings


def _can_activity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user = update.effective_user
    if not user:
        return False
    s = _settings(context)
    return has_permission(s, s.sqlite_path, user.id, "activity")


async def track_message_activity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_chat or not update.effective_user:
        return
    s = _settings(context)
    if update.effective_chat.id != s.main_chat_id:
        return

    msg = update.effective_message
    if not msg:
        return
    if msg.text and msg.text.startswith("/"):
        return

    bump_message_activity(
        s.sqlite_path,
        chat_id=update.effective_chat.id,
        tg_user_id=update.effective_user.id,
        username=update.effective_user.username,
        first_name=update.effective_user.first_name,
    )

    if msg.reply_to_message and msg.reply_to_message.from_user and not msg.reply_to_message.from_user.is_bot:
        bump_reply_pair(
            s.sqlite_path,
            chat_id=update.effective_chat.id,
            from_uid=update.effective_user.id,
            to_uid=msg.reply_to_message.from_user.id,
        )


async def show_activity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_chat:
        return
    if not _can_activity(update, context):
        await update.message.reply_text("Недостаточно прав")
        return

    s = _settings(context)
    chat_id = update.effective_chat.id
    top_rows = get_top_activity(s.sqlite_path, chat_id=chat_id, limit=10)
    asleep_rows = get_asleep_activity(s.sqlite_path, chat_id=chat_id, limit=10)

    parts = []

    # Топ активных
    valid_top = [(uid, u, fn, cnt, la) for uid, u, fn, cnt, la in top_rows
                 if is_valid_name(fn, u) and cnt > 0]
    if valid_top:
        lines = ["🔥 Топ самых активных (по сообщениям)", "───────────────────"]
        for i, (uid, username, first_name, cnt, last_at) in enumerate(valid_top, 1):
            lines.append(f"{i}. {user_link_from_parts(first_name, username, uid)} — {cnt} сообщ. | последнее: {human_date(last_at)}")
        parts.append("\n".join(lines))

    # Топ заснувших
    valid_asleep = [(uid, u, fn, cnt, la) for uid, u, fn, cnt, la in asleep_rows
                    if is_valid_name(fn, u) and la is not None]
    if valid_asleep:
        lines = ["😴 Топ заснувших (дольше всех не пишут)", "───────────────────"]
        for i, (uid, username, first_name, cnt, last_at) in enumerate(valid_asleep, 1):
            silent = days_silent(last_at)
            lines.append(f"{i}. {user_link_from_parts(first_name, username, uid)} — {cnt} сообщ. |{f' {silent}' if silent else ''} | последнее: {human_date(last_at)}")
        parts.append("\n".join(lines))

    if not parts:
        await update.message.reply_text("Пока нет данных по активности (счётчик начался после деплоя).")
        return

    await update.message.reply_text("\n\n".join(parts), parse_mode="HTML")


async def show_today_top(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_chat:
        return
    if not _can_activity(update, context):
        await update.message.reply_text("Недостаточно прав")
        return

    s = _settings(context)
    chat_id = update.effective_chat.id
    rows = get_today_activity(s.sqlite_path, chat_id=chat_id, limit=10)
    total = count_today_messages(s.sqlite_path, chat_id=chat_id)

    if not rows:
        await update.message.reply_text("Сегодня ещё никто не написал сообщений.")
        return

    # Репозиторий возвращает (uid, cnt, last_at, username, first_name)
    lines = [f"📊 Топ за сегодня ({total} сообщ. всего)", "───────────────────"]
    for i, (uid, cnt, last_at, username, first_name) in enumerate(rows, 1):
        lines.append(f"{i}. {user_link_from_parts(first_name, username, uid)} — {cnt} сообщ. | последнее: {human_date(last_at)}")

    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


async def show_top_week(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_chat:
        return
    if not _can_activity(update, context):
        await update.message.reply_text("Недостаточно прав")
        return

    s = _settings(context)
    chat_id = update.effective_chat.id
    rows = get_top_week_activity(s.sqlite_path, chat_id=chat_id, limit=10)

    if not rows:
        await update.message.reply_text("Пока нет данных за последние 7 дней.")
        return

    # Репозиторий возвращает (uid, cnt, last_at, username, first_name)
    lines = ["🏆 Топ за неделю (по сообщениям)", "───────────────────"]
    for i, (uid, cnt, last_at, username, first_name) in enumerate(rows, 1):
        lines.append(f"{i}. {user_link_from_parts(first_name, username, uid)} — {cnt} сообщ. | последнее: {human_date(last_at)}")

    await update.message.reply_text("\n".join(lines), parse_mode="HTML")
