from telegram import Update
from telegram.ext import ContextTypes

from bot.config import Settings
from bot.repositories.pairs import get_top_pairs


def _settings(context: ContextTypes.DEFAULT_TYPE) -> Settings:
    return context.application.bot_data["settings"]


async def show_top_pairs(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message or (update.callback_query.message if update.callback_query else None)
    if not msg or not update.effective_chat:
        return

    s = _settings(context)
    since_days = 7 if context.args and context.args[0].lower() in {"7d", "week"} else None
    rows = get_top_pairs(s.sqlite_path, update.effective_chat.id, limit=10, since_days=since_days)
    if not rows:
        text = "Пока нет данных по топ-парам (нужны reply-сообщения)."
    else:
        from bot.db import get_conn

        uids = set()
        for fr, to, _, _ in rows:
            uids.add(int(fr))
            uids.add(int(to))

        labels = {uid: str(uid) for uid in uids}
        conn = get_conn(s.sqlite_path)
        cur = conn.cursor()
        for uid in uids:
            cur.execute(
                "SELECT COALESCE(username,''), COALESCE(first_name,'') FROM member_activity WHERE chat_id = ? AND tg_user_id = ? ORDER BY updated_at DESC LIMIT 1",
                (update.effective_chat.id, uid),
            )
            r = cur.fetchone()
            if r:
                uname, fname = r
                labels[uid] = f"@{uname}" if uname else (fname or str(uid))
        conn.close()

        title = "💬 Топ пар (7 дней)" if since_days else "💬 Топ пар (по reply)"
        lines = [title, "───────────────────"]
        for i, (from_uid, to_uid, cnt, last_at) in enumerate(rows, 1):
            lines.append(f"{i}. {labels.get(int(from_uid), from_uid)} → {labels.get(int(to_uid), to_uid)} | {cnt} | {last_at or '—'}")
        text = "\n".join(lines)

    if update.callback_query:
        await update.callback_query.edit_message_text(text)
    else:
        await msg.reply_text(text)
