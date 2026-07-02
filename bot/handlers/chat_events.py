from telegram import Update
from telegram.ext import ContextTypes

from bot.services.rbac import invalidate_chat_admins


async def on_my_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Бот promoted/demoted/restricted в чате — сбрасываем кэш админов чата.

    Без этого после потери admin-прав get_chat_administrators() начнёт
    возвращать ошибки, а кэш продолжит отвечать True (до 5 мин).
    """
    chat = update.effective_chat
    if chat:
        invalidate_chat_admins(context, chat.id)
