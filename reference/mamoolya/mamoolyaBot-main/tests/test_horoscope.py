#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
??????' ???>?? ?????????????? ?"??????O???????>?????????'?? ????????????? ?????????????????
"""

import sys
import os
import unittest
from typing import Optional
from unittest.mock import AsyncMock, Mock, patch

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from mamoolyaBot.bot import horoscope
from mamoolyaBot.ai_client import AIResponse


class TestHoroscope(unittest.IsolatedAsyncioTestCase):
    """??????'?< ???>?? ????????????? ?????????????????"""

    async def _run_case(self, *, stream_text: str, zodiac_from_db: Optional[str]):
        with (
            patch("mamoolyaBot.bot.stream_prompt_to_message") as mock_stream,
            patch("mamoolyaBot.bot.cursor") as mock_cursor,
            patch("mamoolyaBot.bot.get_user_rep") as mock_get_user_rep,
            patch("mamoolyaBot.bot.random") as mock_random,
        ):

            mock_cursor.fetchone.return_value = (zodiac_from_db,)
            mock_get_user_rep.return_value = (3, 1)
            mock_random.choice.return_value = "???"

            async def fake_stream(status_message, system_prompt, **kwargs):
                await status_message.edit_text(stream_text)
                return AIResponse(
                    text=stream_text,
                    model="test-model",
                    usage={"input_tokens": 10, "output_tokens": 20},
                )

            mock_stream.side_effect = fake_stream

            update = AsyncMock()
            update.message.reply_text = AsyncMock()
            placeholder = AsyncMock()
            placeholder.edit_text = AsyncMock()
            update.message.reply_text.return_value = placeholder
            update.effective_user.first_name = "Test User"
            update.effective_user.username = "testuser"
            update.effective_user.id = 123

            context = Mock()

            await horoscope(update, context)

            return update, placeholder

    async def test_horoscope_command_with_zodiac(self):
        stream_text = "stream-response-text"
        update, placeholder = await self._run_case(
            stream_text=stream_text, zodiac_from_db="Leo"
        )

        self.assertEqual(update.message.reply_text.await_count, 1)
        placeholder_text = update.message.reply_text.await_args_list[0].args[0]
        self.assertIn("...", placeholder_text)

        self.assertGreaterEqual(placeholder.edit_text.await_count, 1)
        final_text = placeholder.edit_text.await_args_list[-1].args[0]
        self.assertIn("@testuser", final_text)
        self.assertTrue(final_text.endswith(stream_text))

    async def test_horoscope_command_without_zodiac(self):
        stream_text = "fallback-stream-text"
        update, placeholder = await self._run_case(
            stream_text=stream_text, zodiac_from_db=None
        )

        self.assertEqual(update.message.reply_text.await_count, 1)
        placeholder_text = update.message.reply_text.await_args_list[0].args[0]
        self.assertIn("...", placeholder_text)

        self.assertGreaterEqual(placeholder.edit_text.await_count, 1)
        final_text = placeholder.edit_text.await_args_list[-1].args[0]
        self.assertIn("@testuser", final_text)
        self.assertTrue(final_text.endswith(stream_text))


if __name__ == "__main__":
    unittest.main()
