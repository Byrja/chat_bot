from bot.db import init_db
from bot.repositories.karma import apply_karma, get_karma, top_karma


def test_karma_apply_and_top(tmp_path):
    db_file = tmp_path / "md4_karma.db"
    init_db(str(db_file))

    apply_karma(str(db_file), 1, 10, 20, +1)
    apply_karma(str(db_file), 1, 11, 20, +1)
    apply_karma(str(db_file), 1, 10, 30, -1)

    assert get_karma(str(db_file), 1, 20) == 2
    assert get_karma(str(db_file), 1, 30) == -1

    pos, neg = top_karma(str(db_file), 1, 5)
    assert int(pos[0][0]) == 20
    assert int(neg[0][0]) == 30
