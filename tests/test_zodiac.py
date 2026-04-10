from bot.services.zodiac import zodiac_sign


def test_zodiac_sign_basic():
    assert zodiac_sign(21, 3) == "Овен"
    assert zodiac_sign(20, 4) == "Телец"
    assert zodiac_sign(1, 1) == "Козерог"
