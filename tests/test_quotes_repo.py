from bot.db import init_db
from bot.repositories.quotes import add_quote, latest_quote, random_quote


def test_quotes_repo_basic(tmp_path):
    db_file = tmp_path / "md4_quotes.db"
    init_db(str(db_file))

    qid = add_quote(str(db_file), 1, 11, 22, "@user", "hello quote", 33)
    assert qid > 0

    lq = latest_quote(str(db_file), 1)
    assert lq is not None
    assert lq[0] == qid

    rq = random_quote(str(db_file), 1)
    assert rq is not None
