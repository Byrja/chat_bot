# MD4 Deploy Guide

## 1) Prepare env
Create `.env` in repo root:

```env
TELEGRAM_BOT_TOKEN=...
MAIN_CHAT_ID=2366284654
ADMIN_CHAT_ID=3805584677
ADMIN_USER_IDS=472144090
SQLITE_PATH=./data/md4.db
APP_ENV=prod
```

## 2) One-shot local run
```bash
cd /srv/openclaw-bus/chat_bot
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python main.py
```

## 3) Systemd user service install
```bash
mkdir -p ~/.config/systemd/user
cp /srv/openclaw-bus/chat_bot/deploy/md4-bot.service ~/.config/systemd/user/md4-bot.service
systemctl --user daemon-reload
systemctl --user enable --now md4-bot.service
systemctl --user status md4-bot.service --no-pager
```

## 4) Common ops
```bash
systemctl --user restart md4-bot.service
systemctl --user stop md4-bot.service
systemctl --user start md4-bot.service
journalctl --user -u md4-bot.service -n 100 --no-pager
```

## 5) Rollback (to previous commit)
```bash
cd /srv/openclaw-bus/chat_bot
git log --oneline -n 5
git checkout <previous_commit>
systemctl --user restart md4-bot.service
```

## 6) DB backup/restore
See `BACKUP_RUNBOOK.md`.
Quick backup:
```bash
cd /srv/openclaw-bus/chat_bot
./scripts/backup_db.sh ./data/md4.db ./backups
```

## Notes
- Bot must be admin in main group for invite/mute/ban features.
- `/activity` starts tracking from deployment moment.
- Conversation state is persisted in `data/bot_state.pkl` across restarts.
