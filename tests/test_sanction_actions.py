from bot.db import init_db
from bot.repositories.sanctions import add_sanction


def test_add_ban_and_mute_records(tmp_path):
    db_file = tmp_path / "md4_sanction_actions.db"
    init_db(str(db_file))

    mute_id = add_sanction(str(db_file), 101, "mute", 201, reason="flood", until_at="2026-04-11T00:00:00+00:00")
    ban_id = add_sanction(str(db_file), 102, "ban", 202, reason="abuse", until_at=None)

    assert mute_id > 0
    assert ban_id > 0
