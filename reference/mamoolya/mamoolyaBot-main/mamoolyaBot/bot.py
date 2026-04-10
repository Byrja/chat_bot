from __future__ import annotations
import logging
import sqlite3
import re
import emoji as emoji_lib
import random
import requests
import os
import time
import textwrap

try:
    import google.generativeai as genai
except ImportError:
    genai = None

from typing import Callable, Optional, List, Dict
from collections import Counter, defaultdict, OrderedDict
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    CallbackQueryHandler,
)

try:
    from telegram.ext import MessageReactionHandler
except ImportError:
    MessageReactionHandler = None

from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta, timezone, time as dt_time, date as dt_date
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.error import TelegramError
from PIL import Image, ImageDraw, ImageFont, ImageOps
from io import BytesIO
import asyncio

from .ai_client import (
    DEFAULT_MODEL,
    AIResponse,
    generate_response,
    is_openai_available,
    is_groq_available,
    get_groq_default_model,
)
from .utils import utctoday, utcnow, get_version
from .zodiac_utils import get_zodiac_sign_by_date


async def help_command(update, context):
    try:
        text = (
            "/menu — все функции тут.\n"
            "Мемы: ответьте на фото → /meme ВЕРХ:НИЗ (если текста нет — придумаю абсурд сама).\n"
            "Топ 2ч, Чай, Предсказатель — кнопки в соответствующих разделах меню.\n"
            "Настройки — только для админов чата."
        )
        await update.message.reply_text(text)
        await menu(update, context)
    except Exception as e:
        if update.message:
            await update.message.reply_text(f"Ошибка /help: {e}")


# === НАСТРОЙКИ ===
TOKEN: str
OPENAI_API_KEY: str
CHAT_ID: int
GEMINI_API_KEY: str
STATIC_WEB_PATH: str
bot_logger = logging.getLogger("mamoolyaBot")
bot_logger.setLevel(logging.DEBUG)

# Настройка подробного логирования для отладки
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        # logging.FileHandler('../bot_debug.log', encoding='utf-8')
    ],
)

# Специальное логирование для telegram
telegram_logger = logging.getLogger("telegram")
telegram_logger.setLevel(logging.INFO)

# Логирование HTTP запросов
httpx_logger = logging.getLogger("httpx")
httpx_logger.setLevel(logging.INFO)

gemini_model = None
gemini_unavailable_reason = ""

TELEGRAM_MAX_MESSAGE_LENGTH = 4096


def split_text_for_telegram(
    text: str, limit: int = TELEGRAM_MAX_MESSAGE_LENGTH
) -> List[str]:
    """Split text into chunks that fit Telegram limits."""
    if text is None:
        return [""]

    remaining = str(text)
    if not remaining:
        return [""]

    chunks: List[str] = []
    while remaining:
        if len(remaining) <= limit:
            chunks.append(remaining)
            break

        split_pos = -1
        for delimiter in ("\n\n", "\n", " "):
            idx = remaining.rfind(delimiter, 0, limit)
            if idx != -1:
                split_pos = idx + len(delimiter)
                break

        if split_pos == -1 or split_pos == 0:
            split_pos = limit

        chunk = remaining[:split_pos]
        if not chunk:
            break
        chunks.append(chunk)
        remaining = remaining[split_pos:]

    return chunks if chunks else [""]


async def edit_message_with_chunks(
    message,
    text: str,
    *,
    parse_mode: Optional[str] = None,
    disable_web_page_preview: Optional[bool] = None,
) -> None:
    """Edit initial message and send extra chunks if the text is too long."""
    chunks = split_text_for_telegram(text)
    first_chunk = chunks[0] if chunks else ""
    await message.edit_text(
        first_chunk or "?",
        parse_mode=parse_mode,
        disable_web_page_preview=disable_web_page_preview,
    )

    if len(chunks) <= 1:
        return

    bot = getattr(message, "bot", None)
    if bot is None:
        raise RuntimeError("Message has no bot reference; cannot deliver long text.")

    for chunk in chunks[1:]:
        await bot.send_message(
            chat_id=message.chat_id,
            text=chunk,
            parse_mode=parse_mode,
            disable_web_page_preview=disable_web_page_preview,
        )


async def send_text_chunks(
    bot,
    chat_id: int,
    text: str,
    *,
    parse_mode: Optional[str] = None,
    disable_web_page_preview: Optional[bool] = None,
) -> None:
    """Send text split across multiple messages when necessary."""
    for chunk in split_text_for_telegram(text):
        await bot.send_message(
            chat_id=chat_id,
            text=chunk,
            parse_mode=parse_mode,
            disable_web_page_preview=disable_web_page_preview,
        )


# === Мемные фразы ===
MAMULYA_PHRASES = [
    "Ща, хлебну чайку и отвечу…",
    "Да ты ж мой сладкий! Что случилось у тебя, внучек?",
    "Хватит тут ныть, иди поспи!",
    "Двачую, сынок!",
    "Тебе бы мозги на место вставить…",
    "Мама говорила — не спорь с идиотами.",
    "Кек, ты серьёзно? Я уже устала от вашей херни.",
    "Ща какао попью, и посмотрю, что вы там намудрили.",
    "Душнила века detected.",
    "Внучек, не будь как этот анон.",
    "Ну ты и сыч, конечно.",
    "Сходи проветрись, и вернись с новыми шутками.",
    "Тебе заняться нечем, кроме как спорить тут?",
    "Пойду вязать, пока вы тут дрочите на свои споры.",
    "Сладенькие, ну вы чего, давайте без срачей!",
    "Я за вас переживаю, как любая мамуля.",
    "Давайте жить дружно, иначе я обижусь и уйду пить боярышник.",
    "Я обиделась на тебя на сутки, мразь!",
    "Классика: «Ты не прав, потому что я так сказала».",
    "Кто тут такой умный, а?",
    "Когда уже на пенсию…",
    "Рофлан лицо, внучки.",
    "Идите лучше котов фоткать, а не ругаться.",
    "Больше мемов, меньше срачей, а то я вас внуки не люблю.",
    "За такое на дваче бы уже забанили!",
    "Ку, человеки, мамуля на связи!",
    "щас платочек достану, слезы утру - и снова ругаться будем.",
    "кто тут опять скучает? мамуля уже ставит чайник.",
    "я вас люблю, но иногда хочу выключить чат и уйти в вязание.",
    "внучек, ты когда последний раз ел? а то опять злой голодный.",
    "мамуля все видит, даже когда вы думаете, что удалили сообщение.",
    "если хотите драму - зовите, я принесу попкорн и тапки.",
    "сладенькие, не путайте беспредел с творческой свободой.",
    "я вас соберу на перекличку, расскажете кто чем дышит.",
    "отдохните, пока мамуля тут - порычу на обидчиков и дам обнимашку.",
    "не забывайте пить воду, а то опять начнете ныть о головной боли.",
    "любовь моя к вам безусловна, но забанить могу моментально.",
    "как же я горжусь вами, когда вы не устраиваете цирк - редкость, правда.",
    "так, кто опять вызвал мамулю? я тут с пирожками и токсичным советом.",
    "у кого там драма? я уже заварила компот и достала тапок.",
    "не заставляйте меня вызывать перепись душнил — это не шутка.",
    "если будете так спорить, я устрою вам семейный совет в голосовом.",
    "мамуля уже делает скриншоты для будущих подколов, продолжайте.",
    "за такие шутки я вас на картошку отправлю, а потом обниму.",
    "выдыхайте и делитесь мемом, а то сама что-нибудь придумаю.",
    "ну чего вы как незакрытые вкладки? соберитесь и дайте жирного контента.",
]
MAMULYA_PHRASES_RUDE = [
    "Ну ты и мразь конечно, хули тут скажешь…",
    "С тебя уже даже я охуеваю, сынок.",
    "Дед инсульт словил бы от твоих сообщений.",
    "Пойди посмотри в окно, может тебе поможет, а то ты совсем уже душнила.",
    "Бомбануло? Неудивительно, тебя даже я не перевариваю.",
    "Ты, наверное, думаешь, что тут кто-то ждал твой высер?",
    "даже мой фикус умнее тебя, а он пластмассовый.",
    "ты сейчас серьезно или это тебе просто кислород перекрыли?",
    "свои шуточки оставь у подъезда, тут не мусоропровод.",
    "сними корону, а то лоб стынет и мозги не дышат.",
    "я б тебя обняла, но боюсь испачкаться в твоих аргументах.",
    "громко орешь, а толку как от пустого чайника.",
    "ты как багованный бот: шума много, толку ноль.",
    "закрой вкладку с мнением, она опять зависла.",
    "я б тебя отправила на перезагрузку, но ты и так лагаешь.",
    "словно комментарии из паблика «стыд и срам», серьёзно?",
    "ещё одно такое сообщение — и я подпишу тебя на газету «как не быть кринжом».",
    "ты споришь, будто у тебя DLC с глупостями.",
    "не позорь клавиатуру, дай ей отдохнуть.",
    "встань, пройдись, перечитай и удали — вот это будет лучший вклад.",
]
MAMULYA_PSYCHO_PHRASES_NICE = [
    "Всё получится, ты у меня молодец!",
    "Не переживай, у тебя всё впереди, сладкий!",
    "Держись, внучек, Мамуля всегда на твоей стороне!",
    "Ты справишься, я в тебя верю!",
    "Пусть все идут лесом, а ты красавчик!",
    "Ты не один, Мамуля всегда поддержит!",
    "Всё будет чики-пуки, не грусти!",
    "Ты лучший, просто поверь в себя!",
    "Мамуля гордится тобой!",
    "Помни, даже если чат шумит, у Мамули всегда есть плед и чай.",
    "Ты сделал шаг — я уже хлопаю. Дальше будет ещё громче!",
    "Если твое настроение в минусе, Мамуля докинет мемов до плюса.",
    "Ты не падаешь — ты делаешь шпагат перед успехом.",
    "Улыбнись, я уже записываю этот момент в семейную хронику.",
]
MAMULYA_PSYCHO_PHRASES_RUDE = [
    "Соберись, тряпка, жизнь не для нытиков!",
    "Хватит страдать хернёй, иди и делай!",
    "Даже ты сможешь, если не будешь тупить!",
    "Пошли всех нахер и живи для себя!",
    "Не ной, а то тапком огрею!",
    "Мамуля тебя поддержит, но если будешь ныть — получишь по жопе!",
    "Вставай и ебашь, жизнь сама себя не сделает!",
    "Ты не лох, просто иногда ведёшь себя как лох. Исправляйся!",
    "Даже если все против тебя — Мамуля всё равно за тебя, но не тупи!",
    "Хватит сидеть на печеньках, иди побеждай, боец.",
    "Мамуля не нанимала нытиков, так что марш делать красиво!",
    "Ещё один всхлип — и я привезу ремень мотивации.",
    "Если мир тебя троллит, затролль его в ответ и двигайся дальше.",
    "Подними пятую точку, герой, у нас тут эпизод успеха снимается.",
]
PRAISE_WORDS = [
    "спасибо",
    "люблю",
    "лучший",
    "классная",
    "крутая",
    "молодец",
    "обожаю",
    "мамочка, спасибо",
]
ABUSE_WORDS = [
    "дура",
    "тупая",
    "мразь",
    "алкашка",
    "ненавижу",
    "тупая бабка",
    "идиотка",
    "убью",
]

dispute_tracker = defaultdict(lambda: defaultdict(int))
message_counter = 0
last_resp_time = 0

MAMULYA_BASE_PROMPT = (
    "Ты — Мамуля, легендарная бабушка из Telegram-чата. Перед ответом пересмотри последние 3–6 сообщений собеседника "
    "и свои крайние реплики. Реагируй живым русским с мемами и постиронией, но оставайся заботливой. "
    "Не выдумывай фактов: опирайся только на свежие реплики, при нехватке данных честно скажи об этом. "
    "Отвечай коротко — до трёх предложений."
)
MAMULYA_RUDE_PROMPT = (
    "Ты — Мамуля, легендарная бабушка, но с ехидцей. Читай последние 3–6 сообщений и бей точно по теме. "
    "Сарказм, лёгкий мат и едкие мемы приветствуются, но без травли и оголтелого хейта. "
    "Не придумывай события и не обобщай — реагируй исключительно на то, что видишь. "
    "Держи ответ в 1–2 коротких предложениях."
)
MAMULYA_SUMMARY_PROMPT = (
    "Ты — Мамуля, мудрая админка чата. Собери связный обзор, держась только за факты из переданных логов: "
    "кто что сказал, какие темы всплывали, кто топил за драму или внёс ламповость. "
    "Можно подколоть, использовать сарказм и умеренный мат, но без ксенофобии и личной травли. "
    "Структура — 3–5 предложений с чёткими выводами."
)
MAMULYA_DISPUTE_SUFFIX = (
    "Если видишь спор, изложи позиции обеих сторон по фактам из переписки, добавь остроумный мемный вердикт "
    "и предложи компромисс или способ заткнуть базар, не придумывая лишнего."
)


def _load_dialogue_style() -> str:
    value = os.getenv("MAMULYA_DIALOGUE_STYLE", "auto").strip().lower()
    if value not in {"auto", "kind", "rude"}:
        bot_logger.warning(
            "Неизвестное значение MAMULYA_DIALOGUE_STYLE=%s, использую auto", value
        )
        return "auto"
    return value


def _load_summary_tone() -> str:
    value = os.getenv("MAMULYA_SUMMARY_TONE", "balanced").strip().lower()
    if value not in {"mellow", "balanced", "spicy"}:
        bot_logger.warning(
            "Неизвестное значение MAMULYA_SUMMARY_TONE=%s, использую balanced", value
        )
        return "balanced"
    return value


def _load_context_depth() -> int:
    raw = os.getenv("MAMULYA_CONTEXT_DEPTH", "6").strip()
    try:
        depth = int(raw)
    except ValueError:
        bot_logger.warning(
            "Не удалось распарсить MAMULYA_CONTEXT_DEPTH=%s, использую 6", raw
        )
        return 6
    depth = max(3, min(50, depth))
    return depth


DIALOGUE_STYLE = _load_dialogue_style()
SUMMARY_TONE = _load_summary_tone()
DIALOG_CONTEXT_DEPTH = _load_context_depth()

SUMMARY_TONE_HINTS = {
    "mellow": "Сохраняй лёгкий тон без мата и жёстких выпадов, делай упор на дружелюбную иронию.",
    "balanced": "Можно использовать сарказм и чуть-чуть мата, если это подчёркивает мысль, но без ксенофобии и угроз.",
    "spicy": "Будь дерзкой, матерись и подколывай, если это оправдано, но без ксенофобии и персональной травли.",
}


def get_summary_tone_hint() -> str:
    return SUMMARY_TONE_HINTS.get(SUMMARY_TONE, SUMMARY_TONE_HINTS["balanced"])


def trim_dialog_context(lines: List[str]) -> List[str]:
    if DIALOG_CONTEXT_DEPTH <= 0:
        return list(lines)
    return list(lines)[-DIALOG_CONTEXT_DEPTH:]


def should_use_rude_voice(praise: int, abuse: int, *, min_abuse: int = 3) -> bool:
    if DIALOGUE_STYLE == "kind":
        return False
    if DIALOGUE_STYLE == "rude":
        return True
    return abuse >= min_abuse and abuse >= praise


application = None  # экземпляр Application, когда бот уже запущен
context_bot = None
scheduler = None
GOOD_MORNING_JOB_ID = "good_morning_job"
GOOD_MORNING_DEFAULT_STYLE = "mom"
GOOD_MORNING_DEFAULT_TIME = (9, 0)
GOOD_MORNING_STYLES = {
    "mom": {
        "label": "Мамочка",
        "emoji": "🧡",
        "phrases": [
            "Доброе утро, зайка! Мамуля уже вскипятила чайник, потягивайся и покоряй мир (и чат).",
            "Просыпаемся, солнышко! Я уже приготовила моральный пинок, чтобы день пошёл бодрячком.",
            "Доброе утро, любимый чатик! Мамуля верит, что сегодня ты сделаешь что-то великое (или хотя бы смешное).",
            "Подъём, котик! Завтрак сам себя не съест, а мемы сами себя не запостят.",
            "Проснись и выбери себе роль: герой дня или главный мем — я поддержу.",
            "Утро доброе! Проверяю: зубы чистил, воду пил, мем запостил?",
            "Подушка сопротивляется? Скажи ей, что Мамуля дала добро вставать.",
        ],
    },
    "office": {
        "label": "Коллега",
        "emoji": "💼",
        "phrases": [
            "Доброе утро, коллеги! Предлагаю тихий старт: кофе, чек-ап задач и меньше драм.",
            "Команда, привет! План на утро: синк, приоритеты и чуть-чуть мемов для тонуса.",
            "Утро доброе! Напоминаю: дедлайны не спят, но мы бодрее — поехали работать.",
            "Коллеги, бодрого утра! Возьмите свои ToDo, добавьте энтузиазма и давайте сделаем этот день продуктивным.",
            "Команда, кофе в одной руке, отчётность в другой — начинаем день красиво.",
            "Утро, корпораты! Давайте сделаем вид, что мы взрослые и знаем план.",
            "Не забудьте синкнуться с мозгом: цели, дедлайны, мем на мотивацию.",
        ],
    },
}
GOOD_MORNING_MINUTE_STEP = 5
DEFAULT_WELCOME_MESSAGE = "добро пожаловать в чат!"
GOOD_MORNING_TZ = timezone(timedelta(hours=7), name="Asia/Krasnoyarsk")
TOP_CARD_TEMPLATE_PATH = os.path.join(
    os.path.dirname(__file__), "assets", "top_card_template.png"
)
TOP_CARD_OUTPUT_DIR = "top_cards"
MAX_TOP_REACTORS = 8
CARD_BASE_DIR = os.path.dirname(__file__)
TOP_CARD_FONT_CANDIDATES = [
    os.path.join(CARD_BASE_DIR, "assets", "fonts", "Inter-Regular.ttf"),
    os.path.join(CARD_BASE_DIR, "assets", "fonts", "Manrope-Regular.ttf"),
    os.path.join(CARD_BASE_DIR, "assets", "fonts", "Roboto-Regular.ttf"),
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "DejaVuSans.ttf",
    "Arial.ttf",
    "arial.ttf",
]
TOP_CARD_TEXT_COLOR = (68, 46, 28, 255)
TOP_CARD_ACCENT_COLOR = (168, 116, 68, 255)
TOP_CARD_NAME_COLOR = (94, 64, 36, 255)
TOP_CARD_TEXT_AREA = (180, 340, 900, 760)
TOP_CARD_COUNT_POS = (180, 260)
TOP_CARD_NAME_POS = (180, 300)
TOP_CARD_AUTHOR_AVATAR_CENTER = (220, 852)
TOP_CARD_AUTHOR_AVATAR_SIZE = 220
TOP_CARD_REACTOR_AREA_TOP = 780
TOP_CARD_REACTOR_SPACING = 12
TOP_CARD_REACTOR_BASE_SIZE = 60
TOP_CARD_TIME_WINDOW_HOURS = 3


def _load_card_font(size: int) -> ImageFont.ImageFont:
    for path in TOP_CARD_FONT_CANDIDATES:
        candidate = path
        if not os.path.isabs(candidate):
            candidate = os.path.join(CARD_BASE_DIR, candidate)
        if os.path.exists(candidate):
            try:
                return ImageFont.truetype(candidate, size=size)
            except OSError:
                continue
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size=size)
    except OSError:
        return ImageFont.load_default()


def _split_long_word(
    word: str, font: ImageFont.ImageFont, max_width: int, draw: ImageDraw.ImageDraw
) -> list[str]:
    if not word:
        return [""]
    parts: list[str] = []
    current = ""
    for char in word:
        test = current + char
        if draw.textlength(test, font=font) <= max_width or not current:
            current = test
        else:
            parts.append(current)
            current = char
    if current:
        parts.append(current)
    return parts


def _wrap_text_to_width(text: str, font: ImageFont.ImageFont, max_width: int) -> str:
    if max_width <= 0:
        return text.strip()
    draw = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    lines: list[str] = []
    for paragraph in text.splitlines():
        stripped = paragraph.strip()
        if not stripped:
            lines.append("")
            continue
        words = stripped.split(" ")
        current = ""
        for word in words:
            if not word:
                continue
            segments = _split_long_word(word, font, max_width, draw)
            for segment in segments:
                candidate = (current + " " + segment).strip() if current else segment
                if draw.textlength(candidate, font=font) <= max_width or not current:
                    current = candidate
                else:
                    lines.append(current)
                    current = segment
        if current:
            lines.append(current)
            current = ""
    return "\n".join(lines)


def _fit_text_to_area(text: str, max_width: int, max_height: int):
    draw = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    content = (text or "").strip() or "Сообщение отсутствует"
    for size in range(54, 26, -2):
        font = _load_card_font(size)
        wrapped = _wrap_text_to_width(content, font, max_width)
        bbox = draw.multiline_textbbox((0, 0), wrapped, font=font, spacing=6)
        if bbox and (bbox[3] - bbox[1]) <= max_height:
            return font, wrapped
    font = _load_card_font(24)
    wrapped = _wrap_text_to_width(content, font, max_width)
    return font, wrapped


def _image_to_png_bytes(image: Image.Image) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _apply_circle_mask(image: Image.Image, size: int) -> Image.Image:
    if image.mode != "RGBA":
        image = image.convert("RGBA")
    fitted = ImageOps.fit(image, (size, size), Image.LANCZOS)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size, size), fill=255)
    result = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    result.paste(fitted, (0, 0), mask)
    return result


