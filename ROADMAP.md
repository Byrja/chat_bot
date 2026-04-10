# MD4 Roadmap

## Phase 0 — Foundation (current)
- [ ] Requirements frozen
- [ ] Architecture docs
- [ ] DB schema
- [ ] Security baseline (secrets/roles)
- [ ] Test plan + release gates

## Phase 1 — MVP Core
- [x] Questionnaire state machine
- [x] Save draft and final application in DB
- [x] Preview + edit before submit
- [x] Send application to admin chat
- [x] Admin approve/reject with inline actions
- [x] Reject reason support (optional)
- [x] One-time invite generation (24h, 1 user)
- [x] User notifications for approve/reject
- [x] Reapply after reject
- [x] Daily user limit (2 applications/day)

## Phase 2 — Admin moderation tools
- [ ] Warn command
- [ ] Mute command
- [ ] Ban command
- [ ] Action audit log

## Phase 3 — Product hardening
- [ ] Anti-race protections for approve/reject buttons
- [ ] Idempotent moderation actions
- [ ] Metrics dashboard (/admin_stats)
- [ ] Error monitoring + retries
- [ ] Backup/restore DB script

## Phase 4 — Beta and launch
- [ ] Closed beta with real users
- [ ] Fixes by telemetry
- [ ] Production checklist sign-off
