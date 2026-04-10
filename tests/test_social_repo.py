from bot.db import init_db
from bot.repositories.social import create_bottle_game, resolve_bottle_game


def test_bottle_resolve_once(tmp_path):
    db_file = tmp_path / "md4_social.db"
    init_db(str(db_file))

    gid = create_bottle_game(str(db_file), 1, 10, 20, 30)
    assert gid > 0

    r1 = resolve_bottle_game(str(db_file), gid, "done")
    assert r1 is not None

    r2 = resolve_bottle_game(str(db_file), gid, "fail")
    assert r2 is None
