# MD4 Bot (@MD4_byrbot)

Telegram onboarding + moderation + engagement bot for MD4 community.

## Core flow

1. User starts bot (`/start`) and fills onboarding questionnaire step-by-step.
2. Answers are stored in SQLite (`applications`, `application_answers`).
3. Completed application is sent to admin moderation chat.
4. Admin chooses approve/reject via inline buttons; rejection supports a reason.
5. If approved: bot creates a one-time invite link (TTL 24h) and sends it to user in private chat.
6. If rejected: bot sends rejection notice with optional reason.

## Moderation

- `/mod` — opens moderator menu.
- **Профили участников** — inline list of chat members with:
  - profile card (name, username, role, message count, last activity, warns)
  - latest onboarding questionnaire answers
  - role switching buttons
  - warn / 30m mute / ban buttons
  - notes (read + add)
- `/warn` reply to user message — issue warning.
- `/unwarn @username` or via button — remove last warning.
- `/warnlist` / menu **Список осуждённых** — warned users list.
- `/mute`, `/unmute`, `/ban` — admin sanctions.
- `/role`, `/roles`, `/whois` — role management.

## Engagement features

- `/activity`, `/today_top`, `/top_week` — activity tops.
- `/top_pairs` — most replying pairs.
- `/karma`, `/karma_top` — karma.
- `/plus`, `/minus`, `/relation` — friend/foe relations.
- `/bottle` — bottle game.
- `/quote`, `/quotes`, `/randomquote`, `/latest_quote`, `/quoteslist` — quotes system.
- `/days_without_drama`, `/drama` — drama counter.
- `/horoscope` — daily horoscope.
- `/hipish`, `/all`, `/mute_me`, `/topicid` — utility commands.

## UI conventions

- User mentions in lists and stats are rendered as HTML links: `<a href="tg://user?id=UID">first_name</a>`.
- No `@username` tagging in passive lists (tops, quotes, profiles, statuses, warned list).
- Plain `@username` is used only when intentional tagging is required (`/hipish`, `/all`).
- Datetime helpers normalize naive SQLite timestamps to UTC before formatting.

## Tech stack

- Python 3.11+
- python-telegram-bot
- SQLite
- pytest

## Paths

- Code: `/srv/openclaw-bus/chat_bot/`
- DB: `/srv/openclaw-bus/chat_bot/data/md4.db`
- Log: `/srv/openclaw-bus/chat_bot/logs/bot.log`
- Run: `python main.py` from `/srv/openclaw-bus/chat_bot/`

## Status

Production. Last major update: moderator profile panel + UX audit (July 2026).
