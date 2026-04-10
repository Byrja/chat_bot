import sys
import os
import unittest
from unittest.mock import AsyncMock, Mock, patch
from types import SimpleNamespace

sys.path.append(os.path.join(os.path.dirname(__file__), "../mamoolyaBot"))

from mamoolyaBot.bot import horoscope
from mamoolyaBot.zodiac_utils import get_zodiac_sign_by_date
from mamoolyaBot.ai_client import AIResponse


class TestEnhancedHoroscope(unittest.IsolatedAsyncioTestCase):
    async def _invoke_horoscope(
        self, *, db_zodiac, birthdate=None, stream_text="generated-text"
    ):
        with (
            patch("mamoolyaBot.bot.stream_prompt_to_message") as mock_stream,
            patch("mamoolyaBot.bot.cursor") as mock_cursor,
            patch("mamoolyaBot.bot.get_user_rep") as mock_get_user_rep,
            patch("mamoolyaBot.bot.random") as mock_random,
        ):

            mock_cursor.fetchone.return_value = (db_zodiac,)
            mock_get_user_rep.return_value = (4, 1)
            mock_random.choice.return_value = "?"

            async def fake_stream(status_message, system_prompt, **kwargs):
                await status_message.edit_text(stream_text)
                return AIResponse(text=stream_text, model="test-model", usage={})

            mock_stream.side_effect = fake_stream

            update = AsyncMock()
            update.message.reply_text = AsyncMock()
            placeholder = AsyncMock()
            placeholder.edit_text = AsyncMock()
            update.message.reply_text.return_value = placeholder
            update.effective_user.first_name = "Test User"
            update.effective_user.username = "testuser"
            update.effective_user.id = 123

            if birthdate is None:
                if hasattr(update.effective_user, "birthdate"):
                    delattr(update.effective_user, "birthdate")
            else:
                update.effective_user.birthdate = birthdate

            context = Mock()
            await horoscope(update, context)

            return placeholder, mock_stream

    async def test_horoscope_command_with_user_selected_zodiac(self):
        stream_text = "selected-zodiac-response"
        placeholder, mock_stream = await self._invoke_horoscope(
            db_zodiac="Leo", stream_text=stream_text
        )

        self.assertEqual(mock_stream.await_count, 1)
        final_text = placeholder.edit_text.await_args_list[-1].args[0]
        self.assertIn("@testuser", final_text)
        self.assertIn(stream_text, final_text)

    async def test_horoscope_command_with_birthdate_zodiac(self):
        stream_text = "birthdate-response"
        birthdate = SimpleNamespace(day=20, month=4, year=1990)
        placeholder, mock_stream = await self._invoke_horoscope(
            db_zodiac=None, birthdate=birthdate, stream_text=stream_text
        )

        self.assertEqual(mock_stream.await_count, 1)
        final_text = placeholder.edit_text.await_args_list[-1].args[0]
        self.assertIn("@testuser", final_text)
        self.assertIn(stream_text, final_text)

    async def test_horoscope_command_without_zodiac_and_birthdate(self):
        stream_text = "fallback-response"
        placeholder, mock_stream = await self._invoke_horoscope(
            db_zodiac=None, birthdate=None, stream_text=stream_text
        )

        self.assertEqual(mock_stream.await_count, 1)
        final_text = placeholder.edit_text.await_args_list[-1].args[0]
        self.assertIn("@testuser", final_text)
        self.assertIn(stream_text, final_text)


class TestZodiacUtils(unittest.TestCase):
    def test_get_zodiac_sign_by_date(self):
        result = get_zodiac_sign_by_date(20, 4)
        self.assertIsInstance(result, str)
        self.assertTrue(result)

        result = get_zodiac_sign_by_date(19, 2)
        self.assertIsInstance(result, str)
        self.assertTrue(result)

        result = get_zodiac_sign_by_date(32, 1)
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
