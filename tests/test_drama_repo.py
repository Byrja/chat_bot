from bot.db import init_db
from bot.repositories.drama import get_days_without_drama, reset_drama


def test_drama_reset_and_days(tmp_path):
    db_file = tmp_path / "md4_drama.db"
    init_db(str(db_file))

    # no row yet
    assert get_days_without_drama(str(db_file), 1) == 0

    reset_drama(str(db_file), 1, 100)
    assert get_days_without_drama(str(db_file), 1) == 0
