from bot.db import init_db
from bot.repositories.relations import add_goat, create_friend_request, accept_friend_request, relation_stats


def test_relations_flow(tmp_path):
    db = tmp_path / "md4_rel.db"
    init_db(str(db))

    fid = create_friend_request(str(db), 1, 10, 20)
    assert fid and fid > 0
    assert accept_friend_request(str(db), fid, 20) is True

    assert add_goat(str(db), 1, 10, 30) is True

    st = relation_stats(str(db), 1, 10)
    assert st["friends"] == 1
    assert st["goats_out"] == 1
