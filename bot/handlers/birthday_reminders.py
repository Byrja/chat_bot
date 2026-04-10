from telegram.ext import ContextTypes

from bot.config import Settings
from bot.repositories.birthday import (
    get_birthdays_for_offset,
    get_user_label,
    mark_notified,
    was_notified,
)


def _settings(context: ContextTypes.DEFAULT_TYPE) -> Settings:
    return context.application.bot_data.get("settings") or context.application.settings


async def send_birthday_reminders(context: ContextTypes.DEFAULT_TYPE) -> None:
    s = _settings(context)

    # Week before
    week_rows, week_date = get_birthdays_for_offset(s.sqlite_path, 7)
    for uid, d, m in week_rows:
        if was_notified(s.sqlite_path, uid, "week_before", week_date):
            continue
        label = get_user_label(s.sqlite_path, s.main_chat_id, uid)
        await context.bot.send_message(
            chat_id=s.main_chat_id,
            text=f"🎉 Через неделю день рождения у {label} ({d:02d}.{m:02d})",
        )
        mark_notified(s.sqlite_path, uid, "week_before", week_date)

    # Today
    today_rows, today_date = get_birthdays_for_offset(s.sqlite_path, 0)
    for uid, d, m in today_rows:
        if was_notified(s.sqlite_path, uid, "today", today_date):
            continue
        label = get_user_label(s.sqlite_path, s.main_chat_id, uid)
        await context.bot.send_message(
            chat_id=s.main_chat_id,
            text=f"🥳 Сегодня день рождения у {label}! Поздравляем!",
        )
        mark_notified(s.sqlite_path, uid, "today", today_date)
