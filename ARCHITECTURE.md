# MD4 Architecture

## Components
- `bot/app.py` — Telegram app bootstrap, handlers wiring.
- `bot/handlers/` — command and callback handlers.
- `bot/services/questionnaire.py` — step engine + validation.
- `bot/services/moderation.py` — approve/reject + invite issuance.
- `bot/services/sanctions.py` — warn/mute/ban helpers.
- `bot/db.py` — sqlite connection + migrations.
- `bot/repositories/` — DB access layer.
- `bot/models.py` — dataclasses/enums.

## Core entities
- Application
- ApplicationAnswer
- ModerationDecision
- InviteIssue
- SanctionAction

## Access model
- User-facing bot chat: onboarding + status notifications.
- Admin moderation chat: review and decision actions.
- Main community chat: destination for approved users.

## Reliability principles
- Every admin decision is idempotent.
- Invite generation only after approved status transaction committed.
- Callback actions validated by role + decision state.
- All critical actions logged in audit table.
