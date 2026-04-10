from telegram import Update
from telegram.ext import ContextTypes

from bot.config import Settings
from bot.repositories.applications import save_answer
from bot.handlers.questionnaire import WAIT_ALCOHOL, WAIT_AVAILABILITY


_MAP = {
    "alc:yes": "Да",
    "alc:no": "Нет",
    "alc:social": "За компанию",
}


def _settings(context: ContextTypes.DEFAULT_TYPE) -> Settings:
    return context.application.bot_data["settings"]


async def receive_alcohol_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if not query:
        return WAIT_ALCOHOL
    await query.answer()

    value = _MAP.get(query.data or "", "")
    if not value:
        await query.answer("Выбери вариант кнопкой", show_alert=False)
        return WAIT_ALCOHOL

    s = _settings(context)
    app_id = int(context.user_data["application_id"])
    save_answer(s.sqlite_path, app_id, "alcohol", value, 6)

    await query.edit_message_text("Принято ✅")
    await query.message.reply_text(
        "Вопрос 6/8: Как часто у тебя есть свободное время и сможешь ли посещать наши сходки?"
    )
    return WAIT_AVAILABILITY
