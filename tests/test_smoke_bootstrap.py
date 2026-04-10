from bot.config import load_settings


def test_load_settings_defaults(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("MAIN_CHAT_ID", raising=False)
    monkeypatch.delenv("ADMIN_CHAT_ID", raising=False)
    monkeypatch.delenv("ADMIN_USER_IDS", raising=False)

    s = load_settings()
    assert s.main_chat_id == 0
    assert s.admin_chat_id == 0
    assert s.admin_user_ids == set()
    assert s.sqlite_path
