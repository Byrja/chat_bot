from datetime import datetime, timedelta, timezone


def parse_mute_duration(raw: str) -> datetime | None:
    s = (raw or "").strip().lower()
    if not s:
        return None
    if s.endswith("m") and s[:-1].isdigit():
        return datetime.now(timezone.utc) + timedelta(minutes=int(s[:-1]))
    if s.endswith("h") and s[:-1].isdigit():
        return datetime.now(timezone.utc) + timedelta(hours=int(s[:-1]))
    if s.endswith("d") and s[:-1].isdigit():
        return datetime.now(timezone.utc) + timedelta(days=int(s[:-1]))
    return None
