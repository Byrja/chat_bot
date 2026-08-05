from telegram import BotCommand


def command_list() -> list[BotCommand]:
    return [
        BotCommand("menu", "Открыть главное меню"),
        BotCommand("start", "Заполнить анкету"),
        BotCommand("edit_profile", "Редактировать анкету"),
        BotCommand("about", "Полный список команд"),
        BotCommand("activity", "Топ самых активных (всё время)"),
        BotCommand("today_top", "Топ самых активных (за сутки)"),
        BotCommand("top_week", "Топ самых активных (7 дней)"),
        BotCommand("top_pairs", "Топ пар по reply"),
        BotCommand("karma", "Моя карма"),
        BotCommand("karma_top", "Топ кармы"),
        BotCommand("quote", "Сохранить цитату (reply)"),
        BotCommand("quotes", "Случайная цитата"),
        BotCommand("quoteslist", "Список цитат (админ)"),
        BotCommand("randomquote", "Случайная цитата"),
        BotCommand("latest_quote", "Последняя цитата"),
        BotCommand("bottle", "Запустить бутылочку"),
        BotCommand("horoscope", "Гороскоп"),
        BotCommand("mute_me", "Самому себе мут"),
        BotCommand("warn", "Выдать предупреждение (reply)"),
        BotCommand("unwarn", "Снять предупреждение (reply)"),
        BotCommand("warnlist", "Список осужденных"),
        BotCommand("mute", "Замутить пользователя (reply)"),
        BotCommand("unmute", "Размутить пользователя (reply)"),
        BotCommand("ban", "Забанить пользователя (reply)"),
        BotCommand("all", "Тегнуть всех участников"),
        BotCommand("days_without_drama", "Дни без драмы"),
        BotCommand("profile", "Профиль участника"),
    ]
