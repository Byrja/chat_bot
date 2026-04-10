#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Тест для проверки функциональности меню бота
"""

import sys
import os
import unittest
from unittest.mock import AsyncMock, Mock, patch

# Добавляем путь к модулю бота
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from mamoolyaBot.bot import menu, show_stats_menu


class TestMenu(unittest.IsolatedAsyncioTestCase):
    """Тесты для меню бота"""

    async def test_menu_command(self):
        """Тест команды /menu"""
        # Создаем моки для update и context
        update = AsyncMock()
        update.message.reply_text = AsyncMock()
        update.effective_user.id = 12345

        context = Mock()
        context.bot_data = {}

        # Вызываем функцию menu
        await menu(update, context)

        # Проверяем, что был вызван метод reply_text
        update.message.reply_text.assert_called_once()

        # Проверяем, что текст содержит информацию о выборе категорий
        args, kwargs = update.message.reply_text.call_args
        self.assertIn("Выберите категорию команд", args[0])

    async def test_stats_menu(self):
        """Тест меню статистики"""
        # Создаем моки для update и context
        update = AsyncMock()
        update.callback_query.answer = AsyncMock()
        update.callback_query.message.edit_text = AsyncMock()
        update.callback_query.from_user.id = 12345
        update.callback_query.message.message_id = 67890

        context = Mock()
        context.bot_data = {}

        # Вызываем функцию show_stats_menu
        await show_stats_menu(update, context)

        # Проверяем, что были вызваны необходимые методы
        update.callback_query.answer.assert_called_once()
        update.callback_query.message.edit_text.assert_called_once()

        # Проверяем, что текст содержит информацию о статистике
        args, kwargs = update.callback_query.message.edit_text.call_args
        self.assertIn("Статистика", args[0])


if __name__ == "__main__":
    unittest.main()
