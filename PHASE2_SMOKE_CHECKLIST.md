# MD4 Phase 2 Smoke Checklist

## Sanctions
- [ ] `/warn` by reply works for admin
- [ ] `/mute 30m` by reply works for admin
- [ ] `/ban` by reply works for admin
- [ ] non-admin is denied for sanctions commands

## Audit
- [ ] `sanctions` table contains warn/mute/ban records
- [ ] `moderation_events` contains `sanction_warn|sanction_mute|sanction_ban`

## Stats
- [ ] `/admin_stats` accessible for admin
- [ ] `/admin_stats` denied for non-admin
- [ ] counters reflect DB state logically
