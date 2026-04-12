from telegram import Update
from telegram.ext import ContextTypes


async def topic_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_chat:
        return
    chat_id = update.effective_chat.id
    thread_id = update.message.message_thread_id
    if thread_id:
        await update.message.reply_text(
            f"chat_id={chat_id}\nmessage_thread_id={thread_id}"
        )
    else:
        await update.message.reply_text(
            f"chat_id={chat_id}\nmessage_thread_id=NONE (не в топике)"
        )
