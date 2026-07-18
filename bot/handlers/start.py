from telegram import Update
from telegram.ext import ContextTypes


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    if update.effective_chat and update.effective_chat.type != "private":
        bot_username = context.bot.username or "MD4_byrbot"
        await update.message.reply_text(
            "Чтобы заполнить анкету, открой бота в личке:\n"
            f"https://t.me/{bot_username}?start=apply"
        )
        return
    await update.message.reply_text(
        "МДЧ в сети ✅\n"
        "Бот готов к запуску анкеты."
    )


async def health(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    await update.message.reply_text("ok")
