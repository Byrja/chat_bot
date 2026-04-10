from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.ext import ContextTypes, ConversationHandler

from bot.config import Settings
from bot.repositories.applications import (
    count_submitted_today,
    get_answers_map,
    get_application_for_admin,
    get_or_create_draft_application,
    save_answer,
    set_decision,
    submit_application,
    upsert_user,
)
from bot.services.validation import validate_age

WAIT_NAME, WAIT_DISTRICT, WAIT_AGE, WAIT_HOBBY, WAIT_ALCOHOL, WAIT_AVAILABILITY, WAIT_PHOTO, WAIT_PREVIEW = range(8)


def _settings(context: ContextTypes.DEFAULT_TYPE) -> Settings:
    return context.application.bot_data.get("settings") or context.application.settings


async def questionnaire_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.effective_user:
        return ConversationHandler.END

    s = _settings(context)
    user = update.effective_user
    upsert_user(s.sqlite_path, user.id, user.username, user.first_name)
    app_id = get_or_create_draft_application(s.sqlite_path, user.id)
    context.user_data["application_id"] = app_id

    await update.message.reply_text("Анкета МДЧ\nВопрос 1/8: Как тебя зовут?")
    return WAIT_NAME


async def receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message:
        return WAIT_NAME
    text = (update.message.text or "").strip()
    if len(text) < 2:
        await update.message.reply_text("Имя слишком короткое. Напиши, как к тебе обращаться.")
        return WAIT_NAME

    s = _settings(context)
    app_id = int(context.user_data["application_id"])
    save_answer(s.sqlite_path, app_id, "name", text, 1)
    await update.message.reply_text("Вопрос 2/8: Расскажи, где живешь? (район проживания) 🏠")
    return WAIT_DISTRICT


async def receive_district(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message:
        return WAIT_DISTRICT
    text = (update.message.text or "").strip()
    if len(text) < 2:
        await update.message.reply_text("Нужен район/локация, хотя бы пару слов.")
        return WAIT_DISTRICT

    s = _settings(context)
    app_id = int(context.user_data["application_id"])
    save_answer(s.sqlite_path, app_id, "district", text, 3)
    await update.message.reply_text("Вопрос 3/8: Сколько тебе лет? 🔞")
    return WAIT_AGE


async def receive_age(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message:
        return WAIT_AGE
    age = validate_age(update.message.text or "")
    if age is None:
        await update.message.reply_text("Введите возраст числом от 14 до 99.")
        return WAIT_AGE

    s = _settings(context)
    app_id = int(context.user_data["application_id"])
    save_answer(s.sqlite_path, app_id, "age", str(age), 4)
    await update.message.reply_text(
        "Вопрос 4/8: Поделись, чем занимаешься в свободное время, может у тебя есть мегакрутое хобби и у тебя найдутся приятели по интересам? 🧬"
    )
    return WAIT_HOBBY


async def receive_hobby(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message:
        return WAIT_HOBBY
    text = (update.message.text or "").strip()
    if len(text) < 5:
        await update.message.reply_text("Добавь немного деталей про интересы 🙌")
        return WAIT_HOBBY

    s = _settings(context)
    app_id = int(context.user_data["application_id"])
    save_answer(s.sqlite_path, app_id, "hobby", text, 5)

    if update.effective_user:
        handle = f"@{update.effective_user.username}" if update.effective_user.username else str(update.effective_user.id)
        save_answer(s.sqlite_path, app_id, "tg_handle", handle, 2)

    await update.message.reply_text(
        "Вопрос 5/8: Как относишься к алкоголю? 🍺",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Да", callback_data="alc:yes"),
                InlineKeyboardButton("Нет", callback_data="alc:no"),
                InlineKeyboardButton("За компанию", callback_data="alc:social"),
            ]
        ]),
    )
    return WAIT_ALCOHOL


