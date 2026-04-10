from bot.db import init_db
from bot.repositories.pairs import bump_reply_pair, get_top_pairs


def test_pairs_tracking(tmp_path):
    db_file = tmp_path / "md4_pairs.db"
    init_db(str(db_file))

    bump_reply_pair(str(db_file), 1, 10, 20)
    bump_reply_pair(str(db_file), 1, 10, 20)
    bump_reply_pair(str(db_file), 1, 11, 21)

    rows = get_top_pairs(str(db_file), 1, 10)
    assert len(rows) == 2
    assert rows[0][0] == 10
    assert rows[0][1] == 20
    assert rows[0][2] == 2
