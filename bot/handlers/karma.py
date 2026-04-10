from telegram import Update
from telegram.ext import ContextTypes

from bot.config import Settings
from bot.db import get_conn
from bot.repositories.karma import apply_karma, get_karma, top_karma


def _settings(context: ContextTypes.DEFAULT_TYPE) -> Settings:
    return context.application.bot_data["settings"]


def _label(db_path: str, chat_id: int, uid: int) -> str:
    conn = get_conn(db_path)
    cur = conn.cursor()
    cur.execute(
        "SELECT COALESCE(username,''), COALESCE(first_name,'') FROM member_activity WHERE chat_id = ? AND tg_user_id = ? ORDER BY updated_at DESC LIMIT 1",
        (chat_id, uid),
    )
    row = cur.fetchone()
    conn.close()
    if row:
        u, f = row
        if u:
            return f"@{u}"
        if f:
            return f
    return str(uid)


async def karma_plus(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _karma_delta(update, context, +1)


async def karma_minus(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _karma_delta(update, context, -1)


async def _karma_delta(update: Update, context: ContextTypes.DEFAULT_TYPE, delta: int) -> None:
    if not update.message or not update.effective_chat or not update.effective_user:
        return
    src = update.message.reply_to_message
    if not src or not src.from_user:
        await update.message.reply_text("Используй команду reply на сообщение участника")
        return
    target = src.from_user
    if target.is_bot:
        await update.message.reply_text("Ботам карму не меняем")
        return
    if target.id == update.effective_user.id:
        await update.message.reply_text("Самому себе карму менять нельзя")
        return

    s = _settings(context)
    apply_karma(s.sqlite_path, update.effective_chat.id, update.effective_user.id, target.id, delta)
    val = get_karma(s.sqlite_path, update.effective_chat.id, target.id)
    sign = "+1" if delta > 0 else "-1"
    await update.message.reply_text(f"Карма {sign} для {_label(s.sqlite_path, update.effective_chat.id, target.id)}\nТекущий баланс: {val}")


async def karma_me(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_chat or not update.effective_user:
        return
    s = _settings(context)
    val = get_karma(s.sqlite_path, update.effective_chat.id, update.effective_user.id)
    await update.message.reply_text(f"Твоя карма: {val}")


async def karma_plusminus_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return
    txt = update.message.text.strip()
    if txt not in {"+", "-"}:
        return
    if not update.message.reply_to_message:
        return
    await _karma_delta(update, context, +1 if txt == "+" else -1)


async def karma_top_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_chat:
        return
    s = _settings(context)
    pos, neg = top_karma(s.sqlite_path, update.effective_chat.id, limit=5)

    lines = ["⚖️ Карма чата", "───────────────────", "🌟 Топ +:"]
    if pos:
        for i, (uid, score) in enumerate(pos, 1):
            lines.append(f"{i}. {_label(s.sqlite_path, update.effective_chat.id, int(uid))} — {int(score)}")
    else:
        lines.append("—")

    lines.append("")
    lines.append("💀 Топ -:")
    if neg:
        for i, (uid, score) in enumerate(neg, 1):
            lines.append(f"{i}. {_label(s.sqlite_path, update.effective_chat.id, int(uid))} — {int(score)}")
    else:
        lines.append("—")

    await update.message.reply_text("\n".join(lines))