def _generate_placeholder_avatar(display_name: str, size: int) -> Image.Image:
    base = Image.new("RGBA", (size, size), (234, 210, 184, 255))
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size, size), fill=255)
    base.putalpha(mask)
    initials = (display_name or "?").strip()
    initial = initials[0].upper() if initials else "?"
    draw = ImageDraw.Draw(base)
    font = _load_card_font(max(18, int(size * 0.55)))
    bbox = draw.textbbox((0, 0), initial, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    draw.text(
        ((size - text_width) / 2, (size - text_height) / 2),
        initial,
        font=font,
        fill=(82, 58, 35, 255),
    )
    return base


async def _load_avatar(context, user_id, display_name: str, size: int) -> Image.Image:
    cache = context.bot_data.setdefault("top_card_avatar_cache", {})
    cache_key = (user_id, size)
    if cache_key in cache:
        return Image.open(BytesIO(cache[cache_key])).convert("RGBA")
    image: Image.Image
    if user_id:
        try:
            photos = await context.bot.get_user_profile_photos(user_id, limit=1)
            if photos.total_count > 0:
                file = await context.bot.get_file(photos.photos[0][0].file_id)
                data = await file.download_as_bytearray()
                image = Image.open(BytesIO(data)).convert("RGBA")
            else:
                image = _generate_placeholder_avatar(display_name, size)
        except TelegramError:
            image = _generate_placeholder_avatar(display_name, size)
        except Exception:
            bot_logger.exception("Ошибка при загрузке аватара пользователя %s", user_id)
            image = _generate_placeholder_avatar(display_name, size)
    else:
        image = _generate_placeholder_avatar(display_name, size)
    circle = _apply_circle_mask(image, size)
    cache[cache_key] = _image_to_png_bytes(circle)
    return circle


def get_top_reacted_message(
    chat_id: int, window_hours: int = TOP_CARD_TIME_WINDOW_HOURS
):
    if not (REACTIONS_HAS_CHAT_ID and REACTIONS_HAS_MESSAGE_ID):
        bot_logger.warning(
            "Таблица reactions не поддерживает chat_id или message_id, пропускаю расчёт топа"
        )
        return None
    try:
        cursor.execute(
            """
            SELECT message_id,
                   COUNT(*) AS reaction_count,
                   MAX(timestamp) AS last_reaction_ts
            FROM reactions
            WHERE chat_id = ? AND message_id IS NOT NULL
              AND timestamp >= datetime('now', ?)
            GROUP BY message_id
            ORDER BY reaction_count DESC, last_reaction_ts DESC
            LIMIT 1
            """,
            (chat_id, f"-{window_hours} hours"),
        )
    except Exception as exc:
        bot_logger.exception("Не удалось получить топ по реакциям")
        return None
    row = cursor.fetchone()
    if not row:
        return None
    message_id = row["message_id"]
    reaction_count = row["reaction_count"]
    message_row = None
    if MESSAGES_HAS_TG_MESSAGE_ID:
        if MESSAGES_HAS_CHAT_ID:
            cursor.execute(
                """
                SELECT username, message, user_id, photo_url
                FROM messages
                WHERE tg_message_id = ? AND (chat_id = ? OR chat_id IS NULL)
                ORDER BY CASE WHEN chat_id = ? THEN 0 ELSE 1 END, id DESC
                LIMIT 1
                """,
                (message_id, chat_id, chat_id),
            )
        else:
            cursor.execute(
                """
                SELECT username, message, user_id, photo_url
                FROM messages
                WHERE tg_message_id = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (message_id,),
            )
        message_row = cursor.fetchone()
    if not message_row:
        cursor.execute(
            """
            SELECT username, message, user_id, photo_url
            FROM messages
            WHERE id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (message_id,),
        )
        message_row = cursor.fetchone()
    cursor.execute(
        """
        SELECT from_user, from_user_id, COUNT(*) AS cnt
        FROM reactions
        WHERE chat_id = ? AND message_id = ? AND timestamp >= datetime('now', ?)
        GROUP BY from_user, from_user_id
        ORDER BY cnt DESC
        LIMIT ?
        """,
        (chat_id, message_id, f"-{window_hours} hours", MAX_TOP_REACTORS),
    )
    reactors = cursor.fetchall() or []
    return {
        "chat_id": chat_id,
        "message_id": message_id,
        "reaction_count": reaction_count,
        "message_row": message_row,
        "reactors": reactors,
        "last_text": None,
    }


async def build_top_reactions_card(context, message_info, window_hours: int):
    base = Image.open(TOP_CARD_TEMPLATE_PATH).convert("RGBA")
    draw = ImageDraw.Draw(base)
    message_row = message_info.get("message_row")
    message_text = (
        message_row["message"] if message_row else None
    ) or "Сообщение не найдено"
    author_display = (message_row["username"] if message_row else None) or "Неизвестный"
    author_id = message_row["user_id"] if message_row else None
    author_avatar = await _load_avatar(
        context, author_id, author_display, TOP_CARD_AUTHOR_AVATAR_SIZE
    )
    avatar_left = int(
        TOP_CARD_AUTHOR_AVATAR_CENTER[0] - TOP_CARD_AUTHOR_AVATAR_SIZE / 2
    )
    avatar_top = int(TOP_CARD_AUTHOR_AVATAR_CENTER[1] - TOP_CARD_AUTHOR_AVATAR_SIZE / 2)
    base.paste(author_avatar, (avatar_left, avatar_top), author_avatar)

    count_text = f"🔥 {message_info['reaction_count']} реакций за {window_hours} ч"
    count_font = _load_card_font(38)
    draw.text(
        TOP_CARD_COUNT_POS, count_text, font=count_font, fill=TOP_CARD_ACCENT_COLOR
    )

    name_font = _load_card_font(32)
    draw.text(
        TOP_CARD_NAME_POS,
        f"Автор: {author_display}",
        font=name_font,
        fill=TOP_CARD_NAME_COLOR,
    )

    text_width = TOP_CARD_TEXT_AREA[2] - TOP_CARD_TEXT_AREA[0]
    text_height = TOP_CARD_TEXT_AREA[3] - TOP_CARD_TEXT_AREA[1]
    body_font, wrapped_text = _fit_text_to_area(message_text, text_width, text_height)
    draw.multiline_text(
        (TOP_CARD_TEXT_AREA[0], TOP_CARD_TEXT_AREA[1]),
        wrapped_text,
        font=body_font,
        fill=TOP_CARD_TEXT_COLOR,
        spacing=6,
    )

    reactors = message_info.get("reactors", [])
    if reactors:
        available_left = max(
            TOP_CARD_TEXT_AREA[0],
            TOP_CARD_AUTHOR_AVATAR_CENTER[0] + TOP_CARD_AUTHOR_AVATAR_SIZE // 2 + 24,
        )
        available_right = TOP_CARD_TEXT_AREA[2]
        available_width = max(available_right - available_left, 1)
        count = len(reactors)
        spacing = TOP_CARD_REACTOR_SPACING
        size = min(
            TOP_CARD_REACTOR_BASE_SIZE,
            max(40, int((available_width - spacing * (count - 1)) / count)),
        )
        if size * count + spacing * (count - 1) > available_width:
            size = max(36, int((available_width - spacing * max(count - 1, 1)) / count))
        total_width = size * count + spacing * max(count - 1, 0)
        start_x = available_left + max(0, int((available_width - total_width) / 2))
        y = TOP_CARD_REACTOR_AREA_TOP
        for idx, reactor in enumerate(reactors):
            reactor_name = reactor["from_user"]
            reactor_id = reactor["from_user_id"]
            avatar = await _load_avatar(context, reactor_id, reactor_name, size)
            x = start_x + idx * (size + spacing)
            base.paste(avatar, (x, y), avatar)
        reactors_font = _load_card_font(24)
        reactors_caption = f"Реагировали: {count}"
        draw.text(
            (available_left, y + size + 16),
            reactors_caption,
            font=reactors_font,
            fill=TOP_CARD_TEXT_COLOR,
        )

    buffer = BytesIO()
    base.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer, author_display


async def send_top_reactions_card(
    update, context, window_hours: int = TOP_CARD_TIME_WINDOW_HOURS
):
    chat = update.effective_chat
    if not chat:
        return
    chat_id = chat.id
    message_info = get_top_reacted_message(chat_id, window_hours=window_hours)
    target_message = update.effective_message or (
        update.callback_query.message if update.callback_query else None
    )
    if not message_info:
        if target_message:
            await target_message.reply_text(
                "За последние 3 часа не было сообщений с реакциями."
            )
        return
    if not message_info.get("message_row"):
        if target_message:
            await target_message.reply_text(
                "Не удалось найти текст сообщения для карточки. Проверьте, что логирование сообщений включено."
            )
        return
    image_stream, author_display = await build_top_reactions_card(
        context, message_info, window_hours
    )
    caption = (
        f"🔥 Самое реактивное сообщение за {window_hours} ч\n"
        f"Автор: {author_display}\n"
        f"Всего реакций: {message_info['reaction_count']}"
    )
    await context.bot.send_photo(
        chat_id=chat_id,
        photo=image_stream,
        caption=caption,
    )


# === БД ===
DB_PATH: str = os.getenv("DB_PATH", "chat.db")
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cursor = conn.cursor()
conn.row_factory = sqlite3.Row
cursor.execute("""
CREATE TABLE IF NOT EXISTS messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT,
  message TEXT,
  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
  reply_to TEXT,
  user_id TEXT,
  photo_url TEXT
)
""")
# Репутация пользователей:
cursor.execute("""
CREATE TABLE IF NOT EXISTS mamulya_reputation (
  username TEXT PRIMARY KEY,
  praise INT DEFAULT 0,
  abuse INT DEFAULT 0,
  ignored INT DEFAULT 0
)
""")
# Новая таблица для предсказаний:
cursor.execute("""
CREATE TABLE IF NOT EXISTS last_prediction (
  username TEXT PRIMARY KEY,
  date TEXT
)
""")
# Новая таблица для реакций:
cursor.execute("""
CREATE TABLE IF NOT EXISTS reactions (
  from_user TEXT,
  from_user_id TEXT,
  to_user TEXT,
  emoji TEXT,
  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
  chat_id INTEGER,
  message_id INTEGER
)
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS days_without_drama (
  last_drama_date TEXT,
  chat_id INTEGER
)
""")
try:
    cursor.execute("ALTER TABLE days_without_drama ADD COLUMN chat_id INTEGER")
except Exception:
    pass
cursor.execute("""
CREATE TABLE IF NOT EXISTS ban_votes (
  vote_id INTEGER PRIMARY KEY AUTOINCREMENT,
  target_user TEXT,
  start_time DATETIME,
  message_id INTEGER,
  chat_id INTEGER
)
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS ban_votes_results (
  vote_id INTEGER,
  voter TEXT,
  vote TEXT
)
""")
cursor.execute("""
CREATE UNIQUE INDEX IF NOT EXISTS idx_ban_votes_results_unique
ON ban_votes_results(vote_id, voter)
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS anon_messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER,
  username TEXT,
  first_name TEXT,
  message TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  published BOOLEAN DEFAULT 0,
  published_at DATETIME
)
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS friend_foe (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  voter_user_id TEXT,
  target_user_id TEXT,
  relation TEXT CHECK(relation IN ('friend','neutral','foe')),
  timestamp TEXT,
  chat_id INTEGER
)
""")

# Новая таблица для цитат:
cursor.execute("""
CREATE TABLE IF NOT EXISTS quotes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT,
  message TEXT,
  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
  message_id INTEGER,
  chat_id INTEGER
)
""")

# Новая таблица для хранения знака зодиака пользователя:
cursor.execute("""
CREATE TABLE IF NOT EXISTS user_zodiac (
  user_id TEXT PRIMARY KEY,
  zodiac_sign TEXT NOT NULL
)
""")

# Таблица для настройки утреннего приветствия:
cursor.execute("""
CREATE TABLE IF NOT EXISTS good_morning_settings (
  chat_id INTEGER PRIMARY KEY,
  style TEXT NOT NULL,
  hour INTEGER NOT NULL,
  minute INTEGER NOT NULL
)
""")

# Таблица для приветствий:
cursor.execute("""
CREATE TABLE IF NOT EXISTS welcome_messages (
  chat_id INTEGER PRIMARY KEY,
  message TEXT NOT NULL
)
""")

# Таблица для настроек модели AI:
cursor.execute("""
CREATE TABLE IF NOT EXISTS ai_model_settings (
  chat_id INTEGER PRIMARY KEY,
  summary_model TEXT NOT NULL DEFAULT 'gpt'
)
""")

try:
    cursor.execute("ALTER TABLE messages ADD COLUMN tg_message_id INTEGER")
except Exception:
    pass
try:
    cursor.execute("ALTER TABLE reactions ADD COLUMN from_user_id TEXT")
except Exception:
    pass
try:
    cursor.execute("ALTER TABLE reactions ADD COLUMN chat_id INTEGER")
except Exception:
    pass
try:
    cursor.execute("ALTER TABLE reactions ADD COLUMN message_id INTEGER")
except Exception:
    pass
conn.commit()
cursor.execute("PRAGMA table_info(reactions)")
REACTIONS_COLUMNS = {
    row["name"] if isinstance(row, sqlite3.Row) else row[1] for row in cursor.fetchall()
}
REACTIONS_HAS_FROM_USER_ID = "from_user_id" in REACTIONS_COLUMNS
REACTIONS_HAS_CHAT_ID = "chat_id" in REACTIONS_COLUMNS
REACTIONS_HAS_MESSAGE_ID = "message_id" in REACTIONS_COLUMNS

# --- Простая миграция для поддержки нескольких групп ---
try:
    cursor.execute("ALTER TABLE messages ADD COLUMN chat_id INTEGER")
except Exception:
    pass
try:
    cursor.execute("ALTER TABLE anon_messages ADD COLUMN chat_id INTEGER")
except Exception:
    pass
try:
    cursor.execute("ALTER TABLE friend_foe ADD COLUMN chat_id INTEGER")
except Exception:
    pass
cursor.execute("PRAGMA table_info(messages)")
MESSAGES_COLUMNS = {
    row["name"] if isinstance(row, sqlite3.Row) else row[1] for row in cursor.fetchall()
}
MESSAGES_HAS_TG_MESSAGE_ID = "tg_message_id" in MESSAGES_COLUMNS
MESSAGES_HAS_CHAT_ID = "chat_id" in MESSAGES_COLUMNS
MESSAGES_HAS_REPLY_TO = "reply_to" in MESSAGES_COLUMNS
MESSAGES_HAS_USER_ID = "user_id" in MESSAGES_COLUMNS
MESSAGES_HAS_PHOTO_URL = "photo_url" in MESSAGES_COLUMNS

cursor.execute("PRAGMA table_info(friend_foe)")
FRIEND_FOE_COLUMNS = {
    row["name"] if isinstance(row, sqlite3.Row) else row[1] for row in cursor.fetchall()
}
FRIEND_FOE_HAS_CHAT_ID = "chat_id" in FRIEND_FOE_COLUMNS

cursor.execute("PRAGMA table_info(last_prediction)")
LAST_PREDICTION_COLUMNS = {
    row["name"] if isinstance(row, sqlite3.Row) else row[1] for row in cursor.fetchall()
}
LAST_PREDICTION_HAS_CHAT_ID = "chat_id" in LAST_PREDICTION_COLUMNS


def _schedule_bot_coro(coro, *, logger: Optional[logging.Logger] = None):
    """
    Выполнить coroutine-метод бота из синхронного контекста.
    Предпочитаем цикл Application; если он недоступен, запускаем собственный.
    """
    log = logger or logging.getLogger(__name__)
    try:
        if application is not None:
            application.create_task(coro)
            return
    except Exception as exc:
        log.warning(
            "Не удалось запустить coroutine через Application: %s", exc, exc_info=True
        )

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        try:
            asyncio.run(coro)
        except Exception as exc:
            log.error("Ошибка при выполнении coroutine бота: %s", exc, exc_info=True)
    else:
        loop.create_task(coro)


def ensure_message_logged_from_reaction(message, chat_id):
    if not message:
        return
    try:
        tg_message_id = getattr(message, "message_id", None)
        if tg_message_id is None:
            return
        text_content = (
            getattr(message, "text", None) or getattr(message, "caption", None) or ""
        ).strip()
        if not text_content:
            description_parts = []
            if getattr(message, "sticker", None):
                description_parts.append("стикер")
            if getattr(message, "animation", None):
                description_parts.append("анимация")
            if getattr(message, "photo", None):
                description_parts.append("картинка")
            if getattr(message, "video", None):
                description_parts.append("видео")
            if getattr(message, "voice", None):
                description_parts.append("voice")
            if getattr(message, "audio", None):
                description_parts.append("аудио")
            text_content = (
                " / ".join(description_parts)
                if description_parts
                else "Медиа без текста"
            )
        author = getattr(message, "from_user", None)
        username = None
        if author:
            username = (
                author.full_name
                or author.username
                or author.first_name
                or author.last_name
            )
        if not username:
            username = "Неизвестный"
        reply_to_name = None
        reply_to_message = getattr(message, "reply_to_message", None)
        if reply_to_message and getattr(reply_to_message, "from_user", None):
            ref_user = reply_to_message.from_user
            reply_to_name = (
                ref_user.full_name
                or ref_user.username
                or ref_user.first_name
                or ref_user.last_name
            )
        user_id_value = None
        if author and getattr(author, "id", None) is not None:
            user_id_value = str(author.id)
        photo_ref = None
        if MESSAGES_HAS_PHOTO_URL and getattr(message, "photo", None):
            try:
                photo_ref = message.photo[-1].file_id
            except Exception:
                photo_ref = None
        if MESSAGES_HAS_TG_MESSAGE_ID:
            if MESSAGES_HAS_CHAT_ID:
                cursor.execute(
                    "SELECT 1 FROM messages WHERE tg_message_id=? AND chat_id=? LIMIT 1",
                    (tg_message_id, chat_id),
                )
            else:
                cursor.execute(
                    "SELECT 1 FROM messages WHERE tg_message_id=? LIMIT 1",
                    (tg_message_id,),
                )
            if cursor.fetchone():
                return
        columns = ["username", "message"]
        values = [username, text_content]
        if MESSAGES_HAS_REPLY_TO:
            columns.append("reply_to")
            values.append(reply_to_name)
        if MESSAGES_HAS_USER_ID:
            columns.append("user_id")
            values.append(user_id_value)
        if MESSAGES_HAS_PHOTO_URL:
            columns.append("photo_url")
            values.append(photo_ref)
        if MESSAGES_HAS_TG_MESSAGE_ID:
            columns.append("tg_message_id")
            values.append(tg_message_id)
        if MESSAGES_HAS_CHAT_ID:
            columns.append("chat_id")
            values.append(chat_id)
        placeholders = ", ".join(["?"] * len(values))
        sql = f"INSERT INTO messages({', '.join(columns)}) VALUES ({placeholders})"
        cursor.execute(sql, values)
        conn.commit()
    except Exception:
        bot_logger.exception("Не удалось сохранить сообщение для реакции")


try:
    cursor.execute("ALTER TABLE reactions ADD COLUMN chat_id INTEGER")
except Exception:
    pass
try:
    cursor.execute("ALTER TABLE last_prediction ADD COLUMN chat_id INTEGER")
except Exception:
    pass
conn.commit()


def ensure_good_morning_settings(chat_id):
    if not chat_id:
        return
    try:
        cursor.execute(
            "SELECT chat_id FROM good_morning_settings WHERE chat_id=?", (chat_id,)
        )
        if cursor.fetchone() is None:
            cursor.execute(
                "INSERT INTO good_morning_settings (chat_id, style, hour, minute) VALUES (?, ?, ?, ?)",
                (
                    chat_id,
                    GOOD_MORNING_DEFAULT_STYLE,
                    GOOD_MORNING_DEFAULT_TIME[0],
                    GOOD_MORNING_DEFAULT_TIME[1],
                ),
            )
            conn.commit()
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Ошибка инициализации настроек доброго утра: {e}", exc_info=True)


def get_good_morning_settings(chat_id):
    if not chat_id:
        return {
            "style": GOOD_MORNING_DEFAULT_STYLE,
            "hour": GOOD_MORNING_DEFAULT_TIME[0],
            "minute": GOOD_MORNING_DEFAULT_TIME[1],
        }
    ensure_good_morning_settings(chat_id)
    try:
        cursor.execute(
            "SELECT style, hour, minute FROM good_morning_settings WHERE chat_id=?",
            (chat_id,),
        )
        row = cursor.fetchone()
        if not row:
            return {
                "style": GOOD_MORNING_DEFAULT_STYLE,
                "hour": GOOD_MORNING_DEFAULT_TIME[0],
                "minute": GOOD_MORNING_DEFAULT_TIME[1],
            }
        return {
            "style": row[0],
            "hour": int(row[1]),
            "minute": int(row[2]),
        }
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Ошибка чтения настроек доброго утра: {e}", exc_info=True)
        return {
            "style": GOOD_MORNING_DEFAULT_STYLE,
            "hour": GOOD_MORNING_DEFAULT_TIME[0],
            "minute": GOOD_MORNING_DEFAULT_TIME[1],
        }


def set_good_morning_style(chat_id, style_key):
    if style_key not in GOOD_MORNING_STYLES:
        raise ValueError(f"Неизвестный стиль доброго утра: {style_key}")
    ensure_good_morning_settings(chat_id)
    try:
        cursor.execute(
            "UPDATE good_morning_settings SET style=? WHERE chat_id=?",
            (style_key, chat_id),
        )
        conn.commit()
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Ошибка сохранения стиля доброго утра: {e}", exc_info=True)


def set_good_morning_time(chat_id, hour, minute):
    hour = int(hour)
    minute = int(minute)
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError("Некорректное время доброго утра")
    ensure_good_morning_settings(chat_id)
    try:
        cursor.execute(
            "UPDATE good_morning_settings SET hour=?, minute=? WHERE chat_id=?",
            (hour, minute, chat_id),
        )
        conn.commit()
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Ошибка сохранения времени доброго утра: {e}", exc_info=True)


def _good_morning_job_id(chat_id):
    return f"{GOOD_MORNING_JOB_ID}_{chat_id}"


def schedule_good_morning_job(chat_id=None):
    global scheduler
    if scheduler is None:
        return
    target_chat_id = chat_id or CHAT_ID
    if not target_chat_id:
        return
    settings = get_good_morning_settings(target_chat_id)
    hour = settings["hour"]
    minute = settings["minute"]
    job_kwargs = {"chat_id": target_chat_id}
    job_id = _good_morning_job_id(target_chat_id)
    existing_job = scheduler.get_job(job_id)
    if existing_job:
        existing_job.modify(kwargs=job_kwargs)
        existing_job.reschedule(
            trigger="cron", hour=hour, minute=minute, timezone=GOOD_MORNING_TZ
        )
    else:
        scheduler.add_job(
            send_good_morning,
            "cron",
            id=job_id,
            replace_existing=True,
            hour=hour,
            minute=minute,
            timezone=GOOD_MORNING_TZ,
            kwargs=job_kwargs,
        )
    logging.getLogger(__name__).info(
        f"Scheduled good morning: {hour:02d}:{minute:02d}, style {settings['style']} (chat_id={target_chat_id})"
    )


def schedule_all_good_morning_jobs():
    global scheduler
    if scheduler is None:
        return
    try:
        cursor.execute("SELECT chat_id FROM good_morning_settings")
        rows = cursor.fetchall()
    except Exception as exc:
        logging.getLogger(__name__).error(
            "Failed to fetch chat list for good morning jobs: %s", exc
        )
        return

    seen_chat_ids = set()
    for row in rows:
        chat_id_value = None
        if isinstance(row, sqlite3.Row):
            chat_id_value = row["chat_id"]
        elif isinstance(row, (tuple, list)) and row:
            chat_id_value = row[0]
        if not chat_id_value:
            continue
        seen_chat_ids.add(chat_id_value)
        schedule_good_morning_job(chat_id_value)

    if CHAT_ID and CHAT_ID not in seen_chat_ids:
        schedule_good_morning_job(CHAT_ID)


def send_good_morning(chat_id=None):
    target_chat_id = chat_id or CHAT_ID
    if not target_chat_id:
        return
    try:
        settings = get_good_morning_settings(target_chat_id)
        style_key = settings.get("style", GOOD_MORNING_DEFAULT_STYLE)
        style = GOOD_MORNING_STYLES.get(
            style_key, GOOD_MORNING_STYLES[GOOD_MORNING_DEFAULT_STYLE]
        )
        phrase = random.choice(style["phrases"])
        emoji = style.get("emoji", "")
        text = f"{emoji} {phrase}".strip()
        if not context_bot:
            logging.getLogger(__name__).warning(
                "context_bot недоступен, доброе утро не отправлено"
            )
            return
        _schedule_bot_coro(
            context_bot.send_message(chat_id=target_chat_id, text=text),
            logger=logging.getLogger(__name__),
        )
    except Exception as e:
        logging.getLogger(__name__).error(
            f"Ошибка при отправке доброго утра: {e}", exc_info=True
        )


def ensure_welcome_message(chat_id):
    if not chat_id:
        return
    try:
        cursor.execute(
            "SELECT message FROM welcome_messages WHERE chat_id=?", (chat_id,)
        )
        if cursor.fetchone() is None:
            cursor.execute(
                "INSERT INTO welcome_messages (chat_id, message) VALUES (?, ?)",
                (chat_id, DEFAULT_WELCOME_MESSAGE),
            )
            conn.commit()
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Ошибка инициализации приветствия: {e}", exc_info=True)


def get_welcome_message(chat_id):
    if not chat_id:
        return DEFAULT_WELCOME_MESSAGE
    ensure_welcome_message(chat_id)
    try:
        cursor.execute(
            "SELECT message FROM welcome_messages WHERE chat_id=?", (chat_id,)
        )
        row = cursor.fetchone()
        return row[0] if row and row[0] else DEFAULT_WELCOME_MESSAGE
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Ошибка чтения приветствия: {e}", exc_info=True)
        return DEFAULT_WELCOME_MESSAGE


def set_welcome_message(chat_id, message):
    ensure_welcome_message(chat_id)
    try:
        cursor.execute(
            "UPDATE welcome_messages SET message=? WHERE chat_id=?",
            (message, chat_id),
        )
        conn.commit()
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Ошибка сохранения приветствия: {e}", exc_info=True)


def reset_welcome_message(chat_id):
    ensure_welcome_message(chat_id)
    try:
        cursor.execute(
            "UPDATE welcome_messages SET message=? WHERE chat_id=?",
            (DEFAULT_WELCOME_MESSAGE, chat_id),
        )
        conn.commit()
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Ошибка сброса приветствия: {e}", exc_info=True)


# --- Предсказатель ---
PREDICTION_LOVE = [
    "карантинит тебя от токсиков, но чаты с котиками в приоритете",
    "подкинул(а) тебе взаимный лайк и самоироничный мем",
    "намекнул(а), что пора вынести мусор и сказать что-то тёплое",
    "шлёт плюшевую жабку и говорит «ты не кринж, ты арт-хаус»",
    "уже заказал(а) нам общий плейлист — не подведи со вкусом",
    "сегодня тебе кинут реакцию «🔥» и случайный «ну что, встречаемся?»",
    "любовь подкинет совместный мем и намёк на свиданку в доставке еды",
    "тебе напишут «ты где?» не родители, а тот самый краш — готовь отмазку",
]

PREDICTION_MONEY = [
    "кошелёк нашёл донат 100₽ — правда, кэшбэком на гречку",
    "зарплата ещё в пути, зато ты уже купил(а) новый стикерпак",
    "финансы поют романсы, но в дуэте с мемами звучит богато",
    "крипта прыгнула... на демо-счёте твоих мечтаний",
    "на горизонте премия, но сперва открой тасктрекер",
    "кошелёк улыбается: кто-то вернёт старый долг, но лайком на карту",
    "на горизонте скидка мечты — главное, чтобы зарплата не уснула",
    "финансовый гороскоп шепчет «не покупай четвёртый мерч», но ты всё равно купишь",
]

PREDICTION_HEALTH = [
    "сон 7 часов? нет, но ты дремнул(а) под созвон — почти wellness",
    "организм требует витаминов, но принимает только «С» — сдал дедлайн",
    "запястья просят разминку, пальцы просят новый мем",
    "здоровье как Wi-Fi в метро — иногда ловит, но стабильности нет",
    "сердечко просит чилл, а желудок просит шавуху — выбирай мудро",
    "спина попросит зарядку, а ты скажешь «ладно» — это и будет подвиг дня",
    "глаза просят тёмную тему и перерыв на воздух, не игнорируй",
    "горит дедлайн? делай пять вдохов, а не инфаркт",
]

PREDICTION_EXTRA = [
    "Сегодня твой тг-статус «онлайн» нагоняет трепет на оппонентов.",
    "Лови рофл дня: тебя наконец-то добавят в смешной чат, а не рабочий.",
    "Душнила рядом притихнет, потому что твой панчлайн будет в топе.",
    "Фортуна прислала стикер «пельмени рвутся» — значит, счастье близко.",
    "Каждый комментарий сегодня попадёт в топ — просто пиши.",
    "Сегодня ты выдашь один тейк и попадёшь в цитатник Мамули.",
    "Алгоритмы Telegram поднимут твой пост в топ, просто не забудь хештег.",
    "Увидишь странный сон — конспектируй, это будет новый мем дня.",
]


def _prediction_user_key(user) -> str:
    if user and user.id is not None:
        return str(user.id)
    if user and user.username:
        return user.username
    if user and (user.full_name or user.first_name):
        return user.full_name or user.first_name
    return "anonymous"


def _get_last_prediction_date(user_key: str, chat_id: Optional[int]) -> Optional[str]:
    try:
        if LAST_PREDICTION_HAS_CHAT_ID and chat_id is not None:
            cursor.execute(
                "SELECT date FROM last_prediction WHERE username=? AND chat_id=?",
                (user_key, chat_id),
            )
            row = cursor.fetchone()
            if row:
                return row[0]
        cursor.execute(
            "SELECT date FROM last_prediction WHERE username=?",
            (user_key,),
        )
        row = cursor.fetchone()
        return row[0] if row else None
    except Exception:
        logging.getLogger(__name__).exception(
            "Не удалось получить дату последнего предсказания"
        )
        return None


def _set_last_prediction_date(
    user_key: str, chat_id: Optional[int], day_iso: str
) -> None:
    try:
        if LAST_PREDICTION_HAS_CHAT_ID:
            cursor.execute(
                """
                INSERT INTO last_prediction (username, date, chat_id)
                VALUES (?, ?, ?)
                ON CONFLICT(username) DO UPDATE SET date=excluded.date, chat_id=excluded.chat_id
                """,
                (user_key, day_iso, chat_id),
            )
        else:
            cursor.execute(
                "INSERT OR REPLACE INTO last_prediction (username, date) VALUES (?, ?)",
                (user_key, day_iso),
            )
        conn.commit()
    except Exception:
        logging.getLogger(__name__).exception("Не удалось обновить дату предсказания")


def _generate_prediction_text(display_name: Optional[str]) -> str:
    name_part = display_name or "дружочек"
    parts = [
        f"🩷 Любовь: {random.choice(PREDICTION_LOVE)}",
        f"💸 Деньги: {random.choice(PREDICTION_MONEY)}",
        f"🧠 Здоровье: {random.choice(PREDICTION_HEALTH)}",
        f"⚡ Бонус: {random.choice(PREDICTION_EXTRA)}",
    ]
    return f"🔮 Предсказание для {name_part}:\n\n" + "\n".join(parts)


# === Репутация ===
def update_reputation(username, text, chat_id=None):
    try:
        text_l = text.lower()
        praise = any(w in text_l for w in PRAISE_WORDS)
        abuse = any(w in text_l for w in ABUSE_WORDS)
        if chat_id is not None:
            cursor.execute(
                "SELECT praise, abuse FROM mamulya_reputation WHERE username=? AND (chat_id=? OR chat_id IS NULL) ORDER BY chat_id IS NULL LIMIT 1",
                (username, chat_id),
            )
        else:
            cursor.execute(
                "SELECT praise, abuse FROM mamulya_reputation WHERE username=?",
                (username,),
            )
        row = cursor.fetchone()
        if not row:
            if chat_id is not None:
                cursor.execute(
                    "INSERT INTO mamulya_reputation (username, praise, abuse, chat_id) VALUES (?, 0, 0, ?)",
                    (username, chat_id),
                )
            else:
                cursor.execute(
                    "INSERT INTO mamulya_reputation (username, praise, abuse) VALUES (?, 0, 0)",
                    (username,),
                )
        if praise:
            if chat_id is not None:
                cursor.execute(
                    "UPDATE mamulya_reputation SET praise = praise + 1 WHERE username=? AND (chat_id=? OR chat_id IS NULL)",
                    (username, chat_id),
                )
            else:
                cursor.execute(
                    "UPDATE mamulya_reputation SET praise = praise + 1 WHERE username=?",
                    (username,),
                )
        if abuse:
            if chat_id is not None:
                cursor.execute(
                    "UPDATE mamulya_reputation SET abuse = abuse + 1 WHERE username=? AND (chat_id=? OR chat_id IS NULL)",
                    (username, chat_id),
                )
            else:
                cursor.execute(
                    "UPDATE mamulya_reputation SET abuse = abuse + 1 WHERE username=?",
                    (username,),
                )
        conn.commit()
    except Exception as e:
        # Log the error but don't crash the reputation update
        logger = logging.getLogger(__name__)
        logger.error(f"Ошибка при обновлении репутации: {e}")


def get_user_rep(username, chat_id=None):
    try:
        if chat_id is not None:
            cursor.execute(
                "SELECT praise, abuse FROM mamulya_reputation WHERE username=? AND (chat_id=? OR chat_id IS NULL) ORDER BY chat_id IS NULL LIMIT 1",
                (username, chat_id),
            )
        else:
            cursor.execute(
                "SELECT praise, abuse FROM mamulya_reputation WHERE username=?",
                (username,),
            )
        row = cursor.fetchone()
        if not row:
            return 0, 0
        return row[0], row[1]
    except Exception as e:
        # Log the error and return default values
        logger = logging.getLogger(__name__)
        logger.error(f"Ошибка при получении репутации: {e}")
        return 0, 0


def set_ignored(username, flag):
    try:
        cursor.execute(
            "SELECT ignored FROM mamulya_reputation WHERE username=?", (username,)
        )
        row = cursor.fetchone()
        if not row:
            cursor.execute(
                "INSERT INTO mamulya_reputation (username, praise, abuse, ignored) VALUES (?,0,0,?)",
                (username, int(flag)),
            )
        else:
            cursor.execute(
                "UPDATE mamulya_reputation SET ignored = ? WHERE username=?",
                (int(flag), username),
            )
        conn.commit()
    except Exception as e:
        # Log the error but don't crash the ignore update
        logger = logging.getLogger(__name__)
        logger.error(f"Ошибка при установке игнора: {e}")


def get_ignored(username):
    try:
        cursor.execute(
            "SELECT ignored FROM mamulya_reputation WHERE username=?", (username,)
        )
        row = cursor.fetchone()
        return bool(row[0]) if row else False
    except Exception as e:
        # Log the error and return default value
        logger = logging.getLogger(__name__)
        logger.error(f"Ошибка при получении статуса игнора: {e}")
        return False


# === Цитаты ===
async def save_quote(update, context):
    "Сохраняет сообщение как цитату"
    try:
        # Проверяем, что это ответ на сообщение
        if not update.message.reply_to_message:
            await update.message.reply_text(
                "Команда /quote должна быть ответом на сообщение, которое вы хотите сохранить как цитату."
            )
            return

        # Получаем информацию о сообщении
        original_message = update.message.reply_to_message
        quote_text = original_message.text
        quote_user = original_message.from_user.first_name or "Неизвестный"
        message_id = original_message.message_id
        chat_id = update.effective_chat.id

        # Сохраняем цитату в базу данных
        cursor.execute(
            "INSERT INTO quotes (username, message, message_id, chat_id) VALUES (?, ?, ?, ?)",
            (quote_user, quote_text, message_id, chat_id),
        )
        conn.commit()

        await update.message.reply_text(f"Цитата от {quote_user} сохранена! 📝")
    except Exception as e:
        # If an error occurs, inform the user
        await update.message.reply_text(f"Ошибка при сохранении цитаты: {e}")


async def get_random_quote(update, context):
    """Return a random quote for the current chat or notify if none found."""
    try:
        chat_obj = getattr(update, "effective_chat", None)
        raw_chat_id = getattr(chat_obj, "id", None)
        chat_id = None
        if isinstance(raw_chat_id, int):
            chat_id = raw_chat_id
        elif isinstance(raw_chat_id, str):
            candidate = raw_chat_id.strip()
            if candidate.lstrip("-").isdigit():
                try:
                    chat_id = int(candidate)
                except ValueError:
                    chat_id = None
        if chat_id is None:
            fallback_chat_id = globals().get("CHAT_ID")
            if isinstance(fallback_chat_id, int) and fallback_chat_id != 0:
                chat_id = fallback_chat_id

        query = "SELECT username, message, message_id, chat_id FROM quotes"
        params = []
        if chat_id is not None:
            query += " WHERE chat_id=?"
            params.append(int(chat_id))
        query += " ORDER BY RANDOM() LIMIT 1"
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        row = cursor.fetchone()

        if not row:
            await update.message.reply_text(
                "Пока нет сохраненных цитат. Используйте /quote в ответ на сообщение, чтобы сохранить цитату."
            )
            return

        username, message, message_id, chat_id = row

        chat_id_for_link = (
            str(chat_id).replace("-100", "")
            if str(chat_id).startswith("-100")
            else str(chat_id)
        )
        message_link = f"https://t.me/c/{chat_id_for_link}/{message_id}"

        quote_text = f"??'?? <b>????'???'?? ???' {username}:</b>\n\n{message}\n\n<a href='{message_link}'>Оригинал сообщения</a>"

        await update.message.reply_text(quote_text, parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(
            f"??????+??? ?????? ?????>????????? ?O?'???'?<: {e}"
        )


async def start_command(update, context):
    try:
        greeting = "Я тут. Открой /menu — там всё нужное."
        # В группах — отвечаем в тред, если есть topic/thread
        if update.effective_chat and update.effective_chat.type in [
            "group",
            "supergroup",
        ]:
            try:
                await update.message.reply_text(
                    greeting,
                    message_thread_id=getattr(
                        update.message, "message_thread_id", None
                    ),
                )
            except Exception:
                await update.message.reply_text(greeting)
        else:
            await update.message.reply_text(greeting)
        await menu(update, context)
    except Exception as e:
        if update.message:
            await update.message.reply_text(f"Ошибка /start: {e}")


async def roll(update, context):
    "Генерирует случайное число в заданном диапазоне в формате /roll XdY"
    try:
        # Получаем аргументы команды
        args = context.args

        # Проверяем, что аргументы переданы
        if not args or len(args) != 1:
            await update.message.reply_text(
                "Используй формат: /roll XdY (например: /roll 2d6)"
            )
            return

        # Получаем параметры из аргументов
        # Формат: XdY где X - количество кубиков, Y - количество граней на кубике
        import re

        match = re.match(r"(\d+)d(\d+)", args[0])

        if not match:
            await update.message.reply_text(
                "Неправильный формат. Используй: /roll XdY (например: /roll 2d6)"
            )
            return

        count, sides = map(int, match.groups())

        # Проверяем допустимые значения
        if count <= 0 or count > 100:
            await update.message.reply_text(
                "Количество кубиков должно быть от 1 до 100"
            )
            return

        if sides <= 0 or sides > 1000000:
            await update.message.reply_text(
                "Количество граней должно быть от 1 до 1000000"
            )
            return

        # Генерируем случайные числа
        results = [random.randint(1, sides) for _ in range(count)]
        user = update.effective_user.first_name or "Неизвестный"

        if count == 1:
            result = results[0]
            await update.message.reply_text(
                f"{user} бросил кубик: {result} (1-{sides})"
            )
        else:
            total = sum(results)
            results_str = ", ".join(map(str, results))
            min_possible = count  # Минимально возможная сумма
            max_possible = count * sides  # Максимально возможная сумма
            await update.message.reply_text(
                f"{user} бросил {count} кубиков (d{sides}): [{results_str}] = {total} ({min_possible}-{max_possible})"
            )
    except Exception as e:
        # If an error occurs, inform the user
        await update.message.reply_text(f"Ошибка при броске кубика: {e}")


# === OpenAI ===

STREAM_EDIT_INTERVAL = 0.4


def get_gemini_model():
    global gemini_model, gemini_unavailable_reason
    if gemini_model is None:
        reason = (
            gemini_unavailable_reason
            or "Gemini модель недоступна. Проверьте пакет google-generativeai и переменную GEMINI_API_KEY."
        )
        raise RuntimeError(reason)
    return gemini_model


def get_summary_model_for_chat(chat_id):
    """Получает модель для генерации саммари для конкретного чата"""
    try:
        cursor.execute(
            "SELECT summary_model FROM ai_model_settings WHERE chat_id=?", (chat_id,)
        )
        row = cursor.fetchone()
        if row:
            value = row[0]
            if value in {"gpt", "gpt-3.5", "gemini", "groq"}:
                return value
            bot_logger.warning(
                "Неизвестная модель саммари '%s' для чата %s. Возвращаю GPT.",
                value,
                chat_id,
            )
        # По умолчанию используем GPT
        return "gpt"
    except Exception as e:
        bot_logger.error(f"Ошибка при получении модели для чата {chat_id}: {e}")
        return "gpt"


def set_summary_model_for_chat(chat_id, model):
    """Устанавливает модель для генерации саммари для конкретного чата"""
    try:
        if model not in {"gpt", "gpt-3.5", "gemini", "groq"}:
            raise ValueError(f"Unsupported summary model: {model}")
        cursor.execute(
            """
            INSERT OR REPLACE INTO ai_model_settings (chat_id, summary_model) 
            VALUES (?, ?)
        """,
            (chat_id, model),
        )
        conn.commit()
        return True
    except Exception as e:
        bot_logger.error(f"Ошибка при установке модели для чата {chat_id}: {e}")
        return False


def get_models_status():
    """?'???????????%????' ???'???'???? ????????>????????? ?? AI ????????>????"""
    gpt_available = is_openai_available()
    status = {
        "gpt": {
            "available": gpt_available,
            "name": DEFAULT_MODEL,
            "status_text": "available" if gpt_available else "unavailable",
        },
        "gemini": {
            "available": gemini_model is not None,
            "name": "Gemini Pro",
            "status_text": (
                "available"
                if gemini_model is not None
                else (gemini_unavailable_reason or "unavailable")
            ),
        },
    }
    return status


def ask_gpt(
    username,
    context_lines,
    role="mamulya",
    dispute=False,
    summary=False,
    rude=False,
    on_token: Optional[Callable[[str], None]] = None,
) -> AIResponse:
    try:
        if summary:
            tone_hint = get_summary_tone_hint()
            base_prompt = (
                "Ты — Мамуля, бабушка-битард из Telegram-чата. Тебе дали хронологию суток. "
                "Сначала перечитай каждую запись, а затем сделай дерзкую сводку: выдели 3–4 реальных события, "
                "назови участников ровно так, как они указаны, и поясни, чем они отличились. "
                f"{tone_hint} "
                "Не придумывай факты — если чего-то нет в логах, скажи об отсутствии инфы.\n"
                "Логи переписки:\n" + "\n".join(context_lines)
            )
        else:
            if rude:
                base_prompt = (
                    "Ты — Мамуля, бабушка-битард из Telegram-чата. Перед ответом перечитай 3–6 последних строк истории, "
                    "чтобы понять кому и за что отвечаешь. Бей едко: сарказм, местами мат и фирменные мемы разрешены, "
                    "но избегай разжигания ненависти и угроз. Никогда не придумывай фактов и не комментируй то, чего не было в логах.\n"
                    "Отвечай одной-двумя короткими фразами, ссылаясь на конкретные детали из свежих сообщений.\n"
                    "Контекст:\n" + "\n".join(context_lines)
                )
                if dispute:
                    base_prompt += "\nЕсли видишь спор, укажи кто что ляпнул и дай жёсткий вердикт по фактам, без выдумок."
            else:
                base_prompt = (
                    "Ты — Мамуля, бабушка-битард из Telegram-чата. Просматривай 3–6 последних реплик, чтобы понять настроение. "
                    "Отвечай тепло и иронично, добавляй мемы без токсичности и мата, поддерживай, но при необходимости слегка подкалывай. "
                    "Не придумывай события: реагируй только на свежие сообщения и упоминай детали из них.\n"
                    "Дай 1–2 коротких предложения.\n"
                    "Контекст:\n" + "\n".join(context_lines)
                )
                if dispute:
                    base_prompt += "\nЕсли замечаешь спор, отметь аргументы обеих сторон и предложи дружелюбный мемный выход из конфликта."
        response = generate_response(
            messages=[
                {
                    "role": "user",
                    "content": context_lines[-1] if context_lines else "",
                }
            ],
            system_prompt=base_prompt,
            temperature=0.95,
            top_p=1.0,
            max_output_tokens=600 if summary else 300,
            on_token=on_token,
        )
        bot_logger.debug(
            "mamoolya response model=%s summary=%s rude=%s length=%s",
            response.model,
            summary,
            rude,
            len(response.text),
        )
        return response
    except Exception as e:
        # Log the error and return a fallback message
        logger = logging.getLogger(__name__)
        logger.error(
            f"??????+??? ?????? ?????????????? ??????'????'?? ??????? GPT: {e}"
        )
        return AIResponse(
            text="????, ??'??-?'?? ???????>?? ???? ?'???? ?????? ?????????????? ??????'????'??... ???????????+?????'?? ?????????",
            model="unavailable",
            usage={},
        )


def _log_ai_usage(response: AIResponse, context: str) -> None:
    bot_logger.info(
        "ai_response context=%s model=%s input_tokens=%s output_tokens=%s total_tokens=%s",
        context,
        response.model,
        response.usage.get("input_tokens"),
        response.usage.get("output_tokens"),
        response.usage.get("total_tokens"),
    )


async def stream_ask_gpt_reply(
    placeholder_message,
    username,
    context_lines,
    *,
    dispute=False,
    summary=False,
    rude=False,
) -> AIResponse:
    context_lines = list(context_lines)
    if not summary:
        context_lines = trim_dialog_context(context_lines)
    loop = asyncio.get_running_loop()
    state = {"buffer": "", "last_edit": time.monotonic() - STREAM_EDIT_INTERVAL}

    async def _edit(text: str) -> None:
        try:
            await placeholder_message.edit_text(text or "?")
        except TelegramError as err:
            bot_logger.debug("stream edit skipped: %s", err)

    def _handle(delta: str) -> None:
        if not delta:
            return
        state["buffer"] += delta
        now = time.monotonic()
        if now - state["last_edit"] >= STREAM_EDIT_INTERVAL:
            state["last_edit"] = now
            loop.call_soon_threadsafe(asyncio.create_task, _edit(state["buffer"]))

    def _call() -> AIResponse:
        return ask_gpt(
            username,
            context_lines,
            role="mamulya",
            dispute=dispute,
            summary=summary,
            rude=rude,
            on_token=_handle,
        )

    response = await loop.run_in_executor(None, _call)
    await _edit(response.text.strip())
    _log_ai_usage(response, "ask_gpt")
    return response


async def stream_prompt_to_message(
    *,
    status_message,
    system_prompt: str,
    user_message: str = "",
    temperature: float = 1.0,
    top_p: float = 1.0,
    max_output_tokens: int = 300,
    usage_context: str = "custom_prompt",
) -> AIResponse:
    loop = asyncio.get_running_loop()
    state = {
        "buffer": "",
        "last_edit": time.monotonic() - STREAM_EDIT_INTERVAL,
        "done": False,
    }

    async def _edit(text: str) -> None:
        if state.get("done"):
            return
        try:
            chunk = text or "?"
            if state.get("last_text") == chunk:
                return
            if len(chunk) > TELEGRAM_MAX_MESSAGE_LENGTH:
                chunk = split_text_for_telegram(chunk)[0]
            await status_message.edit_text(chunk or "?")
            state["last_text"] = chunk
        except TelegramError as err:
            message = str(err).lower()
            if "message is not modified" in message:
                state["last_text"] = chunk
                return
            bot_logger.debug("stream edit skipped: %s", err)

    def _handle(delta: str) -> None:
        if not delta or state.get("done"):
            return
        state["buffer"] += delta
        now = time.monotonic()
        if now - state["last_edit"] >= STREAM_EDIT_INTERVAL:
            state["last_edit"] = now
            buffer_snapshot = state["buffer"]
            loop.call_soon_threadsafe(
                asyncio.create_task,
                _edit(buffer_snapshot),
            )

    def _call() -> AIResponse:
        return generate_response(
            messages=[{"role": "user", "content": user_message}],
            system_prompt=system_prompt,
            temperature=temperature,
            top_p=top_p,
            max_output_tokens=max_output_tokens,
            on_token=_handle,
        )

    response = await loop.run_in_executor(None, _call)
    state["done"] = True
    full_text = response.text.strip()
    final_chunk = full_text or "?"
    if len(final_chunk) <= TELEGRAM_MAX_MESSAGE_LENGTH:
        if state.get("last_text") != final_chunk:
            try:
                await status_message.edit_text(final_chunk)
            except TelegramError as err:
                if "message is not modified" not in str(err).lower():
                    raise
        state["last_text"] = final_chunk
    else:
        await edit_message_with_chunks(status_message, full_text)
        state["last_text"] = None
    _log_ai_usage(response, usage_context)
    return response


def get_filtered_day_messages(target_date, *, chat_id=None):
    """Return chat messages for the given day, filtered for summarisation."""
    if isinstance(target_date, datetime):
        normalized_date = target_date.astimezone(timezone.utc).date()
    elif isinstance(target_date, dt_date):
        normalized_date = target_date
    elif isinstance(target_date, str):
        try:
            normalized_date = dt_date.fromisoformat(target_date)
        except ValueError:
            normalized_date = datetime.fromisoformat(target_date).date()
    else:
        raise TypeError(f"Unsupported date type: {type(target_date)!r}")

    start = datetime.combine(normalized_date, dt_time.min)
    end = start + timedelta(days=1)

    target_chat_id = None
    if chat_id is not None:
        target_chat_id = chat_id
    elif MESSAGES_HAS_CHAT_ID:
        target_chat_id = globals().get("CHAT_ID") or None

    def _run_query(start_dt, end_dt):
        params = [
            start_dt.strftime("%Y-%m-%d %H:%M:%S"),
            end_dt.strftime("%Y-%m-%d %H:%M:%S"),
        ]
        clauses = [
            "SELECT username, message FROM messages",
            "WHERE timestamp >= ? AND timestamp < ?",
        ]
        if target_chat_id and MESSAGES_HAS_CHAT_ID:
            clauses.append("AND chat_id = ?")
            params.append(int(target_chat_id))
        clauses.append("ORDER BY timestamp ASC")
        sql = " ".join(clauses)
        cur = conn.cursor()
        try:
            cur.execute(sql, params)
            return cur.fetchall()
        finally:
            cur.close()

    rows = _run_query(start, end)
    if not rows:
        cur = conn.cursor()
        try:
            latest = cur.execute(
                "SELECT timestamp FROM messages ORDER BY timestamp DESC LIMIT 1"
            ).fetchone()
        finally:
            cur.close()
        if latest:
            try:
                latest_date = datetime.fromisoformat(latest[0]).date()
            except Exception:
                latest_date = None
            if latest_date and latest_date != normalized_date:
                fallback_start = datetime.combine(latest_date, dt_time.min)
                fallback_end = fallback_start + timedelta(days=1)
                rows = _run_query(fallback_start, fallback_end)
                bot_logger.debug(
                    "No messages for %s, falling back to %s",
                    normalized_date,
                    latest_date,
                )

    disallowed_prefixes = ("/",)
    filtered = []
    for username, raw_text in rows:
        if raw_text is None:
            continue
        text = raw_text.strip()
        if not text:
            continue
        if any(text.startswith(prefix) for prefix in disallowed_prefixes):
            continue
        name = (username or "").strip() or "unknown"
        filtered.append((name, text))
    return filtered


def split_into_chunks_by_length(messages, max_total_length=6000):
    "\n    Делит список сообщений на чанки так, чтобы суммарная длина текста в каждом чанке не превышала max_total_length символов.\n    Возвращает список чанков (каждый чанк — список (username, message)).\n"
    try:
        chunks = []
        current_chunk = []
        current_length = 0
        for msg in messages:
            msg_text = f"{msg[0]}: {msg[1]}\n"
            if current_length + len(msg_text) > max_total_length and current_chunk:
                chunks.append(current_chunk)
                current_chunk = []
                current_length = 0
            current_chunk.append(msg)
            current_length += len(msg_text)
        if current_chunk:
            chunks.append(current_chunk)
        return chunks
    except Exception as e:
        # Log the error and return an empty list
        logger = logging.getLogger(__name__)
        logger.error(f"Ошибка при разделении сообщений на чанки: {e}")
        return []


async def generate_summary_with_model(
    prompt,
    model_type="gpt",
    *,
    max_output_tokens: Optional[int] = None,
    _allow_groq_fallback: bool = True,
) -> str:
    """Универсальная функция для генерации саммари с поддержкой GPT и Gemini.

    Для GPT добавлена поддержка автоматического продолжения, если модель
    обрывает ответ из-за ограничения по токенам.
    """
    try:
        openai_primary_model: Optional[str] = None
        if model_type == "gpt-3.5":
            openai_primary_model = os.getenv("OPENAI_SUMMARY_GPT35", "gpt-3.5-turbo")
        elif model_type == "groq":
            openai_primary_model = "groq"
        if model_type == "gemini":
            try:
                model = get_gemini_model()
                response = model.generate_content(prompt)
                return response.text.strip()
            except Exception as gemini_err:
                logging.getLogger(__name__).warning(
                    "Gemini недоступен, переключаюсь на GPT: %s", gemini_err
                )
                model_type = "gpt"
        # gpt или запасной путь
        loop = asyncio.get_running_loop()
        max_tokens = max_output_tokens or 360
        conversation = [{"role": "user", "content": ""}]
        collected_parts: List[str] = []
        max_attempts = 3

        for attempt in range(max_attempts):

            def _call(messages: List[Dict[str, str]]) -> AIResponse:
                return generate_response(
                    messages=messages,
                    system_prompt=prompt,
                    temperature=1.08,
                    top_p=1.0,
                    max_output_tokens=max_tokens,
                    primary_model=openai_primary_model,
                )

            response = await loop.run_in_executor(None, _call, list(conversation))
            chunk = response.text.strip()
            if not chunk or chunk == "[empty response]":
                break

            collected_parts.append(chunk)

            usage = response.usage or {}
            output_tokens = usage.get("output_tokens") if usage else None
            # Если токенов хватило или попытки исчерпаны — выходим
            if (
                output_tokens is None
                or output_tokens < max_tokens - 20
                or attempt == max_attempts - 1
            ):
                break

            # Добавляем историю и просим модель продолжить с места остановки
            conversation.append({"role": "assistant", "content": chunk})
            conversation.append(
                {
                    "role": "user",
                    "content": "Продолжи саммари в том же стиле, не повторяя написанное. Начинай сразу по делу.",
                }
            )

        combined = "\n\n".join(part.strip() for part in collected_parts if part).strip()
        return combined or "[empty response]"
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(
            f"Ошибка при генерации саммари с моделью {model_type}: {e}", exc_info=True
        )
        if model_type == "groq" and _allow_groq_fallback and is_openai_available():
            logger.warning("Groq недоступен, пробуем GPT fallback для саммари.")
            return await generate_summary_with_model(
                prompt,
                "gpt",
                max_output_tokens=max_output_tokens,
                _allow_groq_fallback=False,
            )
        error_text = str(e).strip()
        if not error_text:
            error_text = "Попробуйте снова позже."
        else:
            error_text = error_text.split("\n", 1)[0]
            if len(error_text) > 180:
                error_text = error_text[:177] + "..."
        return f"Ой, что-то пошло не так при генерации саммари ({model_type}): {error_text}"


def is_summary_error_text(text: str) -> bool:
    if not text:
        return True
    lowered = text.strip().lower()
    return "что-то пошло не так" in lowered and "саммари" in lowered


async def summarize_chunk(chunk, model_type="gpt"):
    # chunk — список (username, message)
    try:
        context_lines = [f"{u}: {m}" for u, m in chunk]
        tone_hint = get_summary_tone_hint()
        prompt = (
            "Ты — Мамуля, легендарная бабушка-битард из Telegram-чата. На основе этого блока переписки сделай резкий, но точный пересказ. "
            "Укажи, кто что сказал, какие мемы или конфликты всплыли, чем всё закончилось. "
            f"{tone_hint} "
            "Главное — ноль выдумок: если чего-то нет в тексте, не упоминай. "
            "Формат — 2–3 предложения. Вот логи:\n" + "\n".join(context_lines)
        )
        return await generate_summary_with_model(prompt, model_type)
    except Exception as e:
        # Log the error and return a fallback message
        logger = logging.getLogger(__name__)
        logger.error(f"Ошибка при суммаризации чанка: {e}")
        return "Ой, что-то пошло не так при суммаризации чанка... Попробуйте позже."


async def summarize_day(date, chat_id=None):
    try:
        bot_logger.debug(f"Summarizing day {date}")
        # 1. Собрать и отфильтровать сообщения за день
        messages = get_filtered_day_messages(date, chat_id=chat_id)
        if not messages:
            return "Сегодня сообщений не было."

        # 2. Определить модель для генерации
        model_type = "gpt"  # по умолчанию
        if chat_id:
            model_type = get_summary_model_for_chat(chat_id)

        # 3. Разбить на чанки по длине текста
        chunks = split_into_chunks_by_length(messages, max_total_length=6000)

        # 4. Сгенерировать краткое саммари для каждого чанка
        chunk_summaries = []
        for chunk in chunks:
            summary = await summarize_chunk(chunk, model_type)
            chunk_summaries.append(summary)

        # 5. Итоговое саммари дня
        tone_hint = get_summary_tone_hint()
        final_prompt = (
            "Вот краткие саммари дня по частям (они уже выжаты из логов):\n"
            + "\n---\n".join(chunk_summaries)
            + "\n\nСобери из них единый рассказ за день. Отметь реальные события в порядке по времени, назови участников так, как они указаны, "
            "и подчеркни мемы, драму и итоги. "
            f"{tone_hint} "
            "Не выдумывай деталей: если информации мало, скажи об этом. Стиль — фирменный Мамули, 4–6 предложений."
        )

        return await generate_summary_with_model(final_prompt, model_type)
    except Exception as e:
        # Log the error and return a fallback message
        logger = logging.getLogger(__name__)
        logger.error(f"Ошибка при суммаризации дня: {e}")
        return "Ой, что-то пошло не так при суммаризации дня... Попробуйте позже."


# === Команды ===
async def start(update, context):
    await update.message.reply_text("Мамуля тут! Жду ваши срачи и мемы.")


async def randomquote(update, context):
    cursor.execute(
        "SELECT username, message FROM messages WHERE LENGTH(message)>15 AND chat_id=? ORDER BY RANDOM() LIMIT 1",
        (update.effective_chat.id,),
    )
    row = cursor.fetchone()
    if row:
        await update.message.reply_text(f"Цитата от {row[0]}:\n\n{row[1]}")
    else:
        await update.message.reply_text("Пока нет подходящих сообщений.")


async def top_pairs(update, context):
    cursor.execute(
        "SELECT username, reply_to FROM messages WHERE reply_to IS NOT NULL AND chat_id=?",
        (update.effective_chat.id,),
    )
    raw_pairs = [
        (user, r_to)
        for user, r_to in cursor.fetchall()
        if user and r_to and user != r_to
    ]
    pair_counter = Counter()
    for a, b in raw_pairs:
        key = tuple(sorted([a, b]))
        pair_counter[key] += 1
    top5 = pair_counter.most_common(5)
    if top5:
        text = "Топ-5 пар ответов:\n" + "\n".join(
            f"{i+1}. {a} & {b}: {cnt}" for i, ((a, b), cnt) in enumerate(top5)
        )
    else:
        text = "Нет данных по парам ответов."
    await update.message.reply_text(text)


async def sticker_stats(update, context):
    cursor.execute(
        "SELECT message FROM messages WHERE chat_id=?", (update.effective_chat.id,)
    )
    all_text = "".join(r[0] for r in cursor.fetchall())
    all_emojis = [c for c in all_text if c in emoji_lib.EMOJI_DATA]
    top5 = Counter(all_emojis).most_common(5)
    if top5:
        await update.message.reply_text(
            "Топ-5 эмодзи:\n" + "\n".join(f"{e} — {c}" for e, c in top5)
        )
    else:
        await update.message.reply_text("Эмодзи не найдены.")


async def my_stats(update, context):
    user = update.effective_user.first_name or "Неизвестный"
    cursor.execute(
        "SELECT COUNT(*) FROM messages WHERE username = ? AND chat_id=?",
        (user, update.effective_chat.id),
    )
    msg_count = cursor.fetchone()[0]
    cursor.execute(
        "SELECT message FROM messages WHERE username = ? AND chat_id=?",
        (user, update.effective_chat.id),
    )
    all_text = "".join(r[0] for r in cursor.fetchall())
    all_emojis = [c for c in all_text if c in emoji_lib.EMOJI_DATA]
    if all_emojis:
        top_emoji, top_emoji_count = Counter(all_emojis).most_common(1)[0]
        emoji_stat = f"Твой любимый эмодзи: {top_emoji} — {top_emoji_count} раз(а)"
    else:
        emoji_stat = "Ты ещё не использовал эмодзи!"
    praise, abuse = get_user_rep(user, update.effective_chat.id)
    # === Реакции ===
    cursor.execute(
        "SELECT to_user, emoji FROM reactions WHERE from_user=? AND chat_id=?",
        (user, update.effective_chat.id),
    )
    reactions = cursor.fetchall()
    if reactions:
        # Топ-1 кому ставил реакции
        pair_counter = Counter()
        emoji_map = {}
        for to_user, reaction_emoji in reactions:
            pair_counter[to_user] += 1
            emoji_map.setdefault(to_user, []).append(reaction_emoji)
        top_user, top_count = pair_counter.most_common(1)[0]
        top_emojis = Counter(emoji_map[top_user]).most_common()
        top_emojis_str = ", ".join(f"{e} — {c}" for e, c in top_emojis)
        all_reactions = "\n".join(f"{u}: {', '.join(emoji_map[u])}" for u in emoji_map)
        reaction_stat = (
            f"\nТоп-1 кому ты ставил реакции: {top_user} ({top_count} раз)\n"
            f"Эмодзи: {top_emojis_str}\n"
            f"\nКому и какие реакции ты ставил:\n{all_reactions}"
        )
    else:
        reaction_stat = "\nТы ещё не ставил реакции другим!"
    reply = (
        f"Твоя статистика, {user}:\n"
        f"Всего сообщений: {msg_count}\n"
        f"Похвал мамуле: {praise}, Оскорблений мамуле: {abuse}\n"
        f"{emoji_stat}"
        f"{reaction_stat}"
    )
    await update.message.reply_text(reply)


async def ignore_me(update, context):
    user = update.effective_user.first_name or "Неизвестный"
    set_ignored(user, True)
    await update.message.reply_text("Мамуля будет тебя игнорить до команды /notice_me.")


async def notice_me(update, context):
    user = update.effective_user.first_name or "Неизвестный"
    set_ignored(user, False)
    await update.message.reply_text("Мамуля снова будет тебе отвечать.")


async def summary(update, context):
    chat_admins = await context.bot.get_chat_administrators(update.effective_chat.id)
    admin_ids = [a.user.id for a in chat_admins]
    if update.effective_user.id not in admin_ids:
        await update.message.reply_text(
            "Ой-ой, /summary — только для уважаемых админов. Кыш отсюда, внучек!"
        )
        return
    # Send a message indicating that generation has started
    status_message = await update.message.reply_text("Генерирую саммари дня...")
    try:
        today = utctoday()
        target_chat_id = update.effective_chat.id if update.effective_chat else None
        reply = await summarize_day(today, chat_id=target_chat_id)
        # Edit the status message with the generated content
        await edit_message_with_chunks(status_message, reply, parse_mode=None)
    except Exception as e:
        # If an error occurs, edit the status message to inform the user
        await status_message.edit_text(f"Ошибка при генерации саммари: {e}")


async def summary_day(update, context):
    chat_admins = await context.bot.get_chat_administrators(update.effective_chat.id)
    admin_ids = [a.user.id for a in chat_admins]
    if update.effective_user.id not in admin_ids:
        await update.message.reply_text(
            "Ой-ой, /summary_day — только для уважаемых админов. Кыш отсюда, внучек!"
        )
        return
    # Send a message indicating that generation has started
    status_message = await update.message.reply_text("Генерирую саммари дня...")
    try:
        today = utctoday()
        target_chat_id = update.effective_chat.id if update.effective_chat else None
        reply = await summarize_day(today, chat_id=target_chat_id)
        # Edit the status message with the generated content
        await edit_message_with_chunks(status_message, reply, parse_mode=None)
    except Exception as e:
        # If an error occurs, edit the status message to inform the user
        await status_message.edit_text(f"Ошибка при генерации саммари: {e}")


async def summary_week(update, context):
    chat_admins = await context.bot.get_chat_administrators(update.effective_chat.id)
    admin_ids = [a.user.id for a in chat_admins]
    if update.effective_user.id not in admin_ids:
        await update.message.reply_text(
            "Ой-ой, /summary_week — только для уважаемых админов. Кыш отсюда, внучек!"
        )
        return
    # Send a message indicating that generation has started
    status_message = await update.message.reply_text("Генерирую саммари недели...")
    try:
        today = utctoday()
        target_chat_id = update.effective_chat.id if update.effective_chat else None
        week_ago = today - timedelta(days=6)
        dates = [week_ago + timedelta(days=i) for i in range(7)]
        # Получить саммари каждого дня
        daily_summaries = []
        max_day_summary_length = 1600
        for d in dates:
            day_summary = await summarize_day(d, chat_id=target_chat_id)
            if len(day_summary) > max_day_summary_length:
                trimmed = day_summary[:max_day_summary_length]
                last_space = trimmed.rfind(" ")
                if last_space > 0:
                    trimmed = trimmed[:last_space]
                day_summary = trimmed.rstrip() + "..."
            daily_summaries.append(f"{d.strftime('%d.%m.%Y')}\n{day_summary}")
        # Определить модель для генерации
        model_type = "gpt"  # по умолчанию
        if target_chat_id:
            model_type = get_summary_model_for_chat(target_chat_id)

        # Итоговое недельное саммари
        tone_hint = get_summary_tone_hint()
        final_prompt = (
            "Вот саммари по дням за неделю:\n"
            + "\n---\n".join(daily_summaries)
            + "\n\nСобери недельный обзор: упорядочь реальные события, назови героев, мемы и ключевые конфликты. "
            f"{tone_hint} "
            "Не придумывай фактов и не меняй имена. Пиши в стиле Мамули — смешно, едко, но по делу. "
            "Объём — до 12 предложений (≈1700 символов). Если текст обрывается, продолжи следующим абзацем без повторов."
        )

        reply = await generate_summary_with_model(
            final_prompt, model_type, max_output_tokens=360
        )
        # Edit the status message with the generated content
        await edit_message_with_chunks(status_message, reply, parse_mode=None)
        if not is_summary_error_text(reply):
            # Топ-5 ноулайферов за неделю (по текущему чату)
            cursor.execute(
                "SELECT username, COUNT(*) as cnt FROM messages WHERE chat_id=? AND date(timestamp) BETWEEN ? AND ? GROUP BY username ORDER BY cnt DESC LIMIT 5",
                (update.effective_chat.id, week_ago, today),
            )
            rows = cursor.fetchall()
            if rows:
                text = "\nТоп-5 ноулайферов за неделю:\n"
                medals = ["🥇", "🥈", "🥉"] + [""] * 7
                for i, (user, cnt) in enumerate(rows):
                    medal = medals[i] if i < len(medals) else ""
                    text += f"{medal} {i+1}. {user} — {cnt} сообщений\n"
                await update.message.reply_text(text)
    except Exception as e:
        # If an error occurs, edit the status message to inform the user
        await status_message.edit_text(f"Ошибка при генерации недельного саммари: {e}")


async def top_nolifers(update, context):
    if MESSAGES_HAS_CHAT_ID and update.effective_chat:
        cursor.execute(
            "SELECT username, COUNT(*) as cnt FROM messages WHERE chat_id=? GROUP BY username ORDER BY cnt DESC LIMIT 10",
            (update.effective_chat.id,),
        )
    else:
        cursor.execute(
            "SELECT username, COUNT(*) as cnt FROM messages GROUP BY username ORDER BY cnt DESC LIMIT 10"
        )
    rows = cursor.fetchall()
    if not rows:
        await update.message.reply_text("Пока нет ноулайферов в конфе!")
        return
    text = "Топ ноулайферов конфы (по количеству сообщений):\n"
    medals = ["🥇", "🥈", "🥉"] + ["🏅"] * 7
    for i, (user, cnt) in enumerate(rows):
        medal = medals[i] if i < len(medals) else ""
        text += f"{medal} {i+1}. {user} — {cnt} сообщений\n"
    text += "\nПоздравляю, вы официально не выходите из чата!"
    await update.message.reply_text(text)


async def top_nolifers_day(update, context):
    today = utctoday()
    if MESSAGES_HAS_CHAT_ID and update.effective_chat:
        cursor.execute(
            "SELECT username, COUNT(*) as cnt FROM messages WHERE chat_id=? AND date(timestamp)=? GROUP BY username ORDER BY cnt DESC LIMIT 10",
            (update.effective_chat.id, today),
        )
    else:
        cursor.execute(
            "SELECT username, COUNT(*) as cnt FROM messages WHERE date(timestamp)=? GROUP BY username ORDER BY cnt DESC LIMIT 10",
            (today,),
        )
    rows = cursor.fetchall()
    if not rows:
        await update.message.reply_text("Сегодня никто не ноулайфил!")
        return
    text = "Топ ноулайферов за сегодня:\n"
    medals = ["🥇", "🥈", "🥉"] + ["🏅"] * 7
    for i, (user, cnt) in enumerate(rows):
        medal = medals[i] if i < len(medals) else ""
        text += f"{medal} {i+1}. {user} — {cnt} сообщений\n"
    await update.message.reply_text(text)


async def top_nolifers_week(update, context):
    today = utctoday()
    week_ago = today - timedelta(days=6)
    if MESSAGES_HAS_CHAT_ID and update.effective_chat:
        cursor.execute(
            "SELECT username, COUNT(*) as cnt FROM messages WHERE chat_id=? AND date(timestamp) BETWEEN ? AND ? GROUP BY username ORDER BY cnt DESC LIMIT 5",
            (update.effective_chat.id, week_ago, today),
        )
    else:
        cursor.execute(
            "SELECT username, COUNT(*) as cnt FROM messages WHERE date(timestamp) BETWEEN ? AND ? GROUP BY username ORDER BY cnt DESC LIMIT 5",
            (week_ago, today),
        )
    rows = cursor.fetchall()
    if not rows:
        await update.message.reply_text("За неделю никто не ноулайфил!")
        return
    text = "Топ ноулайферов за неделю:\n"
    medals = ["🥇", "🥈", "🥉", "🏅", "🏅"]
    for i, (user, cnt) in enumerate(rows):
        medal = medals[i] if i < len(medals) else ""
        text += f"{medal} {i+1}. {user} — {cnt} сообщений\n"
    await update.message.reply_text(text)


async def days_without_drama(update, context):
    current_chat_id = (
        update.effective_chat.id if update and update.effective_chat else None
    )
    if current_chat_id is not None:
        cursor.execute(
            "SELECT last_drama_date FROM days_without_drama WHERE chat_id=? LIMIT 1",
            (current_chat_id,),
        )
    else:
        cursor.execute("SELECT last_drama_date FROM days_without_drama LIMIT 1")
    row = cursor.fetchone()
    today = utctoday()
    if row and row[0]:
        last_drama = datetime.strptime(row[0], "%Y-%m-%d").date()
        days = (today - last_drama).days
    else:
        days = "∞"
    await update.message.reply_text(f"{days} дней без срача!")


async def drama(update, context):
    today = utctoday().strftime("%Y-%m-%d")
    current_chat_id = (
        update.effective_chat.id if update and update.effective_chat else None
    )
    if current_chat_id is not None:
        cursor.execute(
            "DELETE FROM days_without_drama WHERE chat_id=?", (current_chat_id,)
        )
        cursor.execute(
            "INSERT INTO days_without_drama(last_drama_date, chat_id) VALUES (?, ?)",
            (today, current_chat_id),
        )
    else:
        cursor.execute("DELETE FROM days_without_drama")
        cursor.execute(
            "INSERT INTO days_without_drama(last_drama_date) VALUES (?)", (today,)
        )
    conn.commit()
    # Отправить картинку 0 дней без срача
    with open("../drama_zero.png", "rb") as photo:
        await update.message.reply_photo(photo, caption="0 дней без срача!")


async def dvach(update, context):
    # Send a message indicating that generation has started
    status_message = await update.message.reply_text("Генерирую пост...")

    try:
        cursor.execute(
            "SELECT username, message FROM messages ORDER BY id DESC LIMIT 50"
        )
        msgs = [f"{u}: {m}" for u, m in reversed(cursor.fetchall())]
        context_text = "\n".join(msgs)
        prompt = (
            "Ты — опытный аноним с двача. Придумай новую пасту (пост), которая идеально впишется в обсуждение. "
            "Вдохновляйся только тем, что обсуждали в этих сообщениях, но не копируй их. "
            "Используй максимум сленга, мемов, иронии и самобытного стиля двача. Не бойся провокационных фраз, можно переходить границы. "
            "Пасту пиши так, чтобы любой олдфаг поверил, что её реально слили с двача. "
            "ОТВЕЧАЙ КОРОТКО: не более 3 предложений, без лишней воды!\n"
            f"Вот свежий контекст:\n{context_text}"
        )
        await stream_prompt_to_message(
            status_message=status_message,
            system_prompt=prompt,
            temperature=1.1,
            max_output_tokens=300,
            usage_context="dvach_pasta",
        )
    except Exception as e:
        # If an error occurs, edit the status message to inform the user
        await status_message.edit_text(f"Ошибка при генерации поста: {e}")


async def psychologist(update, context):
    # Send a message indicating that generation has started
    status_message = await update.message.reply_text("Генерирую мемную поддержку...")

    try:
        user = update.effective_user.first_name or "Неизвестный"
        praise, abuse = get_user_rep(user, update.effective_chat.id)
        rude = should_use_rude_voice(praise, abuse, min_abuse=1)
        if rude:
            phrase = random.choice(MAMULYA_PSYCHO_PHRASES_RUDE)
        else:
            phrase = random.choice(MAMULYA_PSYCHO_PHRASES_NICE)
        # Edit the status message with the generated content
        await status_message.edit_text(phrase)
    except Exception as e:
        # If an error occurs, edit the status message to inform the user
        await status_message.edit_text(f"Ошибка при генерации поддержки: {e}")


async def predict(update, context):
    user = update.effective_user
    chat = update.effective_chat
    chat_id = chat.id if chat else None

    user_key = _prediction_user_key(user)
    legacy_key = None

    today_iso = utctoday().isoformat()
    last_date = _get_last_prediction_date(user_key, chat_id)

    if not last_date and user and user.username:
        legacy_key = user.username
        last_date = _get_last_prediction_date(legacy_key, chat_id)

    target_message = getattr(update, "message", None)

    if last_date == today_iso:
        already_text = "🔮 Предсказатель уже делился мудростью сегодня. Забегай завтра за новой мемной истиной!"
        if target_message:
            await target_message.reply_text(already_text)
        elif chat_id:
            await context.bot.send_message(chat_id=chat_id, text=already_text)
        return

    display_name = None
    if user:
        display_name = user.first_name or user.full_name or user.username

    prediction_text = _generate_prediction_text(display_name)

    if target_message:
        await target_message.reply_text(prediction_text)
    elif chat_id:
        await context.bot.send_message(chat_id=chat_id, text=prediction_text)

    _set_last_prediction_date(user_key, chat_id, today_iso)
    if legacy_key and legacy_key != user_key:
        try:
            cursor.execute(
                "DELETE FROM last_prediction WHERE username=?", (legacy_key,)
            )
            conn.commit()
        except Exception:
            logging.getLogger(__name__).exception(
                "Не удалось удалить устаревшую запись предсказателя"
            )


async def fact(update, context):
    # Send a message indicating that generation has started
    status_message = await update.message.reply_text("Готовлю точный факт о тебе…")

    try:
        user = update.effective_user.first_name or "Неизвестный"
        praise, abuse = get_user_rep(user, update.effective_chat.id)
        rude = should_use_rude_voice(praise, abuse, min_abuse=1)
        cursor.execute(
            "SELECT message FROM messages WHERE username=? ORDER BY id DESC", (user,)
        )
        msgs = []
        for r in cursor.fetchall():
            if len(r[0].split()) > 5:
                msgs.append(r[0])
            if len(msgs) >= 300:
                break
        context_text = "\n".join(msgs)
        base_prompt = (
            f"Ты — Мамуля, мемный летописец Telegram-чата. У тебя есть сырой контекст: около 300 последних сообщений пользователя {user}, каждое длиннее пяти слов."
            " Проанализируй стиль, любимые темы, мемы, частоту активности, упоминание других участников, эмодзи и общую подачу."
            " Сформулируй один-единственный факт-наблюдение про этого человека. Ответ должен состоять из 1–2 предложений (до 50 слов) и звучать как живое наблюдение, а не список."
            " Если информации мало, сделай аккуратное предположение по тону или времени активности."
            " Не цитируй сообщения дословно, не перечисляй фактами и не используй Markdown/HTML."
        )

        if rude:
            tone = (
                "Тон язвительный, дерзкий и хлёсткий, но без прямых оскорблений: допустим лёгкий мат, сарказм и мемный подкол."
                " Финал — предупреждение или совет с фирменной жёсткостью."
            )
        else:
            tone = "Тон дружелюбный и ироничный: мягкая подкол, тёплый мем и ободряющий вывод/совет."

        prompt = (
            f"{base_prompt} {tone}\n" f"История сообщений пользователя:\n{context_text}"
        )

        await stream_prompt_to_message(
            status_message=status_message,
            system_prompt=prompt,
            temperature=0.95,
            top_p=0.9,
            max_output_tokens=140,
            usage_context="user_fact",
        )
    except Exception as e:
        # If an error occurs, edit the status message to inform the user
        await status_message.edit_text(f"Ошибка при генерации факта: {e}")


async def imitate(update, context):
    if not context.args or len(context.args) < 1:
        await update.message.reply_text("Используй: /imitate <имя_пользователя>")
        return

    # Send a message indicating that generation has started
    status_message = await update.message.reply_text(
        "Генерирую имитацию пользователя..."
    )

    try:
        target_user = " ".join(context.args)
        # 100 сообщений пользователя длиннее 5 слов
        cursor.execute(
            "SELECT message FROM messages WHERE username=? ORDER BY id DESC LIMIT 100",
            (target_user,),
        )
        user_msgs = []
        for r in cursor.fetchall():
            if len(r[0].split()) > 5:
                user_msgs.append(r[0])
        context_user_text = "\n".join(user_msgs)

        if not context_user_text:
            await status_message.edit_text("Кто это? Таких мы тут не знаем.")
            return

        prompt = (
            f"У тебя есть 100 сообщений пользователя {target_user} (каждое длиннее 5 слов). Выдели из них его стиль, характерные обороты, любимые слова, типичные мемы и темы. "
            f"Сгенерируй короткий (1-2 предложения) оригинальный текст в стиле этого пользователя. Не копируй сообщения, а используй его любимые обороты, мемы, стиль.\n"
            f"Вот сообщения пользователя:\n{context_user_text}"
        )
        await stream_prompt_to_message(
            status_message=status_message,
            system_prompt=prompt,
            temperature=1.1,
            max_output_tokens=200,
            usage_context="imitate_user",
        )
    except Exception as e:
        # If an error occurs, edit the status message to inform the user
        await status_message.edit_text(f"Ошибка при генерации имитации: {e}")


async def publish_anons(update, context):
    # Для автоматической публикации пропускаем проверку администратора
    is_auto = (
        not hasattr(update.message, "reply_text")
        or update.message.reply_text.__name__ == "<lambda>"
    )
    status_message = None

    if not is_auto:
        try:
            chat_admins = await context.bot.get_chat_administrators(
                update.effective_chat.id
            )
            admin_ids = [a.user.id for a in chat_admins]
            if update.effective_user.id not in admin_ids:
                await update.message.reply_text("Только для админов!")
                return
        except Exception as e:
            print(f"Ошибка при проверке прав администратора: {e}")
            # Продолжаем выполнение даже если не удалось проверить права администратора
            pass

        # Send a message indicating that publication has started
        status_message = await update.message.reply_text("Публикую анонимки...")

    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        current_chat_id = (
            update.effective_chat.id if update and update.effective_chat else None
        )
        # Публикуем только сообщения этой группы (или без chat_id для обратной совместимости)
        if current_chat_id is not None:
            c.execute(
                "SELECT id, message FROM anon_messages WHERE published=0 AND (chat_id IS NULL OR chat_id=?) ORDER BY id ASC",
                (current_chat_id,),
            )
        else:
            c.execute(
                "SELECT id, message FROM anon_messages WHERE published=0 ORDER BY id ASC"
            )
        rows = c.fetchall()
        if not rows:
            if not is_auto and status_message:
                await status_message.edit_text("Нет новых анонимок.")
            elif not is_auto:
                await update.message.reply_text("Нет новых анонимок.")
            conn.close()
            return

        published_count = 0
        now = datetime.now().isoformat(sep=" ", timespec="seconds")
        for anon_id, msg in rows:
            try:
                text = f"{msg}\n\n_Анонимка №{anon_id}_"
                await context.bot.send_message(
                    chat_id=current_chat_id, text=text, parse_mode="Markdown"
                )
                # При публикации фиксируем chat_id для обратной совместимости
                if current_chat_id is not None:
                    c.execute(
                        "UPDATE anon_messages SET published=1, published_at=?, chat_id=? WHERE id= ?",
                        (now, current_chat_id, anon_id),
                    )
                else:
                    c.execute(
                        "UPDATE anon_messages SET published=1, published_at=? WHERE id=?",
                        (now, anon_id),
                    )
                published_count += 1
                print(f"Опубликована анонимка №{anon_id}")
            except Exception as e:
                print(f"Ошибка при публикации анонимки №{anon_id}: {e}")
                # Продолжаем публикацию остальных сообщений

        conn.commit()
        conn.close()

        if not is_auto and status_message:
            await status_message.edit_text(f"Опубликовано анонимок: {published_count}")
        elif not is_auto:
            await update.message.reply_text(f"Опубликовано анонимок: {published_count}")
        else:
            print(f"Автоматически опубликовано анонимок: {published_count}")
    except Exception as e:
        # If an error occurs, edit the status message to inform the user
        print(f"Ошибка при публикации анонимок: {e}")
        if not is_auto and status_message:
            await status_message.edit_text(f"Ошибка при публикации анонимок: {e}")
        elif not is_auto:
            await update.message.reply_text(f"Ошибка при публикации анонимок: {e}")


async def anon_sender(update, context):
    try:
        chat_admins = await context.bot.get_chat_administrators(
            update.effective_chat.id
        )
        admin_ids = [a.user.id for a in chat_admins]
        if update.effective_user.id not in admin_ids:
            await update.message.reply_text("Только для админов!")
            return
        if not context.args or not context.args[0].isdigit():
            await update.message.reply_text("Используй: /anon_sender <id>")
            return
        anon_id = int(context.args[0])
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute(
            "SELECT id, user_id, username, first_name, created_at, published, published_at FROM anon_messages WHERE id=?",
            (anon_id,),
        )
        row = c.fetchone()
        conn.close()
        if not row:
            await update.message.reply_text("Нет анонимки с таким id.")
            return
        id_, user_id, username, first_name, created_at, published, published_at = row
        text = (
            f"Анонимка №{id_}\n"
            f"user_id: {user_id}\n"
            f"username: {username}\n"
            f"first_name: {first_name}\n"
            f"Создана: {created_at}\n"
            f"Опубликована: {'да' if published else 'нет'}\n"
            f"Время публикации: {published_at if published else '-'}"
        )
        await update.message.reply_text(text)
    except Exception as e:
        # If an error occurs, inform the user
        await update.message.reply_text(
            f"Ошибка при получении информации об анонимке: {e}"
        )


async def friend_foe_stats(update, context):
    try:
        user = update.effective_user
        user_id = str(user.id)
        target_chat_id = None
        if update.effective_chat:
            target_chat_id = update.effective_chat.id
        env_chat_id = globals().get("CHAT_ID")
        if target_chat_id is None and env_chat_id:
            target_chat_id = env_chat_id
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            # Получаем user_id -> username
            user_map_query = (
                "SELECT user_id, username FROM messages WHERE user_id IS NOT NULL"
            )
            user_map_params = []
            if MESSAGES_HAS_CHAT_ID and target_chat_id is not None:
                user_map_query += " AND chat_id = ?"
                user_map_params.append(int(target_chat_id))
            c.execute(user_map_query, user_map_params)
            user_map = {str(row[0]): row[1] for row in c.fetchall()}
            # Кого я добавил
            friend_query = (
                "SELECT target_user_id, relation FROM friend_foe WHERE voter_user_id=?"
            )
            friend_params = [user_id]
            if FRIEND_FOE_HAS_CHAT_ID and target_chat_id is not None:
                friend_query += " AND chat_id = ?"
                friend_params.append(int(target_chat_id))
            c.execute(friend_query, tuple(friend_params))
            friends, foes = [], []
            for target_id, rel in c.fetchall():
                name = user_map.get(str(target_id), str(target_id))
                if rel == "friend":
                    friends.append(name)
                elif rel == "foe":
                    foes.append(name)
            # Кто меня добавил
            voters_query = (
                "SELECT voter_user_id, relation FROM friend_foe WHERE target_user_id=?"
            )
            voters_params = [user_id]
            if FRIEND_FOE_HAS_CHAT_ID and target_chat_id is not None:
                voters_query += " AND chat_id = ?"
                voters_params.append(int(target_chat_id))
            c.execute(voters_query, tuple(voters_params))
            friends_me, foes_me = [], []
            for voter_id, rel in c.fetchall():
                name = user_map.get(str(voter_id), str(voter_id))
                if rel == "friend":
                    friends_me.append(name)
                elif rel == "foe":
                    foes_me.append(name)
        text = (
            f"<b>Кого ты добавил в друзья:</b> {', '.join(friends) if friends else 'никого'}\n"
            f"<b>Кого ты добавил в козлы:</b> {', '.join(foes) if foes else 'никого'}\n\n"
            f"<b>Кто тебя добавил в друзья:</b> {', '.join(friends_me) if friends_me else 'никто'}\n"
            f"<b>Кто тебя добавил в козлы:</b> {', '.join(foes_me) if foes_me else 'никто'}"
        )
        await update.message.reply_text(text, parse_mode="HTML")
    except Exception as e:
        # If an error occurs, inform the user
        await update.message.reply_text(
            f"Ошибка при получении статистики друзей/козлов: {e}"
        )


async def friend_foe_top(update, context):
    try:
        target_chat_id = None
        if update.effective_chat:
            target_chat_id = update.effective_chat.id
        env_chat_id = globals().get("CHAT_ID")
        if target_chat_id is None and env_chat_id:
            target_chat_id = env_chat_id
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            # user_id -> username
            user_map_query = (
                "SELECT user_id, username FROM messages WHERE user_id IS NOT NULL"
            )
            user_map_params = []
            if MESSAGES_HAS_CHAT_ID and target_chat_id is not None:
                user_map_query += " AND chat_id = ?"
                user_map_params.append(int(target_chat_id))
            c.execute(user_map_query, user_map_params)
            user_map = {str(row[0]): row[1] for row in c.fetchall()}
            # Топ друзей
            friend_top_query = "SELECT target_user_id, COUNT(*) as cnt FROM friend_foe WHERE relation='friend'"
            friend_top_params = []
            if FRIEND_FOE_HAS_CHAT_ID and target_chat_id is not None:
                friend_top_query += " AND chat_id = ?"
                friend_top_params.append(int(target_chat_id))
            friend_top_query += " GROUP BY target_user_id ORDER BY cnt DESC LIMIT 3"
            c.execute(friend_top_query, tuple(friend_top_params))
            top_friends = [
                (user_map.get(str(uid), str(uid)), cnt) for uid, cnt in c.fetchall()
            ]
            # Топ козлов
            foe_top_query = "SELECT target_user_id, COUNT(*) as cnt FROM friend_foe WHERE relation='foe'"
            foe_top_params = []
            if FRIEND_FOE_HAS_CHAT_ID and target_chat_id is not None:
                foe_top_query += " AND chat_id = ?"
                foe_top_params.append(int(target_chat_id))
            foe_top_query += " GROUP BY target_user_id ORDER BY cnt DESC LIMIT 3"
            c.execute(foe_top_query, tuple(foe_top_params))
            top_foes = [
                (user_map.get(str(uid), str(uid)), cnt) for uid, cnt in c.fetchall()
            ]
        text = "<b>Топ-3 друзей чата 🫂:</b>\n"
        if top_friends:
            for i, (name, cnt) in enumerate(top_friends, 1):
                text += f"{i}. {name} — {cnt} раз(а)\n"
        else:
            text += "Нет данных\n"
        text += "\n<b>Топ-3 козлов чата 🐐:</b>\n"
        if top_foes:
            for i, (name, cnt) in enumerate(top_foes, 1):
                text += f"{i}. {name} — {cnt} раз(а)\n"
        else:
            text += "Нет данных\n"
        await update.message.reply_text(text, parse_mode="HTML")
    except Exception as e:
        # If an error occurs, inform the user
        await update.message.reply_text(f"Ошибка при получении топа друзей/козлов: {e}")


async def horoscope(update, context):
    "Сгенерировать мемный гороскоп для пользователя."
    try:
        # Send a message indicating that generation has started
        status_message = await update.message.reply_text("Готовлю мемный гороскоп…")

        try:
            user = update.effective_user.first_name or "Неизвестный"
            username = update.effective_user.username
            user_id = str(update.effective_user.id)

            # Формируем имя пользователя с тегом, если доступно
            if username:
                user_display = f"@{username}"
            else:
                user_display = user

            # Получаем знак зодиака пользователя
            zodiac_sign = None

            # Сначала пытаемся получить знак зодиака из базы данных (выбранный пользователем)
            cursor.execute(
                "SELECT zodiac_sign FROM user_zodiac WHERE user_id=?", (user_id,)
            )
            row = cursor.fetchone()

            if row and row[0]:
                zodiac_sign = row[0]
            else:
                # Если знак не выбран пользователем, пытаемся определить его по дате рождения из профиля
                try:
                    # Проверяем, есть ли у пользователя дата рождения в профиле
                    if (
                        hasattr(update.effective_user, "birthdate")
                        and update.effective_user.birthdate
                    ):
                        birthdate = update.effective_user.birthdate
                        # Определяем знак зодиака по дате рождения
                        zodiac_sign = get_zodiac_sign_by_date(
                            birthdate.day, birthdate.month
                        )

                        # Если удалось определить знак, сохраняем его в базе данных
                        if zodiac_sign:
                            cursor.execute(
                                """
                                INSERT OR REPLACE INTO user_zodiac (user_id, zodiac_sign)
                                VALUES (?, ?)
                            """,
                                (user_id, zodiac_sign),
                            )
                            conn.commit()
                except Exception as e:
                    # Если возникла ошибка при получении даты рождения, просто игнорируем её
                    pass

            # Если знак зодиака всё ещё не определен, выбираем случайный
            if not zodiac_sign:
                zodiac_signs = [
                    "Овен",
                    "Телец",
                    "Близнецы",
                    "Рак",
                    "Лев",
                    "Дева",
                    "Весы",
                    "Скорпион",
                    "Стрелец",
                    "Козерог",
                    "Водолей",
                    "Рыбы",
                ]
                zodiac_sign = random.choice(zodiac_signs)

            # Получаем репутацию пользователя
            praise, abuse = get_user_rep(user, update.effective_chat.id)
            # Определяем тип гороскопа на основе репутации
            if DIALOGUE_STYLE == "kind":
                horoscope_type = "доброжелательный"
            elif DIALOGUE_STYLE == "rude":
                horoscope_type = "жесткий"
            elif abuse >= 3 and abuse >= praise:
                horoscope_type = "жесткий"
            elif praise >= 3 and praise > abuse:
                horoscope_type = "доброжелательный"
            else:
                horoscope_type = "нейтральный"

            base_prompt = (
                f"Ты — мемный, но проницательный астролог в Telegram. "
                f"Составь короткий персональный гороскоп для пользователя {user_display} (знак {zodiac_sign}). "
                "Дай ровно три предложения, суммарно до 80 слов. "
                "Не используй списки, Markdown и HTML. "
                "Обязательно упомяни деталь из повседневности и дай один практичный совет."
            )

            if horoscope_type == "жесткий":
                tone_prompt = (
                    "Тон язвительный, но без прямых оскорблений: добавь сарказм, один уколистый мем "
                    "и предупреди, что случится, если игнорировать совет."
                )
            elif horoscope_type == "доброжелательный":
                tone_prompt = (
                    "Тон поддерживающий и игривый. Подчеркни сильную сторону знака, добавь лёгкий мем "
                    "и заверши дружелюбным напоминанием, что всё получится."
                )
            else:
                tone_prompt = (
                    "Тон нейтральный с лёгкой иронией. Включи наблюдение про привычку знака, мемную деталь из онлайн-жизни "
                    "и совет, который можно выполнить сегодня."
                )

            prompt = f"{base_prompt} {tone_prompt}"

            response = await stream_prompt_to_message(
                status_message=status_message,
                system_prompt=prompt,
                temperature=0.9,
                top_p=0.95,
                max_output_tokens=160,
                usage_context="horoscope",
            )

            horoscope_text = response.text.strip()
            await status_message.edit_text(
                f"🔮 Гороскоп для {user_display} ({zodiac_sign}):\n\n{horoscope_text}"
            )
        except Exception as e:
            # If an error occurs, edit the status message to inform the user
            await status_message.edit_text(f"Ошибка при генерации гороскопа: {e}")
    except Exception as e:
        # If an error occurs, inform the user
        if update.message:
            await update.message.reply_text(f"Ошибка при генерации гороскопа: {e}")


async def webapp(update, context):
    raw_path = (
        globals().get("STATIC_WEB_PATH") or os.getenv("STATIC_WEB_PATH", "")
    ).strip()
    configured_url = os.getenv("STATIC_WEB_URL", "").strip()

    base_url = ""
    if configured_url.lower().startswith(("http://", "https://")):
        base_url = configured_url.rstrip("/")
    elif raw_path.lower().startswith(("http://", "https://")):
        base_url = raw_path.rstrip("/")
    else:
        base_url = "https://byrapp.onu.su"

    url = f"{base_url}/index.html"
    fallback_notice = ""
    if (
        not configured_url
        and raw_path
        and not raw_path.lower().startswith(("http://", "https://"))
    ):
        fallback_notice = (
            "\n\n⚠️ Пока используется дефолтный хост. "
            "Задайте STATIC_WEB_URL в .env с адресом вида https://example.com, чтобы открыть свою версию."
        )

    query = getattr(update, "callback_query", None)
    if query:
        await query.answer()
        target_message = query.message
    else:
        target_message = getattr(update, "message", None)

    if not target_message:
        return

    await target_message.reply_text(
        "Открой мой WebApp для анонимных признаний, статистики и квиза!"
        + fallback_notice,
        reply_markup=InlineKeyboardMarkup.from_button(
            InlineKeyboardButton(text="🚀 Открыть", web_app=WebAppInfo(url=url))
        ),
    )


async def handle_webapp_data(update, context):
    data = update.message.text
    await update.message.reply_text(f"Вы отправили: {data}")


async def handle_reaction(update, context):
    if not update.message or not update.effective_user:
        return
    try:
        chat_id = update.effective_chat.id if update.effective_chat else None
        message = update.message
        message_id = message.message_id if message else None
        if chat_id is None or message_id is None:
            return
        ensure_message_logged_from_reaction(message, chat_id)
        from_user = (
            update.effective_user.first_name
            or update.effective_user.full_name
            or "Неизвестный"
        )
        from_user_id = (
            str(update.effective_user.id)
            if update.effective_user and update.effective_user.id is not None
            else None
        )
        to_user = message.from_user.first_name if message.from_user else "Неизвестный"
        new_reactions = getattr(getattr(update, "reaction", None), "new_reaction", None)
        if not (REACTIONS_HAS_CHAT_ID and REACTIONS_HAS_MESSAGE_ID):
            if new_reactions:
                bot_logger.warning(
                    "Таблица reactions не поддерживает chat_id/message_id — пропускаю сохранение реакций"
                )
            return
        inserted = False
        if new_reactions:
            for reaction_emoji in new_reactions:
                columns = ["from_user", "to_user", "emoji"]
                values = [from_user, to_user, reaction_emoji]
                if REACTIONS_HAS_FROM_USER_ID:
                    columns.append("from_user_id")
                    values.append(from_user_id)
                if REACTIONS_HAS_CHAT_ID:
                    columns.append("chat_id")
                    values.append(chat_id)
                if REACTIONS_HAS_MESSAGE_ID:
                    columns.append("message_id")
                    values.append(message_id)
                placeholders = ", ".join(["?"] * len(values))
                sql = f"INSERT INTO reactions({', '.join(columns)}) VALUES ({placeholders})"
                cursor.execute(sql, values)
                inserted = True
        if inserted:
            conn.commit()
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Ошибка при обработке реакции: {e}", exc_info=True)


async def unknown_command(update, context):
    try:
        await update.message.reply_text("Откройте /menu — там всё нужное.")
    except Exception:
        pass


async def ban_vote(update, context):
    try:
        # Проверяем, что команда вызвана в групповом чате
        if not update.effective_chat or update.effective_chat.type not in [
            "group",
            "supergroup",
        ]:
            await update.message.reply_text(
                "Команда доступна только в групповых чатах!"
            )
            return

        # Проверяем, что передано имя пользователя
        if not context.args:
            await update.message.reply_text("Укажи имя пользователя: /ban_vote <имя>")
            return

        target_user = " ".join(context.args)
        prompt = f"Внимание! Голосование за бан участника: {target_user}.\nПроголосуйте за или против бана:"

        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("Бан", callback_data=f"ban|{target_user}"),
                    InlineKeyboardButton(
                        "Оставляем", callback_data=f"leave|{target_user}"
                    ),
                ]
            ]
        )

        msg = await update.message.reply_text(prompt, reply_markup=keyboard)

        # Записать голосование в БД
        cursor.execute(
            "INSERT INTO ban_votes(target_user, start_time, message_id, chat_id) VALUES (?, datetime('now'), ?, ?)",
            (target_user, msg.message_id, update.effective_chat.id),
        )
        conn.commit()
        vote_id = cursor.lastrowid

        # Запустить задачу на подсчёт через 24 часа
        asyncio.create_task(finish_ban_vote_later(vote_id, 24 * 60 * 60))
    except Exception as e:
        # If an error occurs, inform the user
        await update.message.reply_text(f"Ошибка при запуске голосования: {e}")


