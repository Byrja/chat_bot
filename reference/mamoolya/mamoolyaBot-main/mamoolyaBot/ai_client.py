from __future__ import annotations

import hashlib
import logging
import os
import random
import time
import json
from urllib import request as urlrequest
from urllib.error import HTTPError, URLError
from dataclasses import dataclass
from typing import Callable, Dict, Iterable, List, Optional, Sequence

from openai import OpenAI
from openai._exceptions import APIError, APIStatusError, APITimeoutError, RateLimitError

logger = logging.getLogger(__name__)

DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
FALLBACK_MODELS: List[str] = [
    model.strip()
    for model in os.getenv("OPENAI_FALLBACKS", "gpt-4o-mini,gpt-3.5-turbo").split(",")
    if model.strip()
]
API_TIMEOUT_MS = int(os.getenv("OPENAI_TIMEOUT_MS", "60000"))
PROMPT_CACHE_KEY_ENV = os.getenv("PROMPT_CACHE_KEY")
DEFAULT_MAX_OUTPUT_TOKENS = 600
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_DEFAULT_MODEL = "openrouter/free"
OPENROUTER_APP_TITLE = "mamoolyaBot"

DEPRECATED_GROQ_MODELS: Dict[str, str] = {
    "llama3-70b-8192": "llama-3.3-70b-versatile",
    "llama3-8b-8192": "llama-3.1-8b-instant",
}
GROQ_FALLBACK_MODELS: List[str] = [
    model.strip()
    for model in os.getenv("GROQ_FALLBACKS", "llama-3.1-8b-instant").split(",")
    if model.strip()
]

_openai_client: Optional[OpenAI] = None


@dataclass
class AIResponse:
    text: str
    model: str
    usage: Dict[str, int]


def _build_prompt_cache_key(system_prompt: Optional[str]) -> Optional[str]:
    if PROMPT_CACHE_KEY_ENV:
        return PROMPT_CACHE_KEY_ENV
    if not system_prompt:
        return None
    digest = hashlib.sha256(system_prompt.encode("utf-8")).hexdigest()
    return f"mamoolya-sys-{digest[:24]}"


def _extract_message_text(content: object) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: List[str] = []
        for item in content:
            if isinstance(item, str):
                part = item.strip()
                if part:
                    parts.append(part)
                continue
            if isinstance(item, dict):
                text_value = item.get("text") or item.get("content")
                if isinstance(text_value, str):
                    part = text_value.strip()
                    if part:
                        parts.append(part)
        return "\n".join(parts).strip()
    return ""


def _get_models_chain(primary_model: Optional[str] = None) -> List[str]:
    models: List[str] = []
    if primary_model:
        models.append(primary_model)
    if DEFAULT_MODEL and DEFAULT_MODEL not in models:
        models.append(DEFAULT_MODEL)
    for fallback in FALLBACK_MODELS:
        if fallback and fallback not in models:
            models.append(fallback)
    return models


def get_groq_api_key() -> Optional[str]:
    value = os.getenv("GROQ_API_KEY")
    if not value:
        return None
    stripped = value.strip()
    return stripped or None


def get_groq_default_model() -> str:
    value = os.getenv("GROQ_MODEL")
    if value:
        value = value.strip()
        if value:
            replacement = DEPRECATED_GROQ_MODELS.get(value)
            if replacement:
                logger.warning(
                    "Groq model '%s' is deprecated; using '%s' instead.",
                    value,
                    replacement,
                )
                return replacement
            return value
    return "llama-3.3-70b-versatile"


def get_openai_client() -> Optional[OpenAI]:
    global _openai_client
    if _openai_client is not None:
        return _openai_client
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.warning("OPENAI_API_KEY is not set. OpenAI client is unavailable.")
        return None
    timeout_seconds = max(API_TIMEOUT_MS / 1000.0, 1.0)
    _openai_client = OpenAI(api_key=api_key, timeout=timeout_seconds)
    return _openai_client


def is_openai_available() -> bool:
    return get_openai_client() is not None


def is_groq_available() -> bool:
    return bool(get_groq_api_key())


def _resolve_groq_model(model_id: str) -> str:
    return DEPRECATED_GROQ_MODELS.get(model_id, model_id)


def _get_groq_models_chain(primary_model: Optional[str] = None) -> List[str]:
    models: List[str] = []
    if primary_model:
        models.append(_resolve_groq_model(primary_model))
    default_model = _resolve_groq_model(get_groq_default_model())
    if default_model not in models:
        models.append(default_model)
    for fallback in GROQ_FALLBACK_MODELS:
        resolved = _resolve_groq_model(fallback)
        if resolved and resolved not in models:
            models.append(resolved)
    return models


