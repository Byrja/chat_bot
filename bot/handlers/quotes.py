from telegram import Update
from telegram.ext import ContextTypes

from bot.config import Settings
from bot.repositories.quotes import add_quote, latest_quote, random_quote


def _settings(context: ContextTypes.DEFAULT_TYPE) -> Settings:
    return context.application.bot_data["settings"]


async def save_quote(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_chat or not update.effective_user:
        return

    src = update.message.reply_to_message
    if not src or not src.text:
        await update.message.reply_text("Используй /quote ответом на текстовое сообщение")
        return

    author = src.from_user
    label = "unknown"
    if author:
        label = f"@{author.username}" if author.username else (author.first_name or str(author.id))

    s = _settings(context)
    qid = add_quote(
        s.sqlite_path,
        chat_id=update.effective_chat.id,
        source_message_id=src.message_id,
        author_tg_user_id=author.id if author else None,
        author_label=label,
        quote_text=src.text,
        added_by_tg_user_id=update.effective_user.id,
    )
    await update.message.reply_text(f"Цитата сохранена ✅ #{qid}")


async def random_quote_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message or (update.callback_query.message if update.callback_query else None)
    if not msg or not update.effective_chat:
        return
    s = _settings(context)
    row = random_quote(s.sqlite_path, update.effective_chat.id)
    if not row:
        text = "Цитат пока нет"
        if update.callback_query:
            await update.callback_query.edit_message_text(text)
        else:
            await msg.reply_text(text)
        return
    qid, author_label, quote_text, source_message_id, created_at = row
    text = f"📚 Цитата #{qid}\n{quote_text}\n\n— {author_label}"
    if update.callback_query:
        await update.callback_query.edit_message_text(text)
    else:
        await msg.reply_text(text)


async def latest_quote_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message or (update.callback_query.message if update.callback_query else None)
    if not msg or not update.effective_chat:
        return
    s = _settings(context)
    row = latest_quote(s.sqlite_path, update.effective_chat.id)
    if not row:
        text = "Цитат пока нет"
        if update.callback_query:
            await update.callback_query.edit_message_text(text)
        else:
            await msg.reply_text(text)
        return
    qid, author_label, quote_text, source_message_id, created_at = row
    text = f"🆕 Последняя цитата #{qid}\n{quote_text}\n\n— {author_label}"
    if update.callback_query:
        await update.callback_query.edit_message_text(text)
    else:
        await msg.reply_text(text)
