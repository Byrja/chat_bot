# Project Map

## Core modules
- `mamoolyaBot/bot.py` — Telegram bot entrypoint and command handlers.
- `mamoolyaBot/ai_client.py` — LLM integration layer with provider selection and fallbacks.
- `webapp/backend/` — backend API for web application.
- `webapp/frontend/` — Svelte frontend app.

## LLM provider switch
- `LLM_PROVIDER=legacy` (default): keeps existing OpenAI/Groq behavior.
- `LLM_PROVIDER=openrouter`: routes requests through OpenRouter.
- OpenRouter env vars: `OPENROUTER_API_KEY`, `OPENROUTER_MODEL` (default `openrouter/free`).
