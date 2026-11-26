"""Бот-скачивалка: в группе или в личке кидаешь ссылку TikTok, Instagram, YouTube или Spotify — получаешь файлы ответом."""

import asyncio
import html
import logging
import os
import shutil
import sqlite3
import subprocess
import tempfile
import time
from collections import OrderedDict, defaultdict, deque
from contextlib import suppress
from pathlib import Path

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ChatType, ParseMode
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest, TelegramNetworkError, TelegramRetryAfter
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    CallbackQuery,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaAudio,
    InputMediaPhoto,
    InputMediaVideo,
    Message,
    ReplyParameters,
    User,
)
from aiogram.utils.chat_action import ChatActionSender

import downloader
import family_refs
from downloader import SMALL_LIMIT, DownloadError, File, Playlist, download, find_links, is_profile, spotify_track
from emoji import premium, split_icon
from family_lang import Family, sync_private
from family_news import News
from family_news import button as news_button
from family_stats import Stats
from i18n import LANGS, SITE, pick, t
from uploader import Uploader

log = logging.getLogger("savebot")

TOKEN = os.environ["BOT_TOKEN"]
COOKIES = os.environ.get("COOKIES_FILE") or None  # cookies.txt для Instagram, если без входа не отдаёт
SEND_AUDIO = os.environ.get("SEND_AUDIO", "1") != "0"  # к видео отдельно присылать трек
PARALLEL = int(os.environ.get("PARALLEL_DOWNLOADS", "3"))
PER_CHAT_PER_MINUTE = int(os.environ.get("PER_CHAT_PER_MINUTE", "6"))
DB_PATH = os.environ.get("DB_PATH", "data/savebot.sqlite3")
LINKS_PER_MESSAGE = 2
# Spotify: сколько треков альбома или плейлиста присылать в личке и в группе (в группе — чтобы не завалить разговор).
PLAYLIST_PRIVATE = int(os.environ.get("PLAYLIST_PRIVATE", "50"))
PLAYLIST_GROUP = int(os.environ.get("PLAYLIST_GROUP", "10"))
# Сообщение о ходе загрузки или плейлиста меняется не чаще раза в столько секунд.
PROGRESS_EVERY = 8
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
# Файлы больше 50 МБ — по MTProto под токеном бота (uploader.py).
uploader = Uploader(TOKEN)
# Чаты, где сейчас идёт плейлист: второй ждёт конца первого.
playlists: set[int] = set()
recent: dict[int, deque[float]] = defaultdict(deque)
warned: dict[int, float] = {}
# Повторную ссылку отдаём по file_id (или копией большого файла) без нового скачивания; ключ — ссылка или «spotify:track:ID».
cache: OrderedDict[str, list[tuple]] = OrderedDict()
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


def remember(key: str, refs: list[tuple]) -> None:
    """Что ушло по ссылке: ("video"|"audio"|"photo", file_id) или ("copy", chat_id, message_id) — файл больше 50 МБ."""
    cache[key] = refs
    cache.move_to_end(key)
    while len(cache) > CACHE_SIZE:
        cache.popitem(last=False)


@dp.message(F.text | F.caption)
async def on_message(message: Message, bot: Bot) -> None:
    entities = (message.entities or []) + (message.caption_entities or [])
    links = find_links(message.text or message.caption, [e.url for e in entities if e.url])
    if message.chat.type != ChatType.PRIVATE:
        # In a group a profile is mentioned in talk, not asked for: its posts go only to private.
        links = [u for u in links if not is_profile(u)]
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


# --- отправка ----------------------------------------------------------------


async def obey(make):
    """Telegram просит подождать (FloodWait): ждём сколько сказано, если это не дольше минуты, и пробуем ещё раз — один."""
    try:
        return await make()
    except TelegramRetryAfter as e:
        if e.retry_after > 60:
            raise
        await asyncio.sleep(e.retry_after + 1)
        return await make()


def _reply(message: Message) -> ReplyParameters:
    return ReplyParameters(message_id=message.message_id, allow_sending_without_reply=True)


def _size(path: Path) -> str:
    size = path.stat().st_size
    return f"{size / 2**30:.2f} ГБ".replace(".", ",") if size >= 2**30 else f"{size / 2**20:.0f} МБ"


def _video_thumb(path: Path) -> Path | None:
    """Кадр для превью большого видео: по MTProto Telegram сам его не делает."""
    thumb = path.with_suffix(".thumb.jpg")
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-ss", "1", "-i", str(path), "-frames:v", "1", "-vf", "scale=320:-2", "-q:v", "5", str(thumb)],
            capture_output=True,
            timeout=60,
            check=True,
        )
        return thumb if thumb.exists() and thumb.stat().st_size < 200_000 else None
    except (OSError, subprocess.SubprocessError):
        return None


