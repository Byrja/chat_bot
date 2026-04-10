# MD4 Deployment Checklist (MVP)

## Secrets and config
- [ ] Rotate bot token if ever leaked
- [ ] `.env` configured:
  - TELEGRAM_BOT_TOKEN
  - MAIN_CHAT_ID
  - ADMIN_CHAT_ID
  - ADMIN_USER_IDS
  - SQLITE_PATH
- [ ] Bot has admin rights in MAIN_CHAT_ID (invite creation)
- [ ] Bot present in ADMIN_CHAT_ID

## Runtime
- [ ] Virtualenv created and deps installed
- [ ] DB path writable
- [ ] `python main.py` starts without errors

## Verification
- [ ] `pytest` is green
- [ ] MVP smoke checklist complete
- [ ] moderation approve/reject manually verified

## Rollback
- [ ] Keep previous commit hash and service unit/script
- [ ] Backup DB before migration-sensitive changes
