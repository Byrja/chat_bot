from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.ext import ContextTypes, ConversationHandler

from bot.config import Settings
from bot.repositories.applications import (
    get_answers_map,
    get_or_create_draft_application,
    save_answer,
    upsert_user,
)
from bot.services.validation import validate_age

WAIT_NAME, WAIT_DISTRICT, WAIT_AGE, WAIT_HOBBY, WAIT_ALCOHOL, WAIT_AVAILABILITY, WAIT_PHOTO = range(7)


def _settings(context: ContextTypes.DEFAULT_TYPE) -> Settings:
    return context.application.bot_data["settings"]


async def questionnaire_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.effective_user:
        return ConversationHandler.END

    s = _settings(context)
    user = update.effective_user
    upsert_user(s.sqlite_path, user.id, user.username, user.first_name)
    app_id = get_or_create_draft_application(s.sqlite_path, user.id)
    context.user_data["application_id"] = app_id

    await update.message.reply_text("Анкета MD4\nВопрос 1/8: Как тебя зовут?")
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
    return ConversationHandler.END


async def questionnaire_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message:
        await update.message.reply_text("Ок, анкету остановили. Вернуться можно командой /start")
    return ConversationHandler.END
