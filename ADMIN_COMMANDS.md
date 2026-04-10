# MD4 Admin Commands (MVP)

## Sanctions

### `/warn [reason...]`
- Use as reply to user's message.
- Adds warning record to DB + audit event.

### `/mute <duration> [reason...]`
- Use as reply to user's message.
- Duration format:
  - `30m` (minutes)
  - `2h` (hours)
  - `1d` (days)
- Restricts user messaging in current chat.
- Adds mute record to DB + audit event.

### `/ban [reason...]`
- Use as reply to user's message.
- Bans user from current chat.
- Adds ban record to DB + audit event.

### `/admin_stats`
- Shows application funnel and sanctions counters.
- Admin-only.

### `/activity`
- Top nolifers (all-time) by message count + last message date.

### `/top_week`
- Top nolifers for last 7 days.

### `/role <admin|old|trusted|newbie>`
- Admin-only (from `ADMIN_USER_IDS`).
- Use as reply to a user's message.
- Sets participant role.

### `/mod`
- Admin-only.
- Use as reply to a user's message.
- Opens quick inline moderation panel (warn / mute30 / ban).

### `/whois`
- If used in reply: shows target user's role.
- Without reply: shows your role.

### `/menu`
- Opens inline navigation menu with role-based sections.

### `анкета @username`
- Text trigger in chat.
- Bot posts the latest non-draft questionnaire for that username.

### `/mute_me [minutes]`
- Available for all participants.
- Self-mutes sender in current chat. Default: 30 minutes.
- Also available via `⚙️ Настройки` in inline menu.

### `/horoscope`
- Personalized short horoscope by zodiac sign.
- Requires birthdate in settings.
- Uses OpenRouter model with local fallback.

### Social quick notes
- `+` or `-` as reply to message adjusts karma.
- Bottle game has 5-minute chat cooldown.

### `/hipish`
- Available for all participants.
- Mentions configured admins.

## Notes
- Commands available only for IDs listed in `ADMIN_USER_IDS`.
- Bot must have sufficient admin rights in target chat.
