# MD4 Roadmap

## Phase 0 — Foundation (current)
- [ ] Requirements frozen
- [ ] Architecture docs
- [ ] DB schema
- [ ] Security baseline (secrets/roles)
- [ ] Test plan + release gates

## Phase 1 — MVP Core
- [ ] Questionnaire state machine
- [ ] Save draft and final application in DB
- [ ] Preview + edit before submit
- [ ] Send application to admin chat
- [ ] Admin approve/reject with inline actions
- [ ] Reject reason support (optional)
- [ ] One-time invite generation (24h, 1 user)
- [ ] User notifications for approve/reject
- [ ] Reapply after reject
- [ ] Daily user limit (2 applications/day)

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
