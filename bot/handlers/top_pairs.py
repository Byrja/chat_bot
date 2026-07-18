from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from bot.config import Settings
from bot.repositories.pairs import get_top_pairs
from bot.services.formatting import (
    back_to_menu_kb_any,
    fetch_names_bulk,
    human_date,
    user_link_from_parts,
)


def _settings(context: ContextTypes.DEFAULT_TYPE) -> Settings:
    return context.application.bot_data.get("settings") or context.application.settings


async def show_top_pairs(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message or (update.callback_query.message if update.callback_query else None)
    if not msg or not update.effective_chat:
        return

    s = _settings(context)
    since_days = 7 if context.args and context.args[0].lower() in {"7d", "week"} else None
    rows = get_top_pairs(s.sqlite_path, update.effective_chat.id, limit=10, since_days=since_days)

    back_kb = back_to_menu_kb_any()

    if not rows:
        text = "Пока нет данных по топ-парам (нужны reply-сообщения)."
        if update.callback_query:
            await update.callback_query.edit_message_text(text, reply_markup=back_kb)
        else:
            await msg.reply_text(text, reply_markup=back_kb)
        return

    uids = set()
    for fr, to, _, _ in rows:
        uids.add(int(fr))
        uids.add(int(to))
    names = fetch_names_bulk(s.sqlite_path, update.effective_chat.id, list(uids))

    title = "💬 Топ пар (7 дней)" if since_days else "💬 Топ пар (по reply)"
    lines = [title, "───────────────────"]
    for i, (from_uid, to_uid, cnt, last_at) in enumerate(rows, 1):
        fu, ff = names.get(int(from_uid), ("", ""))
        tu, tf = names.get(int(to_uid), ("", ""))
        lines.append(
            f"{i}. {user_link_from_parts(ff, fu, int(from_uid))} → {user_link_from_parts(tf, tu, int(to_uid))} | {cnt} | {human_date(last_at)}"
        )
    text = "\n".join(lines)

    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode="HTML", reply_markup=back_kb)
    else:
        await msg.reply_text(text, parse_mode="HTML", reply_markup=back_kb)
