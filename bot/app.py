from telegram import Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ConversationHandler, MessageHandler, filters

from bot.config import Settings
from bot.handlers.alcohol_tmp import receive_alcohol_choice
from bot.handlers.questionnaire import (
    WAIT_AGE,
    WAIT_ALCOHOL,
    WAIT_DISTRICT,
    WAIT_HOBBY,
    WAIT_NAME,
    WAIT_AVAILABILITY,
    WAIT_PHOTO,
    WAIT_PREVIEW,
    WAIT_REJECT_REASON,
    moderation_action,
    preview_action,
    questionnaire_cancel,
    questionnaire_start,
    receive_age,
    receive_availability,
    receive_district,
    receive_hobby,
    receive_name,
    receive_photo,
    receive_reject_reason,
)
from bot.handlers.activity import show_activity, track_message_activity
from bot.handlers.admin_sanctions import ban_user, mute_user, warn_user
from bot.handlers.admin_stats import admin_stats
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
            WAIT_ALCOHOL: [CallbackQueryHandler(receive_alcohol_choice, pattern=r"^alc:(yes|no|social)$")],
            WAIT_AVAILABILITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_availability)],
            WAIT_PHOTO: [MessageHandler(filters.PHOTO | (filters.TEXT & ~filters.COMMAND), receive_photo)],
            WAIT_PREVIEW: [CallbackQueryHandler(preview_action, pattern=r"^app:(edit|submit)$")],
        },
        fallbacks=[CommandHandler("cancel", questionnaire_cancel)],
        allow_reentry=True,
    )

    app.add_handler(flow)

    mod_flow = ConversationHandler(
        entry_points=[CallbackQueryHandler(moderation_action, pattern=r"^mod:(approve|reject):[0-9]+$")],
        states={
            WAIT_REJECT_REASON: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_reject_reason)],
        },
        fallbacks=[CommandHandler("cancel", questionnaire_cancel)],
        allow_reentry=True,
    )
    app.add_handler(mod_flow)
    app.add_handler(CommandHandler("warn", warn_user))
    app.add_handler(CommandHandler("mute", mute_user))
    app.add_handler(CommandHandler("ban", ban_user))
    app.add_handler(CommandHandler("admin_stats", admin_stats))
    app.add_handler(CommandHandler("activity", show_activity))
    app.add_handler(MessageHandler(filters.ChatType.GROUPS & ~filters.COMMAND, track_message_activity))
    app.add_handler(CommandHandler("health", health))
    return app


def run(settings: Settings) -> None:
    app = build_app(settings)
    app.run_polling(allowed_updates=Update.ALL_TYPES)
