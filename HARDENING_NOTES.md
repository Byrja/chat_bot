# Hardening Notes

## Anti-race protection for moderation callbacks

Implemented lock key in application runtime:
- key format: `mod_lock:<application_id>`
- protects approve/reject callback from concurrent double-click processing
- secondary protection remains in DB transition guard (`status='submitted'` only)

Result:
- First action wins.
- Concurrent callback receives soft message (`already processing`) or `already handled`.
