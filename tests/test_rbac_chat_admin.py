"""Unit tests for the new Telegram-admin based permission model."""
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock

from bot.config import Settings
from bot.services.rbac import (
    effective_role,
    has_permission,
    invalidate_chat_admins,
    is_chat_admin_cached,
    is_chat_admin_cmd,
)


CHAT = -1002366284654
OWNER = 472144090
GLOBUS = 772520960
RANDOM = 123456


def _settings() -> Settings:
    return Settings(
        telegram_bot_token="x",
        main_chat_id=CHAT,
        admin_chat_id=2,
        admin_user_ids={OWNER},
        sqlite_path="./x.db",
        app_env="test",
    )


def _ctx(*, cache_admins: list[int] | None = None,
         cache_ok: bool = True,
         api_admins: list[int] | None = None,
         api_error: Exception | None = None):
    bot_data: dict = {"settings": _settings()}
    if cache_admins is not None:
        bot_data["tg_admins_cache"] = {
            CHAT: {"ts": time.monotonic(), "ids": set(cache_admins), "ok": cache_ok},
        }
    application = MagicMock()
    application.bot_data = bot_data
    bot = MagicMock()
    if api_error is not None:
        bot.get_chat_administrators = AsyncMock(side_effect=api_error)
    elif api_admins is not None:
        bot.get_chat_administrators = AsyncMock(return_value=[
            MagicMock(user=MagicMock(id=u)) for u in api_admins
        ])
    else:
        bot.get_chat_administrators = AsyncMock(return_value=[])
    ctx = MagicMock()
    ctx.application = application
    ctx.bot = bot
    return ctx, bot


# ─── is_chat_admin_cmd (async) ────────────────────────────────────────


def test_owner_true_without_api():
    ctx, bot = _ctx()
    r = asyncio.run(is_chat_admin_cmd(ctx, CHAT, OWNER))
    assert r is True
    assert bot.get_chat_administrators.call_count == 0


def test_globus_true_via_api_then_cached():
    """Пустой кэш → API; повторный вызов → 0 API (cache hit)."""
    ctx, bot = _ctx(api_admins=[GLOBUS, 999_999])
    r1 = asyncio.run(is_chat_admin_cmd(ctx, CHAT, GLOBUS))
    assert r1 is True
    assert bot.get_chat_administrators.call_count == 1

    r2 = asyncio.run(is_chat_admin_cmd(ctx, CHAT, GLOBUS))
    assert r2 is True
    assert bot.get_chat_administrators.call_count == 1


def test_random_user_false():
    ctx, bot = _ctx(api_admins=[GLOBUS, 999_999])
    r = asyncio.run(is_chat_admin_cmd(ctx, CHAT, RANDOM))
    assert r is False


def test_api_error_returns_false():
    ctx, bot = _ctx(api_error=RuntimeError("not admin"))
    r = asyncio.run(is_chat_admin_cmd(ctx, CHAT, GLOBUS))
    assert r is False
    assert ctx.application.bot_data["tg_admins_cache"][CHAT]["ok"] is False


def test_invalidate_forces_refresh():
    ctx, bot = _ctx(cache_admins=[GLOBUS])
    asyncio.run(is_chat_admin_cmd(ctx, CHAT, GLOBUS))
    assert bot.get_chat_administrators.call_count == 0

    invalidate_chat_admins(ctx, CHAT)
    bot.get_chat_administrators = AsyncMock(return_value=[
        MagicMock(user=MagicMock(id=42)),
    ])
    r = asyncio.run(is_chat_admin_cmd(ctx, CHAT, 42))
    assert r is True
    assert bot.get_chat_administrators.call_count == 1


