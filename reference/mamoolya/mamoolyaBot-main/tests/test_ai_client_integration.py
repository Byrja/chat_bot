import unittest
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import patch

from mamoolyaBot import ai_client
from mamoolyaBot.ai_client import (
    AIResponse,
    APITimeoutError,
    OpenRouterAPIError,
    _extract_message_text,
)


class FakeStream:
    def __init__(self, events, final_response):
        self._events = events
        self._final_response = final_response
        self.closed = False

    def __iter__(self):
        return iter(self._events)

    def close(self):
        self.closed = True

    def get_final_response(self):
        return self._final_response


class GenerateResponseTests(unittest.TestCase):
    def tearDown(self):
        ai_client._openai_client = None

    def test_streaming_accumulates_text(self):
        events = [
            SimpleNamespace(type="response.output_text.delta", delta="Hello "),
            SimpleNamespace(type="response.output_text.delta", delta="world"),
            SimpleNamespace(type="response.output_text.delta", delta="!"),
        ]
        usage = SimpleNamespace(
            to_dict=lambda: {"input_tokens": 5, "output_tokens": 7, "total_tokens": 12}
        )
        final_response = SimpleNamespace(model="gpt-4.1-mini", usage=usage)
        captured_kwargs = []

        @contextmanager
        def fake_stream(**kwargs):
            captured_kwargs.append(kwargs)
            yield FakeStream(events, final_response)

        fake_client = SimpleNamespace(responses=SimpleNamespace(stream=fake_stream))

        with patch("mamoolyaBot.ai_client.get_openai_client", return_value=fake_client):
            result = ai_client.generate_response(
                messages=[{"role": "user", "content": "Hi"}],
                system_prompt="Test prompt",
            )

        self.assertEqual(result.text, "Hello world!")
        self.assertEqual(result.model, "gpt-4.1-mini")
        self.assertEqual(result.usage["total_tokens"], 12)
        self.assertEqual(captured_kwargs[0]["model"], ai_client.DEFAULT_MODEL)
        self.assertIn("prompt_cache_key", captured_kwargs[0])

    def test_respects_max_output_tokens(self):
        events = [SimpleNamespace(type="response.output_text.delta", delta="Chunk")]
        usage = SimpleNamespace(to_dict=lambda: {})
        final_response = SimpleNamespace(model="gpt-4o", usage=usage)
        captured_kwargs = []

        @contextmanager
        def fake_stream(**kwargs):
            captured_kwargs.append(kwargs)
            yield FakeStream(events, final_response)

        fake_client = SimpleNamespace(responses=SimpleNamespace(stream=fake_stream))

        with patch("mamoolyaBot.ai_client.get_openai_client", return_value=fake_client):
            result = ai_client.generate_response(
                messages=[{"role": "user", "content": "Ping"}],
                system_prompt="Long system prompt",
                max_output_tokens=123,
            )

        self.assertEqual(result.text, "Chunk")
        self.assertEqual(captured_kwargs[0]["max_output_tokens"], 123)

    def test_fallback_on_retryable_error(self):
        models_chain = ["primary-model", "fallback-model"]
        call_count = {"value": 0}

        def fake_execute(**kwargs):
            call_count["value"] += 1
            model = kwargs["model"]
            if call_count["value"] == 1:
                self.assertEqual(model, models_chain[0])
                raise APITimeoutError(request=None)
            self.assertEqual(model, models_chain[1])
            return AIResponse(text="fallback success", model=model, usage={})

        with (
            patch("mamoolyaBot.ai_client.get_openai_client", return_value=object()),
            patch("mamoolyaBot.ai_client._get_models_chain", return_value=models_chain),
            patch(
                "mamoolyaBot.ai_client._execute_streaming_request",
                side_effect=fake_execute,
            ),
            patch("mamoolyaBot.ai_client._sleep_with_backoff") as mock_sleep,
        ):
            result = ai_client.generate_response(
                messages=[{"role": "user", "content": "Test"}]
            )

        self.assertEqual(result.text, "fallback success")
        self.assertEqual(result.model, models_chain[1])
        self.assertEqual(call_count["value"], 2)
        mock_sleep.assert_called_once()

    def test_extract_message_text_supports_openrouter_content_parts(self):
        text = _extract_message_text(
            [
                {"type": "text", "text": "Первая часть"},
                {"type": "text", "text": "Вторая часть"},
            ]
        )
        self.assertEqual(text, "Первая часть\nВторая часть")

    def test_openrouter_error_is_raised_without_legacy_fallback(self):
        with (
            patch("mamoolyaBot.ai_client._get_llm_provider", return_value="openrouter"),
            patch("mamoolyaBot.ai_client.is_openrouter_available", return_value=True),
            patch(
                "mamoolyaBot.ai_client._generate_with_openrouter",
                side_effect=OpenRouterAPIError("Forbidden", status=403),
            ),
        ):
            with self.assertRaises(OpenRouterAPIError):
                ai_client.generate_response(messages=[{"role": "user", "content": "hi"}])


if __name__ == "__main__":
    unittest.main()
