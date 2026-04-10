# MD4 Production Readiness

Date: 2026-04-10
Status: Ready for controlled production beta

## 1) Core Product Flow
- [x] User questionnaire (step-by-step)
- [x] Draft persistence in DB
- [x] Preview + edit + submit
- [x] Daily limit (2/day)
- [x] Admin moderation approve/reject
- [x] Optional reject reason
- [x] One-time invite link (TTL 24h)

## 2) Moderation & Roles
- [x] `/warn` (admin-only)
- [x] `/mute` (admin-only)
- [x] `/ban` (admin-only)
- [x] Role model: admin/old/trusted/newbie
- [x] RBAC checks enforced for sensitive commands
- [x] `/role` and `/whois`

## 3) Activity & Utility
- [x] `/activity` leaderboard (count + last message date)
- [x] `/mute_me` (self mute)
- [x] `/hipish` with 1h anti-spam cooldown

## 4) Hardening
- [x] Anti-race lock for moderation callbacks
- [x] DB status-guard idempotency (`submitted` -> decision once)
- [x] Global error handler + structured logs
- [x] Backup/restore scripts + runbook

## 5) Deployment
- [x] `run.sh`
- [x] `deploy/md4-bot.service`
- [x] `README_DEPLOY.md`
- [x] Deployed on DE host (service active)

## 6) Testing
- [x] Automated tests green (18 passed)
- [x] Smoke checklists prepared:
  - `MVP_SMOKE_CHECKLIST.md`
  - `PHASE2_SMOKE_CHECKLIST.md`
  - `ROLE_PERMISSIONS_CHECKLIST.md`

## 7) Remaining before broader scale
- [ ] Full manual smoke in live chats after latest changes
- [ ] Optional: move service from root user to non-root runtime user
- [ ] Optional: richer analytics ranges (7d/30d filters)

## Release recommendation
Proceed with controlled beta in real audience. Collect incidents/feedback, then batch hotfixes daily.
