"""Бот-скачивалка: в группе или в личке кидаешь ссылку TikTok/Instagram — получаешь видео и трек ответом."""

import asyncio
import logging
import os
import sqlite3
import tempfile
import time
from collections import OrderedDict, defaultdict, deque
from pathlib import Path

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ChatType, ParseMode
from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup, Message, User
from aiogram.utils.chat_action import ChatActionSender

from downloader import DownloadError, download, find_links
from emoji import premium, split_icon
from i18n import LANGS, pick, t

log = logging.getLogger("savebot")

TOKEN = os.environ["BOT_TOKEN"]
COOKIES = os.environ.get("COOKIES_FILE") or None  # cookies.txt для Instagram, если без входа не отдаёт
SEND_AUDIO = os.environ.get("SEND_AUDIO", "1") != "0"  # к видео отдельно присылать трек
PARALLEL = int(os.environ.get("PARALLEL_DOWNLOADS", "3"))
PER_CHAT_PER_MINUTE = int(os.environ.get("PER_CHAT_PER_MINUTE", "6"))
DB_PATH = os.environ.get("DB_PATH", "data/savebot.sqlite3")
LINKS_PER_MESSAGE = 2

dp = Dispatcher()
slots = asyncio.Semaphore(PARALLEL)
recent: dict[int, deque[float]] = defaultdict(deque)
# Повторную ссылку отдаём по file_id без нового скачивания.
cache: OrderedDict[str, tuple[str | None, str | None]] = OrderedDict()
CACHE_SIZE = 2000
caption = ""
username = ""
db: sqlite3.Connection


# --- язык чата ---------------------------------------------------------------


def open_db() -> sqlite3.Connection:
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("CREATE TABLE IF NOT EXISTS chat_lang (chat_id INTEGER PRIMARY KEY, lang TEXT NOT NULL)")
    return conn


def lang_of(chat_id: int, user: User | None) -> str:
    """Язык, выбранный в чате; если не выбирали — язык Telegram у человека."""
    row = db.execute("SELECT lang FROM chat_lang WHERE chat_id = ?", (chat_id,)).fetchone()
    if row and row[0] in LANGS:
        return row[0]
    return pick(user.language_code if user else None)


def set_lang(chat_id: int, lang: str) -> None:
    db.execute(
        "INSERT INTO chat_lang (chat_id, lang) VALUES (?, ?) ON CONFLICT(chat_id) DO UPDATE SET lang = excluded.lang", (chat_id, lang)
    )
    db.commit()


def button(text: str, data: str | None, style: str | None = None, url: str | None = None) -> InlineKeyboardButton:
    """Эмодзи в начале текста становится премиум-иконкой кнопки; выбранный язык — зелёная кнопка."""
    icon, label = split_icon(text)
    return InlineKeyboardButton(text=label, icon_custom_emoji_id=icon, style=style, callback_data=data, url=url)


def menu(lang: str) -> InlineKeyboardMarkup:
    flags = [button(label, f"lang:{code}", "success" if code == lang else None) for code, label in LANGS.items()]
    rows = [[button(t(lang, "add"), None, "primary", url=f"https://t.me/{username}?startgroup=true")]]
    rows += [flags[i : i + 2] for i in range(0, len(flags), 2)]
    return InlineKeyboardMarkup(inline_keyboard=rows)


@dp.message(CommandStart())
@dp.message(Command("lang", "help"))
async def start(message: Message) -> None:
    lang = lang_of(message.chat.id, message.from_user)
    await message.answer(premium(t(lang, "start")), reply_markup=menu(lang))


@dp.callback_query(F.data.startswith("lang:"))
async def choose_lang(query: CallbackQuery, bot: Bot) -> None:
    lang = query.data.split(":", 1)[1]
    msg = query.message
    if lang not in LANGS or not isinstance(msg, Message):
        await query.answer()
        return
    if msg.chat.type != ChatType.PRIVATE:
        member = await bot.get_chat_member(msg.chat.id, query.from_user.id)
        if member.status not in ("creator", "administrator"):
            await query.answer(t(lang_of(msg.chat.id, query.from_user), "admins_only"), show_alert=True)
            return
    set_lang(msg.chat.id, lang)
    try:
        await msg.edit_text(premium(t(lang, "start")), reply_markup=menu(lang))
    except TelegramBadRequest:
        pass  # тот же язык — текст не изменился
    await query.answer(t(lang, "lang_set"))


# --- скачивание --------------------------------------------------------------


def allowed(chat_id: int) -> bool:
    """Не больше PER_CHAT_PER_MINUTE ссылок в минуту на чат: лишние молча пропускаем."""
    now = time.monotonic()
    q = recent[chat_id]
    while q and now - q[0] > 60:
        q.popleft()
    if len(q) >= PER_CHAT_PER_MINUTE:
        return False
    q.append(now)
    return True


def remember(url: str, video_id: str | None, audio_id: str | None) -> None:
    cache[url] = (video_id, audio_id)
    cache.move_to_end(url)
    while len(cache) > CACHE_SIZE:
        cache.popitem(last=False)


@dp.message(F.text | F.caption)
async def on_message(message: Message, bot: Bot) -> None:
    entities = (message.entities or []) + (message.caption_entities or [])
    links = find_links(message.text or message.caption, [e.url for e in entities if e.url])
    for url in links[:LINKS_PER_MESSAGE]:
        if not allowed(message.chat.id):
            return
        try:
            await handle(message, bot, url)
        except TelegramRetryAfter as e:
            log.warning("FloodWait %s с в чате %s", e.retry_after, message.chat.id)
            return
        except Exception:
            log.exception("Сбой на %s", url)


async def handle(message: Message, bot: Bot, url: str) -> None:
    if url in cache:
        video_id, audio_id = cache[url]
        if video_id:
            await message.reply_video(video_id, caption=caption)
        if audio_id and (SEND_AUDIO or not video_id):
            await message.reply_audio(audio_id, caption=caption)
        return

    lang = lang_of(message.chat.id, message.from_user)
    async with slots, ChatActionSender.upload_video(bot=bot, chat_id=message.chat.id, message_thread_id=message.message_thread_id):
        with tempfile.TemporaryDirectory(prefix="savebot-") as tmp:
            try:
                media = await asyncio.to_thread(download, url, Path(tmp), COOKIES)
            except DownloadError as e:
                await message.reply(premium("❌ " + t(lang, str(e))))
                return

            video_id = audio_id = None
            if media.video:
                sent = await message.reply_video(
                    FSInputFile(media.video, filename="video.mp4"),
                    caption=caption,
                    duration=media.duration,
                    width=media.width,
                    height=media.height,
                    supports_streaming=True,
                )
                video_id = sent.video.file_id if sent.video else None
            elif media.video_too_big:
                await message.reply(premium("❗️ " + t(lang, "too_big")))

            if media.audio and (SEND_AUDIO or not media.video):
                sent = await message.reply_audio(
                    FSInputFile(media.audio, filename=f"{media.title}.mp3"),
                    caption=caption,
                    title=media.title,
                    performer=media.performer,
                    duration=media.duration,
                    thumbnail=FSInputFile(media.thumb) if media.thumb else None,
                )
                audio_id = sent.audio.file_id if sent.audio else None

            remember(url, video_id, audio_id)


async def main() -> None:
    global caption, username, db
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    db = open_db()
    bot = Bot(TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    me = await bot.get_me()
    username = me.username or ""
    caption = premium(os.environ.get("CAPTION") or f"📥 @{username}")
    log.info("Запущен @%s", username)
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())
