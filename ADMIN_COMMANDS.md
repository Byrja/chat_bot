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

### `/role <admin|old|trusted|newbie>`
- Admin-only (from `ADMIN_USER_IDS`).
- Use as reply to a user's message.
- Sets participant role.

### `/whois`
- If used in reply: shows target user's role.
- Without reply: shows your role.

## Notes
- Commands available only for IDs listed in `ADMIN_USER_IDS`.
- Bot must have sufficient admin rights in target chat.
