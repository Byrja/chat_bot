from bot.db import init_db
from bot.repositories.roles import get_role, set_role
from bot.config import Settings
from bot.services.rbac import has_permission


def _settings() -> Settings:
    return Settings(
        telegram_bot_token="x",
        main_chat_id=1,
        admin_chat_id=2,
        admin_user_ids={777},
        sqlite_path="./x.db",
        app_env="test",
    )


def test_default_role_newbie(tmp_path):
    db_file = tmp_path / "md4_roles.db"
    init_db(str(db_file))
    assert get_role(str(db_file), 123) == "newbie"


def test_set_role_and_permissions(tmp_path):
    db_file = tmp_path / "md4_roles2.db"
    init_db(str(db_file))
    assert set_role(str(db_file), 123, "old", 777) is True
    assert get_role(str(db_file), 123) == "old"

    s = _settings()
    assert has_permission(s, str(db_file), 123, "activity") is True
    assert has_permission(s, str(db_file), 123, "warn") is False
    assert has_permission(s, str(db_file), 777, "warn") is True
