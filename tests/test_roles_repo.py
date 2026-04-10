from bot.db import init_db
from bot.repositories.roles import get_role, set_role


def test_set_and_get_role(tmp_path):
    db_file = tmp_path / "md4_role_set.db"
    init_db(str(db_file))

    assert get_role(str(db_file), 1) == "newbie"
    assert set_role(str(db_file), 1, "trusted", assigned_by_tg_user_id=99) is True
    assert get_role(str(db_file), 1) == "trusted"


def test_set_role_invalid(tmp_path):
    db_file = tmp_path / "md4_role_invalid.db"
    init_db(str(db_file))
    assert set_role(str(db_file), 1, "vip", assigned_by_tg_user_id=99) is False
