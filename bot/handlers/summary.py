import os

from telegram import Update
from telegram.ext import ContextTypes

from bot.config import Settings
from bot.handlers.mod_utils import has_permission
from bot.repositories.summary import can_use_summary, get_last_text_messages, log_summary_usage, remaining_summary_uses
from bot.services.llm_client import complete_text


def _settings(context: ContextTypes.DEFAULT_TYPE) -> Settings:
    return context.application.bot_data.get("settings") or context.application.settings


def _can_activity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user = update.effective_user
    if not user:
        return False
    s = _settings(context)
    return has_permission(s, s.sqlite_path, user.id, "activity")


async def summary_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """ИИ-суммари последних сообщений из основного чата.
    Доступно всем, но не чаще 3 раз в сутки.
    """
    if not update.effective_chat or not update.effective_user:
        return

    s = _settings(context)
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    if not _can_activity(update, context):
        await update.message.reply_text("🚫 У тебя нет доступа к этой команде.")
        return

    if not can_use_summary(s.sqlite_path, user_id, max_per_day=3):
        await update.message.reply_text(
            "⏳ Лимит саммари исчерпан: максимум 3 раза в сутки. Попробуй завтра."
        )
        return

    await update.message.chat.send_action(action="typing")

    msgs = get_last_text_messages(s.sqlite_path, s.main_chat_id, limit=50)
    if len(msgs) < 5:
        await update.message.reply_text(
            "📭 Слишком мало текстовых сообщений для саммари. "
            "Нужно минимум 5 сообщений."
        )
        return

    # Build prompt
    lines = []
    for m in msgs:
        name = m.get("first_name") or f"User{m['tg_user_id']}"
        lines.append(f"{name}: {m['text']}")

    prompt = (
        "Ты — дружелюбный ассистент для чата MD4. Суммарируй последнюю активность чата.\n"
        "Кратко, по-русски, весело. Укажи кто о чём говорил, какие темы поднимались, "
        "есть ли какие-то забавные моменты или драмы. Не более 400 слов.\n\n"
        + "\n".join(lines)
    )

    result = complete_text(prompt, max_tokens=350, temperature=0.8)

    if not result:
        await update.message.reply_text(
            "🤖 ИИ-провайдер сейчас недоступен. Попробуй позже."
        )
        return

    remaining = remaining_summary_uses(s.sqlite_path, user_id, max_per_day=3)
    footer = f"\n\n— Осталось саммари сегодня: {remaining}/3"

    await update.message.reply_text(result + footer)
    log_summary_usage(s.sqlite_path, user_id)
