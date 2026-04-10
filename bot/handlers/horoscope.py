import random

from telegram import Update
from telegram.ext import ContextTypes

from bot.config import Settings
from bot.repositories.profile import get_birthdate
from bot.services.llm_client import complete_text, llm_enabled
from bot.services.zodiac import today_key, zodiac_sign

_FALLBACK = {
    "Овен": ["Сегодня день быстрых решений. Главное — не сжигай мосты раньше времени."],
    "Телец": ["Стабильность сегодня твой суперскилл: доведи начатое до красивого финала."],
    "Близнецы": ["Твой козырь сегодня — коммуникация. Один разговор может всё поменять."],
    "Рак": ["Береги ресурс и границы. Спокойный темп даст лучший результат."],
    "Лев": ["Покажи инициативу — тебя заметят. Но оставь место для команды."],
    "Дева": ["Детали решают. Маленькая правка сегодня даст большой эффект завтра."],
    "Весы": ["Ищи баланс между «хочу» и «надо». Верное решение уже рядом."],
    "Скорпион": ["Фокус на главном. Отсеки лишнее — и получишь сильный прорыв."],
    "Стрелец": ["Хороший день для новых идей и коротких экспериментов."],
    "Козерог": ["Дисциплина сегодня окупится. Маленькие шаги приведут к крупному результату."],
    "Водолей": ["Нестандартный подход сегодня сработает лучше шаблона."],
    "Рыбы": ["Слушай интуицию, но проверяй фактами — так выйдет лучше всего."],
}


def _settings(context: ContextTypes.DEFAULT_TYPE) -> Settings:
    return context.application.bot_data.get("settings") or context.application.settings


async def horoscope(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message or (update.callback_query.message if update.callback_query else None)
    if not msg or not update.effective_user:
        return

    s = _settings(context)
    b = get_birthdate(s.sqlite_path, update.effective_user.id)
    if not b:
        text = "Чтобы получить гороскоп, сначала укажи дату рождения в ⚙️ Настройки."
        if update.callback_query:
            await update.callback_query.edit_message_text(text)
        else:
            await msg.reply_text(text)
        return

    sign = zodiac_sign(b[0], b[1])
    if not sign:
        text = "Не удалось определить знак зодиака. Проверь дату рождения в настройках."
        if update.callback_query:
            await update.callback_query.edit_message_text(text)
        else:
            await msg.reply_text(text)
        return

    text_out = None
    if llm_enabled():
        prompt = (
            f"Сделай короткий гороскоп на сегодня для знака {sign}. "
            f"Формат: 3-4 короткие строки на русском, дружелюбно, без токсичности, без мистического бреда, "
            f"с акцентом на день {today_key()}."
        )
        text_out = complete_text(prompt, max_tokens=140, temperature=0.8)

    if not text_out:
        text_out = random.choice(_FALLBACK.get(sign, ["Сегодня держи фокус на важном и не распыляйся."]))

    final = f"🔮 Гороскоп на сегодня ({sign})\n───────────────────\n{text_out}"
    if update.callback_query:
        await update.callback_query.edit_message_text(final)
    else:
        await msg.reply_text(final)
