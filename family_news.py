"""News of a bot of the family, for those who asked for them: the button, the subscription, the sending.

Nobody gets anything without having pressed «🔔 Новости» in this very bot; under every message there is a button that ends it, and
it ends at once. The list of people lives here, in the bot, and never leaves it: Pixel Hub gives the text and the time, the bot sends
it itself and tells the hub only how many got it. Six languages. The file is the same in SaveBot, CircleBot, StickerBot, ParserPixel,
Pixel Hub and Pixel Radio; the anonymous chat has broadcasts of its own.

A message is sent once: what was being sent when the bot stopped is marked «unknown» and not repeated. Telegram's «wait» is obeyed,
a person who blocked the bot is taken off the list, a run of refusals stops the job.
"""

import asyncio
import contextlib
import json
import logging
import os
import sqlite3
import time
from pathlib import Path

import aiohttp
from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, LinkPreviewOptions, Message

log = logging.getLogger("family_news")
HUB = "https://hub.pixelradio.app/api/news-bot"
EVERY = 20  # Seconds between the looks at the hub.
PAUSE = 0.07  # Between two messages: about fourteen a second.
REFUSALS = 20  # So many in a row and the job stops.
KEEP = 30 * 86_400  # How long the list of who got a job is kept after it is over.

BUTTON = {"ru": "🔔 Новости", "uk": "🔔 Новини", "en": "🔔 News", "es": "🔔 Novedades", "pt": "🔔 Novidades", "tr": "🔔 Haberler"}
ABOUT = {
    "ru": "🔔 <b>Новости бота</b>\n\nНе чаще раза в день: что появилось нового. Отписаться можно в любой момент.",
    "uk": "🔔 <b>Новини бота</b>\n\nНе частіше разу на день: що з’явилося нового. Відписатися можна будь-коли.",
    "en": "🔔 <b>News of the bot</b>\n\nAt most once a day: what is new. You can unsubscribe at any time.",
    "es": "🔔 <b>Novedades del bot</b>\n\nComo mucho una vez al día. Puedes darte de baja cuando quieras.",
    "pt": "🔔 <b>Novidades do bot</b>\n\nNo máximo uma vez por dia. Você pode cancelar quando quiser.",
    "tr": "🔔 <b>Bot haberleri</b>\n\nEn fazla günde bir kez. İstediğin zaman aboneliği bırakabilirsin.",
}
ON = {"ru": "✅ Подписаться", "uk": "✅ Підписатися", "en": "✅ Subscribe", "es": "✅ Suscribirme", "pt": "✅ Assinar", "tr": "✅ Abone ol"}
OFF = {"ru": "Отписаться", "uk": "Відписатися", "en": "Unsubscribe", "es": "Darme de baja", "pt": "Cancelar", "tr": "Aboneliği bırak"}
STATE_ON = {
    "ru": "Подписка включена.",
    "uk": "Підписку ввімкнено.",
    "en": "You are subscribed.",
    "es": "Estás suscrito.",
    "pt": "Você está inscrito.",
    "tr": "Abonesin.",
}
STOPPED = {
    "ru": "Больше не пришлю. Вернуть — «Новости» в меню.",
    "uk": "Більше не надішлю. Повернути — «Новини» в меню.",
    "en": "No more news. To get them again: “News” in the menu.",
    "es": "No enviaré más. Para volver: «Novedades» en el menú.",
    "pt": "Não envio mais. Para voltar: “Novidades” no menu.",
    "tr": "Artık göndermem. Geri almak için menüde «Haberler».",
}
PRIVATE = {
    "ru": "Подписка — в личном чате с ботом.",
    "uk": "Підписка — в особистому чаті з ботом.",
    "en": "Subscribe in the private chat with the bot.",
    "es": "Suscríbete en el chat privado con el bot.",
    "pt": "Assine no chat privado com o bot.",
    "tr": "Botla özel sohbette abone ol.",
}
_SCHEMA = """
CREATE TABLE IF NOT EXISTS subscribers (user_id INTEGER PRIMARY KEY, at INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS langs (user_id INTEGER PRIMARY KEY, lang TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS jobs (id INTEGER PRIMARY KEY, data TEXT NOT NULL, state TEXT NOT NULL, at INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS deliveries (job INTEGER NOT NULL, user_id INTEGER NOT NULL, status TEXT NOT NULL, PRIMARY KEY (job, user_id))
    WITHOUT ROWID;
"""


def _in(texts: dict[str, str], lang: str) -> str:
    return texts.get(lang) or texts.get("en") or texts["ru"]


def button(lang: str) -> str:
    return _in(BUTTON, lang)


