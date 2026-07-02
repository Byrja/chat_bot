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


def test_rbac_matrix_admin(tmp_path):
    """has_permission теперь только для activity. Админские права — в is_chat_admin_cmd."""
    db_file = tmp_path / "md4_rbac_matrix.db"
    init_db(str(db_file))
    s = _settings()

    set_role(str(db_file), 100, "old", 9001)
    set_role(str(db_file), 101, "trusted", 9001)
    set_role(str(db_file), 102, "newbie", 9001)
    set_role(str(db_file), 103, "lava", 9001)
    set_role(str(db_file), 104, "admin", 9001)

    # activity — для всех ролей (через has_permission бэк-совместимость)
    for uid in (100, 101, 102, 103, 104, 9001):
        assert has_permission(s, str(db_file), uid, "activity") is True

    # admin-команды — больше не от роли (deprecated ключи возвращают False)
    for cmd in ("warn", "mute", "ban", "admin_stats"):
        for uid in (100, 101, 102, 103, 104, 9001):
            assert has_permission(s, str(db_file), uid, cmd) is False, (
                f"{uid}/{cmd} должен быть False — админские права идут через is_chat_admin_cmd"
            )


def test_default_role_newbie(tmp_path):
    """Без записи в member_roles роль = newbie."""
    from bot.services.rbac import effective_role
    db_file = tmp_path / "md4_default.db"
    init_db(str(db_file))
    s = _settings()
    # 9999 — нет в admin_user_ids и нет записи в member_roles
    assert effective_role(s, str(db_file), 9999) == "newbie"
    # 9001 — в admin_user_ids → admin
    assert effective_role(s, str(db_file), 9001) == "admin"
