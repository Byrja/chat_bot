#!/usr/bin/env python3
"""
Скрипт для локального запуска WebApp

Использование:
    python start_local.py

Этот скрипт:
1. Проверяет доступность базы данных
2. Запускает Flask приложение
3. Показывает информацию для настройки бота
"""

import os
import sys
import sqlite3
from datetime import datetime

# Загружаем .env файл из корня проекта
try:
    from dotenv import load_dotenv

    dotenv_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
    load_dotenv(dotenv_path)
except ImportError:
    print("python-dotenv не установлен, используем системные переменные окружения")


def check_database():
    """Проверяет доступность базы данных"""
    db_path = os.getenv(
        "DB_PATH", "chat.db"
    )
    try:
        with sqlite3.connect(db_path) as conn:
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
            table_count = c.fetchone()[0]
            print(f"✅ База данных доступна: {db_path}")
            print(f"📊 Количество таблиц: {table_count}")
            return True
    except Exception as e:
        print(f"❌ Ошибка базы данных: {e}")
        print(f"🔍 Проверьте переменную окружения DB_PATH или создайте файл {db_path}")
        return False


def print_setup_info():
    """Выводит информацию по настройке бота"""
    print("\n" + "=" * 60)
    print("🤖 НАСТРОЙКА TELEGRAM БОТА")
    print("=" * 60)
    print("1. Откройте @BotFather в Telegram")
    print("2. Выберите вашего бота: /mybots")
    print("3. Bot Settings -> Menu Button -> Configure Menu Button")
    print("4. Укажите URL: http://localhost:5001")
    print("5. Название кнопки: WebApp Мамули")
    print("")
    print("📋 Переменные окружения в .env:")
    print("TOKEN=ваш_токен_бота")
    print("CHAT_ID=id_вашего_чата")
    print("DB_PATH=chat.db")
    print("STATIC_WEB_PATH=static")
    print("OPENAI_API_KEY=ваш_openai_ключ")
    print("")
    print("Или добавьте команду в бота:")
    print("")
    print("@bot.message_handler(commands=['webapp'])")
    print("def send_webapp(message):")
    print("    markup = types.InlineKeyboardMarkup()")
    print("    webapp_button = types.InlineKeyboardButton(")
    print("        text='Открыть WebApp',")
    print("        web_app=types.WebAppInfo(url='http://localhost:5001')")
    print("    markup.add(webapp_button)")
    print(
        "    bot.send_message(message.chat.id, 'Нажмите кнопку:', reply_markup=markup)"
    )
    print("")
    print("=" * 60)
    print("🚀 ТЕСТИРОВАНИЕ")
    print("=" * 60)
    print("1. Запустите вашего бота")
    print("2. Откройте Telegram Desktop или мобильное приложение")
    print("3. Найдите вашего бота")
    print("4. Нажмите кнопку WebApp или отправьте /webapp")
    print("5. Проверьте, что на главной странице отображается ✅")
    print("")
    print("❗ ВАЖНО: WebApp НЕ РАБОТАЕТ в обычном браузере!")
    print("         Только через официальные приложения Telegram!")
    print("=" * 60)


def main():
    print("🚀 Запуск WebApp Мамули")
    print(f"⏰ Время запуска: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("")

    # Проверяем TOKEN
    token = os.getenv("TOKEN")
    if token and token != "YOUR_BOT_TOKEN_HERE":
        print("✅ TOKEN найден")
    else:
        print("⚠️  TOKEN не найден в переменных окружения")
        print("   Создайте файл .env с переменной TOKEN")

    # Проверяем базу данных
    if not check_database():
        print("❌ Не удалось подключиться к базе данных")
        sys.exit(1)

    # Проверяем Flask
    try:
        from flask import Flask

        print("✅ Flask доступен")
    except ImportError:
        print("❌ Flask не установлен. Установите: pip install flask")
        sys.exit(1)

    # Проверяем дополнительные библиотеки
    try:
        import emoji

        print("✅ emoji библиотека доступна")
    except ImportError:
        print("⚠️  emoji библиотека не установлена (для статистики эмодзи)")
        print("   Установите: pip install emoji")

    print("")
    print("🌐 Запуск веб-сервера...")
    print("📍 URL: http://localhost:5001")
    print("🔍 Для отладки: http://127.0.0.1:5001")
    print("")

    # Показываем информацию по настройке
    print_setup_info()

    print("\n🔄 Запуск Flask приложения...")
    print("Для остановки нажмите Ctrl+C")
    print("-" * 60)

    # Запускаем приложение
    try:
        from app import app

        app.run(
            host="127.0.0.1",
            port=5001,
            debug=True,
            use_reloader=False,  # Избегаем двойного запуска
        )
    except KeyboardInterrupt:
        print("\n👋 Остановка сервера...")
    except Exception as e:
        print(f"\n❌ Ошибка запуска: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