class GroqAPIError(RuntimeError):
    def __init__(self, message: str, *, status: Optional[int] = None):
        super().__init__(message)
        self.status = status


class OpenRouterAPIError(RuntimeError):
    def __init__(self, message: str, *, status: Optional[int] = None):
        super().__init__(message)
        self.status = status


def _get_llm_provider() -> str:
    provider = os.getenv("LLM_PROVIDER", "legacy").strip().lower()
    if provider in {"legacy", "openrouter"}:
        return provider
    logger.warning("Unknown LLM_PROVIDER=%r, using legacy provider.", provider)
    return "legacy"


def get_openrouter_api_key() -> Optional[str]:
    value = os.getenv("OPENROUTER_API_KEY")
    if not value:
        return None
    stripped = value.strip()
    return stripped or None


def get_openrouter_default_model() -> str:
    value = os.getenv("OPENROUTER_MODEL")
    if value:
        stripped = value.strip()
        if stripped:
            return stripped
    return OPENROUTER_DEFAULT_MODEL


def is_openrouter_available() -> bool:
    return bool(get_openrouter_api_key())


def _should_retry(exc: Exception) -> bool:
    if isinstance(exc, (RateLimitError, APITimeoutError)):
        return True
    if isinstance(exc, APIStatusError):
        status = getattr(exc, "status_code", None)
        return status is not None and status >= 500
    if isinstance(exc, APIError):
        status = getattr(exc, "status_code", None)
        return status is not None and status >= 500
    return False


def _sleep_with_backoff(attempt: int) -> None:
    base = min(2**attempt, 16)
    jitter = random.uniform(0, 0.75)
    time.sleep(base + jitter)


def generate_response(
    messages: Sequence[Dict[str, str]],
    *,
    system_prompt: Optional[str] = None,
    temperature: float = 0.9,
    top_p: float = 1.0,
    max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS,
    on_token: Optional[Callable[[str], None]] = None,
    primary_model: Optional[str] = None,
) -> AIResponse:
    """
    Выполняет запрос к Responses API с поддержкой стриминга и фолбэков.
    """
    content_messages: List[Dict[str, str]] = []
    if system_prompt:
        content_messages.append({"role": "system", "content": system_prompt})
    content_messages.extend(messages)

    if primary_model == "groq":
        if not is_groq_available():
            raise RuntimeError("Groq API key is not configured.")
        return _generate_with_groq(
            messages=list(content_messages),
            temperature=temperature,
            top_p=top_p,
            max_output_tokens=max_output_tokens,
            on_token=on_token,
            primary_model=None,
        )

    provider = _get_llm_provider()
    if provider == "openrouter":
        if not is_openrouter_available():
            logger.error(
                "LLM_PROVIDER=openrouter but OPENROUTER_API_KEY is not set. Falling back to legacy provider."
            )
        else:
            try:
                return _generate_with_openrouter(
                    messages=content_messages,
                    temperature=temperature,
                    top_p=top_p,
                    max_output_tokens=max_output_tokens,
                    on_token=on_token,
                )
            except OpenRouterAPIError as exc:
                logger.error(
                    "OpenRouter request failed with status %s (%s).",
                    exc.status,
                    exc,
                )
                raise
            except Exception as exc:
                logger.exception("OpenRouter unexpected error (%s).", exc)
                raise

    client = get_openai_client()
    if client is None and is_groq_available():
        return _generate_with_groq(
            messages=list(content_messages),
            temperature=temperature,
            top_p=top_p,
            max_output_tokens=max_output_tokens,
            on_token=on_token,
            primary_model=None,
        )
    if client is None:
        raise RuntimeError("OpenAI client is not configured.")

    cache_key = _build_prompt_cache_key(system_prompt)

    models_chain = _get_models_chain(primary_model)
    last_error: Optional[Exception] = None

    for attempt, model in enumerate(models_chain):
        try:
            return _execute_streaming_request(
                client=client,
                model=model,
                messages=content_messages,
                temperature=temperature,
                top_p=top_p,
                max_output_tokens=max_output_tokens,
                cache_key=cache_key,
                on_token=on_token,
            )
        except Exception as exc:
            last_error = exc
            if attempt == len(models_chain) - 1 or not _should_retry(exc):
                logger.exception("OpenAI request failed on model %s", model)
                break
            logger.warning(
                "OpenAI request failed on model %s (%s). Switching to fallback...",
                model,
                exc,
            )
            _sleep_with_backoff(attempt)
            continue

    if last_error:
        if is_groq_available():
            logger.warning("Falling back to Groq after OpenAI failure: %s", last_error)
            return _generate_with_groq(
                messages=content_messages,
                temperature=temperature,
                top_p=top_p,
                max_output_tokens=max_output_tokens,
                on_token=on_token,
                primary_model=None,
            )
        raise last_error
    raise RuntimeError("Failed to obtain response from all OpenAI models.")


