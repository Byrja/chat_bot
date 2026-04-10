from telegram import Update
from telegram.ext import Application, CommandHandler

from bot.config import Settings
from bot.handlers.start import health, start


def build_app(settings: Settings) -> Application:
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set")

    app = Application.builder().token(settings.telegram_bot_token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("health", health))
    return app


def run(settings: Settings) -> None:
    app = build_app(settings)
    app.run_polling(allowed_updates=Update.ALL_TYPES)
