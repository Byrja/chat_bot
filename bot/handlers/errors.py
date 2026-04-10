import logging

from telegram import Update
from telegram.ext import ContextTypes


logger = logging.getLogger(__name__)


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Unhandled exception in update handler", exc_info=context.error)

    # Best-effort user feedback only for explicit command/callback flows.
    # Do NOT spam group chats on every passive message-processing error.
    try:
        if isinstance(update, Update):
            if update.callback_query:
                await update.callback_query.answer("Ошибка обработки", show_alert=False)
                return

            msg = update.effective_message
            if msg and msg.text and msg.text.startswith("/"):
                await msg.reply_text("Произошла ошибка. Мы уже чиним 🙏")
    except Exception:
        pass
