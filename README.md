# MD4 Bot

Telegram onboarding + moderation bot.

## Core flow
1. User starts bot and fills questionnaire step-by-step.
2. Answers are stored in DB.
3. Completed application is sent to admin moderation chat.
4. Admin chooses approve/reject via inline buttons (optional reason on reject).
5. If approved: bot creates unique one-time invite link (TTL 24h) and sends it to user in private chat.
6. If rejected: bot sends rejection notice (with optional reason).

## Additional moderation features (MVP)
- Admin commands for warning users.
- Temporary mute.
- Ban.

## Tech stack (MVP)
- Python 3.11+
- python-telegram-bot
- SQLite
- pytest

## Status
Planning + architecture setup in progress.
