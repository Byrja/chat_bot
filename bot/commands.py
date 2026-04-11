from telegram import BotCommand


def command_list() -> list[BotCommand]:
    return [
        BotCommand("menu", "Открыть главное меню"),
        BotCommand("start", "Заполнить анкету"),
        BotCommand("about", "Полный список команд"),
        BotCommand("activity", "Топ ноулайферов (всё время)"),
        BotCommand("top_week", "Топ ноулайферов (7 дней)"),
        BotCommand("top_pairs", "Топ пар по reply"),
        BotCommand("karma", "Моя карма"),
        BotCommand("karma_top", "Топ кармы"),
        BotCommand("quote", "Сохранить цитату (reply)"),
        BotCommand("quotes", "Случайная цитата"),
        BotCommand("bottle", "Запустить бутылочку"),
        BotCommand("horoscope", "Гороскоп"),
        BotCommand("mute_me", "Самому себе мут"),
    ]