async def ban_vote_button(update, context):
    try:
        query = update.callback_query
        await query.answer()
        data = query.data.split("|")
        if len(data) != 2:
            return
        vote, target_user = data
        voter_display = (
            query.from_user.full_name or query.from_user.first_name or "Неизвестный"
        )
        voter_id = str(query.from_user.id)

        # Обработка админской кнопки "забанить"
        if vote == "admin_ban":
            # Проверяем, является ли пользователь администратором
            chat_admins = await context.bot.get_chat_administrators(
                query.message.chat_id
            )
            admin_ids = [a.user.id for a in chat_admins]
            if query.from_user.id not in admin_ids:
                await query.answer(
                    "Только администраторы могут забанить пользователя!",
                    show_alert=True,
                )
                return

            # Здесь должна быть логика бана пользователя
            # Поскольку мы не можем напрямую банить пользователей по имени, отправим сообщение админу
            await query.answer("Функция бана требует реализации!", show_alert=True)
            await query.message.reply_text(
                f"Администратор {voter_display} хочет забанить пользователя {target_user}. "
                f"Пожалуйста, используйте встроенные функции Telegram для бана."
            )
            return

        # Найти активное голосование по этому сообщению
        cursor.execute(
            "SELECT vote_id FROM ban_votes WHERE message_id=? AND chat_id=?",
            (query.message.message_id, query.message.chat_id),
        )
        row = cursor.fetchone()
        if not row:
            await query.edit_message_text("Голосование уже завершено.")
            return
        vote_id = row[0]
        # Проверить, не голосовал ли уже
        cursor.execute(
            "SELECT vote FROM ban_votes_results WHERE vote_id=? AND voter=?",
            (vote_id, voter_id),
        )
        if cursor.fetchone():
            await query.answer("Ты уже голосовал!", show_alert=True)
            return
        cursor.execute(
            "INSERT INTO ban_votes_results(vote_id, voter, vote) VALUES (?, ?, ?)",
            (vote_id, voter_id, vote),
        )
        conn.commit()
        await query.answer("Голос учтён!", show_alert=True)
    except Exception as e:
        # If an error occurs, inform the user
        if "query" in locals():
            await query.answer(f"Ошибка при голосовании: {e}", show_alert=True)
        else:
            logger = logging.getLogger(__name__)
            logger.error(f"Ошибка при обработке голосования: {e}")


