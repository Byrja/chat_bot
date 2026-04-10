from telegram import Update
from telegram.ext import Application, CommandHandler, ConversationHandler, MessageHandler, filters

from bot.config import Settings
from bot.handlers.questionnaire import (
    WAIT_AGE,
    WAIT_DISTRICT,
    WAIT_HOBBY,
    WAIT_NAME,
    questionnaire_cancel,
    questionnaire_start,
    receive_age,
    receive_district,
    receive_hobby,
    receive_name,
)
from bot.handlers.start import health


def build_app(settings: Settings) -> Application:
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set")

    app = Application.builder().token(settings.telegram_bot_token).build()
    app.bot_data["settings"] = settings

    flow = ConversationHandler(
        entry_points=[CommandHandler("start", questionnaire_start)],
        states={
            WAIT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_name)],
            WAIT_DISTRICT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_district)],
            WAIT_AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_age)],
            WAIT_HOBBY: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_hobby)],
        },
        fallbacks=[CommandHandler("cancel", questionnaire_cancel)],
        allow_reentry=True,
    )

    app.add_handler(flow)
    app.add_handler(CommandHandler("health", health))
    return app


def run(settings: Settings) -> None:
    app = build_app(settings)
    app.run_polling(allowed_updates=Update.ALL_TYPES)
