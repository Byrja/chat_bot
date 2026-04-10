from datetime import date


def zodiac_sign(day: int, month: int) -> str | None:
    if not (1 <= day <= 31 and 1 <= month <= 12):
        return None
    # (month, day, sign_before, sign_after)
    borders = [
        (1, 20, "Козерог", "Водолей"),
        (2, 19, "Водолей", "Рыбы"),
        (3, 21, "Рыбы", "Овен"),
        (4, 20, "Овен", "Телец"),
        (5, 21, "Телец", "Близнецы"),
        (6, 21, "Близнецы", "Рак"),
        (7, 23, "Рак", "Лев"),
        (8, 23, "Лев", "Дева"),
        (9, 23, "Дева", "Весы"),
        (10, 23, "Весы", "Скорпион"),
        (11, 22, "Скорпион", "Стрелец"),
        (12, 22, "Стрелец", "Козерог"),
    ]
    for m, d, before, after in borders:
        if month == m:
            return before if day < d else after
    return None


def today_key() -> str:
    return date.today().isoformat()