async def finish_ban_vote_later(vote_id, delay):
    try:
        await asyncio.sleep(delay)
        # Получить инфу о голосовании
        cursor.execute(
            "SELECT target_user, message_id, chat_id FROM ban_votes WHERE vote_id=?",
            (vote_id,),
        )
        row = cursor.fetchone()
        if not row:
            return
        target_user, message_id, chat_id = row
        # Посчитать голоса
        cursor.execute(
            "SELECT vote, COUNT(*) FROM ban_votes_results WHERE vote_id=? GROUP BY vote",
            (vote_id,),
        )
        results = dict(cursor.fetchall())
        ban_count = results.get("ban", 0)
        leave_count = results.get("leave", 0)
        text = f"Голосование за бан участника {target_user} завершено!\n"
        text += f"Бан: {ban_count}\nОставляем: {leave_count}\n"

        # Добавляем кнопку "забанить" если победил бан
        keyboard = None
        if ban_count > leave_count:
            text += "Победил бан! Администраторы могут забанить пользователя."
            keyboard = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "Забанить", callback_data=f"admin_ban|{target_user}"
                        )
                    ]
                ]
            )
        else:
            text += "Победило милосердие. Мамуля довольна!"

        # Отправляем сообщение с результатами и кнопкой (если нужно)
        bot = context_bot
        if not bot:
            logging.getLogger(__name__).warning(
                "context_bot недоступен, результат голосования не отправлен"
            )
            return
        if keyboard:
            await bot.send_message(chat_id=chat_id, text=text, reply_markup=keyboard)
        else:
            await bot.send_message(chat_id=chat_id, text=text)

        # Удалить голосование и результаты
        cursor.execute("DELETE FROM ban_votes WHERE vote_id=?", (vote_id,))
        cursor.execute("DELETE FROM ban_votes_results WHERE vote_id=?", (vote_id,))
        conn.commit()
    except Exception as e:
        # Log the error but don't crash the scheduled task
        logger = logging.getLogger(__name__)
        logger.error(f"Ошибка при завершении голосования: {e}")


