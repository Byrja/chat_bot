from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from bot.config import Settings
from bot.services.rbac import has_permission


def _settings(context: ContextTypes.DEFAULT_TYPE) -> Settings:
    return context.application.bot_data["settings"]


def _menu_kb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> InlineKeyboardMarkup:
    s = _settings(context)
    uid = update.effective_user.id if update.effective_user else 0

    rows = [
        [InlineKeyboardButton("📊 Статистика", callback_data="menu:stats"), InlineKeyboardButton("👥 Актив", callback_data="menu:activity")],
        [InlineKeyboardButton("🎭 Развлечения", callback_data="menu:fun")],
    ]

    if has_permission(s, s.sqlite_path, uid, "warn"):
        rows.append([InlineKeyboardButton("🛡 Модерация", callback_data="menu:mod")])

    return InlineKeyboardMarkup(rows)


async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message or (update.callback_query.message if update.callback_query else None)
    if not msg:
        return
    text = "MD4 меню\nВыбери действие:"
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=_menu_kb(update, context))
    else:
        await msg.reply_text(text, reply_markup=_menu_kb(update, context))


async def menu_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return
    await query.answer()

    action = (query.data or "menu:").split(":", 1)[1]
    if action == "stats":
        await query.message.reply_text("Статистика: /admin_stats")
    elif action == "activity":
        await query.message.reply_text("Актив: /activity")
    elif action == "fun":
        await query.message.reply_text("Развлечения: /hipish или /mute_me 30")
    elif action == "mod":
        await query.message.reply_text("Модерация: /warn, /mute, /ban (reply на пользователя)")

    await show_menu(update, context)
