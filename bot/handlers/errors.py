import logging

from telegram import Update
from telegram.ext import ContextTypes


logger = logging.getLogger(__name__)


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Unhandled exception in update handler", exc_info=context.error)

    # Best-effort user feedback for command/callback contexts.
    try:
        if isinstance(update, Update):
            if update.effective_message:
                await update.effective_message.reply_text("Произошла ошибка. Мы уже чиним 🙏")
            elif update.callback_query:
                await update.callback_query.answer("Ошибка обработки", show_alert=False)
    except Exception:
        pass
