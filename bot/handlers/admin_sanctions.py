from telegram import ChatPermissions, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from bot.config import Settings
from bot.repositories.sanctions import add_sanction, count_warns, remove_last_warn
from bot.services.rbac import has_permission
from bot.services.timeparse import parse_mute_duration


def _settings(context: ContextTypes.DEFAULT_TYPE) -> Settings:
    return context.application.bot_data.get("settings") or context.application.settings


def _can(update: Update, context: ContextTypes.DEFAULT_TYPE, command: str) -> bool:
    user = update.effective_user
    if not user:
        return False
    s = _settings(context)
    return has_permission(s, s.sqlite_path, user.id, command)


async def mute_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_chat:
        return
    if not _can(update, context, "mute"):
        await update.message.reply_text("Недостаточно прав")
        return

    if not update.message.reply_to_message or not update.message.reply_to_message.from_user:
        await update.message.reply_text("Используй /mute ответом на сообщение пользователя")
        return

    if not context.args:
        await update.message.reply_text("Формат: /mute 30 причина (минуты, можно также 30m/2h/1d)")
        return

    target = update.message.reply_to_message.from_user
    if target.is_bot:
        await update.message.reply_text("Нельзя выдать мут боту")
        return

    until_dt = parse_mute_duration(context.args[0])
    if until_dt is None:
        await update.message.reply_text("Некорректная длительность. Используй: 30 (мин), 30m, 2h, 1d")
        return
    reason = " ".join(context.args[1:]).strip() or None

    s = _settings(context)
    try:
        await context.bot.restrict_chat_member(
            chat_id=update.effective_chat.id,
            user_id=target.id,
            permissions=ChatPermissions(can_send_messages=False),
            until_date=until_dt,
        )
    except Exception as e:
        await update.message.reply_text(f"Не удалось выдать мут: {e}")
        return

    add_sanction(
        s.sqlite_path,
        target_tg_user_id=target.id,
        action="mute",
        issued_by_tg_user_id=update.effective_user.id,
        reason=reason,
        until_at=until_dt.isoformat(),
    )

    txt = f"🔇 Мут выдан пользователю {target.id} до {until_dt.strftime('%Y-%m-%d %H:%M UTC')}"
    if reason:
        txt += f"\nПричина: {reason}"
    await update.message.reply_text(txt)


async def ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_chat:
        return
    if not _can(update, context, "ban"):
        await update.message.reply_text("Недостаточно прав")
        return

    if not update.message.reply_to_message or not update.message.reply_to_message.from_user:
        await update.message.reply_text("Используй /ban ответом на сообщение пользователя")
        return

    target = update.message.reply_to_message.from_user
    if target.is_bot:
        await update.message.reply_text("Нельзя забанить бота")
        return

    reason = " ".join(context.args).strip() if context.args else None

    s = _settings(context)
    try:
        await context.bot.ban_chat_member(
            chat_id=update.effective_chat.id,
            user_id=target.id,
            revoke_messages=False,
        )
    except Exception as e:
        await update.message.reply_text(f"Не удалось выдать бан: {e}")
        return

    add_sanction(
        s.sqlite_path,
        target_tg_user_id=target.id,
        action="ban",
        issued_by_tg_user_id=update.effective_user.id,
        reason=reason,
        until_at=None,
    )

    text = f"⛔ Бан выдан пользователю {target.id}"
    if reason:
        text += f"\nПричина: {reason}"
    await update.message.reply_text(text)


async def unmute_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_chat:
        return
    if not _can(update, context, "mute"):
        await update.message.reply_text("Недостаточно прав")
        return

    if not update.message.reply_to_message or not update.message.reply_to_message.from_user:
        await update.message.reply_text("Используй /unmute ответом на сообщение пользователя")
        return

    target = update.message.reply_to_message.from_user
    if target.is_bot:
        await update.message.reply_text("Боту unmute не требуется")
        return

    try:
        await context.bot.restrict_chat_member(
            chat_id=update.effective_chat.id,
            user_id=target.id,
            permissions=ChatPermissions(
                can_send_messages=True,
                can_send_audios=True,
                can_send_documents=True,
                can_send_photos=True,
                can_send_videos=True,
                can_send_video_notes=True,
                can_send_voice_notes=True,
                can_send_polls=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True,
            ),
        )
    except Exception as e:
        await update.message.reply_text(f"Не удалось снять мут: {e}")
        return

    await update.message.reply_text(f"🔊 Мут снят с пользователя {target.id}")


