from bot.services.timeparse import parse_mute_duration


def test_parse_mute_duration_valid():
    assert parse_mute_duration("30m") is not None
    assert parse_mute_duration("2h") is not None
    assert parse_mute_duration("1d") is not None


def test_parse_mute_duration_invalid():
    assert parse_mute_duration("") is None
    assert parse_mute_duration("10x") is None
    assert parse_mute_duration("abc") is None
