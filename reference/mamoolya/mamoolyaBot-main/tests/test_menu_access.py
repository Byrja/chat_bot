#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Тест для проверки ограничения доступа к меню
"""

import sys
import os
import unittest
from unittest.mock import AsyncMock, Mock, patch

# Добавляем путь к модулю бота
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from mamoolyaBot.bot import menu_button_handler


class TestMenuAccess(unittest.IsolatedAsyncioTestCase):
    """Тесты для проверки ограничения доступа к меню"""

    async def test_menu_access_same_user(self):
        """Тест доступа к меню тем же пользователем, который его вызвал"""
        # Создаем моки для update и context
        update = AsyncMock()
        update.callback_query.answer = AsyncMock()
        update.callback_query.from_user.id = 12345
        update.callback_query.message.message_id = 67890
        update.callback_query.data = "menu_stats"

        context = Mock()
        context.bot_data = {"menu_users": {67890: 12345}}  # Тот же пользователь

        # Вызываем функцию menu_button_handler
        await menu_button_handler(update, context)

        # Проверяем, что пользователю позволили использовать меню
        # (не должно быть вызова show_alert=True)
        args, kwargs = update.callback_query.answer.call_args
        self.assertNotIn("show_alert", kwargs or {})

    async def test_menu_access_different_user(self):
        """Тест доступа к меню другим пользователем"""
        # Создаем моки для update и context
        update = AsyncMock()
        update.callback_query.answer = AsyncMock()
        update.callback_query.from_user.id = 54321  # Другой пользователь
        update.callback_query.message.message_id = 67890
        update.callback_query.data = "menu_stats"

        context = Mock()
        context.bot_data = {
            "menu_users": {67890: 12345}
        }  # Меню вызвано другим пользователем

        # Вызываем функцию menu_button_handler
        await menu_button_handler(update, context)

        # Проверяем, что пользователю показали уведомление об ограничении доступа
        args, kwargs = update.callback_query.answer.call_args
        self.assertIn(
            "Вы можете использовать только меню, которое вызвали сами!", args[0]
        )
        self.assertTrue(kwargs.get("show_alert", False))


if __name__ == "__main__":
    unittest.main()
