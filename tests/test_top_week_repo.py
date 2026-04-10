from bot.db import init_db
from bot.repositories.activity import bump_message_activity, get_top_week_activity


def test_top_week_activity(tmp_path):
    db_file = tmp_path / "md4_week.db"
    init_db(str(db_file))

    bump_message_activity(str(db_file), 1, 10, "u10", "U10")
    bump_message_activity(str(db_file), 1, 10, "u10", "U10")
    bump_message_activity(str(db_file), 1, 20, "u20", "U20")

    rows = get_top_week_activity(str(db_file), 1, 10)
    assert len(rows) >= 2
    assert rows[0][0] == 10
    assert rows[0][1] == 2