async def receive_availability(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message:
        return WAIT_AVAILABILITY
    text = (update.message.text or "").strip()
    if len(text) < 4:
        await update.message.reply_text("Напиши чуть подробнее, чтобы админам было проще принять решение.")
        return WAIT_AVAILABILITY

    s = _settings(context)
    app_id = int(context.user_data["application_id"])
    save_answer(s.sqlite_path, app_id, "availability", text, 7)
    await update.message.reply_text("Вопрос 7/8: Прикрепи фотографию, чтобы мы знали, с кем нам предстоит дружить!")
    return WAIT_PHOTO


async def receive_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message:
        return WAIT_PHOTO
    if not update.message.photo:
        await update.message.reply_text("Нужна именно фотография (как фото-сообщение).")
        return WAIT_PHOTO

    s = _settings(context)
    app_id = int(context.user_data["application_id"])
    photo = update.message.photo[-1]
    save_answer(s.sqlite_path, app_id, "photo_file_id", photo.file_id, 8)

    answers = get_answers_map(s.sqlite_path, app_id)
    preview = (
        "🧾 Предпросмотр анкеты\n"
        "───────────────────\n"
        f"Имя: {answers.get('name', '—')}\n"
        f"TG: {answers.get('tg_handle', '—')}\n"
        f"Район: {answers.get('district', '—')}\n"
        f"Возраст: {answers.get('age', '—')}\n"
        f"Хобби: {answers.get('hobby', '—')}\n"
        f"Алкоголь: {answers.get('alcohol', '—')}\n"
        f"Свободное время: {answers.get('availability', '—')}\n"
        "Фото: прикреплено ✅"
    )
    await update.message.reply_text(
        preview,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✏️ Редактировать", callback_data="app:edit")],
            [InlineKeyboardButton("✅ Отправить", callback_data="app:submit")],
        ]),
    )
    return WAIT_PREVIEW


async def preview_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if not query:
        return ConversationHandler.END
    await query.answer()

    data = query.data or ""
    if data == "app:edit":
        await query.edit_message_text("Ок, давай обновим анкету с начала ✏️")
        if query.message:
            await query.message.reply_text("Вопрос 1/8: Как тебя зовут?")
        return WAIT_NAME

    if data == "app:submit":
        app_id = int(context.user_data.get("application_id", 0) or 0)
        if not app_id:
            await query.edit_message_text("Черновик не найден. Начни заново: /start")
            return ConversationHandler.END
        s = _settings(context)
        uid = update.effective_user.id if update.effective_user else 0
        if uid and count_submitted_today(s.sqlite_path, uid) >= 2:
            await query.edit_message_text("Лимит заявок на сегодня исчерпан (2/день). Попробуй завтра.")
            return ConversationHandler.END

        ok = submit_application(s.sqlite_path, app_id)
        if not ok:
            await query.edit_message_text("Заявка уже отправлена или недоступна.")
            return ConversationHandler.END

        packet = get_application_for_admin(s.sqlite_path, app_id)
        if packet:
            owner_id, answers = packet
            text = (
                "🆕 Новая анкета МДЧ\n"
                "───────────────────\n"
                f"Application ID: {app_id}\n"
                f"User: {owner_id} ({answers.get('tg_handle', '—')})\n"
                f"Имя: {answers.get('name', '—')}\n"
                f"Район: {answers.get('district', '—')}\n"
                f"Возраст: {answers.get('age', '—')}\n"
                f"Хобби: {answers.get('hobby', '—')}\n"
                f"Алкоголь: {answers.get('alcohol', '—')}\n"
                f"Свободное время: {answers.get('availability', '—')}"
            )
            photo_id = answers.get("photo_file_id")
            markup = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("✅ Одобрить", callback_data=f"mod:approve:{app_id}"),
                    InlineKeyboardButton("❌ Отказать", callback_data=f"mod:reject:{app_id}"),
                ]
            ])
            if photo_id:
                await context.bot.send_photo(
                    chat_id=s.admin_chat_id,
                    photo=photo_id,
                    caption=text,
                    reply_markup=markup,
                )
            else:
                await context.bot.send_message(
                    chat_id=s.admin_chat_id,
                    text=text,
                    reply_markup=markup,
                )

        await query.edit_message_text(
            "Анкета отправлена на модерацию ✅\n"
            "После рассказа о себе, я добавлю тебя к ребятам 😊 Приятного времяпрепровождения ❤️"
        )
        return ConversationHandler.END

    return ConversationHandler.END


