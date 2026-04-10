#!/usr/bin/env python3
"""
Скрипт для запуска Backend API

Использование:
    python start.py

Этот скрипт:
1. Проверяет наличие TOKEN в переменных окружения
2. Запускает Flask API сервер
3. Показывает информацию о настройке WebApp
"""

import os
import sys

# Загружаем .env файл из корня проекта
try:
    from dotenv import load_dotenv

    dotenv_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
    load_dotenv(dotenv_path)
except ImportError:
    print("python-dotenv не установлен, используем системные переменные окружения")

from webapp.backend.app import app


def check_bot_token():
    """Проверяет наличие TOKEN"""
    bot_token = os.getenv("TOKEN")

    if not bot_token or bot_token == "YOUR_BOT_TOKEN_HERE":
        print("❌ Не найден TOKEN в переменных окружения")
        print("\n📋 Как настроить:")
        print("1. Получите токен бота от @BotFather")
        print("2. Экспортируйте токен в переменную окружения:")
        print("   export TOKEN=your_bot_token_here")
        print("3. Или создайте файл .env с содержимым:")
        print("   TOKEN=your_bot_token_here")
        print("\n⚠️  Без токена валидация Telegram WebApp не будет работать!")

        choice = input("\nПродолжить без токена? (y/N): ").strip().lower()
        if choice != "y":
            sys.exit(1)
    else:
        print("✅ TOKEN найден")


def print_setup_info():
    """Показывает информацию о настройке WebApp"""
    print("\n🚀 Backend API запущен на http://localhost:5001")
    print("\n📱 Настройка Telegram WebApp:")
    print("1. Откройте @BotFather в Telegram")
    print("2. Выберите вашего бота")
    print("3. Нажмите 'Bot Settings' → 'Menu Button'")
    print("4. Установите URL: http://localhost:5173")
    print("5. Название кнопки: 'Открыть WebApp'")
    print("\n🔧 Для продакшена:")
    print("- Замените localhost на ваш домен")
    print("- Используйте HTTPS для WebApp URL")
    print("- Настройте переменные окружения на сервере")


def main():
    """Основная функция запуска"""
    print("🤖 Запуск Backend API для WebApp Мамули")
    print("=" * 50)

    check_bot_token()

    try:
        print_setup_info()
        print("\n🔥 Сервер запускается...")
        host = os.environ.get("HOST", "0.0.0.0")
        port = int(os.environ.get("PORT", 5001))
        debug = os.environ.get("DEVELOPMENT_MODE", "false").lower() == "true"
        app.run(host=host, port=port, debug=debug)
    except KeyboardInterrupt:
        print("\n\n👋 Сервер остановлен пользователем")
    except Exception as e:
        print(f"\n❌ Ошибка запуска сервера: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