class Subscribers:
    """Who asked for the news: the bot's own table. A bot that already has such a list gives its own object instead."""

    def __init__(self, db: sqlite3.Connection):
        self.db = db

    def add(self, user_id: int):
        with self.db:
            self.db.execute("INSERT OR IGNORE INTO subscribers VALUES (?, ?)", (user_id, int(time.time())))

    def remove(self, user_id: int):
        with self.db:
            self.db.execute("DELETE FROM subscribers WHERE user_id = ?", (user_id,))

    def has(self, user_id: int) -> bool:
        return self.db.execute("SELECT 1 FROM subscribers WHERE user_id = ?", (user_id,)).fetchone() is not None

    def all(self) -> list[int]:
        return [row[0] for row in self.db.execute("SELECT user_id FROM subscribers")]


class News:
    """`lang_of(user_id)` — the language a person chose, None if none (then the one of their Telegram); `back` — the data of the button
    back to the bot's menu; `premium` — the bot's way to draw its emoji; `exchange(report)` — tells the hub and gets its answer (over
    the net, if not given); `people` — a list of subscribers the bot already has."""

    def __init__(self, slug: str, path: str | Path, lang_of, back: str, *, premium=lambda text: text, exchange=None, people=None):
        self.slug, self.lang_of, self.back, self.premium = slug, lang_of, back, premium
        self.exchange = exchange or self._ask
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, timeout=5)
        self.db.executescript(_SCHEMA)
        with self.db:
            # Sent or not, nobody knows: a second time is worse than none.
            self.db.execute("UPDATE deliveries SET status = 'unknown' WHERE status = 'sending'")
        self.people = people or Subscribers(self.db)
        self._refused = 0
        self._wait = 0.0

    def lang(self, user_id: int) -> str:
        """The language to write to a person in: the chosen one, or that of their Telegram on the day they subscribed."""
        if chosen := self.lang_of(user_id):
            return chosen
        row = self.db.execute("SELECT lang FROM langs WHERE user_id = ?", (user_id,)).fetchone()
        return row[0] if row else "en"

    def _seen(self, user_id: int, code: str | None):
        lang = (code or "").lower()[:2]
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO langs VALUES (?, ?)", (user_id, lang if lang in BUTTON else "en"))

    # -- the subscription -----------------------------------------------------------------------------------------------------------

    def screen(self, user_id: int) -> tuple[str, InlineKeyboardMarkup]:
        lang, on = self.lang(user_id), self.people.has(user_id)
        text = _in(ABOUT, lang) + (f"\n\n<b>{_in(STATE_ON, lang)}</b>" if on else "")
        switch = InlineKeyboardButton(text=_in(OFF if on else ON, lang), callback_data="news:off" if on else "news:on")
        back = InlineKeyboardButton(text="←", callback_data=self.back)
        return self.premium(text), InlineKeyboardMarkup(inline_keyboard=[[switch], [back]])

    def router(self) -> Router:
        router = Router(name="family_news")

        @router.callback_query(F.data.in_({"news", "news:on", "news:off"}))
        async def show(query: CallbackQuery):
            message, user_id = query.message, query.from_user.id
            if not isinstance(message, Message):
                await query.answer()
                return
            if message.chat.type != "private":
                await query.answer(_in(PRIVATE, self.lang(user_id)), show_alert=True)
                return
            self._seen(user_id, query.from_user.language_code)
            if query.data == "news:on":
                self.people.add(user_id)
            elif query.data == "news:off":
                self.people.remove(user_id)
            text, markup = self.screen(user_id)
            try:
                if message.photo:
                    await message.edit_caption(caption=text, reply_markup=markup, parse_mode="HTML")
                else:
                    await message.edit_text(text, reply_markup=markup, parse_mode="HTML")
            except TelegramBadRequest:
                pass  # A second press: the message is already what it should be.
            await query.answer()

        @router.callback_query(F.data == "news:stop")
        async def stop(query: CallbackQuery):
            self.people.remove(query.from_user.id)
            await query.answer(_in(STOPPED, self.lang(query.from_user.id)), show_alert=True)
            if isinstance(query.message, Message):
                with contextlib.suppress(TelegramAPIError):
                    await query.message.edit_reply_markup(reply_markup=None)

        return router

    # -- the hub --------------------------------------------------------------------------------------------------------------------

    async def _ask(self, report: dict) -> dict:
        token = os.getenv("FAMILY_LANG_TOKEN", "").strip()
        if not token:
            return {}
        headers = {"Authorization": f"Bearer {token}", "User-Agent": f"PixelFamily/{self.slug}"}
        timeout = aiohttp.ClientTimeout(total=10)
        async with (
            aiohttp.ClientSession(headers=headers, timeout=timeout) as session,
            session.post(f"{HUB}/{self.slug}", json=report) as answer,
        ):
            if answer.status != 200:
                raise ValueError(f"HTTP {answer.status}")
            return await answer.json(content_type=None)

    def report(self) -> dict:
        jobs = []
        for job, state in self.db.execute("SELECT id, state FROM jobs ORDER BY id DESC LIMIT 10"):
            counts = dict(self.db.execute("SELECT status, COUNT(*) FROM deliveries WHERE job = ? GROUP BY 1", (job,)).fetchall())
            jobs.append(
                {
                    "id": job,
                    "state": state,
                    "total": sum(counts.values()),
                    "sent": counts.get("sent", 0),
                    "blocked": counts.get("blocked", 0),
                    "failed": counts.get("failed", 0) + counts.get("unknown", 0),
                    "left": counts.get("pending", 0),
                }
            )
        return {"subscribers": len(self.people.all()), "jobs": jobs}

    def take(self, job: dict):
        """What the hub wants: a new job is written down with everyone subscribed at this moment; a known one follows the hub's word."""
        with self.db:
            known = self.db.execute("SELECT state FROM jobs WHERE id = ?", (job["id"],)).fetchone()
            if job["state"] == "cancel":
                if known is None or known[0] in ("run", "pause"):
                    self.db.execute("UPDATE deliveries SET status = 'skipped' WHERE job = ? AND status = 'pending'", (job["id"],))
                    data = json.dumps(job)
                    self.db.execute("INSERT OR REPLACE INTO jobs VALUES (?, ?, 'cancelled', ?)", (job["id"], data, int(time.time())))
                return
            if known is None:
                self.db.execute("INSERT INTO jobs VALUES (?, ?, ?, ?)", (job["id"], json.dumps(job), job["state"], int(time.time())))
                self.db.executemany("INSERT INTO deliveries VALUES (?, ?, 'pending')", [(job["id"], user) for user in self.people.all()])
            elif known[0] in ("run", "pause"):
                self.db.execute("UPDATE jobs SET state = ? WHERE id = ?", (job["state"], job["id"]))

    # -- the sending ----------------------------------------------------------------------------------------------------------------

    def _mark(self, job: int, user_id: int, status: str):
        with self.db:
            self.db.execute("UPDATE deliveries SET status = ? WHERE job = ? AND user_id = ?", (status, job, user_id))

    async def send_one(self, bot) -> bool:
        """The next message of the running job; False — there is none to send now."""
        row = self.db.execute("SELECT id, data FROM jobs WHERE state = 'run' ORDER BY id LIMIT 1").fetchone()
        if row is None or time.monotonic() < self._wait:
            return False
        job, data = row[0], json.loads(row[1])
        found = self.db.execute("SELECT user_id FROM deliveries WHERE job = ? AND status = 'pending' LIMIT 1", (job,)).fetchone()
        if found is None:
            with self.db:
                self.db.execute("UPDATE jobs SET state = 'done' WHERE id = ?", (job,))
                self.db.execute("DELETE FROM deliveries WHERE job IN (SELECT id FROM jobs WHERE at < ?)", (int(time.time()) - KEEP,))
                self.db.execute("DELETE FROM jobs WHERE at < ?", (int(time.time()) - KEEP,))
            return False
        user_id = found[0]
        if not self.people.has(user_id):  # Unsubscribed while waiting.
            self._mark(job, user_id, "skipped")
            return True
        lang = self.lang(user_id)
        rows = []
        if data.get("url") and data.get("buttons"):
            rows.append([InlineKeyboardButton(text=_in(data["buttons"], lang), url=data["url"])])
        rows.append([InlineKeyboardButton(text="🔕 " + _in(OFF, lang), callback_data="news:stop")])
        self._mark(job, user_id, "sending")
        try:
            await bot.send_message(
                user_id,
                _in(data["texts"], lang),
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
                link_preview_options=LinkPreviewOptions(is_disabled=True),
            )
        except TelegramRetryAfter as error:
            self._mark(job, user_id, "pending")
            self._wait = time.monotonic() + error.retry_after + 1
            log.warning("Новости: Telegram просит подождать %s с", error.retry_after)
            return False
        except TelegramForbiddenError:
            self.people.remove(user_id)
            self._mark(job, user_id, "blocked")
        except TelegramAPIError as error:
            self._mark(job, user_id, "failed")
            self._refused += 1
            log.warning("Новости: не отправлено (%s)", type(error).__name__)
            if self._refused >= REFUSALS:
                self._refused = 0
                with self.db:
                    self.db.execute("UPDATE jobs SET state = 'stopped' WHERE id = ?", (job,))
                return False
            return True
        else:
            self._mark(job, user_id, "sent")
        self._refused = 0
        return True

    async def run(self, bot):
        """Without end: looks at the hub, sends what it asked for."""
        looked = 0.0
        while True:
            try:
                if time.monotonic() - looked >= EVERY:
                    looked = time.monotonic()
                    answer = await self.exchange(self.report())
                    if isinstance(answer, dict) and isinstance(answer.get("job"), dict):
                        self.take(answer["job"])
                more = await self.send_one(bot)
            except (aiohttp.ClientError, TimeoutError, ValueError, KeyError, sqlite3.Error) as error:
                log.warning("Новости: %s", type(error).__name__)
                more = False
            await asyncio.sleep(PAUSE if more else 2)
