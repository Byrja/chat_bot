# MD4 Release Note — MVP Stage 1

## Included
- Questionnaire flow implemented (steps 1-7 + preview)
- Draft persistence in SQLite
- Submit action and status transition to `submitted`
- Daily submit limit (2/day)
- Admin moderation callbacks:
  - approve -> invite link (24h TTL, one-time)
  - reject -> optional reason flow
- User notifications for approve/reject

## Test status
- Repository and validation tests green (`8 passed`)
- Manual smoke checklist prepared (`MVP_SMOKE_CHECKLIST.md`)

## Known gaps
- Sanctions commands (warn/mute/ban) not wired yet
- Analytics dashboard minimal
- Production service wrapper not yet added in repo
