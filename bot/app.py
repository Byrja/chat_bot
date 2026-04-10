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
from bot.handlers.menu import menu_action, show_menu
from bot.handlers.mod_panel import mod_panel, mod_quick_action, mod_quick_ask_reason
from bot.handlers.profile_input import capture_birthdate_input
from bot.handlers.questionnaire_lookup import questionnaire_lookup
from bot.handlers.admin_sanctions import ban_user, mute_user, warn_user
from bot.handlers.admin_stats import admin_stats
from bot.handlers.errors import on_error
from bot.handlers.fun import hipish, mute_me
from bot.handlers.roles_admin import set_role_command, whois_command
from bot.handlers.start import health
from bot.handlers.top_pairs import show_top_pairs
from bot.handlers.top_week import show_top_week
from bot.handlers.birthday_reminders import send_birthday_reminders


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
    app.add_handler(CommandHandler("role", set_role_command))
    app.add_handler(CommandHandler("whois", whois_command))
    app.add_handler(CommandHandler("activity", show_activity))
    app.add_handler(CommandHandler("top_pairs", show_top_pairs))
    app.add_handler(CommandHandler("top_week", show_top_week))
    app.add_handler(CommandHandler("menu", show_menu))
    app.add_handler(CommandHandler("mod", mod_panel))
    app.add_handler(CallbackQueryHandler(menu_action, pattern=r"^menu:(home|stats|activity|pairs|pairs_all|pairs_week|week|fun|fun_hipish|mod|settings|settings_muteme15|settings_bday|settings_editform|settings_kick_confirm|settings_kick_do):[0-9]+$"))
    app.add_handler(CallbackQueryHandler(mod_quick_ask_reason, pattern=r"^modquickask:(warn|mute30|ban):[0-9]+:[0-9]+$"))
    app.add_handler(CallbackQueryHandler(mod_quick_action, pattern=r"^modquick:(warn|mute30|ban):[0-9]+:[0-9]+:(spam|abuse|offtopic|other)$"))
    app.add_handler(MessageHandler(filters.Regex(r"(?i)^\s*анкета\s+@?[a-zA-Z0-9_]{3,}\s*$"), questionnaire_lookup))
    app.add_handler(MessageHandler(filters.Regex(r"^\d{1,2}\.\d{1,2}$"), capture_birthdate_input))
    app.add_handler(CommandHandler("mute_me", mute_me))
    app.add_handler(CommandHandler("hipish", hipish))
    app.add_handler(MessageHandler(filters.ChatType.GROUPS & ~filters.COMMAND, track_message_activity))
    app.add_handler(CommandHandler("health", health))
    app.add_error_handler(on_error)

    if app.job_queue:
        app.job_queue.run_repeating(send_birthday_reminders, interval=3600, first=120, name="birthday_reminders")

    return app


def run(settings: Settings) -> None:
    app = build_app(settings)
    app.run_polling(allowed_updates=Update.ALL_TYPES)
