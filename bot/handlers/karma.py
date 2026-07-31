from __future__ import annotations
import logging
from telegram import Update
from telegram.ext import ContextTypes

from bot.config import Settings
from bot.db import get_conn
from bot.repositories.karma import apply_karma, get_karma, top_karma
from bot.services.formatting import (
    back_to_menu_kb_any,
    fetch_names_bulk,
    user_link_from_parts,
    user_link_from_user,
)

logger = logging.getLogger(__name__)


def _settings(context: ContextTypes.DEFAULT_TYPE) -> Settings:
    return context.application.bot_data.get("settings") or context.application.settings


async def karma_plus(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info("[KARMA] /plus called by uid=%s chat=%s", update.effective_user.id if update.effective_user else None, update.effective_chat.id if update.effective_chat else None)
    await _karma_delta(update, context, +1)


async def karma_minus(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info("[KARMA] /minus called by uid=%s chat=%s", update.effective_user.id if update.effective_user else None, update.effective_chat.id if update.effective_chat else None)
    await _karma_delta(update, context, -1)


async def _karma_delta(update: Update, context: ContextTypes.DEFAULT_TYPE, delta: int) -> None:
    if not update.message or not update.effective_chat or not update.effective_user:
        logger.warning("[KARMA] _karma_delta missing update fields")
        return
    src = update.message.reply_to_message
    if not src or not src.from_user:
        logger.info("[KARMA] no reply target")
        await update.message.reply_text("Используй команду reply на сообщение участника")
        return
    target = src.from_user
    if target.is_bot:
        logger.info("[KARMA] target is bot")
        await update.message.reply_text("Ботам карму не меняем")
        return
    if target.id == update.effective_user.id:
        logger.info("[KARMA] self-karma attempt")
        await update.message.reply_text("Самому себе карму менять нельзя")
        return

    s = _settings(context)
    logger.info("[KARMA] apply delta=%s from=%s to=%s chat=%s db=%s", delta, update.effective_user.id, target.id, update.effective_chat.id, s.sqlite_path)
    apply_karma(s.sqlite_path, update.effective_chat.id, update.effective_user.id, target.id, delta)
    val = get_karma(s.sqlite_path, update.effective_chat.id, target.id)
    logger.info("[KARMA] new value for target=%s: %s", target.id, val)
    sign = "+1" if delta > 0 else "-1"
    target_label = user_link_from_user(target)
    await update.message.reply_text(
        f"Карма {sign} для {target_label}\nТекущий баланс: {val}",
        parse_mode="HTML",
    )


async def karma_me(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_chat or not update.effective_user:
        return
    s = _settings(context)
    logger.info("[KARMA] /karma me uid=%s chat=%s db=%s", update.effective_user.id, update.effective_chat.id, s.sqlite_path)
    val = get_karma(s.sqlite_path, update.effective_chat.id, update.effective_user.id)
    logger.info("[KARMA] /karma result uid=%s val=%s", update.effective_user.id, val)
    await update.message.reply_text(
        f"Твоя карма: {val}",
        reply_markup=back_to_menu_kb_any(),
    )


async def karma_plusminus_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return
    txt = update.message.text.strip()
    if txt not in {"+", "-"}:
        return
    if not update.message.reply_to_message:
        return
    logger.info("[KARMA] reply +/- from uid=%s to uid=%s chat=%s", update.effective_user.id if update.effective_user else None, update.message.reply_to_message.from_user.id if update.message.reply_to_message.from_user else None, update.effective_chat.id if update.effective_chat else None)
    await _karma_delta(update, context, +1 if txt == "+" else -1)


async def karma_top_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_chat:
        return
    s = _settings(context)
    logger.info("[KARMA] /karma_top chat=%s", update.effective_chat.id)
    pos, neg = top_karma(s.sqlite_path, update.effective_chat.id, limit=5)
    logger.info("[KARMA] top counts pos=%d neg=%d", len(pos), len(neg))

    uids = {int(uid) for uid, _ in pos} | {int(uid) for uid, _ in neg}
    names = fetch_names_bulk(s.sqlite_path, update.effective_chat.id, list(uids))

    lines = ["⚖️ Карма чата", "───────────────────", "🌟 Топ +:"]
    if pos:
        for i, (uid, score) in enumerate(pos, 1):
            u_, f_ = names.get(int(uid), ("", ""))
            lines.append(f"{i}. {user_link_from_parts(f_, u_, int(uid))} — {int(score)}")
    else:
        lines.append("—")
    lines.append("")
    lines.append("💀 Топ -:")
    if neg:
        for i, (uid, score) in enumerate(neg, 1):
            u_, f_ = names.get(int(uid), ("", ""))
            lines.append(f"{i}. {user_link_from_parts(f_, u_, int(uid))} — {int(score)}")
    else:
        lines.append("—")

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=back_to_menu_kb_any(),
    )
