#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Тест для проверки функциональности команды roll
"""

import sys
import os
import unittest
from unittest.mock import AsyncMock, Mock, patch

# Добавляем путь к модулю бота
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from mamoolyaBot.bot import roll


class TestRollCommand(unittest.IsolatedAsyncioTestCase):
    """Тесты для команды roll"""

    async def test_roll_command_single_die(self):
        """Тест команды /roll 1d5"""
        # Создаем моки для update и context
        update = AsyncMock()
        update.effective_user.first_name = "ТестовыйПользователь"
        update.message.reply_text = AsyncMock()

        context = Mock()
        context.args = ["1d5"]

        # Вызываем функцию roll
        await roll(update, context)

        # Проверяем, что был вызван метод reply_text
        update.message.reply_text.assert_called_once()

        # Проверяем, что результат находится в правильном диапазоне
        args, kwargs = update.message.reply_text.call_args
        result_text = args[0]
        self.assertIn("ТестовыйПользователь бросил кубик:", result_text)
        self.assertIn("(1-5)", result_text)

        # Извлекаем число из результата и проверяем диапазон
        import re

        match = re.search(r": (\d+) \(1-5\)", result_text)
        self.assertIsNotNone(match)
        result_number = int(match.group(1))
        self.assertGreaterEqual(result_number, 1)
        self.assertLessEqual(result_number, 5)

    async def test_roll_command_multiple_dice(self):
        """Тест команды /roll 2d6"""
        # Создаем моки для update и context
        update = AsyncMock()
        update.effective_user.first_name = "ТестовыйПользователь"
        update.message.reply_text = AsyncMock()

        context = Mock()
        context.args = ["2d6"]

        # Вызываем функцию roll
        await roll(update, context)

        # Проверяем, что был вызван метод reply_text
        update.message.reply_text.assert_called_once()

        # Проверяем, что результат содержит правильную информацию
        args, kwargs = update.message.reply_text.call_args
        result_text = args[0]
        self.assertIn("ТестовыйПользователь бросил 2 кубиков (d6):", result_text)
        self.assertIn("(2-12)", result_text)  # Минимум 2 (1+1), максимум 12 (6+6)
        self.assertIn(" = ", result_text)

        # Проверяем формат результата
        import re

        match = re.search(r": \[([^\]]+)\] = (\d+) \(2-12\)", result_text)
        self.assertIsNotNone(match)

        # Проверяем, что есть два числа в скобках
        dice_results = match.group(1)
        total = int(match.group(2))
        self.assertIn(",", dice_results)

        # Проверяем, что числа в правильном диапазоне
        numbers = [int(x.strip()) for x in dice_results.split(",")]
        self.assertEqual(len(numbers), 2)
        for num in numbers:
            self.assertGreaterEqual(num, 1)
            self.assertLessEqual(num, 6)

        # Проверяем, что сумма правильная
        self.assertEqual(sum(numbers), total)
        self.assertGreaterEqual(total, 2)  # Минимум 1+1=2
        self.assertLessEqual(total, 12)  # Максимум 6+6=12

    async def test_roll_command_invalid_format(self):
        """Тест команды с неправильным форматом"""
        # Создаем моки для update и context
        update = AsyncMock()
        update.message.reply_text = AsyncMock()

        context = Mock()
        context.args = ["invalid"]

        # Вызываем функцию roll
        await roll(update, context)

        # Проверяем, что был вызван метод reply_text с сообщением об ошибке
        update.message.reply_text.assert_called_once()
        args, kwargs = update.message.reply_text.call_args
        self.assertIn("Неправильный формат", args[0])

    async def test_roll_command_no_args(self):
        """Тест команды без аргументов"""
        # Создаем моки для update и context
        update = AsyncMock()
        update.message.reply_text = AsyncMock()

        context = Mock()
        context.args = []

        # Вызываем функцию roll
        await roll(update, context)

        # Проверяем, что был вызван метод reply_text с сообщением об ошибке
        update.message.reply_text.assert_called_once()
        args, kwargs = update.message.reply_text.call_args
        self.assertIn("Используй формат", args[0])


if __name__ == "__main__":
    unittest.main()
