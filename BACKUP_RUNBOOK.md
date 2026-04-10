# MD4 Backup/Restore Runbook

## Backup DB
```bash
cd /srv/openclaw-bus/chat_bot
./scripts/backup_db.sh ./data/md4.db ./backups
```

## Restore DB
1. Stop bot service:
```bash
systemctl --user stop md4-bot.service
```
2. Restore selected backup:
```bash
cd /srv/openclaw-bus/chat_bot
./scripts/restore_db.sh ./backups/md4_YYYYMMDD_HHMMSS.db ./data/md4.db
```
3. Start service:
```bash
systemctl --user start md4-bot.service
systemctl --user status md4-bot.service --no-pager
```

## Safety notes
- Always make a fresh backup before restore.
- Prefer restore during low activity window.
- Verify `/admin_stats` after restore.
