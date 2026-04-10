from bot.db import init_db
from bot.repositories.applications import count_submitted_today, get_or_create_draft_application, submit_application, upsert_user


def test_daily_limit_counter(tmp_path):
    db_file = tmp_path / "md4_limit.db"
    init_db(str(db_file))
    upsert_user(str(db_file), 10, "u10", "U10")

    a1 = get_or_create_draft_application(str(db_file), 10)
    submit_application(str(db_file), a1)

    a2 = get_or_create_draft_application(str(db_file), 10)
    submit_application(str(db_file), a2)

    assert count_submitted_today(str(db_file), 10) == 2
