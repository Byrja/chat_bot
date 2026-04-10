def validate_age(text: str) -> int | None:
    raw = (text or "").strip()
    if not raw.isdigit():
        return None
    age = int(raw)
    if age < 14 or age > 99:
        return None
    return age
