# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Russian-language Telegram bot "Мааамууляя" (Mamulya) with AI integration, web interface, and entertainment features. The bot uses async architecture with python-telegram-bot v21.

## Common Commands

### Development
```bash
# Run bot locally
python bot.py

# Run tests
pytest tests/

# Run single test file
pytest tests/test_ai_client_integration.py -v

# Run tests matching pattern
pytest tests/ -k "horoscope"
```

### Webapp (frontend at webapp/frontend/)
```bash
yarn install --frozen-lockfile
yarn dev      # development server
yarn build    # production build
```

### Deployment (on server)
```bash
make update   # fetches code, installs deps, restarts systemd services
```

## Architecture

### Project Structure
- `bot.py` - Entry point only, calls `mamoolyaBot.bot.mamoolyaMain()`
- `mamoolyaBot/` - Core bot code
  - `bot.py` - Main handlers, commands, scheduled tasks (~6000 lines)
  - `ai_client.py` - OpenAI/Groq streaming client with fallback chains
  - `zodiac_utils.py` - Zodiac sign calculations
  - `utils.py` - Utilities including `get_version()` from git tags
- `webapp/backend/app.py` - Flask REST API
- `webapp/frontend/` - SvelteKit + Tailwind CSS frontend
- `tests/` - pytest + pytest-asyncio test suite

### AI Integration
The `ai_client.py` module provides:
- Streaming responses via `generate_response()` with `on_token` callback
- Fallback chain: OpenAI → Groq (configured via `OPENAI_FALLBACKS` env var)
- Prompt caching for system prompts
- Rate limit detection and automatic retry

### Key Patterns
- All handlers are async coroutines (python-telegram-bot v21 async API)
- APScheduler runs background tasks (daily summaries, morning messages)
- SQLite3 database for persistence
- Environment-driven configuration via `.env` (loaded by python-dotenv)

## Configuration

Key environment variables (see `.env.example`):
- `TOKEN` - Telegram bot token
- `OPENAI_API_KEY`, `OPENAI_MODEL` (default: `gpt-4.1-mini`)
- `OPENAI_FALLBACKS` - Comma-separated fallback models
- `GROQ_API_KEY`, `GROQ_MODEL` - Groq fallback
- `MAMULYA_DIALOGUE_STYLE` - `auto`|`kind`|`rude`
- `MAMULYA_SUMMARY_TONE` - `mellow`|`balanced`|`spicy`
- `MAMULYA_CONTEXT_DEPTH` - Messages in prompt (3-50)

## Testing

Tests use pytest with `asyncio_mode = auto`. Key test areas:
- `test_ai_client_integration.py` - OpenAI streaming, fallbacks
- `test_webapp.py` - Flask API endpoints
- `test_bottle_game.py`, `test_horoscope.py`, etc. - Feature tests

## Code Standards

### Fail Fast and Loud
- Fail explicitly when requirements aren't met (throw exceptions, return error results)
- Never silently skip, suppress exceptions, or return null/defaults that hide problems
- No broad exception catching (avoid `except Exception:` without re-raising)
- Provide clear, actionable error messages explaining what went wrong and how to fix it

### Typing
- All new code must be fully typed
- Never use `Any` type

## Version Management

Uses git tags for versioning. The `get_version()` utility returns: `v{tag}-{commits}-{hash}-{dirty}`
