from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from bot.config import Settings
from bot.repositories.relations import accept_friend_request, add_goat, create_friend_request, relation_stats


def _settings(context: ContextTypes.DEFAULT_TYPE) -> Settings:
    return context.application.bot_data.get("settings") or context.application.settings


def _label(user) -> str:
    if not user:
        return "unknown"
    return user.first_name or (f"@{user.username}" if user.username else str(user.id))


async def relation_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_user:
        return
    src = update.message.reply_to_message
    if not src or not src.from_user:
        await update.message.reply_text("Используй /relation ответом на сообщение участника")
        return
    target = src.from_user
    if target.is_bot:
        await update.message.reply_text("С ботами отношения не строим")
        return
    if target.id == update.effective_user.id:
        await update.message.reply_text("С собой не получится 😅")
        return

    issuer = update.effective_user.id
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🤝 Предложить дружбу", callback_data=f"rel:friend_offer:{target.id}:{issuer}")],
        [InlineKeyboardButton("😈 Записать в козлы", callback_data=f"rel:goat:{target.id}:{issuer}")],
    ])
    await update.message.reply_text(f"Отношения с {_label(target)}:", reply_markup=kb)


async def relation_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    if not q or not update.effective_user or not update.effective_chat:
        return
    await q.answer()

    parts = (q.data or "").split(":")
    if len(parts) != 4:
        return
    action, target_s, issuer_s = parts[1], parts[2], parts[3]
    target_id = int(target_s)
    issuer_id = int(issuer_s)

    if update.effective_user.id != issuer_id:
        await q.answer("Эта кнопка не для тебя", show_alert=True)
        return

    s = _settings(context)
    if action == "goat":
        ok = add_goat(s.sqlite_path, update.effective_chat.id, issuer_id, target_id)
        if ok:
            await q.edit_message_text("😈 Записано в козлы")
        else:
            await q.edit_message_text("😈 Уже в козлах")
        return

    if action == "friend_offer":
        fid = create_friend_request(s.sqlite_path, update.effective_chat.id, issuer_id, target_id)
        if fid is None:
            await q.edit_message_text("Не удалось создать запрос дружбы")
            return
        if fid == 0:
            await q.edit_message_text("Вы уже друзья 🤝")
            return

        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Подтвердить дружбу", callback_data=f"rel:friend_accept:{fid}:{target_id}")]
        ])
        await q.edit_message_text(
            "🤝 Запрос дружбы отправлен. Ждём подтверждение второго участника.",
            reply_markup=kb,
        )
        return


async def relation_accept(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    if not q or not update.effective_user:
        return
    await q.answer()

    parts = (q.data or "").split(":")
    if len(parts) != 4:
        return
    fid = int(parts[2])
    target_id = int(parts[3])

    if update.effective_user.id != target_id:
        await q.answer("Подтвердить может только тот, кому отправили дружбу", show_alert=True)
        return

    s = _settings(context)
    ok = accept_friend_request(s.sqlite_path, fid, update.effective_user.id)
    if not ok:
        await q.edit_message_text("Запрос недоступен или уже обработан")
        return
    await q.edit_message_text("🤝 Дружба подтверждена")


async def relation_stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_user or not update.effective_chat:
        return
    s = _settings(context)
    st = relation_stats(s.sqlite_path, update.effective_chat.id, update.effective_user.id)
    await update.message.reply_text(
        "👥 Твои отношения\n"
        "───────────────────\n"
        f"Друзья: {st['friends']}\n"
        f"В козлы записал: {st['goats_out']}\n"
        f"Тебя записали в козлы: {st['goats_in']}"
    )
