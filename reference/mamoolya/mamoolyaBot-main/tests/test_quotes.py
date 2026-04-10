#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Тест для проверки функциональности цитат
"""

import sys
import os
import unittest
from unittest.mock import AsyncMock, Mock, patch
import sqlite3

# Добавляем путь к модулю бота
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from mamoolyaBot.bot import save_quote, get_random_quote


class TestQuotes(unittest.IsolatedAsyncioTestCase):
    """Тесты для функциональности цитат"""

    def setUp(self):
        # Создаем временную базу данных для тестов
        self.test_db = sqlite3.connect(":memory:")
        cursor = self.test_db.cursor()
        cursor.execute("""
            CREATE TABLE quotes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT,
                message TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                message_id INTEGER,
                chat_id INTEGER
            )
        """)
        self.test_db.commit()

    def tearDown(self):
        self.test_db.close()

    async def test_save_quote(self):
        """Тест сохранения цитаты"""
        # Создаем моки для update и context
        update = AsyncMock()
        update.message.reply_text = AsyncMock()
        update.message.reply_to_message = AsyncMock()
        update.message.reply_to_message.text = "Это тестовая цитата"
        update.message.reply_to_message.from_user.first_name = "ТестовыйПользователь"
        update.message.reply_to_message.message_id = 123
        update.effective_chat.id = -1001234567890

        context = Mock()

        # Заменяем глобальную переменную conn на тестовую базу данных
        with patch("mamoolyaBot.bot.conn", self.test_db):
            with patch("mamoolyaBot.bot.cursor", self.test_db.cursor()):
                # Вызываем функцию save_quote
                await save_quote(update, context)

        # Проверяем, что была вызвана функция reply_text
        update.message.reply_text.assert_called_once()

        # Проверяем, что цитата была сохранена в базе данных
        cursor = self.test_db.cursor()
        cursor.execute("SELECT COUNT(*) FROM quotes")
        count = cursor.fetchone()[0]
        self.assertEqual(count, 1)

        # Проверяем содержимое сохраненной цитаты
        cursor.execute("SELECT username, message, message_id, chat_id FROM quotes")
        row = cursor.fetchone()
        self.assertEqual(row[0], "ТестовыйПользователь")
        self.assertEqual(row[1], "Это тестовая цитата")
        self.assertEqual(row[2], 123)
        self.assertEqual(row[3], -1001234567890)

    async def test_save_quote_no_reply(self):
        """Тест сохранения цитаты без ответа на сообщение"""
        # Создаем моки для update и context
        update = AsyncMock()
        update.message.reply_text = AsyncMock()
        update.message.reply_to_message = None

        context = Mock()

        # Вызываем функцию save_quote
        await save_quote(update, context)

        # Проверяем, что была показана инструкция
        update.message.reply_text.assert_called_once_with(
            "Команда /quote должна быть ответом на сообщение, которое вы хотите сохранить как цитату."
        )

    async def test_get_random_quote_no_quotes(self):
        """Тест получения случайной цитаты при отсутствии цитат"""
        # Создаем моки для update и context
        update = AsyncMock()
        update.message.reply_text = AsyncMock()

        context = Mock()

        # Заменяем глобальную переменную conn на тестовую базу данных
        with patch("mamoolyaBot.bot.conn", self.test_db):
            with patch("mamoolyaBot.bot.cursor", self.test_db.cursor()):
                # Вызываем функцию get_random_quote
                await get_random_quote(update, context)

        # Проверяем, что была показана инструкция
        update.message.reply_text.assert_called_once_with(
            "Пока нет сохраненных цитат. Используйте /quote в ответ на сообщение, чтобы сохранить цитату."
        )

    async def test_get_random_quote_with_quotes(self):
        """Тест получения случайной цитаты при наличии цитат"""
        # Создаем моки для update и context
        update = AsyncMock()
        update.message.reply_text = AsyncMock()
        update.effective_chat.id = -1001234567890

        context = Mock()

        # Добавляем тестовую цитату в базу данных
        cursor = self.test_db.cursor()
        cursor.execute(
            "INSERT INTO quotes (username, message, message_id, chat_id) VALUES (?, ?, ?, ?)",
            ("ТестовыйПользователь", "Это тестовая цитата", 123, -1001234567890),
        )
        self.test_db.commit()

        # Заменяем глобальную переменную conn на тестовую базу данных
        with patch("mamoolyaBot.bot.conn", self.test_db):
            with patch("mamoolyaBot.bot.cursor", self.test_db.cursor()):
                # Вызываем функцию get_random_quote
                await get_random_quote(update, context)

        # Проверяем, что была показана цитата
        update.message.reply_text.assert_called_once()
        args, kwargs = update.message.reply_text.call_args
        self.assertIn("ТестовыйПользователь", args[0])
        self.assertIn("Это тестовая цитата", args[0])
        self.assertIn("Оригинал сообщения", args[0])


if __name__ == "__main__":
    unittest.main()