async def warn_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    if not _can(update, context, "warn"):
        await update.message.reply_text("Недостаточно прав")
        return

    target = None
    if update.message.reply_to_message and update.message.reply_to_message.from_user:
        target = update.message.reply_to_message.from_user
    elif context.args:
        mention = context.args[0].strip()
        # Не можем резолвить @username без extra API call; требуем reply
        if mention.startswith("@"):
            await update.message.reply_text(
                "Для /warn используй ответ на сообщение пользователя. "
                "Или укажи @username через reply."
            )
            return

    if not target:
        await update.message.reply_text("Используй /warn ответом на сообщение пользователя")
        return

    if target.is_bot:
        await update.message.reply_text("Нельзя выдать предупреждение боту")
        return

    reason = " ".join(context.args).strip() if context.args else None
    s = _settings(context)
    add_sanction(
        s.sqlite_path,
        target_tg_user_id=target.id,
        action="warn",
        issued_by_tg_user_id=update.effective_user.id,
        reason=reason,
        until_at=None,
    )

    text = f"⚠️ Предупреждение выдано пользователю {target.id}"
    if reason:
        text += f"\nПричина: {reason}"
    await update.message.reply_text(text)

    try:
        dm = "Тебе выдано предупреждение администратором."
        if reason:
            dm += f"\nПричина: {reason}"
        await context.bot.send_message(chat_id=target.id, text=dm)
    except Exception:
        pass

    # 3 warn check
    warn_count = count_warns(s.sqlite_path, target.id)
    if warn_count >= 3:
        markup = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Да, кикнуть", callback_data=f"warnkick_yes_{target.id}"),
                InlineKeyboardButton("❌ Нет, отмена", callback_data=f"warnkick_no_{target.id}"),
            ]
        ])
        await update.message.reply_text(
            f"⚠️ У пользователя {target.id} уже {warn_count} предупреждений.\n"
            "Кикнуть за 3е предупреждение?",
            reply_markup=markup,
        )


async def unwarn_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_chat:
        return
    if not _can(update, context, "warn"):
        await update.message.reply_text("Недостаточно прав")
        return

    target = None
    if update.message.reply_to_message and update.message.reply_to_message.from_user:
        target = update.message.reply_to_message.from_user
    elif context.args:
        mention = context.args[0].strip()
        if mention.startswith("@"):
            await update.message.reply_text(
                "Для /unwarn используй ответ на сообщение пользователя."
            )
            return

    if not target:
        await update.message.reply_text("Используй /unwarn ответом на сообщение пользователя")
        return

    if target.is_bot:
        await update.message.reply_text("У ботов нет предупреждений")
        return

    s = _settings(context)
    ok = remove_last_warn(s.sqlite_path, target.id)
    if ok:
        await update.message.reply_text(f"✅ Последнее предупреждение снято с пользователя {target.id}")
    else:
        await update.message.reply_text(f"У пользователя {target.id} нет предупреждений")


async def warn_kick_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not update.effective_user:
        await query.answer() if query else None
        return
    await query.answer()

    if not _can(update, context, "warn"):
        await query.answer("Недостаточно прав", show_alert=True)
        return

    data = query.data or ""
    if not data.startswith("warnkick_"):
        return

    parts = data.split("_")
    if len(parts) != 3:
        return
    action = parts[1]
    try:
        target_id = int(parts[2])
    except ValueError:
        return

    chat = query.message.chat if query.message else None
    if not chat:
        return

    if action == "no":
        await query.edit_message_text("Кик отменён.")
        return

    if action == "yes":
        try:
            await context.bot.ban_chat_member(
                chat_id=chat.id,
                user_id=target_id,
                revoke_messages=False,
            )
            await context.bot.unban_chat_member(
                chat_id=chat.id,
                user_id=target_id,
            )
        except Exception as e:
            await query.edit_message_text(f"Не удалось кикнуть: {e}")
            return

        s = _settings(context)
        add_sanction(
            s.sqlite_path,
            target_tg_user_id=target_id,
            action="ban",
            issued_by_tg_user_id=update.effective_user.id,
            reason="3е предупреждение",
            until_at=None,
        )
        await query.edit_message_text(
            f"👢 Пользователь {target_id} кикнут по причине: 3е предупреждение"
        )


async def warn_list_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_chat:
        return
    if not _can(update, context, "warn"):
        await update.message.reply_text("Недостаточно прав")
        return

    s = _settings(context)
    from bot.repositories.sanctions import list_warned

    rows = list_warned(s.sqlite_path, update.effective_chat.id)
    if not rows:
        await update.message.reply_text("Предупреждений пока нет.")
        return

    lines = ["⚠️ Список осужденных", "───────────────────"]
    for uid, username, first_name, cnt in rows:
        label = (first_name or username or str(uid)).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        if username:
            lines.append(f"• @{username} — {cnt} пред.")
        else:
            lines.append(f'• <a href="tg://user?id={uid}">{label}</a> — {cnt} пред.')

    await update.message.reply_text("\n".join(lines), parse_mode="HTML", disable_web_page_preview=True)


async def all_members(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        if not update.message or not update.effective_chat:
            return
        if not _can(update, context, "warn"):
            await update.message.reply_text("Недостаточно прав")
            return

        s = _settings(context)
        from bot.repositories.activity import get_activity_members

        rows = get_activity_members(s.sqlite_path, update.effective_chat.id)
        if not rows:
            await update.message.reply_text("Не найдено участников для упоминания.")
            return

        mentions = []
        for uid, username, first_name in rows:
            if username:
                mentions.append(f"@{username}")
            else:
                label = (first_name or str(uid)).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                mentions.append(f'<a href="tg://user?id={uid}">{label}</a>')

        if not mentions:
            await update.message.reply_text("Не найдено участников для упоминания.")
            return

        # Telegram limit ~4096 chars; split into chunks
        chunk_size = 50
        for i in range(0, len(mentions), chunk_size):
            chunk = mentions[i:i + chunk_size]
            text = " ".join(chunk)
            await update.message.reply_text(text, parse_mode="HTML")
    except Exception as e:
        if update.message:
            await update.message.reply_text(f"Ошибка /all: {e}")