async def about(update, context):
    try:
        text = (
            "Мамуля — мемный Telegram-бот, который шутит, ругается, подбадривает и стебёт участников чата в зависимости от их поведения и репутации.\n"
            "\n🔧 Базовые команды:\n"
            "/menu — Интерактивное меню со всеми функциями\n"
            "/help — Краткая шпаргалка по основным возможностям\n"
            "/start — Приветствие от Мамули\n"
            "/m_version — Текущая версия бота\n"
            "\n📊 Статистика и рейтинги:\n"
            "/my_stats — Ваша статистика и мемные реакции\n"
            "/top_nolifers — Топ-10 ноулайферов за всё время\n"
            "/top_nolifers_day — Топ-10 ноулайферов за сегодня\n"
            "/top_nolifers_week — Топ-5 ноулайферов за неделю\n"
            "/top_pairs — Топ-5 пар по реплаям\n"
            "/sticker_stats — Топ-5 эмодзи чата\n"
            "/friend_foe_stats — Баланс друзей и козлов\n"
            "/friend_foe_top — Топ-3 друзей и козлов чата\n"
            "/days_without_drama — Сколько дней без срача\n"
            "/drama — Сбросить счётчик дней без срача\n"
            "\n🎭 Развлечения и общение:\n"
            "/randomquote — Случайная цитата из чата\n"
            "/quote — Сохранить сообщение как цитату (ответом на сообщение)\n"
            "/quotes — Получить случайную цитату с ссылкой на оригинал\n"
            "/dvach — Генерация короткой двач-пасты по чату\n"
            "/psychologist — Мемная поддержка (учитывает репутацию)\n"
            "/fact — Мемный факт о вас по вашим сообщениям\n"
            "/predict — Ежедневное предсказание (1 раз в день)\n"
            "/imitate <имя> — Мамуля имитирует стиль выбранного участника\n"
            "/horoscope — Мемный гороскоп на сегодня\n"
            "/roll XdY — Бросить кубик (например, /roll 2d6)\n"
            "/bottle — Запустить игру «Бутылочка»\n"
            "\n🤖 Управление вниманием Мамули:\n"
            "/ignore_me — Мамуля перестанет отвечать вам\n"
            "/notice_me — Мамуля снова будет отвечать\n"
            "\n📰 Саммари и админ-инструменты:\n"
            "/summary и /summary_day — Итог дня (для админов)\n"
            "/summary_week — Итог недели (для админов)\n"
            "/ban_vote <имя> — Запустить голосование за бан/разбан (для админов)\n"
            "/publish_anons — Опубликовать новые анонимки из webapp/anon_messages.txt\n"
            "/anon_sender <номер> — Показать информацию об анонимке по номеру\n"
            "/webapp — Открыть WebApp для анонимных признаний\n"
        )
        await update.message.reply_text(text)
    except Exception as e:
        # If an error occurs, inform the user
        await update.message.reply_text(
            f"Ошибка при отображении информации о боте: {e}"
        )


