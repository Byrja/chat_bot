import time

from telegram.ext import ContextTypes

from bot.config import Settings
from bot.repositories.roles import get_role


# Кэш Telegram-админов чата. Ключ: chat_id.
# Значение: {"ts": monotonic_seconds, "ids": set[int], "ok": bool}
# TTL — 5 минут. Инвалидируется автоматически по TTL или вручную
# через invalidate_chat_admins() при my_chat_member updates.
_TG_ADMINS_TTL = 5 * 60  # seconds
_TG_ADMINS_KEY = "tg_admins_cache"  # dict[chat_id -> entry]


def _settings(context: ContextTypes.DEFAULT_TYPE) -> Settings:
    return context.application.bot_data.get("settings") or context.application.settings


def _cache(context: ContextTypes.DEFAULT_TYPE) -> dict:
    cache = context.application.bot_data.get(_TG_ADMINS_KEY)
    if cache is None:
        cache = {}
        context.application.bot_data[_TG_ADMINS_KEY] = cache
    return cache


def invalidate_chat_admins(context: ContextTypes.DEFAULT_TYPE, chat_id: int) -> None:
    """Сбросить кэш админов для конкретного чата (вызывать из my_chat_member)."""
    cache = _cache(context)
    cache.pop(chat_id, None)


async def is_chat_admin_cmd(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    user_id: int,
) -> bool:
    """
    Проверка: является ли user_id админом chat_id.
    Источники (по приоритету):
      1) settings.admin_user_ids (owner / Саша)
      2) Telegram get_chat_administrators() — реальные админы чата, кэш 5 мин

    Возвращает False если бот не админ чата / нет доступа / нет данных / user в blocked.
    """
    s = _settings(context)
    if user_id in s.blocked_user_ids:
        return False
    if user_id in s.admin_user_ids:
        return True

    if chat_id is None:
        return False

    cache = _cache(context)
    entry = cache.get(chat_id)
    now = time.monotonic()
    if entry is None or now - entry.get("ts", 0) > _TG_ADMINS_TTL or not entry.get("ok", False):
        try:
            admins = await context.bot.get_chat_administrators(chat_id)
            ids = {a.user.id for a in admins if a.user}
            cache[chat_id] = {"ts": now, "ids": ids, "ok": True}
        except Exception:
            cache[chat_id] = {"ts": now, "ids": set(), "ok": False}
            return False

    return user_id in cache[chat_id]["ids"]


def is_chat_admin_cached(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    user_id: int,
) -> bool:
    """
    Sync-проверка ТОЛЬКО по кэшу (без API-вызова). True если:
      - user в settings.admin_user_ids
      - в кэше есть свежая запись для chat_id и user там
    Используется для UI-фильтров (показать/спрятать кнопку). Если кэша нет —
    вернёт False, чтобы не ломать UX лишними API-вызовами в hot-path.
    """
    s = _settings(context)
    if user_id in s.blocked_user_ids:
        return False
    if user_id in s.admin_user_ids:
        return True
    if chat_id is None:
        return False
    cache = _cache(context)
    entry = cache.get(chat_id)
    if not entry or not entry.get("ok", False):
        return False
    if time.monotonic() - entry.get("ts", 0) > _TG_ADMINS_TTL:
        return False
    return user_id in entry["ids"]


# ─────────────────────────────────────────────────────────
# Роли (для UI и НЕ для админских команд)
# ─────────────────────────────────────────────────────────


def effective_role(settings: Settings, db_path: str, tg_user_id: int) -> str:
    """Роль из БД. Используется только для UI (бейджики, /activity)."""
    if tg_user_id in settings.admin_user_ids:
        return "admin"
    return get_role(db_path, tg_user_id)


def has_role(settings: Settings, db_path: str, tg_user_id: int, role: str) -> bool:
    return effective_role(settings, db_path, tg_user_id) == role


# Backward-compat alias: старая has_permission(.. "warn") должна вернуть False
# для всех, чтобы случайно не пройти проверку через роли.
def has_permission(settings: Settings, db_path: str, tg_user_id: int, command: str) -> bool:
    """
    DEPRECATED. Админские права больше не зависят от ролей в БД — только от
    Telegram-админки (см. is_chat_admin_cmd). Эта функция сохранена для
    обратной совместимости и теперь возвращает True только для activity.
    """
    if command == "activity":
        return True
    return False
