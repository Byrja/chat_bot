from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from bot.config import Settings
from bot.repositories.quotes import add_quote, delete_quote, get_quote_by_id, latest_quote, list_quotes, random_quote
from bot.services.rbac import has_permission


def _settings(context: ContextTypes.DEFAULT_TYPE) -> Settings:
    return context.application.bot_data.get("settings") or context.application.settings


async def _is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Check if user is an admin (env list, DB role, or Telegram chat admin)."""
    user = update.effective_user
    if not user:
        return False
    s = _settings(context)
    if user.id in s.admin_user_ids:
        return True
    if has_permission(s, s.sqlite_path, user.id, "warn"):
        return True
    chat_id = update.effective_chat.id if update.effective_chat else None
    if not chat_id:
        return False
    cache_key = f"admin_list:{chat_id}"
    admins = context.application.bot_data.get(cache_key)
    if admins is None:
        try:
            admins = await context.bot.get_chat_administrators(chat_id)
            context.application.bot_data[cache_key] = admins
        except Exception:
            return False
    return any(a.user.id == user.id for a in admins)


def _chat_link(chat_id: int, message_id: int | None) -> str | None:
    if not message_id:
        return None
    cid = str(chat_id)
    if cid.startswith("-100"):
        cid = cid[4:]
    return f"https://t.me/c/{cid}/{message_id}"


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
    link = _chat_link(update.effective_chat.id, source_message_id)
    text = f"📚 Цитата #{qid}\n{quote_text}\n\n— {author_label}"
    if link:
        text += f"\n\n🔗 {link}"
    if update.callback_query:
        await update.callback_query.edit_message_text(text, disable_web_page_preview=True)
    else:
        await msg.reply_text(text, disable_web_page_preview=True)


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
    link = _chat_link(update.effective_chat.id, source_message_id)
    text = f"🆕 Последняя цитата #{qid}\n{quote_text}\n\n— {author_label}"
    if link:
        text += f"\n\n🔗 {link}"
    if update.callback_query:
        await update.callback_query.edit_message_text(text, disable_web_page_preview=True)
    else:
        await msg.reply_text(text, disable_web_page_preview=True)


def _build_list_markup(rows, page: int = 0, per_page: int = 5):
    start = page * per_page
    end = start + per_page
    page_rows = rows[start:end]
    buttons = []
    for qid, author_label, quote_text, source_message_id, created_at in page_rows:
        snippet = quote_text[:40] + "…" if len(quote_text) > 40 else quote_text
        buttons.append([InlineKeyboardButton(f"#{qid} — {snippet}", callback_data=f"quote_view_{qid}_{page}")])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"quote_page_{page - 1}"))
    if end < len(rows):
        nav.append(InlineKeyboardButton("Вперёд ➡️", callback_data=f"quote_page_{page + 1}"))
    if nav:
        buttons.append(nav)

    return InlineKeyboardMarkup(buttons)


async def quotes_list_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        if not update.message or not update.effective_chat:
            return
        if not await _is_admin(update, context):
            await update.message.reply_text("Недостаточно прав")
            return

        s = _settings(context)
        rows = list_quotes(s.sqlite_path, update.effective_chat.id, limit=20)
        if not rows:
            await update.message.reply_text("Цитат пока нет")
            return

        markup = _build_list_markup(rows, page=0)
        await update.message.reply_text("📋 Список цитат (нажми для просмотра):", reply_markup=markup)
    except Exception as e:
        if update.message:
            await update.message.reply_text(f"Ошибка списка цитат: {e}")


async def quotes_page_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        query = update.callback_query
        if not query or not query.message or not query.message.chat:
            return
        await query.answer()

        data = query.data or ""
        if not data.startswith("quote_page_"):
            return

        page = int(data.split("_")[-1])
        s = _settings(context)
        rows = list_quotes(s.sqlite_path, query.message.chat.id, limit=20)
        if not rows:
            await query.edit_message_text("Цитат пока нет")
            return

        markup = _build_list_markup(rows, page=page)
        await query.edit_message_text("📋 Список цитат (нажми для просмотра):", reply_markup=markup)
    except Exception as e:
        if update.callback_query and update.callback_query.message:
            await update.callback_query.message.reply_text(f"Ошибка пагинации: {e}")


async def quotes_view_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        query = update.callback_query
        if not query or not update.effective_user:
            await query.answer() if query else None
            return
        await query.answer()

        if not await _is_admin(update, context):
            await query.answer("Недостаточно прав", show_alert=True)
            return

        data = query.data or ""
        if not data.startswith("quote_view_"):
            return

        parts = data.split("_")
        if len(parts) < 3:
            return
        qid = int(parts[2])
        page = int(parts[3]) if len(parts) > 3 else 0

        s = _settings(context)
        chat = query.message.chat if query.message else None
        if not chat:
            return

        row = get_quote_by_id(s.sqlite_path, qid, chat.id)
        if not row:
            await query.edit_message_text(f"Цитата #{qid} не найдена")
            return

        _, author_label, quote_text, source_message_id, created_at = row
        link = _chat_link(chat.id, source_message_id)
        text = f"📚 Цитата #{qid}\n{quote_text}\n\n— {author_label}"
        if link:
            text += f"\n\n🔗 {link}"

        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("🗑 Удалить", callback_data=f"quote_del_{qid}")],
            [InlineKeyboardButton("⬅️ Назад к списку", callback_data=f"quote_page_{page}")],
        ])
        await query.edit_message_text(text, reply_markup=markup, disable_web_page_preview=True)
    except Exception as e:
        if update.callback_query and update.callback_query.message:
            await update.callback_query.message.reply_text(f"Ошибка просмотра: {e}")


async def quotes_delete_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        query = update.callback_query
        if not query or not update.effective_user:
            await query.answer() if query else None
            return
        await query.answer()

        if not await _is_admin(update, context):
            await query.answer("Недостаточно прав", show_alert=True)
            return

        data = query.data or ""
        if not data.startswith("quote_del_"):
            return

        try:
            qid = int(data.split("_")[-1])
        except (IndexError, ValueError):
            await query.edit_message_text("Ошибка: некорректный ID цитаты")
            return

        s = _settings(context)
        chat = query.message.chat if query.message else None
        if not chat:
            return

        ok = delete_quote(s.sqlite_path, qid, chat.id)
        if ok:
            await query.edit_message_text(f"Цитата #{qid} удалена 🗑")
        else:
            await query.edit_message_text(f"Цитата #{qid} не найдена или уже удалена")
    except Exception as e:
        if update.callback_query and update.callback_query.message:
            await update.callback_query.message.reply_text(f"Ошибка удаления: {e}")
