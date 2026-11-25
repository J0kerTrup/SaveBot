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
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest, TelegramNetworkError, TelegramRetryAfter
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup, Message, User
from aiogram.utils.chat_action import ChatActionSender

import family_refs
from downloader import DownloadError, download, find_links
from emoji import premium, split_icon
from family_lang import Family, sync_private
from family_news import News
from family_news import button as news_button
from family_stats import Stats
from i18n import LANGS, SITE, pick, t

log = logging.getLogger("savebot")

TOKEN = os.environ["BOT_TOKEN"]
COOKIES = os.environ.get("COOKIES_FILE") or None  # cookies.txt для Instagram, если без входа не отдаёт
SEND_AUDIO = os.environ.get("SEND_AUDIO", "1") != "0"  # к видео отдельно присылать трек
PARALLEL = int(os.environ.get("PARALLEL_DOWNLOADS", "3"))
PER_CHAT_PER_MINUTE = int(os.environ.get("PER_CHAT_PER_MINUTE", "6"))
DB_PATH = os.environ.get("DB_PATH", "data/savebot.sqlite3")
LINKS_PER_MESSAGE = 2
# "Too many links" goes to a chat at most once a minute: a busy group must not get a reply to every message.
WARN_EVERY = 60

dp = Dispatcher()
# The language a person chose in any bot of Pixel Radio (family_lang.py).
family = Family("PixelSaver/1.0")
# What people do here, in numbers only, for the map of Pixel Hub's admin (family_stats.py).
stats = Stats(Path(DB_PATH).parent / "stats.sqlite3", ("start", "help", "lang"))
dp.message.outer_middleware(stats.middleware)
dp.callback_query.outer_middleware(stats.middleware)
# Added to a group, taken out of it.
dp.my_chat_member.register(stats.membership)
slots = asyncio.Semaphore(PARALLEL)
recent: dict[int, deque[float]] = defaultdict(deque)
warned: dict[int, float] = {}
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
    rows = [[button(t(lang, "add"), None, "primary", url=f"https://t.me/{username}?startgroup=true")]]
    rows.append([button(family_refs.button(lang), "ui:ref"), button(news_button(lang), "news")])
    rows.append([button(t(lang, "language"), "ui:lang")])
    rows.append(
        [
            button(t(lang, "hub"), None, url="https://t.me/HUBPIXELBOT?start=bot_saver"),
            button(t(lang, "site"), None, url=f"https://{SITE}/?from=bot_saver"),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def language_menu(lang: str) -> InlineKeyboardMarkup:
    flags = [button(label, f"lang:{code}", "success" if code == lang else None) for code, label in LANGS.items()]
    rows = [flags[i : i + 2] for i in range(0, len(flags), 2)]
    rows.append([button(t(lang, "back"), "ui:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def edit_ui(message: Message, text: str, markup: InlineKeyboardMarkup) -> None:
    """Keep navigation in one message, whether it started as text or as a banner."""
    if message.photo:
        await message.edit_caption(caption=premium(text), reply_markup=markup)
    else:
        await message.edit_text(premium(text), reply_markup=markup)


# News for those who asked for them (family_news.py): what to send and when comes from Pixel Hub.
news = News("saver", Path(DB_PATH).parent / "news.sqlite3", lambda user_id: _own_lang(user_id), "ui:home", premium=premium)
dp.include_router(news.router())


@dp.message(CommandStart())
async def start(message: Message) -> None:
    lang = lang_of(message.chat.id, message.from_user)
    await message.answer_photo(FSInputFile("assets/banners/start.png"), caption=premium(t(lang, "start")), reply_markup=menu(lang))


@dp.message(Command("help"))
async def help_command(message: Message) -> None:
    lang = lang_of(message.chat.id, message.from_user)
    await message.answer(premium(t(lang, "help")), reply_markup=menu(lang))


@dp.message(Command("lang"))
async def lang_command(message: Message) -> None:
    lang = lang_of(message.chat.id, message.from_user)
    await message.answer(premium(t(lang, "choose_language")), reply_markup=language_menu(lang))


@dp.callback_query(F.data.startswith("ui:"))
async def navigate(query: CallbackQuery) -> None:
    msg = query.message
    if not isinstance(msg, Message):
        await query.answer()
        return
    lang = lang_of(msg.chat.id, query.from_user)
    page = (query.data or "").split(":", 1)[1]
    if page == "ref":
        stats.hit("press", "invite")
        if msg.chat.type != ChatType.PRIVATE:
            await query.answer(family_refs.private_only(lang), show_alert=True)
            return
        share = button(family_refs.share(lang), None, "primary", url=family_refs.share_url(stats, username, query.from_user.id))
        rows = [[share], [button(t(lang, "back"), "ui:home")]]
        try:
            await edit_ui(msg, family_refs.screen(stats, username, query.from_user.id, lang), InlineKeyboardMarkup(inline_keyboard=rows))
        except TelegramBadRequest:
            pass
        await query.answer()
        return
    text, markup = (t(lang, "choose_language"), language_menu(lang)) if page == "lang" else (t(lang, "start"), menu(lang))
    try:
        await edit_ui(msg, text, markup)
    except TelegramBadRequest:
        pass
    await query.answer()


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
    if msg.chat.type == ChatType.PRIVATE:
        await family.put(query.from_user.id, lang)
    try:
        await edit_ui(msg, t(lang, "choose_language"), language_menu(lang))
    except TelegramBadRequest:
        pass  # тот же язык — текст не изменился
    await query.answer(t(lang, "lang_set"))


# --- скачивание --------------------------------------------------------------


def allowed(chat_id: int) -> bool:
    """Не больше PER_CHAT_PER_MINUTE ссылок в минуту на чат."""
    now = time.monotonic()
    q = recent[chat_id]
    while q and now - q[0] > 60:
        q.popleft()
    if len(q) >= PER_CHAT_PER_MINUTE:
        return False
    q.append(now)
    return True


def should_warn(chat_id: int) -> bool:
    now = time.monotonic()
    if now - warned.get(chat_id, -WARN_EVERY) < WARN_EVERY:
        return False
    if len(warned) > 10_000:
        warned.clear()
    warned[chat_id] = now
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
    if not links:
        # In a group people just talk; in private a message without a link is a question the bot should answer.
        if message.chat.type == ChatType.PRIVATE and not (message.text or "").startswith("/"):
            await message.answer(premium(t(lang_of(message.chat.id, message.from_user), "no_link")))
        return
    for url in links[:LINKS_PER_MESSAGE]:
        if not allowed(message.chat.id):
            stats.hit("result", "limited")
            if should_warn(message.chat.id):
                await message.reply(premium("⏳ " + t(lang_of(message.chat.id, message.from_user), "rate_limited")))
            return
        # One try per link of a message: the same update delivered again goes on with it, or is left alone if it is done.
        attempt, state = stats.attempt(f"{message.chat.id}:{message.message_id}:{url}")
        if state == "done":
            continue
        if state == "new":
            stats.hit("result", "link")
        try:
            await handle(message, bot, url, attempt)
        except TelegramRetryAfter as e:
            stats.finished(attempt, "fail", "delivery", "flood")
            log.warning("FloodWait %s с в чате %s", e.retry_after, message.chat.id)
            return
        except Exception as e:
            log.exception("Сбой на %s", url)
            stats.hit("result", "fail")
            stats.finished(attempt, "fail", *failure_of(e))
            await message.reply(premium("❌ " + t(lang_of(message.chat.id, message.from_user), "unexpected")))


def failure_of(error: Exception) -> tuple[str, str]:
    """What an unexpected error was, for the count of tries: the time, the delivery to Telegram, or something else."""
    if isinstance(error, TimeoutError | TelegramNetworkError):
        return "timeout", "delivery"
    if isinstance(error, TelegramAPIError):
        return "delivery", "telegram"
    return "other", "unexpected"


async def handle(message: Message, bot: Bot, url: str, attempt: str | None = None) -> None:
    if url in cache:
        video_id, audio_id = cache[url]
        stats.hit("result", "cached")
        if video_id:
            await message.reply_video(video_id, caption=caption)
        if audio_id and (SEND_AUDIO or not video_id):
            await message.reply_audio(audio_id, caption=caption)
        stats.finished(attempt, "ok", detail="cached")
        return

    lang = lang_of(message.chat.id, message.from_user)
    async with slots, ChatActionSender.upload_video(bot=bot, chat_id=message.chat.id, message_thread_id=message.message_thread_id):
        stats.started(attempt)
        with tempfile.TemporaryDirectory(prefix="savebot-") as tmp:
            try:
                media = await asyncio.to_thread(download, url, Path(tmp), COOKIES)
            except DownloadError as e:
                stats.hit("result", "fail")
                stats.finished(attempt, "fail", e.why, e.code)
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
                stats.hit("result", "video")
                # The file has come: the try is a success, whatever happens to the track after it.
                stats.finished(attempt, "ok", detail="video")
            elif media.long_video:
                stats.hit("result", "big")
                await message.reply(premium("❗️ " + t(lang, "long_video")))
            elif media.video_too_big:
                stats.hit("result", "big")
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
                stats.hit("result", "audio")
                stats.finished(attempt, "ok", detail="audio")

            if video_id or audio_id:
                remember(url, video_id, audio_id)
            # Nothing was sent: the video was too big and there was no track to send instead.
            stats.finished(attempt, "fail", "too_big", "no_file")


@dp.message(F.chat.type == ChatType.PRIVATE)
async def not_a_link(message: Message) -> None:
    """A sticker, voice, photo or file in private: say what the bot takes instead of staying silent."""
    await message.answer(premium(t(lang_of(message.chat.id, message.from_user), "no_link")))


def _own_lang(chat_id: int) -> str | None:
    row = db.execute("SELECT lang FROM chat_lang WHERE chat_id = ?", (chat_id,)).fetchone()
    return row[0] if row and row[0] in LANGS else None


@dp.message.outer_middleware()
@dp.callback_query.outer_middleware()
async def family_language(handler, event, data):
    """In private, the language chosen in any bot of the family wins over this bot's own; a group keeps the language its admins
    chose here."""
    message = event.message if isinstance(event, CallbackQuery) else event
    user = event.from_user
    if user and isinstance(message, Message) and message.chat.type == ChatType.PRIVATE:
        chat_id = message.chat.id
        await sync_private(
            family, user.id, _own_lang(chat_id), lambda lang: set_lang(chat_id, lang), event.text if isinstance(event, Message) else None
        )
    return await handler(event, data)


async def main() -> None:
    global caption, username, db
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    db = open_db()
    bot = Bot(TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    me = await bot.get_me()
    username = me.username or ""
    caption = premium(os.environ.get("CAPTION") or f'📥 <a href="https://t.me/{username}?start=chat">@{username}</a>')
    log.info("Запущен @%s", username)
    sending = asyncio.create_task(news.run(bot))
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        sending.cancel()


if __name__ == "__main__":
    asyncio.run(main())
