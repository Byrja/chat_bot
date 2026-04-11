from telegram import Update
from telegram.ext import ContextTypes

from bot.config import Settings
from bot.db import get_conn
from bot.repositories.roles import get_role
from bot.services.rbac import has_permission


_ROLE_RU = {
    "admin": "Админ",
    "old": "Олд",
    "trusted": "Проверенный",
    "newbie": "Новичок",
}


def _settings(context: ContextTypes.DEFAULT_TYPE) -> Settings:
    return context.application.bot_data.get("settings") or context.application.settings


async def roles_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_user or not update.effective_chat:
        return

    s = _settings(context)
    if not has_permission(s, s.sqlite_path, update.effective_user.id, "warn"):
        await update.message.reply_text("Недостаточно прав")
        return

    conn = get_conn(s.sqlite_path)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT tg_user_id, COALESCE(username,''), COALESCE(first_name,'')
        FROM member_activity
        WHERE chat_id = ?
        ORDER BY datetime(updated_at) DESC
        LIMIT 200
        """,
        (update.effective_chat.id,),
    )
    rows = cur.fetchall()
    conn.close()

    if not rows:
        await update.message.reply_text("Пока нет данных по участникам в этом чате.")
        return

    # Dedup by uid while preserving recency order.
    seen = set()
    users = []
    for uid, uname, fname in rows:
        uid = int(uid)
        if uid in seen:
            continue
        seen.add(uid)
        users.append((uid, str(uname), str(fname)))

    grouped: dict[str, list[str]] = {"admin": [], "old": [], "trusted": [], "newbie": []}
    for uid, uname, fname in users:
        role = "admin" if uid in s.admin_user_ids else get_role(s.sqlite_path, uid)
        label = (fname or uname or str(uid))
        grouped.setdefault(role, []).append(label)

    lines = ["👥 Статусы участников", "───────────────────"]
    for role_key in ["admin", "old", "trusted", "newbie"]:
        arr = grouped.get(role_key, [])
        lines.append(f"\n{_ROLE_RU.get(role_key, role_key)} ({len(arr)}):")
        if arr:
            for i, label in enumerate(arr, 1):
                lines.append(f"{i}. {label}")
        else:
            lines.append("—")

    # Avoid oversized telegram messages
    text = "\n".join(lines)
    if len(text) > 3900:
        chunks = []
        cur_chunk = []
        cur_len = 0
        for line in lines:
            if cur_len + len(line) + 1 > 3500 and cur_chunk:
                chunks.append("\n".join(cur_chunk))
                cur_chunk = []
                cur_len = 0
            cur_chunk.append(line)
            cur_len += len(line) + 1
        if cur_chunk:
            chunks.append("\n".join(cur_chunk))
        for c in chunks:
            await update.message.reply_text(c)
    else:
        await update.message.reply_text(text)