def _execute_streaming_request(
    *,
    client: OpenAI,
    model: str,
    messages: Sequence[Dict[str, str]],
    temperature: float,
    top_p: float,
    max_output_tokens: int,
    cache_key: Optional[str],
    on_token: Optional[Callable[[str], None]],
) -> AIResponse:
    text_chunks: List[str] = []
    final_model = model
    usage_dict: Dict[str, int] = {}

    stream_kwargs = {
        "model": model,
        "input": list(messages),
        "temperature": temperature,
        "top_p": top_p,
        "max_output_tokens": max_output_tokens,
    }
    if cache_key:
        stream_kwargs["prompt_cache_key"] = cache_key

    try:
        stream_context = client.responses.stream(**stream_kwargs)
    except TypeError as exc:
        if cache_key and "prompt_cache_key" in str(exc):
            logger.info(
                "OpenAI client does not support prompt_cache_key; retrying without prompt caching."
            )
            stream_kwargs.pop("prompt_cache_key", None)
            stream_context = client.responses.stream(**stream_kwargs)
        else:
            raise

    with stream_context as stream:
        for event in stream:
            event_type = getattr(event, "type", "")
            if event_type == "response.output_text.delta":
                delta = getattr(event, "delta", "")
                if delta:
                    text_chunks.append(delta)
                    if on_token:
                        on_token(delta)
            elif event_type == "response.error":
                details = getattr(event, "error", None)
                stream.close()
                raise RuntimeError(f"OpenAI streaming error: {details}")

        try:
            final_response = stream.get_final_response()
        except RuntimeError as err:
            if "response.completed" in str(err):
                logger.warning(
                    "OpenAI stream finished without response.completed; using accumulated text only."
                )
                final_response = None
            else:
                raise

    if final_response is not None:
        final_model = getattr(final_response, "model", model)
        usage = getattr(final_response, "usage", None)
        if usage is not None:
            if hasattr(usage, "to_dict"):
                usage_dict = usage.to_dict()
            elif isinstance(usage, dict):
                usage_dict = usage
        if not text_chunks:
            output_text = getattr(final_response, "output_text", None)
            if output_text:
                if isinstance(output_text, str):
                    text_chunks.append(output_text)
                elif isinstance(output_text, Iterable):
                    text_chunks.extend([str(part) for part in output_text])

    full_text = "".join(text_chunks).strip()
    if not full_text:
        full_text = "[empty response]"

    logger.info(
        "OpenAI usage model=%s input_tokens=%s output_tokens=%s total_tokens=%s",
        final_model,
        usage_dict.get("input_tokens"),
        usage_dict.get("output_tokens"),
        usage_dict.get("total_tokens"),
    )

    return AIResponse(text=full_text, model=final_model, usage=usage_dict)