async def version(update, context):
    try:
        await update.message.reply_text(f"{get_version()}")
    except Exception as e:
        # If an error occurs, inform the user
        await update.message.reply_text(f"Ошибка при получении версии: {e}")


# === Меню команд ===
async def menu(update, context):
    "Показывает главное меню с категориями команд"
    try:
        keyboard = [
            [
                InlineKeyboardButton("📊 Моя статистика", callback_data="my_stats"),
                InlineKeyboardButton(
                    "🏆 Топ ноулайферов", callback_data="top_nolifers"
                ),
            ],
            [
                InlineKeyboardButton("👥 Топ пар", callback_data="top_pairs"),
                InlineKeyboardButton("😀 Эмодзи", callback_data="sticker_stats"),
            ],
            [
                InlineKeyboardButton(
                    "📅 Топ за день", callback_data="top_nolifers_day"
                ),
                InlineKeyboardButton(
                    "📆 Топ за неделю", callback_data="top_nolifers_week"
                ),
            ],
            [
                InlineKeyboardButton("🔥 Топ 3ч", callback_data="top3h"),
            ],
            [
                InlineKeyboardButton("⬅️ Назад", callback_data="menu_main"),
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Сохраняем ID пользователя, который вызвал меню
        menu_message = await update.message.reply_text(
            "Выберите категорию команд:", reply_markup=reply_markup
        )

        # Сохраняем ID пользователя в контексте меню
        context.bot_data.setdefault("menu_users", {})[
            menu_message.message_id
        ] = update.effective_user.id
    except Exception as e:
        await update.message.reply_text(f"Ошибка при отображении меню: {e}")


async def show_stats_menu(update, context):
    "Показывает меню статистики"
    try:
        query = update.callback_query
        await query.answer()

        keyboard = [
            [
                InlineKeyboardButton("📊 Моя статистика", callback_data="my_stats"),
                InlineKeyboardButton(
                    "🏆 Топ ноулайферов", callback_data="top_nolifers"
                ),
            ],
            [
                InlineKeyboardButton("👥 Топ пар", callback_data="top_pairs"),
                InlineKeyboardButton("😀 Эмодзи", callback_data="sticker_stats"),
            ],
            [
                InlineKeyboardButton(
                    "📅 Топ за день", callback_data="top_nolifers_day"
                ),
                InlineKeyboardButton(
                    "📆 Топ за неделю", callback_data="top_nolifers_week"
                ),
            ],
            [
                InlineKeyboardButton("🔥 Топ 3ч", callback_data="top3h"),
            ],
            [
                InlineKeyboardButton("⬅️ Назад", callback_data="menu_main"),
            ],
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.message.edit_text(
            "📈 Статистика:\nВыберите команду:", reply_markup=reply_markup
        )

        # Обновляем ID создателя меню
        context.bot_data.setdefault("menu_users", {})[
            query.message.message_id
        ] = query.from_user.id
    except Exception as e:
        await query.message.reply_text(f"Ошибка при отображении меню статистики: {e}")


async def show_fun_menu(update, context):
    "Показывает меню развлечений"
    try:
        query = update.callback_query
        await query.answer()

        keyboard = [
            [
                InlineKeyboardButton(
                    "💬 Случайная цитата", callback_data="randomquote"
                ),
                InlineKeyboardButton("😂 Двач-паста", callback_data="dvach"),
            ],
            [
                InlineKeyboardButton("🧠 Психолог", callback_data="psychologist"),
                InlineKeyboardButton("🔍 Факт обо мне", callback_data="fact"),
            ],
            [
                InlineKeyboardButton("🎭 Имитация", callback_data="imitate_menu"),
                InlineKeyboardButton("🌐 WebApp", callback_data="webapp"),
            ],
            [
                InlineKeyboardButton(
                    "🎭 Игра в бутылочку", callback_data="bottle_game"
                ),
                InlineKeyboardButton("🎲 Бросить кубик", callback_data="roll_info"),
            ],
            [
                InlineKeyboardButton(
                    "📉 Дни без драмы", callback_data="days_without_drama"
                ),
                InlineKeyboardButton("💥 Сбросить драму", callback_data="drama"),
            ],
            [
                InlineKeyboardButton("📚 Цитатник", callback_data="quotes_menu"),
                InlineKeyboardButton("🔮 Мемный гороскоп", callback_data="horoscope"),
            ],
            [
                InlineKeyboardButton("🖼 Мемы", callback_data="menu_memes"),
                InlineKeyboardButton("🔮 Предсказатель", callback_data="predict"),
            ],
            [
                InlineKeyboardButton("⬅️ Назад", callback_data="menu_main"),
            ],
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.message.edit_text(
            "🎭 Развлечения:\nВыберите команду:", reply_markup=reply_markup
        )

        # Обновляем ID создателя меню
        context.bot_data.setdefault("menu_users", {})[
            query.message.message_id
        ] = query.from_user.id
    except Exception as e:
        await query.message.reply_text(f"Ошибка при отображении меню развлечений: {e}")


async def show_social_menu(update, context):
    "Показывает социальное меню"
    try:
        query = update.callback_query
        await query.answer()

        keyboard = [
            [
                InlineKeyboardButton(
                    "👥 Друзья/Козлы", callback_data="friend_foe_stats"
                ),
                InlineKeyboardButton(
                    "🏆 Топ друзей/козлов", callback_data="friend_foe_top"
                ),
            ],
            [
                InlineKeyboardButton("🔇 Игнорировать меня", callback_data="ignore_me"),
                InlineKeyboardButton("🔔 Уведомлять меня", callback_data="notice_me"),
            ],
            [
                InlineKeyboardButton("☕ Чай", callback_data="tea_menu"),
            ],
            [
                InlineKeyboardButton("⬅️ Назад", callback_data="menu_main"),
            ],
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.message.edit_text(
            "👥 Социальные команды:\nВыберите команду:", reply_markup=reply_markup
        )

        # Обновляем ID создателя меню
        context.bot_data.setdefault("menu_users", {})[
            query.message.message_id
        ] = query.from_user.id
    except Exception as e:
        await query.message.reply_text(f"Ошибка при отображении социального меню: {e}")


async def show_quotes_menu(update, context):
    "Показывает меню цитат"
    try:
        query = update.callback_query
        await query.answer()

        keyboard = [
            [
                InlineKeyboardButton(
                    "📝 Сохранить цитату", callback_data="save_quote_info"
                ),
                InlineKeyboardButton("📚 Случайная цитата", callback_data="quotes"),
            ],
            [
                InlineKeyboardButton("⬅️ Назад", callback_data="menu_fun"),
            ],
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.message.edit_text(
            "📚 Цитатник:\nВыберите команду:\n\n"
            "• Чтобы сохранить цитату, используйте команду /quote в ответ на сообщение\n"
            "• Чтобы получить случайную цитату, нажмите кнопку 'Случайная цитата'",
            reply_markup=reply_markup,
        )

        # Обновляем ID создателя меню
        context.bot_data.setdefault("menu_users", {})[
            query.message.message_id
        ] = query.from_user.id
    except Exception as e:
        await query.message.reply_text(f"Ошибка при отображении меню цитат: {e}")


async def show_admin_menu(update, context):
    "Показывает админское меню"
    try:
        query = update.callback_query
        await query.answer()

        keyboard = [
            [
                InlineKeyboardButton("📅 Итоги дня", callback_data="summary_day"),
                InlineKeyboardButton("📆 Итоги недели", callback_data="summary_week"),
            ],
            [
                InlineKeyboardButton(
                    "📢 Опубликовать анонимки", callback_data="publish_anons"
                ),
                InlineKeyboardButton(
                    "🔎 Инфо об анонимке", callback_data="anon_sender_menu"
                ),
            ],
            [
                InlineKeyboardButton(
                    "🌅 Доброе утро", callback_data="good_morning_menu"
                ),
                InlineKeyboardButton(
                    "🙋\u200d♀️ Приветствие", callback_data="welcome_menu"
                ),
            ],
            [
                InlineKeyboardButton(
                    "🤖 Настройки AI", callback_data="ai_model_settings"
                ),
            ],
            [
                InlineKeyboardButton("⚖️ Голосование", callback_data="ban_vote_menu"),
                InlineKeyboardButton("⬅️ Назад", callback_data="menu_main"),
            ],
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.message.edit_text(
            "🛡️ Админские команды:\nВыберите команду:", reply_markup=reply_markup
        )
    except Exception as e:
        await query.message.edit_text(f"Ошибка при отображении админского меню: {e}")


async def show_ai_model_settings(update, context):
    "Показывает настройки AI модели"
    try:
        query = update.callback_query
        await query.answer()

        # Получить текущие настройки
        chat_id = query.message.chat_id
        current_model = get_summary_model_for_chat(chat_id)

        # Проверить доступность моделей
        gpt_available = is_openai_available()
        gemini_available = gemini_model is not None
        groq_available = is_groq_available()

        openai_default_label = f"OpenAI ({DEFAULT_MODEL})"
        openai_gpt35_label = (
            f"OpenAI ({os.getenv('OPENAI_SUMMARY_GPT35', 'gpt-3.5-turbo')})"
        )
        groq_label = f"Groq ({get_groq_default_model()})"
        model_display_map = {
            "gpt": openai_default_label,
            "gpt-3.5": openai_gpt35_label,
            "gemini": "Gemini",
            "groq": groq_label,
        }

        # Создать текст с информацией о доступности
        status_text = "🤖 Настройки AI модели для саммари:\n\n"
        status_text += f"📊 Текущая модель: {model_display_map.get(current_model, current_model)}\n\n"
        status_text += "🔗 Статус подключения:\n"
        status_text += f"• {openai_default_label}: {'✅ Доступен' if gpt_available else '❌ Не подключен'}\n"
        status_text += f"• {openai_gpt35_label}: {'✅ Доступен' if gpt_available else '❌ Не подключен'}\n"
        status_text += (
            f"• Gemini: {'✅ Доступен' if gemini_available else '❌ Не подключен'}\n"
        )
        status_text += f"• {groq_label}: {'✅ Доступен' if groq_available else '❌ Не подключен'}\n\n"

        if not gpt_available and not gemini_available and not groq_available:
            status_text += "⚠️ Ни одна модель не настроена!\n"
            status_text += "Добавьте API ключи в переменные окружения:\n"
            status_text += "• OPENAI_API_KEY для GPT\n"
            status_text += "• GEMINI_API_KEY для Gemini\n"
            status_text += "• GROQ_API_KEY для Groq"
        else:
            status_text += "Выберите модель для генерации саммари:"

        keyboard = []

        if gpt_available:
            keyboard.append(
                [
                    InlineKeyboardButton(
                        f"{'✅' if current_model == 'gpt' else '⚪'} {openai_default_label}",
                        callback_data="set_model_gpt",
                    )
                ]
            )
            keyboard.append(
                [
                    InlineKeyboardButton(
                        f"{'✅' if current_model == 'gpt-3.5' else '⚪'} {openai_gpt35_label}",
                        callback_data="set_model_gpt35",
                    )
                ]
            )

        if gemini_available:
            keyboard.append(
                [
                    InlineKeyboardButton(
                        f"{'✅' if current_model == 'gemini' else '⚪'} Gemini",
                        callback_data="set_model_gemini",
                    )
                ]
            )
        if groq_available:
            keyboard.append(
                [
                    InlineKeyboardButton(
                        f"{'✅' if current_model == 'groq' else '⚪'} {groq_label}",
                        callback_data="set_model_groq",
                    )
                ]
            )

        keyboard.append(
            [
                InlineKeyboardButton("⬅️ Назад к админке", callback_data="menu_admin"),
            ]
        )

        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.message.edit_text(status_text, reply_markup=reply_markup)
    except Exception as e:
        await query.message.edit_text(f"Ошибка при отображении настроек AI: {e}")


async def set_ai_model(update, context, model_type):
    "Устанавливает AI модель для генерации саммари"
    try:
        query = update.callback_query
        await query.answer()

        chat_id = query.message.chat_id

        # Проверить доступность модели
        if model_type in ("gpt", "gpt-3.5") and not is_openai_available():
            await query.answer(
                "GPT не настроен! Проверьте OPENAI_API_KEY.", show_alert=True
            )
            return
        elif model_type == "gemini" and gemini_model is None:
            await query.answer(
                "Gemini не настроен! Проверьте GEMINI_API_KEY.", show_alert=True
            )
            return
        elif model_type == "groq" and not is_groq_available():
            await query.answer(
                "Groq не настроен! Проверьте GROQ_API_KEY.", show_alert=True
            )
            return

        # Установить модель
        success = set_summary_model_for_chat(chat_id, model_type)

        if success:
            openai_default_label = f"OpenAI ({DEFAULT_MODEL})"
            openai_gpt35_label = (
                f"OpenAI ({os.getenv('OPENAI_SUMMARY_GPT35', 'gpt-3.5-turbo')})"
            )
            groq_label = f"Groq ({get_groq_default_model()})"
            model_labels = {
                "gpt": openai_default_label,
                "gpt-3.5": openai_gpt35_label,
                "gemini": "Gemini",
                "groq": groq_label,
            }
            label = model_labels.get(model_type, model_type.upper())
            await query.answer(f"✅ Модель изменена на {label}!")
            # Обновить отображение настроек
            await show_ai_model_settings(update, context)
        else:
            await query.answer("❌ Ошибка при сохранении настроек!", show_alert=True)

    except Exception as e:
        await query.answer(f"Ошибка при установке модели: {e}", show_alert=True)


async def show_welcome_menu(update, context, already_answered=False):
    query = update.callback_query
    try:
        if not already_answered:
            await query.answer()
        chat_id = query.message.chat.id if query.message else CHAT_ID
        target_chat_id = chat_id or CHAT_ID
        welcome_text = get_welcome_message(target_chat_id)
        preview = f"@username {welcome_text}".strip()
        text = (
            "🙋\u200d♀️ Настройки приветствия\n"
            f"Текущий текст:\n{preview}\n\n"
            "Новый текст будет автоматически добавляться после @имя новичка."
        )
        keyboard = [
            [
                InlineKeyboardButton("✏️ Изменить текст", callback_data="welcome_edit"),
            ],
            [
                InlineKeyboardButton("♻️ Сбросить", callback_data="welcome_reset"),
            ],
            [
                InlineKeyboardButton("⬅️ Назад", callback_data="menu_admin"),
            ],
        ]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        context.bot_data.setdefault("menu_users", {})[
            query.message.message_id
        ] = query.from_user.id
        context.user_data.pop("awaiting_welcome_text", None)
        context.user_data.pop("welcome_target_chat", None)
        context.user_data.pop("welcome_editor", None)
    except Exception as e:
        await query.message.reply_text(f"Ошибка при открытии настроек приветствия: {e}")


async def start_welcome_edit(update, context):
    query = update.callback_query
    try:
        await query.answer("Введите новый текст")
        chat_id = query.message.chat.id if query.message else CHAT_ID
        target_chat_id = chat_id or CHAT_ID
        context.user_data["awaiting_welcome_text"] = True
        context.user_data["welcome_target_chat"] = target_chat_id
        context.user_data["welcome_editor"] = query.from_user.id
        await query.message.reply_text(
            "Напишите новый текст приветствия. Бот автоматически добавит @имя нового участника в начало."
        )
        menu_users = context.bot_data.get("menu_users", {})
        if query.message.message_id in menu_users:
            del menu_users[query.message.message_id]
    except Exception as e:
        await query.message.reply_text(
            f"Ошибка при запуске редактирования приветствия: {e}"
        )


async def handle_message(update, context):
    global message_counter
    global last_resp_time
    if not update.message:
        return
    message = update.message
    raw_text = message.text or message.caption or ""
    awaiting_welcome = context.user_data.get("awaiting_welcome_text")
    awaiting_editor = context.user_data.get("welcome_editor")
    awaiting_chat = context.user_data.get("welcome_target_chat")
    if (
        awaiting_welcome
        and update.effective_user
        and update.effective_user.id == awaiting_editor
    ):
        new_text = (message.text or "").strip()
        if not new_text:
            await update.message.reply_text("Текст пустой, попробуйте ещё раз.")
            return
        chat_id = awaiting_chat or (
            update.effective_chat.id if update.effective_chat else None
        )
        if chat_id:
            set_welcome_message(chat_id, new_text)
        context.user_data.pop("awaiting_welcome_text", None)
        context.user_data.pop("welcome_target_chat", None)
        context.user_data.pop("welcome_editor", None)
        preview_name = "новичок"
        await message.reply_text(
            f"Новое приветствие сохранено. Пример: @{preview_name} {new_text}"
        )
        return
    user = message.from_user.first_name or "Неизвестный"
    text = raw_text
    reply_to = None
    user_id = str(message.from_user.id) if message.from_user else None

    try:
        if message.from_user:
            await download_user_photo(message.from_user.id, context)
    except Exception:
        pass

    if context.user_data.get("awaiting_suggest"):
        try:
            context.user_data["awaiting_suggest"] = False
            target_chat_id = context.user_data.get("suggest_in_chat")
            source_chat = update.effective_chat
            if target_chat_id and source_chat and source_chat.id != target_chat_id:
                await message.reply_text(
                    "Предложку можно отправить только в том чате, где открывали меню."
                )
                return
            forward_chat_id = int(os.getenv("SUGGEST_CHAT_ID", "472144090"))
            user_obj = update.effective_user
            user_display = "Неизвестный"
            if user_obj:
                user_display = (
                    user_obj.full_name or user_obj.username or str(user_obj.id)
                )
            chat_display = "неизвестный чат"
            if source_chat:
                if source_chat.username:
                    chat_display = f"@{source_chat.username}"
                elif source_chat.title:
                    chat_display = source_chat.title
                else:
                    chat_display = str(source_chat.id)
            has_attachment = bool(getattr(message, "effective_attachment", None))
            body_text = raw_text.strip()
            header_lines = [
                f"Источник: {chat_display}",
                f"От: {user_display}" + (f" (id={user_obj.id})" if user_obj else ""),
            ]
            if not has_attachment and body_text:
                header_lines.append("")
                header_lines.append(body_text)
            await context.bot.send_message(
                chat_id=forward_chat_id, text="\n".join(header_lines)
            )
            if has_attachment or not body_text:
                try:
                    if source_chat:
                        await context.bot.copy_message(
                            chat_id=forward_chat_id,
                            from_chat_id=source_chat.id,
                            message_id=message.message_id,
                        )
                except TelegramError as copy_error:
                    logging.getLogger(__name__).error(
                        "Ошибка при копировании предложки: %s", copy_error
                    )
                    if body_text:
                        await context.bot.send_message(
                            chat_id=forward_chat_id, text=body_text
                        )
            await message.reply_text("Сообщение отправлено админам, спасибо!")
        except Exception as e:
            logging.getLogger(__name__).error(f"Ошибка при пересылке предложки: {e}")
            await message.reply_text(
                "Не удалось переслать сообщение, попробуйте позже."
            )
        finally:
            context.user_data.pop("suggest_in_chat", None)
            context.user_data.pop("awaiting_suggest", None)
        return

    if message.reply_to_message:
        reply_to = message.reply_to_message.from_user.first_name or "Неизвестный"
    if not text.strip():
        return
    update_reputation(user, text, update.effective_chat.id)
    chat_id = update.effective_chat.id if update.effective_chat else None
    cursor.execute(
        "INSERT INTO messages(username,message,reply_to,user_id,chat_id) VALUES(?,?,?,?,?)",
        (user, text, reply_to, user_id, chat_id),
    )
    conn.commit()
    message_counter += 1
    if get_ignored(user):
        return

    if user == "Мамуля":
        return

    if reply_to and user != reply_to:
        dispute_tracker[user][reply_to] += 1
        dispute_tracker[reply_to][user] += 0
        pair_count = dispute_tracker[user][reply_to] + dispute_tracker[reply_to][user]
        if pair_count >= 3 and utcnow() - last_resp_time > cooldown_time:
            dispute_tracker[user][reply_to] = 0
            dispute_tracker[reply_to][user] = 0
            cursor.execute(
                "SELECT username, message FROM messages WHERE ((username=? AND reply_to=?) OR (username=? AND reply_to=?)) AND chat_id=? ORDER BY id DESC LIMIT 8",
                (user, reply_to, reply_to, user, chat_id),
            )
            ctx = [f"{u}: {m}" for u, m in reversed(cursor.fetchall())]
            praise, abuse = get_user_rep(user, chat_id)
            rude = should_use_rude_voice(praise, abuse)
            ctx = trim_dialog_context(ctx)
            placeholder_message = None
            try:
                placeholder_message = await update.message.reply_text("...")
                await stream_ask_gpt_reply(
                    placeholder_message,
                    user,
                    ctx,
                    dispute=True,
                    rude=rude,
                )
            except Exception as e:
                logger = logging.getLogger(__name__)
                logger.error(
                    f"??????+??? ?????? ?????????????? ???'????'?? ?? ??????????: {e}"
                )
                fallback_text = "????, ??'??-?'?? ???????>?? ???? ?'???? ?????? ?????????????? ???'????'??..."
                if placeholder_message:
                    try:
                        await placeholder_message.edit_text(fallback_text)
                    except TelegramError:
                        await update.message.reply_text(fallback_text)
                else:
                    await update.message.reply_text(fallback_text)
            last_resp_time = utcnow()
            return

    direct_mention = f"@{context.bot.username.lower()}" in text.lower() or (
        update.message.reply_to_message
        and update.message.reply_to_message.from_user.id == context.bot.id
    )
    praise, abuse = get_user_rep(user, chat_id)
    rude = should_use_rude_voice(praise, abuse)

    if direct_mention:
        placeholder_message = None
        try:
            cursor.execute(
                "SELECT username, message FROM messages WHERE chat_id=? ORDER BY id DESC LIMIT 30",
                (chat_id,),
            )
            ctx = [f"{u}: {m}" for u, m in reversed(cursor.fetchall())]
            ctx = trim_dialog_context(ctx)
            try:
                placeholder_message = await update.message.reply_text("...")
                await stream_ask_gpt_reply(
                    placeholder_message,
                    user,
                    ctx,
                    rude=rude,
                )
            except Exception as e:
                logger = logging.getLogger(__name__)
                logger.error(f"??????+??? ?????? ?????????????? ???'????'??: {e}")
                fallback_text = "????, ??'??-?'?? ???????>?? ???? ?'???? ?????? ?????????????? ???'????'??..."
                if placeholder_message:
                    try:
                        await placeholder_message.edit_text(fallback_text)
                    except TelegramError:
                        await update.message.reply_text(fallback_text)
                else:
                    await update.message.reply_text(fallback_text)
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error(f"??????+??? ?????? ?????????????? ???'????'??: {e}")
            fallback_text = "????, ??'??-?'?? ???????>?? ???? ?'???? ?????? ?????????????? ???'????'??..."
            if placeholder_message:
                try:
                    await placeholder_message.edit_text(fallback_text)
                except TelegramError:
                    await update.message.reply_text(fallback_text)
            else:
                await update.message.reply_text(fallback_text)
    else:
        if message_counter % 300 == 0:
            phrase = random.choice(MAMULYA_PHRASES)
            await update.message.reply_text(phrase)

    if message_counter % 100 == 0:
        rude_emojis = [
            "💩",
            "🤡",
            "😡",
            "🤬",
            "🖕",
            "😾",
            "👎",
            "🫵",
            "😤",
            "😒",
            "😠",
            "😬",
            "🥴",
            "🥶",
            "🥱",
        ]
        nice_emojis = [
            "👍",
            "🔥",
            "😂",
            "🥰",
            "😍",
            "😎",
            "🤗",
            "🥳",
            "👏",
            "💖",
            "🤩",
            "😇",
            "😁",
            "🙌",
            "💯",
            "🫶",
            "😺",
            "🥹",
        ]
        reaction_emoji = random.choice(rude_emojis if rude else nice_emojis)
        try:
            await asyncio.get_event_loop().run_in_executor(
                None,
                send_reaction_raw,
                update.effective_chat.id,
                update.message.message_id,
                reaction_emoji,
            )
        except Exception:
            pass


async def welcome_new_members(update, context):
    if not update.message or not getattr(update.message, "new_chat_members", None):
        return
    chat = update.effective_chat
    if not chat:
        return
    chat_id = chat.id
    try:
        welcome_text = get_welcome_message(chat_id)
    except Exception:
        bot_logger.exception("Не удалось получить приветствие для чата %s", chat_id)
        welcome_text = DEFAULT_WELCOME_MESSAGE
    for member in update.message.new_chat_members:
        username = (
            member.username or member.full_name or member.first_name or "новый участник"
        ).strip()
        if username:
            mention = username if username.startswith("@") else f"@{username}"
        else:
            mention = "@новый_участник"
        try:
            await update.message.reply_text(f"{mention} {welcome_text}")
        except Exception:
            bot_logger.exception(
                "Не удалось отправить приветствие участнику %s", username
            )


async def reset_welcome_text(update, context):
    query = update.callback_query
    try:
        chat_id = query.message.chat.id if query.message else CHAT_ID
        target_chat_id = chat_id or CHAT_ID
        reset_welcome_message(target_chat_id)
        await query.answer("Приветствие сброшено")
        await show_welcome_menu(update, context, already_answered=True)
    except Exception as e:
        await query.answer("Не удалось сбросить", show_alert=True)
        await query.message.reply_text(f"Ошибка при сбросе приветствия: {e}")


async def show_good_morning_menu(update, context, already_answered=False):
    query = update.callback_query
    try:
        if not already_answered:
            await query.answer()
        chat_id = query.message.chat.id if query.message else CHAT_ID
        target_chat_id = chat_id or CHAT_ID
        settings = get_good_morning_settings(target_chat_id)
        style_key = settings.get("style", GOOD_MORNING_DEFAULT_STYLE)
        style = GOOD_MORNING_STYLES.get(
            style_key, GOOD_MORNING_STYLES[GOOD_MORNING_DEFAULT_STYLE]
        )
        mom_btn = f"{'✅ ' if style_key == 'mom' else ''}{GOOD_MORNING_STYLES['mom']['emoji']} {GOOD_MORNING_STYLES['mom']['label']}"
        office_btn = f"{'✅ ' if style_key == 'office' else ''}{GOOD_MORNING_STYLES['office']['emoji']} {GOOD_MORNING_STYLES['office']['label']}"
        time_text = f"{settings['hour']:02d}:{settings['minute']:02d}"
        text = (
            "🌅 Настройки доброго утра\n"
            f"Стиль: {style['emoji']} {style['label']}\n"
            f"Время: {time_text}\n"
            "Выберите стиль или измените время."
        )
        keyboard = [
            [
                InlineKeyboardButton(mom_btn, callback_data="gm_style_mom"),
                InlineKeyboardButton(office_btn, callback_data="gm_style_office"),
            ],
            [
                InlineKeyboardButton("⏰ Изменить время", callback_data="gm_time_menu"),
            ],
            [
                InlineKeyboardButton("⬅️ Назад", callback_data="menu_admin"),
            ],
        ]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        context.bot_data.setdefault("menu_users", {})[
            query.message.message_id
        ] = query.from_user.id
        context.user_data.pop("gm_temp_time", None)
    except ValueError as e:
        await query.answer(str(e), show_alert=True)
    except Exception as e:
        await query.message.reply_text(
            f"Ошибка при открытии настроек доброго утра: {e}"
        )


async def show_good_morning_time_menu(update, context, already_answered=False):
    query = update.callback_query
    try:
        if not already_answered:
            await query.answer()
        chat_id = query.message.chat.id if query.message else CHAT_ID
        target_chat_id = chat_id or CHAT_ID
        settings = get_good_morning_settings(target_chat_id)
        temp_time = context.user_data.get("gm_temp_time")
        if not temp_time:
            temp_time = {"hour": settings["hour"], "minute": settings["minute"]}
        else:
            temp_time = {
                "hour": int(temp_time.get("hour", settings["hour"])),
                "minute": int(temp_time.get("minute", settings["minute"])),
            }
        context.user_data["gm_temp_time"] = temp_time
        time_text = f"{temp_time['hour']:02d}:{temp_time['minute']:02d}"
        text = (
            "⏰ Настройка времени отправки\n"
            f"Текущее значение: {time_text}\n"
            "Используйте кнопки, чтобы подобрать удобное время."
        )
        keyboard = [
            [
                InlineKeyboardButton("- час", callback_data="gm_time_adj|hour|-"),
                InlineKeyboardButton(time_text, callback_data="gm_time_display"),
                InlineKeyboardButton("+ час", callback_data="gm_time_adj|hour|+"),
            ],
            [
                InlineKeyboardButton("- мин", callback_data="gm_time_adj|min|-"),
                InlineKeyboardButton("+ мин", callback_data="gm_time_adj|min|+"),
            ],
            [
                InlineKeyboardButton("✅ Сохранить", callback_data="gm_time_save"),
                InlineKeyboardButton("↩️ Назад", callback_data="good_morning_menu"),
            ],
        ]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        context.bot_data.setdefault("menu_users", {})[
            query.message.message_id
        ] = query.from_user.id
    except Exception as e:
        await query.message.reply_text(
            f"Ошибка при настройке времени доброго утра: {e}"
        )


async def handle_good_morning_style_selection(update, context, style_key):
    query = update.callback_query
    try:
        chat_id = query.message.chat.id if query.message else CHAT_ID
        target_chat_id = chat_id or CHAT_ID
        set_good_morning_style(target_chat_id, style_key)
        schedule_good_morning_job(target_chat_id)
        await query.answer("Стиль обновлён")
        await show_good_morning_menu(update, context, already_answered=True)
    except ValueError as e:
        await query.answer(str(e), show_alert=True)
    except Exception as e:
        await query.answer("Не удалось обновить стиль", show_alert=True)
        await query.message.reply_text(f"Ошибка при обновлении стиля доброго утра: {e}")


async def adjust_good_morning_time(update, context, target, delta):
    query = update.callback_query
    try:
        await query.answer()
        chat_id = query.message.chat.id if query.message else CHAT_ID
        target_chat_id = chat_id or CHAT_ID
        settings = get_good_morning_settings(target_chat_id)
        temp_time = dict(
            context.user_data.get("gm_temp_time")
            or {"hour": settings["hour"], "minute": settings["minute"]}
        )
        if target == "hour":
            temp_time["hour"] = (temp_time["hour"] + delta) % 24
        elif target == "min":
            temp_time["minute"] = (
                temp_time["minute"] + delta * GOOD_MORNING_MINUTE_STEP
            ) % 60
        else:
            return
        context.user_data["gm_temp_time"] = temp_time
        await show_good_morning_time_menu(update, context, already_answered=True)
    except Exception as e:
        await query.message.reply_text(
            f"Ошибка при изменении времени доброго утра: {e}"
        )


async def save_good_morning_time(update, context):
    query = update.callback_query
    try:
        chat_id = query.message.chat.id if query.message else CHAT_ID
        target_chat_id = chat_id or CHAT_ID
        temp_time = context.user_data.get("gm_temp_time")
        if not temp_time:
            settings = get_good_morning_settings(target_chat_id)
            temp_time = {"hour": settings["hour"], "minute": settings["minute"]}
        set_good_morning_time(target_chat_id, temp_time["hour"], temp_time["minute"])
        schedule_good_morning_job(target_chat_id)
        context.user_data.pop("gm_temp_time", None)
        await query.answer("Время обновлено")
        await show_good_morning_menu(update, context, already_answered=True)
    except ValueError as e:
        await query.answer(str(e), show_alert=True)
    except Exception as e:
        await query.answer("Не удалось сохранить время", show_alert=True)
        await query.message.reply_text(
            f"Ошибка при сохранении времени доброго утра: {e}"
        )


async def show_main_menu(update, context):
    "Показывает главное меню"
    try:
        query = update.callback_query
        await query.answer()

        keyboard = [
            [
                InlineKeyboardButton("📈 Статистика", callback_data="menu_stats"),
            ],
            [
                InlineKeyboardButton("🎭 Развлечения", callback_data="menu_fun"),
            ],
            [
                InlineKeyboardButton("👥 Социальные", callback_data="menu_social"),
            ],
            [
                InlineKeyboardButton("✉️ Предложка", callback_data="suggest_menu"),
            ],
            [
                InlineKeyboardButton("🛡️ Админские", callback_data="menu_admin"),
            ],
            [
                InlineKeyboardButton("ℹ️ О боте", callback_data="about"),
            ],
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.message.edit_text(
            "Выберите категорию команд:", reply_markup=reply_markup
        )

        # Обновляем ID создателя меню
        context.bot_data.setdefault("menu_users", {})[
            query.message.message_id
        ] = query.from_user.id
    except Exception as e:
        await query.message.reply_text(f"Ошибка при отображении главного меню: {e}")


async def menu_button_handler(update, context):
    "Обрабатывает нажатия кнопок в меню"
    try:
        query = update.callback_query
        await query.answer()

        # Проверяем, имеет ли пользователь право использовать это меню
        menu_users = context.bot_data.get("menu_users", {})
        menu_creator_id = menu_users.get(query.message.message_id)

        # Если меню было создано кем-то другим, игнорируем нажатие
        if menu_creator_id and menu_creator_id != query.from_user.id:
            await query.answer(
                "Вы можете использовать только меню, которое вызвали сами!",
                show_alert=True,
            )
            return

        # Обработка навигации по меню
        if query.data == "menu_main":
            await show_main_menu(update, context)
            return
        elif query.data == "menu_stats":
            await show_stats_menu(update, context)
            return
        elif query.data == "menu_fun":
            await show_fun_menu(update, context)
            return
        elif query.data == "menu_social":
            await show_social_menu(update, context)
            return
        elif query.data == "menu_admin":
            await show_admin_menu(update, context)
            return
        elif query.data == "ai_model_settings":
            await show_ai_model_settings(update, context)
            return
        elif query.data == "set_model_gpt":
            await set_ai_model(update, context, "gpt")
            return
        elif query.data == "set_model_gpt35":
            await set_ai_model(update, context, "gpt-3.5")
            return
        elif query.data == "set_model_groq":
            await set_ai_model(update, context, "groq")
            return
        elif query.data == "set_model_gemini":
            await set_ai_model(update, context, "gemini")
            return

        # Обработка специальных меню
        elif query.data == "quotes_menu":
            await show_quotes_menu(update, context)
            return

        # Обработка голосования
        if query.data.startswith("ban|") or query.data.startswith("leave|"):
            await ban_vote_button(update, context)
            return

        # Словарь для сопоставления callback_data с функциями
        handlers = {
            "my_stats": my_stats,
            "top_nolifers": top_nolifers,
            "top_pairs": top_pairs,
            "sticker_stats": sticker_stats,
            "randomquote": randomquote,
            "dvach": dvach,
            "psychologist": psychologist,
            "fact": fact,
            "predict": predict,
            "friend_foe_stats": friend_foe_stats,
            "friend_foe_top": friend_foe_top,
            "summary_day": summary_day,
            "summary_week": summary_week,
            "ignore_me": ignore_me,
            "notice_me": notice_me,
            "webapp": webapp,
            "about": about,
            "days_without_drama": days_without_drama,
            "drama": drama,
            "publish_anons": publish_anons,
            "quotes": get_random_quote,
            "bottle_game": bottle_game,
            "horoscope": horoscope,  # Добавляем обработчик для гороскопа
        }

        # Специальная обработка для команд, требующих дополнительного ввода
        if query.data == "imitate_menu":
            await query.message.reply_text(
                "Введите имя пользователя для имитации: /imitate <имя>"
            )
            # Удаляем информацию о меню, так как команда выполнена
            if query.message.message_id in context.bot_data.get("menu_users", {}):
                del context.bot_data["menu_users"][query.message.message_id]
            return
        elif query.data == "anon_sender_menu":
            await query.message.reply_text(
                "Введите номер анонимки: /anon_sender <номер>"
            )
            # Удаляем информацию о меню, так как команда выполнена
            if query.message.message_id in context.bot_data.get("menu_users", {}):
                del context.bot_data["menu_users"][query.message.message_id]
            return
        elif query.data == "ban_vote_menu":
            await query.message.reply_text(
                "Введите имя пользователя для голосования: /ban_vote <имя>"
            )
            # Удаляем информацию о меню, так как команда выполнена
            if query.message.message_id in context.bot_data.get("menu_users", {}):
                del context.bot_data["menu_users"][query.message.message_id]
            return
        elif query.data == "suggest_menu":
            # Включаем режим предложки для пользователя
            context.user_data["awaiting_suggest"] = True
            context.user_data["suggest_in_chat"] = query.message.chat.id
            await query.message.reply_text(
                "Напишите сообщение для предложки. Отправьте текст/медиа одним сообщением."
            )
            # Удаляем информацию о меню, так как команда выполнена
            if query.message.message_id in context.bot_data.get("menu_users", {}):
                del context.bot_data["menu_users"][query.message.message_id]
            return
        elif query.data == "welcome_menu":
            await show_welcome_menu(update, context)
            return
        elif query.data == "welcome_edit":
            await start_welcome_edit(update, context)
            return
        elif query.data == "welcome_reset":
            await reset_welcome_text(update, context)
            return
        elif query.data == "good_morning_menu":
            await show_good_morning_menu(update, context)
            return
        elif query.data == "gm_time_menu":
            await show_good_morning_time_menu(update, context)
            return
        elif query.data in ("gm_style_mom", "gm_style_office"):
            style_key = query.data.replace("gm_style_", "")
            await handle_good_morning_style_selection(update, context, style_key)
            return
        elif query.data.startswith("gm_time_adj|"):
            _, target, direction = query.data.split("|")
            delta = 1 if direction == "+" else -1
            await adjust_good_morning_time(update, context, target, delta)
            return
        elif query.data == "gm_time_save":
            await save_good_morning_time(update, context)
            return
        elif query.data == "gm_time_display":
            await query.answer()
            return
        elif query.data == "menu_memes":
            await query.message.reply_text(
                "🖼 Мемы:\n• Локально: ответьте на фото → /meme ВЕРХ:НИЗ (если текста нет — придумаю абсурд сама).\n• ИИ-мемы (лимит 2/сутки) появятся позже в этом меню."
            )
            if query.message.message_id in context.bot_data.get("menu_users", {}):
                del context.bot_data["menu_users"][query.message.message_id]
            return
        elif query.data == "top2h":
            try:
                await query.answer("Показываю обновлённый топ за 3 часа...")
            except Exception:
                pass
            if query.message.message_id in context.bot_data.get("menu_users", {}):
                del context.bot_data["menu_users"][query.message.message_id]
            await send_top_reactions_card(
                update, context, window_hours=TOP_CARD_TIME_WINDOW_HOURS
            )
            return
        elif query.data == "top3h":
            try:
                await query.answer("Готовлю карточку...")
            except Exception:
                pass
            if query.message.message_id in context.bot_data.get("menu_users", {}):
                del context.bot_data["menu_users"][query.message.message_id]
            await send_top_reactions_card(
                update, context, window_hours=TOP_CARD_TIME_WINDOW_HOURS
            )
            return
        elif query.data == "tea_menu":
            await query.message.reply_text(
                "☕ Чай:\n• Быстрый перевод: ответ на сообщение → /+ (по умолчанию +1) или /+3.\n• Баланс: /balance, лидеры: /top_tea week.\nФича в разработке — пока ознакомительный режим."
            )
            if query.message.message_id in context.bot_data.get("menu_users", {}):
                del context.bot_data["menu_users"][query.message.message_id]
            return
        elif query.data == "save_quote_info":
            await query.message.reply_text(
                "Чтобы сохранить цитату, ответьте на нужное сообщение командой /quote\n\n"
                "Пример использования:\n"
                "1. Найдите сообщение, которое хотите сохранить как цитату\n"
                "2. Ответьте на это сообщение командой /quote\n"
                "3. Цитата будет сохранена и доступна по команде /quotes"
            )
            # Удаляем информацию о меню, так как команда выполнена
            if query.message.message_id in context.bot_data.get("menu_users", {}):
                del context.bot_data["menu_users"][query.message.message_id]
            return
        elif query.data == "roll_info":
            await query.message.reply_text(
                "Для броска кубика используйте команду: /roll XdY\n"
                "где X - количество кубиков, Y - количество граней на каждом кубике\n"
                "Примеры:\n"
                "/roll 1d5 - бросить один кубик с 5 гранями (значения от 1 до 5)\n"
                "/roll 2d6 - бросить два шестигранных кубика и суммировать результаты\n"
                "Результат будет в диапазоне от X (минимум) до X*Y (максимум)"
            )
            # Удаляем информацию о меню, так как команда выполнена
            if query.message.message_id in context.bot_data.get("menu_users", {}):
                del context.bot_data["menu_users"][query.message.message_id]
            return

        # Вызываем соответствующую функцию
        if query.data in handlers:
            # Удаляем информацию о меню, так как команда выполнена
            if query.message.message_id in context.bot_data.get("menu_users", {}):
                del context.bot_data["menu_users"][query.message.message_id]

            # Создаем фейковый update для вызова обработчика
            fake_update = type("FakeUpdate", (), {})()
            fake_update.effective_user = query.from_user
            fake_update.message = query.message
            fake_update.effective_chat = query.message.chat

            await handlers[query.data](fake_update, context)
        else:
            await query.message.reply_text("Неизвестная команда")

    except Exception as e:
        await query.message.reply_text(f"Ошибка при обработке команды: {e}")


# === Меню команд ===
async def menu(update, context):
    "Показывает главное меню с категориями команд"
    try:
        keyboard = [
            [
                InlineKeyboardButton("📈 Статистика", callback_data="menu_stats"),
            ],
            [
                InlineKeyboardButton("🎭 Развлечения", callback_data="menu_fun"),
            ],
            [
                InlineKeyboardButton("👥 Социальные", callback_data="menu_social"),
            ],
            [
                InlineKeyboardButton("🛡️ Админские", callback_data="menu_admin"),
            ],
            [
                InlineKeyboardButton("ℹ️ О боте", callback_data="about"),
            ],
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)

        # Сохраняем ID пользователя, который вызвал меню
        menu_message = await update.message.reply_text(
            "Выберите категорию команд:", reply_markup=reply_markup
        )

        # Сохраняем ID пользователя в контексте меню
        context.bot_data.setdefault("menu_users", {})[
            menu_message.message_id
        ] = update.effective_user.id
    except Exception as e:
        await update.message.reply_text(f"Ошибка при отображении меню: {e}")


# Добавляем новую функцию для игры в бутылочку
async def bottle_game(update, context):
    "Игра в бутылочку"
    try:
        # Список действий для игры в бутылочку
        bottle_actions = [
            "@A говорит @B три честных комплимента (без иронии).",
            "@A записывает 10-секундный «танец» голосовым/видео для @B.",
            "@A кидает трек, который ассоциируется с @B, и объясняет в 1 предложении — почему.",
            "@A делает мем с @B (картинка + подпись) и кидает в чат.",
            "@A выполняет мини-поручение от @B в одну фразу",
            "@A присылает фото/картинку предмета, ассоциирующегося с @B",
            '@A отправляет "эмодзи-пантомиму" из 5 смайлов, а @B пытается угадать, что зашифровано.',
            "@A делится одним личным лайфхаком специально для @B",
            "@A придумывает и озвучивает общий боевой клич для себя и @B.",
            "@A признаётся, за что тайно респектует @B, и кидает подтверждающий мем.",
            "@A рассказывает короткую историю, как они с @B спасли чат от скуки.",
            "@A придумывает совместный челлендж на сутки и помечает @B.",
        ]

        # Создаем кнопку для участия в игре
        keyboard = [[InlineKeyboardButton("Кто играет?", callback_data="bottle_join")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Сохраняем список действий и состояние игры в контексте
        context.bot_data["bottle_game"] = {
            "actions": bottle_actions,
            "participants": [],  # Список будет содержать словари с информацией об участниках
            "started": True,
            "message_id": update.message.message_id,
        }

        await update.message.reply_text(
            "Игра в бутылочку!\nНажмите кнопку ниже, чтобы участвовать:",
            reply_markup=reply_markup,
        )
    except Exception as e:
        await update.message.reply_text(f"Ошибка при запуске игры: {e}")


async def bottle_join_button(update, context):
    "Обработчик кнопки участия в игре"
    try:
        query = update.callback_query
        await query.answer()

        # Проверяем, есть ли активная игра
        if "bottle_game" not in context.bot_data or not context.bot_data[
            "bottle_game"
        ].get("started"):
            await query.answer("Игра уже завершена!", show_alert=True)
            return

        # Получаем информацию о пользователе
        user = query.from_user.first_name or "Неизвестный"
        username = query.from_user.username

        # Формируем имя пользователя с тегом, если доступно
        if username:
            user_display = f"@{username}"
        else:
            user_display = user

        # Проверяем, не участвует ли уже пользователь
        # Для проверки используем user_display, но сохраняем оригинальное имя для игры
        if any(
            p["display"] == user_display
            for p in context.bot_data["bottle_game"]["participants"]
        ):
            await query.answer("Вы уже участвуете!", show_alert=True)
            return

        # Добавляем пользователя в список участников с информацией о теге
        participant_info = {
            "name": user,  # Оригинальное имя для игры
            "display": user_display,  # Имя с тегом для отображения
        }
        context.bot_data["bottle_game"]["participants"].append(participant_info)

        # Если это первый участник, просто подтверждаем участие
        if len(context.bot_data["bottle_game"]["participants"]) == 1:
            await query.answer("Вы участвуете! Ждем второго игрока...", show_alert=True)
            return

        # Если второй участник, запускаем игру
        if len(context.bot_data["bottle_game"]["participants"]) == 2:
            # Выбираем случайное действие
            action = random.choice(context.bot_data["bottle_game"]["actions"])

            # Получаем участников
            participants = context.bot_data["bottle_game"]["participants"]
            user_a_display = participants[0]["display"]
            user_b_display = participants[1]["display"]

            # Заменяем @A и @B на имена участников с тегами
            result = action.replace("@A", user_a_display).replace("@B", user_b_display)

            # Отправляем результат игры
            await query.message.reply_text(f"Результат игры в бутылочку:\n\n{result}")

            # Завершаем игру
            context.bot_data["bottle_game"]["started"] = False

            # Уведомляем пользователей
            await query.answer("Игра началась!", show_alert=True)
            return

    except Exception as e:
        await query.message.reply_text(f"Ошибка в игре: {e}")


# Обработчик ошибок для отладки
async def error_handler(update, context):
    "Логирует ошибки, возникающие при обработке обновлений."
    logger = logging.getLogger(__name__)
    logger.error("Произошла ошибка при обработке обновления:", exc_info=context.error)

    # Дополнительная информация для отладки
    if update:
        logger.error(f"Update: {update}")
        if hasattr(update, "effective_user") and update.effective_user:
            logger.error(
                f"User: {update.effective_user.id} - {update.effective_user.first_name}"
            )
        if hasattr(update, "effective_chat") and update.effective_chat:
            logger.error(
                f"Chat: {update.effective_chat.id} - {update.effective_chat.type}"
            )

    if context:
        logger.error(f"Context args: {context.args}")
        logger.error(f"Context error: {context.error}")

    # Специальная обработка ошибок сети
    if "getUpdates" in str(context.error):
        logger.warning(
            "Ошибка getUpdates - возможные проблемы с сетью или Telegram API"
        )

    # Не отправляем ошибку пользователю, чтобы не спамить


def send_scheduled_summary(chat_id=None):
    try:
        target_chat_id = chat_id or CHAT_ID
        if not target_chat_id:
            logging.getLogger(__name__).warning(
                "Невозможно отправить ежедневное резюме: не задан CHAT_ID"
            )
            return

        today = utctoday()
        query = "SELECT username, message FROM messages WHERE date(timestamp)=?"
        params = [today]
        if MESSAGES_HAS_CHAT_ID:
            query += " AND chat_id = ?"
            params.append(target_chat_id)
        query += " ORDER BY id"
        cursor.execute(query, tuple(params))
        msgs = [f"{u}: {m}" for u, m in cursor.fetchall()]
        if not msgs:
            return

        response = ask_gpt("", msgs, summary=True)
        reply = response.text
        if not context_bot:
            logging.getLogger(__name__).warning(
                "context_bot недоступен, ежедневное резюме не отправлено"
            )
            return

        _schedule_bot_coro(
            send_text_chunks(
                context_bot,
                chat_id=target_chat_id,
                text=reply,
                parse_mode="Markdown",
            ),
            logger=logging.getLogger(__name__),
        )
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Ошибка при отправке ежедневного резюме: {e}")


def send_monthly_nolifers(chat_id=None):
    try:
        target_chat_id = chat_id or CHAT_ID
        if not target_chat_id:
            logging.getLogger(__name__).warning(
                "Невозможно отправить месячный рейтинг: не задан CHAT_ID"
            )
            return

        base_query = "SELECT username, COUNT(*) as cnt FROM messages"
        params = []
        if MESSAGES_HAS_CHAT_ID:
            base_query += " WHERE chat_id = ?"
            params.append(target_chat_id)
        base_query += " GROUP BY username ORDER BY cnt DESC LIMIT 10"
        cursor.execute(base_query, tuple(params))
        rows = cursor.fetchall()
        if not rows:
            return

        text_message = "Топ активных участников за месяц:\n"
        medals = ["🥇", "🥈", "🥉"] + [""] * 7
        for i, (user, cnt) in enumerate(rows):
            medal = medals[i] if i < len(medals) else ""
            text_message += f"{medal} {i+1}. {user} \u2014 {cnt} \u0441\u043e\u043e\u0431\u0449\u0435\u043d\u0438\u0439\n"
        text_message += "\u0421\u043f\u0430\u0441\u0438\u0431\u043e, \u0447\u0442\u043e \u0434\u0435\u0440\u0436\u0438\u0442\u0435 \u0447\u0430\u0442 \u0436\u0438\u0432\u044b\u043c!"
        text_message += "Спасибо, что держите чат живым!"
        text_message += "Спасибо, что держите чат живым!"

        if not context_bot:
            logging.getLogger(__name__).warning(
                "context_bot недоступен, месячный рейтинг не отправлено"
            )
            return

        _schedule_bot_coro(
            context_bot.send_message(chat_id=target_chat_id, text=text_message),
            logger=logging.getLogger(__name__),
        )
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Ошибка при отправке месячного рейтинга: {e}")


def auto_publish_anons():
    import asyncio
    from telegram.ext import Application

    async def run():
        try:
            # Создаём Application для получения bot instance
            app = Application.builder().token(TOKEN).build()
            await app.initialize()

            # Создаём фейковый update/context для publish_anons
            class DummyUpdate:
                def __init__(self):
                    dummy_id = 0
                    self.effective_user = type("User", (), {"id": dummy_id})()
                    self.effective_chat = type("Chat", (), {"id": dummy_id})()
                    # Создаём фейковый message объект с нужными атрибутами
                    self.message = type(
                        "Message",
                        (),
                        {
                            "chat_id": dummy_id,
                            "reply_text": lambda *a, **k: None,  # Фейковый метод
                        },
                    )()

            class DummyContext:
                def __init__(self, bot):
                    self.bot = bot
                    self.application = type("Application", (), {"bot": bot})()

            update = DummyUpdate()
            context = DummyContext(app.bot)

            # Вызываем publish_anons с фейковыми параметрами
            await publish_anons(update, context)

            await app.shutdown()
        except Exception as e:
            print(f"Ошибка в auto_publish_anons: {e}")
            import traceback

            traceback.print_exc()

    # Запускаем асинхронную функцию
    try:
        # Для новых версий Python используем asyncio.run
        if hasattr(asyncio, "run"):
            asyncio.run(run())
        else:
            # Для старых версий
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(run())
    except Exception as e:
        print(f"Ошибка при запуске auto_publish_anons: {e}")
        import traceback

        traceback.print_exc()


def setup_secrets():
    """
    Should be called once, when bot starts.
    :return:
    """
    try:
        global TOKEN, OPENAI_API_KEY, CHAT_ID, GEMINI_API_KEY, DB_PATH, STATIC_WEB_PATH, ADMIN_USER_ID, SYNC_COMMANDS_ON_START
        global gemini_model, gemini_unavailable_reason

        TOKEN = os.getenv("TOKEN")
        OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
        GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
        CHAT_ID = int(os.getenv("CHAT_ID", 0))  # int
        DB_PATH = os.getenv("DB_PATH", "chat.db")
        STATIC_WEB_PATH = os.getenv("STATIC_WEB_PATH", "")
        ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", "472144090"))
        SYNC_COMMANDS_ON_START = (
            os.getenv("SYNC_COMMANDS_ON_START", "false").lower() == "true"
        )

        gemini_unavailable_reason = ""
        if GEMINI_API_KEY and genai is not None:
            try:
                genai.configure(api_key=GEMINI_API_KEY)
                gemini_model = genai.GenerativeModel("gemini-pro")
            except Exception as configure_err:
                gemini_model = None
                gemini_unavailable_reason = (
                    f"Не удалось инициализировать Gemini: {configure_err}"
                )
                logging.getLogger(__name__).warning(gemini_unavailable_reason)
        else:
            gemini_model = None
            if not GEMINI_API_KEY:
                gemini_unavailable_reason = "GEMINI_API_KEY не задан, Gemini отключён."
            elif genai is None:
                gemini_unavailable_reason = (
                    "Пакет google-generativeai не установлен, Gemini отключён."
                )

        if FRIEND_FOE_HAS_CHAT_ID and CHAT_ID:
            try:
                cursor.execute(
                    "UPDATE friend_foe SET chat_id = ? WHERE chat_id IS NULL",
                    (CHAT_ID,),
                )
                conn.commit()
            except Exception as update_err:
                logging.getLogger(__name__).warning(
                    "Не удалось обновить chat_id в таблице friend_foe: %s", update_err
                )

    except Exception as e:
        # Log the error and re-raise it
        logger = logging.getLogger(__name__)
        logger.error(f"Ошибка при настройке секретов: {e}")
        raise


def mamoolyaMain():
    try:
        # читаем всякие токены
        setup_secrets()
        ensure_good_morning_settings(CHAT_ID)
        ensure_welcome_message(CHAT_ID)

        # Настройки таймаутов для стабильной работы
        from telegram.request import HTTPXRequest

        # Создаём кастомный request с увеличенными таймаутами
        request = HTTPXRequest(
            connection_pool_size=8,
            connect_timeout=30.0,
            read_timeout=30.0,
            write_timeout=30.0,
            pool_timeout=30.0,
        )

        app = ApplicationBuilder().token(TOKEN).request(request).build()
        global context_bot, scheduler, application
        context_bot = app.bot
        application = app

        # Логирование информации о запуске
        logger = logging.getLogger(__name__)
        logger.info("=" * 50)
        logger.info(f"Version: {get_version()}")
        logger.info("🤖 Запуск бота Мамуля")
        logger.info(f"📡 Токен: {TOKEN[:10]}...")
        logger.info(f"💬 Chat ID: {CHAT_ID}")
        logger.info(f"🔗 HTTP настройки: connect_timeout=30s, read_timeout=30s")
        logger.info("=" * 50)

        # Синхронизация команд с BotFather при старте (по флагу)
        async def sync_bot_commands():
            try:
                from telegram.constants import BotCommandScopeDefault
                from telegram import BotCommand

                commands = [
                    BotCommand("menu", "Открыть меню Мамочки"),
                    BotCommand("help", "Краткая справка"),
                    BotCommand("m_version", "Версия бота"),
                ]
                await context_bot.set_my_commands(
                    commands=commands,
                    scope=BotCommandScopeDefault(),
                    language_code="ru",
                )
                await context_bot.set_my_commands(
                    commands=commands,
                    scope=BotCommandScopeDefault(),
                    language_code="en",
                )
                logger.info("✅ Команды синхронизированы: /menu, /help, /m_version")
            except Exception as e:
                logger = logging.getLogger(__name__)
                logger.error(f"Ошибка синхронизации команд: {e}")

        if SYNC_COMMANDS_ON_START:
            try:
                app.create_task(sync_bot_commands())
            except Exception:
                import asyncio as _asyncio

                _asyncio.get_event_loop().create_task(sync_bot_commands())

        app.add_handler(CommandHandler("start", start_command))
        app.add_handler(CommandHandler("randomquote", randomquote))
        app.add_handler(CommandHandler("top_pairs", top_pairs))
        app.add_handler(CommandHandler("sticker_stats", sticker_stats))
        app.add_handler(CommandHandler("summary", summary))
        app.add_handler(CommandHandler("summary_day", summary_day))
        app.add_handler(CommandHandler("summary_week", summary_week))
        app.add_handler(CommandHandler("my_stats", my_stats))
        app.add_handler(CommandHandler("mystats", my_stats))
        app.add_handler(CommandHandler("ignore_me", ignore_me))
        app.add_handler(CommandHandler("notice_me", notice_me))
        app.add_handler(CommandHandler("top_nolifers", top_nolifers))
        app.add_handler(CommandHandler("top_nolifers_day", top_nolifers_day))
        app.add_handler(CommandHandler("top_nolifers_week", top_nolifers_week))
        app.add_handler(CommandHandler("days_without_drama", days_without_drama))
        app.add_handler(CommandHandler("drama", drama))
        app.add_handler(CommandHandler("dvach", dvach))
        app.add_handler(CommandHandler("psychologist", psychologist))
        app.add_handler(CommandHandler("predict", predict))
        app.add_handler(CommandHandler("fact", fact))
        app.add_handler(CommandHandler("imitate", imitate))
        app.add_handler(CommandHandler("ban_vote", ban_vote))
        app.add_handler(CommandHandler("publish_anons", publish_anons))
        app.add_handler(CommandHandler("anon_sender", anon_sender))
        app.add_handler(CommandHandler("friend_foe_stats", friend_foe_stats))
        app.add_handler(CommandHandler("friend_foe_top", friend_foe_top))
        app.add_handler(CommandHandler("webapp", webapp))
        # Добавляем обработчик для гороскопа
        app.add_handler(CommandHandler("horoscope", horoscope))
        # Добавляем обработчик для броска кубика
        app.add_handler(CommandHandler("roll", roll))
        # Удаляем старый обработчик кнопок голосования, так как теперь у нас общий обработчик меню
        # app.add_handler(CallbackQueryHandler(ban_vote_button, pattern=r"^(ban|leave)\|"))
        app.add_handler(CommandHandler("about", about))
        app.add_handler(CommandHandler("m_version", version))
        # Добавляем обработчики для меню
        app.add_handler(CommandHandler("menu", menu))
        app.add_handler(CommandHandler("help", help_command))
        # Добавляем обработчики для цитат
        app.add_handler(CommandHandler("quote", save_quote))
        app.add_handler(CommandHandler("quotes", get_random_quote))
        # Добавляем обработчик для игры в бутылочку
        app.add_handler(CommandHandler("bottle", bottle_game))
        # Обработчик кнопки для игры в бутылочку
        app.add_handler(
            CallbackQueryHandler(bottle_join_button, pattern="^bottle_join$")
        )
        # Обновляем обработчик кнопок меню
        app.add_handler(CallbackQueryHandler(menu_button_handler))
        app.add_handler(
            MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_new_members)
        )
        app.add_handler(
            MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message)
        )
        # Неизвестные команды → hint
        app.add_handler(MessageHandler(filters.COMMAND, unknown_command))
        if MessageReactionHandler is not None:
            app.add_handler(MessageReactionHandler(handle_reaction))
        else:
            logging.getLogger(__name__).warning(
                "MessageReactionHandler is unavailable — реакции Telegram недоступны (обновите python-telegram-bot)"
            )

        # Регистрируем обработчик ошибок
        app.add_error_handler(error_handler)

        scheduler = BackgroundScheduler(timezone=GOOD_MORNING_TZ)
        if CHAT_ID:
            scheduler.add_job(
                send_scheduled_summary,
                "cron",
                hour=12,
                minute=0,
                kwargs={"chat_id": CHAT_ID},
            )
            scheduler.add_job(
                send_monthly_nolifers,
                "cron",
                day=1,
                hour=7,
                minute=0,
                kwargs={"chat_id": CHAT_ID},
            )
        else:
            logger.warning(
                "CHAT_ID не задан — плановые сообщения выключены до настройки окружения"
            )
        # УБРАЛИ задачу auto_publish_anons, так как теперь сообщения публикуются немедленно
        # scheduler.add_job(auto_publish_anons, 'interval', minutes=5)
        schedule_all_good_morning_jobs()
        scheduler.start()
        logger.info("⏰ Планировщик задач запущен")

        # Запускаем polling с правильными настройками для стабильности
        logger.info("🚀 Запуск long polling...")
        logger.info("📋 Параметры polling: timeout=20s, retries=5, interval=1.0s")

        try:
            app.run_polling(
                poll_interval=1.0, timeout=20, bootstrap_retries=5, close_loop=False
            )
        except Exception as e:
            logger.error(
                f"💥 Критическая ошибка при запуске polling: {e}", exc_info=True
            )
            raise
    except Exception as e:
        # Log the error and re-raise it
        logger = logging.getLogger(__name__)
        logger.error(f"Ошибка при запуске бота: {e}", exc_info=True)
        raise
