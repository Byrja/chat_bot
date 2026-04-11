from telegram import Update
from telegram.ext import ContextTypes


async def about(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message or (update.callback_query.message if update.callback_query else None)
    if not msg:
        return

    text = (
        "🤖 МДЧ — справка по командам\n"
        "───────────────────\n"
        "Базовое:\n"
        "/menu — главное меню\n"
        "/start — анкета\n"
        "/about — эта справка\n\n"
        "Статистика:\n"
        "/activity — топ ноулайферов (всё время)\n"
        "/top_week — топ ноулайферов (7 дней)\n"
        "/top_pairs — топ пар по reply\n\n"
        "Карма:\n"
        "/plus (reply) — +1 кармы\n"
        "/minus (reply) — -1 кармы\n"
        "/karma — моя карма\n"
        "/karma_top — топ кармы\n\n"
        "Социалка:\n"
        "/friend_foe_stats — friend/foe статистика\n"
        "/friend_foe_top — friend/foe топ\n"
        "/bottle — бутылочка\n"
        "+ / - (reply) — быстрые карма-реакции\n\n"
        "Цитаты:\n"
        "/quote (reply) — сохранить цитату\n"
        "/quotes — случайная цитата\n"
        "/randomquote — случайная цитата (алиас)\n"
        "/latest_quote — последняя цитата\n\n"
        "Развлечения / утилиты:\n"
        "/horoscope — гороскоп\n"
        "/hipish — призвать админов\n"
        "/mute_me [мин] — самомут\n"
        "/days_without_drama — дней без драмы\n"
        "/drama — сброс драмы (админ)\n\n"
        "Модерация (админ):\n"
        "/mod (reply) — кнопочная мод-панель\n"
        "/warn (reply)\n"
        "/mute <минуты> (reply)\n"
        "/ban (reply)\n"
        "/admin_stats\n"
        "/role <1|2|3|4> (reply)\n"
        "/whois (reply)\n"
        "/drama — сброс счётчика драмы\n"
    )

    if update.callback_query:
        await update.callback_query.edit_message_text(text)
    else:
        await msg.reply_text(text)
