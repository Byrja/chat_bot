from telegram import Update
from telegram.ext import ContextTypes

from bot.config import Settings
from bot.db import get_conn
from bot.services.rbac import has_permission


def _settings(context: ContextTypes.DEFAULT_TYPE) -> Settings:
    return context.application.bot_data["settings"]


async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_user:
        return

    s = _settings(context)
    if not has_permission(s, s.sqlite_path, update.effective_user.id, "admin_stats"):
        await update.message.reply_text("Недостаточно прав")
        return

    conn = get_conn(s.sqlite_path)
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM applications")
    total = int(cur.fetchone()[0] or 0)
    cur.execute("SELECT COUNT(*) FROM applications WHERE status='submitted'")
    submitted = int(cur.fetchone()[0] or 0)
    cur.execute("SELECT COUNT(*) FROM applications WHERE status='approved'")
    approved = int(cur.fetchone()[0] or 0)
    cur.execute("SELECT COUNT(*) FROM applications WHERE status='rejected'")
    rejected = int(cur.fetchone()[0] or 0)

    cur.execute("SELECT COUNT(*) FROM sanctions WHERE action='warn'")
    warns = int(cur.fetchone()[0] or 0)
    cur.execute("SELECT COUNT(*) FROM sanctions WHERE action='mute'")
    mutes = int(cur.fetchone()[0] or 0)
    cur.execute("SELECT COUNT(*) FROM sanctions WHERE action='ban'")
    bans = int(cur.fetchone()[0] or 0)

    conn.close()

    decision_total = approved + rejected
    approve_rate = (approved / decision_total * 100) if decision_total else 0.0

    text = (
        "📊 МДЧ Admin Stats\n"
        "───────────────────\n"
        f"Applications total: {total}\n"
        f"Submitted: {submitted}\n"
        f"Approved: {approved}\n"
        f"Rejected: {rejected}\n"
        f"Approve rate: {approve_rate:.1f}%\n\n"
        "Sanctions:\n"
        f"Warn: {warns}\n"
        f"Mute: {mutes}\n"
        f"Ban: {bans}"
    )
    await update.message.reply_text(text)
