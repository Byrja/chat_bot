#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Тест для проверки API endpoint'а цитат
"""

import sys
import os
import unittest
import json
from unittest.mock import patch, MagicMock
import sqlite3

# Добавляем путь к модулю app
sys.path.append(os.path.join(os.path.dirname(__file__)))

from app import app


class TestQuotesAPI(unittest.TestCase):
    """Тесты для API endpoint'а цитат"""

    def setUp(self):
        """Настройка тестового клиента и базы данных"""
        self.app = app.test_client()
        self.app.testing = True

        # Создаем временную базу данных для тестов
        self.test_db = sqlite3.connect(":memory:")
        cursor = self.test_db.cursor()

        # Создаем таблицу quotes
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

        # Добавляем тестовые данные
        cursor.execute(
            """
            INSERT INTO quotes (username, message, message_id, chat_id) 
            VALUES (?, ?, ?, ?)
        """,
            ("ТестовыйПользователь", "Это тестовая цитата", 123, -1001234567890),
        )

        self.test_db.commit()

    def tearDown(self):
        """Закрываем соединение с тестовой базой данных"""
        self.test_db.close()

    @patch("app.sqlite3.connect")
    def test_get_quotes_success(self, mock_connect):
        """Тест успешного получения цитат"""
        # Настраиваем mock для подключения к базе данных
        mock_connect.return_value.__enter__.return_value.cursor.return_value.fetchall.return_value = [
            (
                1,
                "ТестовыйПользователь",
                "Это тестовая цитата",
                "2025-09-10 12:00:00",
                123,
                -1001234567890,
            )
        ]

        # Отправляем GET запрос к endpoint'у
        response = self.app.get("/api/quotes")

        # Проверяем статус ответа
        self.assertEqual(response.status_code, 200)

        # Проверяем содержимое ответа
        data = json.loads(response.data)
        self.assertIn("quotes", data)
        self.assertEqual(len(data["quotes"]), 1)

        quote = data["quotes"][0]
        self.assertEqual(quote["username"], "ТестовыйПользователь")
        self.assertEqual(quote["message"], "Это тестовая цитата")
        self.assertIn("message_link", quote)

    @patch("app.sqlite3.connect")
    def test_get_quotes_empty(self, mock_connect):
        """Тест получения цитат при отсутствии данных"""
        # Настраиваем mock для подключения к базе данных
        mock_connect.return_value.__enter__.return_value.cursor.return_value.fetchall.return_value = (
            []
        )

        # Отправляем GET запрос к endpoint'у
        response = self.app.get("/api/quotes")

        # Проверяем статус ответа
        self.assertEqual(response.status_code, 200)

        # Проверяем содержимое ответа
        data = json.loads(response.data)
        self.assertIn("quotes", data)
        self.assertEqual(len(data["quotes"]), 0)

    @patch("app.sqlite3.connect")
    def test_get_quotes_error(self, mock_connect):
        """Тест обработки ошибки при получении цитат"""
        # Настраиваем mock для генерации исключения
        mock_connect.side_effect = Exception("Ошибка базы данных")

        # Отправляем GET запрос к endpoint'у
        response = self.app.get("/api/quotes")

        # Проверяем статус ответа
        self.assertEqual(response.status_code, 500)

        # Проверяем содержимое ответа
        data = json.loads(response.data)
        self.assertIn("error", data)


if __name__ == "__main__":
    unittest.main()