def _generate_with_groq(
    messages: Sequence[Dict[str, str]],
    *,
    temperature: float,
    top_p: float,
    max_output_tokens: int,
    on_token: Optional[Callable[[str], None]],
    primary_model: Optional[str] = None,
) -> AIResponse:
    groq_api_key = get_groq_api_key()
    if not groq_api_key:
        raise RuntimeError("Groq API key is not configured.")

    headers = {
        "Authorization": f"Bearer {groq_api_key}",
        "Content-Type": "application/json",
    }
    timeout = max(API_TIMEOUT_MS / 1000.0, 60.0)
    url = "https://api.groq.com/openai/v1/chat/completions"
    messages_payload = list(messages)

    models_chain = _get_groq_models_chain(primary_model)
    max_attempts_per_model = max(1, int(os.getenv("GROQ_MODEL_ATTEMPTS", "3")))
    last_error: Optional[Exception] = None

    for model_index, groq_model in enumerate(models_chain):
        last_error = None
        for attempt in range(max_attempts_per_model):
            payload = {
                "model": groq_model,
                "messages": messages_payload,
                "temperature": temperature,
                "top_p": top_p,
                "max_tokens": max_output_tokens,
            }
            req = urlrequest.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST",
            )
            try:
                with urlrequest.urlopen(req, timeout=timeout) as resp:
                    response_body = resp.read().decode("utf-8")
                    data = json.loads(response_body)
            except HTTPError as exc:
                status = getattr(exc, "code", None)
                try:
                    error_body = exc.read().decode("utf-8")
                    details = json.loads(error_body)
                    message = details.get("error", {}).get("message", str(exc))
                except Exception:
                    message = str(exc)
                last_error = GroqAPIError(f"Groq API error: {message}", status=status)
            except URLError as exc:
                last_error = GroqAPIError(f"Groq network error: {exc}")
            except Exception as exc:
                last_error = GroqAPIError(f"Groq unexpected error: {exc}")
            else:
                choices = data.get("choices", [])
                if not choices:
                    last_error = GroqAPIError("Groq API returned no choices.")
                else:
                    message = choices[0].get("message", {})
                    text = _extract_message_text(message.get("content", ""))
                    if on_token and text:
                        on_token(text)

                    usage_raw = data.get("usage") or {}
                    usage_dict: Dict[str, int] = {}
                    for key in ("input_tokens", "output_tokens", "total_tokens"):
                        value = usage_raw.get(key)
                        if value is not None:
                            try:
                                usage_dict[key] = int(value)
                            except Exception:
                                continue

                    final_model = data.get("model") or groq_model
                    return AIResponse(text=text, model=final_model, usage=usage_dict)

            if last_error is None:
                continue

            message_lower = str(last_error).lower()
            is_rate_limited = isinstance(last_error, GroqAPIError) and (
                getattr(last_error, "status", None) == 429
                or "rate limit" in message_lower
            )
            if is_rate_limited and attempt < max_attempts_per_model - 1:
                backoff = min(2**attempt, 10)
                logger.warning(
                    "Groq model %s rate limited (attempt %s/%s); retrying after %ss",
                    groq_model,
                    attempt + 1,
                    max_attempts_per_model,
                    backoff,
                )
                time.sleep(backoff)
                last_error = None
                continue

            break

        if last_error is not None and model_index < len(models_chain) - 1:
            logger.warning(
                "Groq model %s failed after %s attempt(s) (%s); trying fallback %s",
                groq_model,
                max_attempts_per_model,
                last_error,
                models_chain[model_index + 1],
            )
            time.sleep(min(2 ** (model_index + 1), 10))
            continue

        if last_error is not None:
            raise last_error

    raise RuntimeError("Groq request failed after exhausting all Groq models.")


def _generate_with_openrouter(
    messages: Sequence[Dict[str, str]],
    *,
    temperature: float,
    top_p: float,
    max_output_tokens: int,
    on_token: Optional[Callable[[str], None]],
) -> AIResponse:
    openrouter_api_key = get_openrouter_api_key()
    if not openrouter_api_key:
        raise OpenRouterAPIError("OpenRouter API key is not configured.")

    headers = {
        "Authorization": f"Bearer {openrouter_api_key}",
        "Content-Type": "application/json",
        "X-Title": OPENROUTER_APP_TITLE,
    }
    referer = os.getenv("OPENROUTER_SITE_URL", "").strip()
    if referer:
        headers["HTTP-Referer"] = referer

    timeout = max(API_TIMEOUT_MS / 1000.0, 60.0)
    url = f"{OPENROUTER_BASE_URL}/chat/completions"
    payload = {
        "model": get_openrouter_default_model(),
        "messages": list(messages),
        "temperature": temperature,
        "top_p": top_p,
        "max_tokens": max_output_tokens,
    }
    req = urlrequest.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    try:
        with urlrequest.urlopen(req, timeout=timeout) as resp:
            response_body = resp.read().decode("utf-8")
            data = json.loads(response_body)
    except HTTPError as exc:
        status = getattr(exc, "code", None)
        try:
            error_body = exc.read().decode("utf-8")
            details = json.loads(error_body)
            message = details.get("error", {}).get("message", str(exc))
        except Exception:
            message = str(exc)
        raise OpenRouterAPIError(f"OpenRouter API error: {message}", status=status) from exc
    except URLError as exc:
        raise OpenRouterAPIError(f"OpenRouter network error: {exc}") from exc
    except Exception as exc:
        raise OpenRouterAPIError(f"OpenRouter unexpected error: {exc}") from exc

    choices = data.get("choices", [])
    if not choices:
        raise OpenRouterAPIError("OpenRouter API returned no choices.")

    message = choices[0].get("message", {})
    text = _extract_message_text(message.get("content", ""))
    if on_token and text:
        on_token(text)

    usage_raw = data.get("usage") or {}
    usage_dict: Dict[str, int] = {}
    for key in ("input_tokens", "output_tokens", "total_tokens"):
        value = usage_raw.get(key)
        if value is not None:
            try:
                usage_dict[key] = int(value)
            except Exception:
                continue

    final_model = data.get("model") or get_openrouter_default_model()
    return AIResponse(text=text, model=final_model, usage=usage_dict)
