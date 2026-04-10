from bot.db import init_db
from bot.repositories.activity import bump_message_activity, get_top_activity


def test_activity_top_order(tmp_path):
    db_file = tmp_path / "md4_activity.db"
    init_db(str(db_file))

    chat_id = 1
    bump_message_activity(str(db_file), chat_id, 101, "u1", "U1")
    bump_message_activity(str(db_file), chat_id, 101, "u1", "U1")
    bump_message_activity(str(db_file), chat_id, 202, "u2", "U2")

    rows = get_top_activity(str(db_file), chat_id, limit=10)
    assert len(rows) == 2
    assert rows[0][0] == 101
    assert rows[0][3] == 2
