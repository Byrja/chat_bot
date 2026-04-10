from bot.config import Settings
from bot.db import init_db
from bot.repositories.roles import set_role
from bot.services.rbac import has_permission


def _settings() -> Settings:
    return Settings(
        telegram_bot_token="x",
        main_chat_id=1,
        admin_chat_id=2,
        admin_user_ids={9001},
        sqlite_path="./x.db",
        app_env="test",
    )


def test_rbac_matrix(tmp_path):
    db_file = tmp_path / "md4_rbac_matrix.db"
    init_db(str(db_file))
    s = _settings()

    set_role(str(db_file), 100, "old", 9001)
    set_role(str(db_file), 101, "trusted", 9001)
    set_role(str(db_file), 102, "newbie", 9001)

    # admin
    assert has_permission(s, str(db_file), 9001, "warn") is True
    assert has_permission(s, str(db_file), 9001, "mute") is True
    assert has_permission(s, str(db_file), 9001, "ban") is True
    assert has_permission(s, str(db_file), 9001, "admin_stats") is True

    # old
    assert has_permission(s, str(db_file), 100, "warn") is False
    assert has_permission(s, str(db_file), 100, "mute") is False
    assert has_permission(s, str(db_file), 100, "ban") is False
    assert has_permission(s, str(db_file), 100, "activity") is True

    # trusted
    assert has_permission(s, str(db_file), 101, "warn") is False
    assert has_permission(s, str(db_file), 101, "mute") is False
    assert has_permission(s, str(db_file), 101, "ban") is False
    assert has_permission(s, str(db_file), 101, "activity") is True

    # newbie
    assert has_permission(s, str(db_file), 102, "warn") is False
    assert has_permission(s, str(db_file), 102, "mute") is False
    assert has_permission(s, str(db_file), 102, "ban") is False
    assert has_permission(s, str(db_file), 102, "activity") is True
