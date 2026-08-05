from telegram import Update
from telegram.ext import ContextTypes

from bot.config import Settings
from bot.services.rbac import has_permission
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


async def _do_summary(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    user_id: int,
) -> None:
    """Core logic: собрать сообщения, вызвать ИИ, ответить."""
    s = _settings(context)

    if not _can_activity(update, context):
        await update.effective_chat.send_message("🚫 У тебя нет доступа к этой команде.")
        return

    if not can_use_summary(s.sqlite_path, user_id, max_per_day=3):
        await update.effective_chat.send_message(
            "⏳ Лимит саммари исчерпан: максимум 3 раза в сутки. Попробуй завтра."
        )
        return

    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    msgs = get_last_text_messages(s.sqlite_path, s.main_chat_id, limit=1000)
    if len(msgs) < 5:
        await update.effective_chat.send_message(
            "📭 Слишком мало текстовых сообщений для саммари. "
            "Нужно минимум 5 сообщений."
        )
        return

    lines = []
    for m in msgs:
        name = m.get("first_name") or f"User{m['tg_user_id']}"
        lines.append(f"{name}: {m['text']}")

    prompt = (
        "Ты — дерзкий, циничный, но по-своему обаятельный бот чата MD4. "
        "Веди сводку активности в грубом, матершинном, но смешном стиле. "
        "Как будто ты сидишь с пацанами на кухне и пересказываешь, что творилось в чате. "
        "Не цензурь себя, используй мат по полной. "
        "Кто о чём говорил, кого послали нахуй, какие темы поднимались, "
        "какие драмы разгорелись, кто кого заебал. Не более 400 слов.\n\n"
        + "\n".join(lines)
    )

    result = complete_text(prompt, max_tokens=500, temperature=0.9)

    if not result:
        await update.effective_chat.send_message(
            "🤖 ИИ-провайдер сейчас недоступен. Попробуй позже."
        )
        return

    remaining = remaining_summary_uses(s.sqlite_path, user_id, max_per_day=3)
    footer = f"\n\n— Осталось саммари сегодня: {remaining}/3"

    await update.effective_chat.send_message(result + footer)
    log_summary_usage(s.sqlite_path, user_id)


async def summary_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """ИИ-саммари последних сообщений из основного чата.
    Доступно всем, но не чаще 3 раз в сутки.
    """
    if not update.effective_chat or not update.effective_user:
        return
    await _do_summary(update, context, update.effective_chat.id, update.effective_user.id)


async def summary_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Вызов из inline-кнопки меню."""
    if not update.effective_chat or not update.effective_user:
        return
    await _do_summary(update, context, update.effective_chat.id, update.effective_user.id)


async def summary_text_trigger(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Триггер по фразе 'бот чо было?' в чате."""
    if not update.effective_chat or not update.effective_user or not update.effective_message:
        return
    text = (update.effective_message.text or "").lower()
    if "бот" in text and ("чо было" in text or "что было" in text):
        await _do_summary(update, context, update.effective_chat.id, update.effective_user.id)