WAIT_REJECT_REASON = 90


async def moderation_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int | None:
    query = update.callback_query
    if not query or not update.effective_user:
        return
    await query.answer()

    s = _settings(context)
    if update.effective_user.id not in s.admin_user_ids:
        await query.answer("Недостаточно прав", show_alert=True)
        return

    parts = (query.data or "").split(":")
    if len(parts) != 3:
        return
    action, app_id = parts[1], int(parts[2])

    lock_key = f"mod_lock:{app_id}"
    if context.application.bot_data.get(lock_key):
        await query.answer("Заявка уже обрабатывается…", show_alert=False)
        return
    context.application.bot_data[lock_key] = True

    try:
        if action == "approve":
            ok = set_decision(s.sqlite_path, app_id, "approved", update.effective_user.id)
            if not ok:
                await query.edit_message_text("Заявка уже обработана или недоступна.")
                return
            owner = get_application_for_admin(s.sqlite_path, app_id)
            if owner:
                owner_id, _ = owner
                from datetime import datetime, timedelta, timezone
                invite = await context.bot.create_chat_invite_link(
                    chat_id=s.main_chat_id,
                    member_limit=1,
                    expire_date=datetime.now(timezone.utc) + timedelta(hours=24),
                    creates_join_request=False,
                    name=f"mdch-{app_id}",
                )
                await context.bot.send_message(
                    chat_id=owner_id,
                    text=f"Твоя заявка одобрена ✅\nВот ссылка в чат (одноразовая):\n{invite.invite_link}",
                )
            await query.edit_message_text(f"Анкета #{app_id} одобрена ✅")
            return

        if action == "reject":
            context.user_data["reject_app_id"] = app_id
            await query.edit_message_text(
                f"Анкета #{app_id}: укажи причину отказа текстом (или отправь '-' чтобы без причины)."
            )
            return WAIT_REJECT_REASON
    finally:
        context.application.bot_data.pop(lock_key, None)


async def receive_reject_reason(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.effective_user:
        return ConversationHandler.END

    s = _settings(context)
    if update.effective_user.id not in s.admin_user_ids:
        await update.message.reply_text("Недостаточно прав")
        return ConversationHandler.END

    app_id = int(context.user_data.get("reject_app_id", 0) or 0)
    if not app_id:
        await update.message.reply_text("Не найдена заявка для отказа.")
        return ConversationHandler.END

    reason_raw = (update.message.text or "").strip()
    reason = None if reason_raw in {"", "-", "нет", "без причины"} else reason_raw[:500]

    ok = set_decision(s.sqlite_path, app_id, "rejected", update.effective_user.id, reject_reason=reason)
    if not ok:
        await update.message.reply_text("Заявка уже обработана или недоступна.")
        return ConversationHandler.END

    owner = get_application_for_admin(s.sqlite_path, app_id)
    if owner:
        owner_id, _ = owner
        msg = "К сожалению, по анкете отказ. Можно подать повторно позже."
        if reason:
            msg += f"\nПричина: {reason}"
        await context.bot.send_message(chat_id=owner_id, text=msg)

    await update.message.reply_text(f"Анкета #{app_id} отклонена ❌")
    context.user_data.pop("reject_app_id", None)
    return ConversationHandler.END


async def questionnaire_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message:
        await update.message.reply_text("Ок, анкету остановили. Вернуться можно командой /start")
    return ConversationHandler.END
