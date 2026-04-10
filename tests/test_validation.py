from bot.services.validation import validate_age


def test_validate_age_ok():
    assert validate_age("18") == 18


def test_validate_age_fail():
    assert validate_age("abc") is None
    assert validate_age("9") is None
    assert validate_age("120") is None
