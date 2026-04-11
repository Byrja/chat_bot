from bot.config import Settings
from bot.repositories.roles import get_role


_ALLOWED = {
    "warn": {"admin"},
    "mute": {"admin"},
    "ban": {"admin"},
    "admin_stats": {"admin"},
    "activity": {"admin", "old", "trusted", "newbie", "lava"},
}


def effective_role(settings: Settings, db_path: str, tg_user_id: int) -> str:
    # hard override from env admins
    if tg_user_id in settings.admin_user_ids:
        return "admin"
    return get_role(db_path, tg_user_id)


def has_permission(settings: Settings, db_path: str, tg_user_id: int, command: str) -> bool:
    role = effective_role(settings, db_path, tg_user_id)
    allowed = _ALLOWED.get(command)
    if not allowed:
        return False
    return role in allowed
