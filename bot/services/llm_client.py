import json
import os
from typing import Optional
from urllib import request
from urllib.error import HTTPError, URLError


def llm_enabled() -> bool:
    return bool(os.getenv("OPENROUTER_API_KEY", "").strip())


def _build_headers() -> dict[str, str]:
    key = os.getenv("OPENROUTER_API_KEY", "").strip()
    return {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "HTTP-Referer": os.getenv("OPENROUTER_REFERRER", "https://github.com/Byrja/chat_bot"),
        "X-Title": os.getenv("OPENROUTER_APP_NAME", "MD4"),
    }


def complete_text(prompt: str, max_tokens: int = 180, temperature: float = 0.7) -> Optional[str]:
    key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not key:
        return None

    model = os.getenv("OPENROUTER_MODEL", "openai/gpt-oss-20b:free").strip()
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "Отвечай кратко, дружелюбно, на русском. Без токсичности и без запрещённого контента."},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }

    req = request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers=_build_headers(),
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=22) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        text = data["choices"][0]["message"]["content"].strip()
        if not text:
            return None
        if len(text) > 900:
            text = text[:900]
        return text
    except (HTTPError, URLError, TimeoutError, KeyError, json.JSONDecodeError):
        return None
