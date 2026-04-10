#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Тест для проверки функциональности WebApp
"""

import sys
import os
import unittest
from unittest.mock import AsyncMock, Mock

# Добавляем путь к модулю бота
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from mamoolyaBot.bot import webapp


class TestWebApp(unittest.IsolatedAsyncioTestCase):
    """Тесты для WebApp"""

    async def test_webapp_command(self):
        """Тест команды /webapp"""
        # Создаем моки для update и context
        update = AsyncMock()
        update.message.reply_text = AsyncMock()

        context = Mock()

        # Вызываем функцию webapp
        await webapp(update, context)

        # Проверяем, что был вызван метод reply_text
        update.message.reply_text.assert_called_once()

        # Проверяем, что текст содержит информацию о WebApp
        args, kwargs = update.message.reply_text.call_args
        self.assertIn(
            "Открой мой WebApp для анонимных признаний, статистики и квиза!", args[0]
        )

        # Проверяем, что клавиатура была передана
        self.assertIn("reply_markup", kwargs)
        reply_markup = kwargs["reply_markup"]
        self.assertIsNotNone(reply_markup)


if __name__ == "__main__":
    unittest.main()
