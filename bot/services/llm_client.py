import json
import os
from typing import Optional
from urllib import request
from urllib.error import HTTPError, URLError


def llm_enabled() -> bool:
    return bool(os.getenv("WORMSOFT_API_KEY", "").strip())


def _build_headers() -> dict[str, str]:
    key = os.getenv("WORMSOFT_API_KEY", "").strip()
    return {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


def _model_chain() -> list[str]:
    primary = os.getenv("WORMSOFT_MODEL", "qwen/qwen3.6:35b-a3b").strip()
    fallbacks = [
        m.strip()
        for m in os.getenv("WORMSOFT_FALLBACK_MODELS", "deepseek-ai/deepseek-v4-pro,kimi/kimi-k2.7-code").split(",")
        if m.strip()
    ]
    models = [primary]
    for m in fallbacks:
        if m not in models:
            models.append(m)
    return models


def _call_model(
    model: str,
    messages: list[dict[str, str]],
    max_tokens: int,
    temperature: float,
    top_p: float,
    timeout: float,
) -> Optional[str]:
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "top_p": top_p,
    }
    req = request.Request(
        "https://ai.wormsoft.ru/api/gpt/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers=_build_headers(),
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        text = data["choices"][0]["message"]["content"].strip()
        return text if text else None
    except (HTTPError, URLError, TimeoutError, KeyError, json.JSONDecodeError):
        return None


def complete_text(
    prompt: str,
    system_prompt: Optional[str] = None,
    max_tokens: int = 1000,
    temperature: float = 0.7,
    top_p: float = 1.0,
    timeout: float = 35.0,
) -> Optional[str]:
    if not llm_enabled():
        return None

    messages: list[dict[str, str]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    last_error_text: Optional[str] = None
    for model in _model_chain():
        text = _call_model(model, messages, max_tokens, temperature, top_p, timeout)
        if text:
            # Telegram text message limit is ~4096; keep a safety margin.
            if len(text) > 3800:
                text = text[:3797] + "..."
            return text

    return None
