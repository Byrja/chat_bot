#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Тест для проверки функциональности игры в бутылочку
"""

import sys
import os
import unittest
from unittest.mock import AsyncMock, Mock, patch

# Добавляем путь к модулю бота
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from mamoolyaBot.bot import bottle_game, bottle_join_button


class TestBottleGame(unittest.IsolatedAsyncioTestCase):
    """Тесты для игры в бутылочку"""

    async def test_bottle_game_command(self):
        """Тест команды /bottle"""
        # Создаем моки для update и context
        update = AsyncMock()
        update.message.reply_text = AsyncMock()
        update.message.message_id = 12345
        update.effective_user.id = 67890

        context = Mock()
        context.bot_data = {}

        # Вызываем функцию bottle_game
        await bottle_game(update, context)

        # Проверяем, что был вызван метод reply_text
        update.message.reply_text.assert_called_once()

        # Проверяем, что текст содержит информацию об игре
        args, kwargs = update.message.reply_text.call_args
        self.assertIn("Игра в бутылочку!", args[0])
        self.assertIn("Нажмите кнопку ниже, чтобы участвовать", args[0])

        # Проверяем, что игра была инициализирована в контексте
        self.assertIn("bottle_game", context.bot_data)
        self.assertTrue(context.bot_data["bottle_game"]["started"])
        self.assertEqual(context.bot_data["bottle_game"]["participants"], [])
        self.assertEqual(context.bot_data["bottle_game"]["message_id"], 12345)

    async def test_bottle_join_button_first_player(self):
        """Тест кнопки участия первого игрока"""
        # Создаем моки для update и context
        update = AsyncMock()
        update.callback_query.answer = AsyncMock()
        update.callback_query.from_user.first_name = "Игрок1"
        update.callback_query.from_user.username = "player1"
        update.callback_query.message.reply_text = AsyncMock()

        context = Mock()
        context.bot_data = {
            "bottle_game": {
                "actions": ["@A говорит @B три честных комплимента (без иронии)."],
                "participants": [],
                "started": True,
            }
        }

        # Вызываем функцию bottle_join_button
        await bottle_join_button(update, context)

        # Проверяем, что игрок добавлен в список участников
        self.assertEqual(len(context.bot_data["bottle_game"]["participants"]), 1)
        participant = context.bot_data["bottle_game"]["participants"][0]
        self.assertEqual(participant["name"], "Игрок1")
        self.assertEqual(participant["display"], "@player1")

        # Проверяем, что был вызван ответ с правильными аргументами
        # Проверяем, что метод answer был вызван с нужными аргументами
        self.assertTrue(update.callback_query.answer.called)
        args, kwargs = update.callback_query.answer.call_args
        self.assertEqual(args[0], "Вы участвуете! Ждем второго игрока...")
        self.assertTrue(kwargs.get("show_alert", False))

    async def test_bottle_join_button_second_player(self):
        """Тест кнопки участия второго игрока"""
        # Создаем моки для update и context
        update = AsyncMock()
        update.callback_query.answer = AsyncMock()
        update.callback_query.from_user.first_name = "Игрок2"
        update.callback_query.from_user.username = "player2"
        update.callback_query.message.reply_text = AsyncMock()

        context = Mock()
        context.bot_data = {
            "bottle_game": {
                "actions": ["@A говорит @B три честных комплимента (без иронии)."],
                "participants": [{"name": "Игрок1", "display": "@player1"}],
                "started": True,
            }
        }

        # Вызываем функцию bottle_join_button
        await bottle_join_button(update, context)

        # Проверяем, что второй игрок добавлен в список участников
        self.assertEqual(len(context.bot_data["bottle_game"]["participants"]), 2)
        participant = context.bot_data["bottle_game"]["participants"][1]
        self.assertEqual(participant["name"], "Игрок2")
        self.assertEqual(participant["display"], "@player2")

        # Проверяем, что игра завершена
        self.assertFalse(context.bot_data["bottle_game"]["started"])

        # Проверяем, что был отправлен результат игры
        update.callback_query.message.reply_text.assert_called_once()
        args, kwargs = update.callback_query.message.reply_text.call_args
        self.assertIn("Результат игры в бутылочку:", args[0])
        self.assertIn(
            "@player1 говорит @player2 три честных комплимента (без иронии).", args[0]
        )


if __name__ == "__main__":
    unittest.main()
