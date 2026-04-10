# MD4 Test Plan

## Unit tests
- Questionnaire state transitions
- Validation rules per question type
- Daily limit check
- Decision state machine (submitted -> approved/rejected)
- Invite generation constraints (ttl=24h, member_limit=1)

## Integration tests
- Full user flow: start -> fill -> preview -> edit -> submit
- Admin flow: receive application -> approve/reject
- Reapply flow after reject
- Moderation commands warn/mute/ban authorization

## Failure tests
- Double-click approve/reject (idempotency)
- Invite generation API errors
- Missing bot rights in target chat
- DB lock/retry behavior

## Release gate
- All tests green
- Manual smoke in staging chat
- Security checklist (no secrets in repo/logs)
- Rollback plan validated
