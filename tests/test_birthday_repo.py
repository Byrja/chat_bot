from bot.db import init_db
from bot.repositories.profile import set_birthdate
from bot.repositories.birthday import get_birthdays_for_offset


def test_get_birthdays_for_offset_today(tmp_path):
    db_file = tmp_path / "md4_bday.db"
    init_db(str(db_file))

    from datetime import date

    t = date.today()
    set_birthdate(str(db_file), 123, t.day, t.month)

    rows, _ = get_birthdays_for_offset(str(db_file), 0)
    assert any(uid == 123 for uid, _, _ in rows)
