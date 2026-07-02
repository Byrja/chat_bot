# Permission Model (Phase 4.x)

## Главное правило
**Админские права определяются Telegram-админкой чата, а не ролью в БД.**

Роли в БД (`admin`, `old`, `trusted`, `newbie`, `lava`) используются ТОЛЬКО для UI
(бейджики, /roles_list, /activity) и НЕ дают доступа к админским командам.

## Источник правды
`bot/services/rbac.py`:
- `is_chat_admin_cmd(context, chat_id, user_id)` — async, главная проверка.
  Источники: `settings.admin_user_ids` (owner / Саша) → Telegram `get_chat_administrators()`
  с кэшем 5 минут.
- `is_chat_admin_cached(...)` — sync, для UI-фильтров (только кэш, без API-вызовов).
- `invalidate_chat_admins(...)` — сброс кэша (вызывать из my_chat_member).
- `has_permission(...)` — DEPRECATED, оставлен для обратной совместимости.
  Возвращает True только для `"activity"`. Для всех остальных команд (warn/mute/ban)
  всегда False.

## Команды, привязанные к Telegram-админке
- /mute, /unmute
- /ban
- /warn, /unwarn, /warnlist
- /all (упоминание всех)
- /mod (мод-панель)
- /quoteslist + просмотр/удаление цитат (через menu и callback)
- /roles (список ролей участников)
- /drama (сброс счётчика драмы)
- /admin_stats
- Все «mod_…» пункты меню (mod / mod_roles / mod_warnlist / mod_quoteslist)
- bottle_result_action («отметить как выполнено/провалено» — админ ИЛИ исполнитель)

## Команды, привязанные к роли
- /activity (leaderboard) — доступна всем ролям через `has_permission(.. "activity")` (бэк-совместимость).
  Реально это просто проверка что роль != "нет роли"; у всех пользователей есть роль (default = newbie).

## Кэш Telegram-админов
- Ключ: `tg_admins_cache[chat_id]` в `application.bot_data`.
- TTL: 5 минут (`_TG_ADMINS_TTL = 5 * 60`).
- Структура: `{"ts": monotonic, "ids": set[int], "ok": bool}`.
- При ошибке API (бот не админ чата) — `ok=False`, возвращаем False.
  Следующий вызов после истечения TTL попробует снова.
- Ручная инвалидация: `invalidate_chat_admins(context, chat_id)`.

## Smoke-тест
- @globus_125 (роль `old` в БД) должен иметь доступ ко всем админским командам,
  потому что он — Telegram-админ MAIN_CHAT_ID.
- @bur (owner) — `ADMIN_USER_IDS=472144090` в env — имеет доступ везде.

## Платформо-специфичное
- MAIN_CHAT_ID и ADMIN_CHAT_ID из env.
- Бот должен быть админом обоих чатов, иначе `get_chat_administrators` упадёт
  и все админские команды будут недоступны (включая у owner из env — там
  проверка до этого шага не доходит).