def test_ttl_expiry_refreshes():
    ctx, bot = _ctx(cache_admins=[GLOBUS])
    asyncio.run(is_chat_admin_cmd(ctx, CHAT, GLOBUS))
    assert bot.get_chat_administrators.call_count == 0

    entry = ctx.application.bot_data["tg_admins_cache"][CHAT]
    entry["ts"] = time.monotonic() - 6 * 60  # > 5 мин TTL

    bot.get_chat_administrators = AsyncMock(return_value=[
        MagicMock(user=MagicMock(id=GLOBUS)),
    ])
    r = asyncio.run(is_chat_admin_cmd(ctx, CHAT, GLOBUS))
    assert r is True
    assert bot.get_chat_administrators.call_count == 1


def test_chat_id_none_returns_false():
    ctx, bot = _ctx()
    r = asyncio.run(is_chat_admin_cmd(ctx, None, GLOBUS))
    assert r is False
    assert bot.get_chat_administrators.call_count == 0


def test_cached_entry_used_directly():
    """Предзаполненный кэш (ok=True) → 0 API-вызовов."""
    ctx, bot = _ctx(cache_admins=[GLOBUS])
    r = asyncio.run(is_chat_admin_cmd(ctx, CHAT, GLOBUS))
    assert r is True
    assert bot.get_chat_administrators.call_count == 0


def test_cached_ok_false_triggers_retry():
    """ok=False в кэше → всегда пробуем API снова (best-effort, бот мог стать админом)."""
    ctx, bot = _ctx(cache_admins=[], cache_ok=False, api_admins=[GLOBUS])
    r = asyncio.run(is_chat_admin_cmd(ctx, CHAT, GLOBUS))
    assert r is True
    assert bot.get_chat_administrators.call_count == 1
    # Кэш обновился, ok=True
    assert ctx.application.bot_data["tg_admins_cache"][CHAT]["ok"] is True


# ─── is_chat_admin_cached (sync) ──────────────────────────────────────


def test_cached_owner_always_true():
    ctx, _ = _ctx()
    assert is_chat_admin_cached(ctx, CHAT, OWNER) is True


def test_cached_uses_cache_only():
    """sync-функция НЕ делает API-вызовов, без кэша → False."""
    ctx, bot = _ctx()
    r = is_chat_admin_cached(ctx, CHAT, GLOBUS)
    assert r is False
    assert bot.get_chat_administrators.call_count == 0


def test_cached_returns_true_after_population():
    ctx, _ = _ctx(api_admins=[GLOBUS])
    asyncio.run(is_chat_admin_cmd(ctx, CHAT, GLOBUS))
    assert is_chat_admin_cached(ctx, CHAT, GLOBUS) is True


def test_cached_after_api_error_returns_false():
    ctx, _ = _ctx(api_error=RuntimeError("nope"))
    asyncio.run(is_chat_admin_cmd(ctx, CHAT, GLOBUS))
    assert is_chat_admin_cached(ctx, CHAT, GLOBUS) is False


def test_cached_expired_returns_false():
    """TTL > 5 мин — sync считает запись протухшей (False)."""
    ctx, _ = _ctx(cache_admins=[GLOBUS])
    ctx.application.bot_data["tg_admins_cache"][CHAT]["ts"] = time.monotonic() - 6 * 60
    assert is_chat_admin_cached(ctx, CHAT, GLOBUS) is False


# ─── has_permission (deprecated) ─────────────────────────────────────


def test_has_permission_activity_always_true():
    s = _settings()
    for uid in (OWNER, GLOBUS, RANDOM):
        assert has_permission(s, "./x.db", uid, "activity") is True


def test_has_permission_admin_commands_always_false():
    s = _settings()
    for cmd in ("warn", "mute", "ban", "admin_stats"):
        for uid in (OWNER, GLOBUS, RANDOM):
            assert has_permission(s, "./x.db", uid, cmd) is False


# ─── effective_role (UI) ──────────────────────────────────────────────


def test_effective_role_owner_returns_admin():
    s = _settings()
    from bot.db import init_db
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        db = f"{td}/x.db"
        init_db(db)
        assert effective_role(s, db, OWNER) == "admin"
        assert effective_role(s, db, RANDOM) == "newbie"