async def send_big(message: Message, file: File, lang: str) -> tuple:
    """Файл больше 50 МБ — по MTProto, с одним сообщением о ходе загрузки, которое потом исчезает."""
    status = await obey(lambda: message.reply(premium("⏫ " + t(lang, "uploading").format(size=_size(file.path), percent=0))))
    last = time.monotonic()

    async def progress(done: int, total: int) -> None:
        nonlocal last
        if time.monotonic() - last < PROGRESS_EVERY or not total:
            return
        last = time.monotonic()
        text = premium("⏫ " + t(lang, "uploading").format(size=_size(file.path), percent=done * 100 // total))
        with suppress(TelegramAPIError):
            await status.edit_text(text)

    thumb = file.thumb or (await asyncio.to_thread(_video_thumb, file.path) if file.kind == "video" else None)
    try:
        sent = await uploader.send(
            message.chat.id,
            message.message_id,
            file.path,
            file.kind,
            caption,
            title=file.title,
            performer=file.performer,
            duration=file.duration,
            width=file.width,
            height=file.height,
            thumb=thumb,
            filename=file.filename,
            progress=progress,
        )
    finally:
        with suppress(TelegramAPIError):
            await status.delete()
    return ("copy", message.chat.id, sent)


async def send_one(message: Message, file: File, lang: str) -> tuple:
    """Один файл: до 50 МБ — через Bot API (file_id в кеш), больше — по MTProto."""
    if file.path.stat().st_size > SMALL_LIMIT and uploader.enabled:
        return await send_big(message, file, lang)
    upload = FSInputFile(file.path, filename=file.filename or file.path.name)
    if file.kind == "video":
        sent = await obey(
            lambda: message.reply_video(
                upload, caption=caption, duration=file.duration, width=file.width, height=file.height, supports_streaming=True
            )
        )
        return ("video", sent.video.file_id if sent.video else None)
    if file.kind == "audio":
        thumb = FSInputFile(file.thumb) if file.thumb else None
        sent = await obey(
            lambda: message.reply_audio(
                upload, caption=caption, title=file.title, performer=file.performer, duration=file.duration, thumbnail=thumb
            )
        )
        return ("audio", sent.audio.file_id if sent.audio else None)
    sent = await obey(lambda: message.reply_photo(upload, caption=caption))
    return ("photo", sent.photo[-1].file_id if sent.photo else None)


def _input(item: File | tuple, with_caption: bool):
    """Элемент альбома: свежий файл или file_id из кеша."""
    text = caption if with_caption else None
    if isinstance(item, tuple):
        what, media = item
    else:
        what, media = item.kind, FSInputFile(item.path, filename=item.filename or item.path.name)
    if what == "photo":
        return InputMediaPhoto(media=media, caption=text)
    if what == "video":
        extra = {} if isinstance(item, tuple) else {"duration": item.duration, "width": item.width, "height": item.height}
        return InputMediaVideo(media=media, caption=text, supports_streaming=True, **extra)
    extra = {} if isinstance(item, tuple) else {"title": item.title, "performer": item.performer, "duration": item.duration}
    if not isinstance(item, tuple) and item.thumb:
        extra["thumbnail"] = FSInputFile(item.thumb)
    return InputMediaAudio(media=media, caption=text, **extra)


def _ref(sent: Message) -> tuple:
    if sent.video:
        return ("video", sent.video.file_id)
    if sent.audio:
        return ("audio", sent.audio.file_id)
    if sent.photo:
        return ("photo", sent.photo[-1].file_id)
    return ("copy", sent.chat.id, sent.message_id)


async def send_ref(message: Message, ref: tuple) -> tuple:
    """Один файл из кеша: file_id отправляется заново, большой файл — копией уже отправленного сообщения."""
    if ref[0] == "copy":
        sent = await obey(
            lambda: message.bot.copy_message(
                message.chat.id, ref[1], ref[2], caption=caption, reply_parameters=_reply(message),
                message_thread_id=message.message_thread_id,
            )
        )  # fmt: skip
        return ("copy", message.chat.id, sent.message_id)
    send = getattr(message, f"reply_{ref[0]}")
    await obey(lambda: send(ref[1], caption=caption))
    return ref


async def send_many(message: Message, items: list[File | tuple], lang: str) -> list[tuple]:
    """Файлы и ссылки кеша альбомами по 10 (фото с видео вместе, звук отдельно); большие и копии — по одному."""
    refs: list[tuple] = []
    group: list[File | tuple] = []

    def kind_of(item: File | tuple) -> str:
        return item[0] if isinstance(item, tuple) else item.kind

    async def flush() -> None:
        if len(group) == 1:
            item = group[0]
            refs.append(await send_one(message, item, lang) if isinstance(item, File) else await send_ref(message, item))
        elif group:
            media = [_input(item, i == 0) for i, item in enumerate(group)]
            sent = await obey(lambda: message.reply_media_group(media))
            refs.extend(_ref(s) for s in sent)
        group.clear()

    for item in items:
        alone = kind_of(item) == "copy" or (isinstance(item, File) and item.path.stat().st_size > SMALL_LIMIT)
        if alone or (group and (kind_of(item) == "audio") != (kind_of(group[0]) == "audio")):
            await flush()
        if alone:
            refs.append(await send_one(message, item, lang) if isinstance(item, File) else await send_ref(message, item))
            continue
        group.append(item)
        if len(group) == 10:
            await flush()
    await flush()
    return refs


async def resend(message: Message, refs: list[tuple]) -> None:
    await send_many(message, refs, lang_of(message.chat.id, message.from_user))


# --- ссылка ------------------------------------------------------------------


async def handle(message: Message, bot: Bot, url: str, attempt: str | None = None) -> None:
    if url in cache:
        stats.hit("result", "cached")
        await resend(message, cache[url])
        stats.finished(attempt, "ok", detail="cached")
        return

    lang = lang_of(message.chat.id, message.from_user)
    async with slots, ChatActionSender.upload_video(bot=bot, chat_id=message.chat.id, message_thread_id=message.message_thread_id):
        stats.started(attempt)
        with tempfile.TemporaryDirectory(prefix="savebot-") as tmp:
            try:
                result = await asyncio.to_thread(download, url, Path(tmp), COOKIES, uploader.limit)
            except DownloadError as e:
                stats.hit("result", "fail")
                stats.finished(attempt, "fail", e.why, e.code)
                await message.reply(premium("❌ " + t(lang, str(e))))
                return
            if isinstance(result, Playlist):
                await deliver_playlist(message, result, Path(tmp), lang, attempt)
                return
            media = result

            refs: list[tuple] = []
            if media.gallery:
                refs += await send_many(message, list(media.gallery), lang)
                stats.hit("result", "gallery")
                stats.finished(attempt, "ok", detail="gallery")
            if media.video:
                file = File(media.video, "video", duration=media.duration, width=media.width, height=media.height, filename="video.mp4")
                refs.append(await send_one(message, file, lang))
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
                name = media.audio_name or f"{media.title}{media.audio.suffix}"
                file = File(media.audio, "audio", media.title, media.performer, media.duration, thumb=media.thumb, filename=name)
                refs.append(await send_one(message, file, lang))
                stats.hit("result", "audio")
                stats.finished(attempt, "ok", detail="audio")

            refs = [r for r in refs if r and r[-1]]
            if refs:
                remember(url, refs)
            # Nothing was sent: the video was too big and there was no track to send instead.
            stats.finished(attempt, "fail", "too_big", "no_file")


async def deliver_playlist(message: Message, playlist: Playlist, workdir: Path, lang: str, attempt: str | None) -> None:
    """Альбом, плейлист или топ исполнителя: треки качаются по одному и уходят альбомами по 10; одно сообщение о ходе."""
    private = message.chat.type == ChatType.PRIVATE
    cap = PLAYLIST_PRIVATE if private else PLAYLIST_GROUP
    ids = playlist.ids[:cap]
    if message.chat.id in playlists:
        await message.reply(premium("⏳ " + t(lang, "playlist_busy")))
        stats.finished(attempt, "fail", "other", "busy")
        return
    playlists.add(message.chat.id)
    title = html.escape(playlist.title)
    status = await obey(lambda: message.reply(premium("🎵 " + t(lang, "playlist").format(title=title, done=0, total=len(ids)))))
    last = time.monotonic()
    sent = missed = 0
    pending: list[tuple[str, File | tuple]] = []

    async def flush() -> None:
        nonlocal sent
        if not pending:
            return
        refs = await send_many(message, [item for _, item in pending], lang)
        for (track_id, _), ref in zip(pending, refs, strict=False):
            if ref and ref[-1]:
                remember(f"spotify:track:{track_id}", [ref])
        sent += len(pending)
        for track_id, item in pending:
            if isinstance(item, File):
                shutil.rmtree(workdir / track_id, ignore_errors=True)
        pending.clear()

    try:
        for i, track_id in enumerate(ids, 1):
            cached = cache.get(f"spotify:track:{track_id}")
            if cached:
                pending.append((track_id, cached[0]))
            else:
                try:
                    file = await asyncio.to_thread(spotify_track, track_id, workdir, COOKIES, uploader.limit)
                    pending.append((track_id, file))
                except DownloadError:
                    missed += 1
            if len(pending) == 10:
                await flush()
            if time.monotonic() - last >= PROGRESS_EVERY:
                last = time.monotonic()
                with suppress(TelegramAPIError):
                    await status.edit_text(premium("🎵 " + t(lang, "playlist").format(title=title, done=i, total=len(ids))))
        await flush()
    finally:
        playlists.discard(message.chat.id)

    text = "✅ " + t(lang, "playlist_done").format(title=title, sent=sent, total=len(ids))
    if missed:
        text += "\n" + t(lang, "playlist_missed").format(n=missed)
    if len(playlist.ids) > len(ids):
        text += "\n" + t(lang, "playlist_cut_private" if private else "playlist_cut_group").format(n=len(ids))
    with suppress(TelegramAPIError):
        await status.edit_text(premium(text))
    if sent:
        stats.hit("result", "playlist")
        stats.finished(attempt, "ok", detail="playlist")
    else:
        stats.hit("result", "fail")
        stats.finished(attempt, "fail", "unavailable", "notfound")


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
    downloader.setup(COOKIES)
    await uploader.start()
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
        await uploader.stop()


if __name__ == "__main__":
    asyncio.run(main())
