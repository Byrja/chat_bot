"""Тесты для ChatMember инвалидации кэша админов."""
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock

from bot.config import Settings
from bot.services.rbac import (
    invalidate_chat_admins,
    is_chat_admin_cmd,
)
from bot.handlers.chat_events import on_my_chat_member


MAIN_CHAT = -1002366284654
OTHER_CHAT = -100999000999
OWNER = 472144090
GLOBUS = 772520960


def _ctx(*, cache_admins: list[int] | None = None, api_admins: list[int] | None = None):
    bot_data: dict = {"settings": _settings()}
    if cache_admins is not None:
        bot_data["tg_admins_cache"] = {
            MAIN_CHAT: {"ts": time.monotonic(), "ids": set(cache_admins), "ok": True},
        }
    application = MagicMock()
    application.bot_data = bot_data
    bot = MagicMock()
    if api_admins is not None:
        bot.get_chat_administrators = AsyncMock(return_value=[
            MagicMock(user=MagicMock(id=u)) for u in api_admins
        ])
    else:
        bot.get_chat_administrators = AsyncMock(return_value=[])
    ctx = MagicMock()
    ctx.application = application
    ctx.bot = bot
    return ctx, bot


def _settings() -> Settings:
    return Settings(
        telegram_bot_token="x",
        main_chat_id=MAIN_CHAT,
        admin_chat_id=2,
        admin_user_ids={OWNER},
        sqlite_path="./x.db",
        app_env="test",
    )


# ─── on_my_chat_member ───────────────────────────────────────────────


def test_on_my_chat_member_clears_main_chat_cache():
    """MyChatMember (статус самого бота) сбрасывает кэш для chat_id."""
    ctx, _ = _ctx(cache_admins=[GLOBUS])
    assert MAIN_CHAT in ctx.application.bot_data["tg_admins_cache"]

    update = MagicMock()
    update.effective_chat = MagicMock()
    update.effective_chat.id = MAIN_CHAT

    asyncio.run(on_my_chat_member(update, ctx))

    assert MAIN_CHAT not in ctx.application.bot_data["tg_admins_cache"]


def test_on_my_chat_member_no_chat_safe():
    """Нет effective_chat — no-op, без exception."""
    ctx, _ = _ctx(cache_admins=[GLOBUS])
    update = MagicMock()
    update.effective_chat = None
    asyncio.run(on_my_chat_member(update, ctx))
    assert MAIN_CHAT in ctx.application.bot_data["tg_admins_cache"]


def test_on_my_chat_member_other_chat_only_clears_that():
    """Событие в чужом чате — кэш только этого чата, main не трогаем."""
    ctx, _ = _ctx(cache_admins=[GLOBUS])
    # Добавим кэш для чужого чата
    ctx.application.bot_data["tg_admins_cache"][OTHER_CHAT] = {
        "ts": time.monotonic(), "ids": {42}, "ok": True,
    }

    update = MagicMock()
    update.effective_chat = MagicMock(id=OTHER_CHAT)
    asyncio.run(on_my_chat_member(update, ctx))

    assert OTHER_CHAT not in ctx.application.bot_data["tg_admins_cache"]
    assert MAIN_CHAT in ctx.application.bot_data["tg_admins_cache"]


def test_on_my_chat_member_then_api_refetches():
    """После my_chat_member invalidate — следующий is_chat_admin_cmd идёт в API."""
    ctx, bot = _ctx(cache_admins=[GLOBUS], api_admins=[42])
    r1 = asyncio.run(is_chat_admin_cmd(ctx, MAIN_CHAT, GLOBUS))
    assert r1 is True
    assert bot.get_chat_administrators.call_count == 0

    update = MagicMock()
    update.effective_chat = MagicMock(id=MAIN_CHAT)
    asyncio.run(on_my_chat_member(update, ctx))

    r2 = asyncio.run(is_chat_admin_cmd(ctx, MAIN_CHAT, 42))
    assert r2 is True
    assert bot.get_chat_administrators.call_count == 1


# ─── member_status_event (CHAT_MEMBER) ───────────────────────────────


def test_member_status_event_clears_main_chat_cache():
    """CHAT_MEMBER в main chat — кэш сбрасывается."""
    from bot.handlers.member_events import member_status_event

    ctx, _ = _ctx(cache_admins=[GLOBUS])

    cmu = MagicMock()
    cmu.chat.id = MAIN_CHAT
    update = MagicMock()
    update.chat_member = cmu
    update.effective_chat = MagicMock(id=MAIN_CHAT)

    asyncio.run(member_status_event(update, ctx))

    assert MAIN_CHAT not in ctx.application.bot_data["tg_admins_cache"]


def test_member_status_event_in_main_chat_subsequent_api_call():
    """Сценарий целиком: cached → chat_member event → API."""
    from bot.handlers.member_events import member_status_event

    ctx, bot = _ctx(cache_admins=[GLOBUS], api_admins=[GLOBUS, 42])

    # cached — без API
    asyncio.run(is_chat_admin_cmd(ctx, MAIN_CHAT, GLOBUS))
    assert bot.get_chat_administrators.call_count == 0

    # CHAT_MEMBER event — invalidate
    cmu = MagicMock()
    cmu.chat.id = MAIN_CHAT
    update = MagicMock()
    update.chat_member = cmu
    update.effective_chat = MagicMock(id=MAIN_CHAT)
    asyncio.run(member_status_event(update, ctx))

    # Следующий вызов идёт в API
    asyncio.run(is_chat_admin_cmd(ctx, MAIN_CHAT, 42))
    assert bot.get_chat_administrators.call_count == 1
