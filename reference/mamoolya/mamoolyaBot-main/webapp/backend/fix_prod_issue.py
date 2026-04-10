#!/usr/bin/env python3
"""
Скрипт для быстрого исправления проблемы в продакшене
Временно включает режим разработки с дополнительными проверками
"""

import os

# Создаем .env файл в корне проекта, если его нет
env_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
env_dir = os.path.dirname(env_path)

# Создаем директорию если нужно
os.makedirs(env_dir, exist_ok=True)

# Читаем существующий .env файл
existing_env = {}
if os.path.exists(env_path):
    with open(env_path, "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                existing_env[key] = value

# Обновляем настройки
env_settings = {
    "DEVELOPMENT_MODE": "true",  # Временно включаем режим разработки
    "FLASK_ENV": "production",
    "FLASK_DEBUG": "false",
}

# Если токен не установлен, добавляем заглушку
if "TOKEN" not in existing_env:
    print("⚠️  Токен бота не найден в .env файле!")
    print("   Пожалуйста, добавьте TOKEN=ваш_токен_бота в .env файл")
    env_settings["TOKEN"] = "YOUR_BOT_TOKEN_HERE"

# Объединяем настройки
final_env = {**existing_env, **env_settings}

# Записываем обновленный .env файл
with open(env_path, "w") as f:
    f.write("# Конфигурация для WebApp\n")
    f.write("# Создано автоматически fix_prod_issue.py\n\n")

    for key, value in final_env.items():
        f.write(f"{key}={value}\n")

print(f"✅ .env файл обновлен: {env_path}")
print(f"✅ DEVELOPMENT_MODE установлен в: {final_env['DEVELOPMENT_MODE']}")
print(
    f"✅ TOKEN установлен: {'да' if final_env.get('TOKEN') != 'YOUR_BOT_TOKEN_HERE' else 'нет'}"
)

print("\n=== ВАЖНО ===")
print("1. Это временное решение для диагностики")
print("2. Не забудьте установить правильный TOKEN в .env файле")
print("3. После исправления установите DEVELOPMENT_MODE=false")
print("4. Перезапустите сервер после изменения .env файла")

print("\n=== СЛЕДУЮЩИЕ ШАГИ ===")
print("1. Откройте .env файл и убедитесь, что TOKEN установлен правильно")
print("2. Перезапустите backend сервер")
print("3. Проверьте работу приложения")
print("4. Если все работает, установите DEVELOPMENT_MODE=false")
