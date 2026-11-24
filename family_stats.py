"""What people do in the bot and by which links they come, for the analytics and the map of Pixel Hub's admin.

Two things are kept, KEEP_DAYS of each. Counters: (hour, what, how many times). Events of private chats: (time, who, what), where
«who» is not a Telegram ID but a keyed hash of it with a key of this database alone: a person can be counted once and their way
through the screens seen, but not named, and not matched with another bot. No name, text, link or file ever gets here: a command is
counted by its name if the bot has it, a button by the first word of its data, a message by its type, /start by its short tag.
Counting never breaks an answer: an error of the database is one line in the log.

The file is the same in every bot of the family written in Python; the hub's collector reads stats.sqlite3 next to the bot's own
database and takes only numbers out of it.
"""

import hashlib
import hmac
import logging
import re
import secrets
import sqlite3
import time
from contextlib import suppress
from contextvars import ContextVar
from pathlib import Path

log = logging.getLogger("family_stats")
KEEP_DAYS = 90
# So many different values of one kind in an hour: /start tags and referrers come from outside and must not fill the disk.
MAX_VALUES = 200
LANGS = ("ru", "uk", "en", "es", "pt", "tr")
_TAG = re.compile(r"[a-z][a-z0-9_-]{0,31}")
_WORD = re.compile(r"[a-z_]{1,24}")
_SCHEMA = """
CREATE TABLE IF NOT EXISTS family_stats (hour INTEGER NOT NULL, kind TEXT NOT NULL, value TEXT NOT NULL, n INTEGER NOT NULL,
    PRIMARY KEY (hour, kind, value)) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS family_stats_meta (id INTEGER PRIMARY KEY CHECK (id = 1), since INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS family_key (id INTEGER PRIMARY KEY CHECK (id = 1), key BLOB NOT NULL, since INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS people (who INTEGER PRIMARY KEY, first_at INTEGER NOT NULL, last_at INTEGER NOT NULL, lang TEXT NOT NULL,
    source TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, at INTEGER NOT NULL, who INTEGER NOT NULL, what TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS events_at ON events (at);
"""
# Whose update is being answered: an explicit hit() of a handler belongs to them. None in groups and outside of updates.
_who: ContextVar[int | None] = ContextVar("family_stats_who", default=None)


def start_tag(arg: str) -> str:
    """The argument of /start → «organic» without one, its tag, or «unknown». A tag starts with a letter: a bare number could be
    somebody's ID and is never kept. «ref_…» is an invitation: whose, is not kept either."""
    arg = arg.strip().lower()
    if not arg:
        return "organic"
    if arg.startswith(("ref_", "r_")):
        return "ref"
    return arg if _TAG.fullmatch(arg) and not any(len(run) > 5 for run in re.findall(r"\d+", arg)) else "unknown"


class Stats:
    def __init__(self, path: str | Path, commands: tuple[str, ...] = (), press=None):
        """`commands` — the names of the bot's commands; `press` — the data of a button → its name, where the first word is not it."""
        self.commands, self.press = frozenset(commands), press or (lambda data: data.partition(":")[0])
        self._swept = 0
        self._key = b""
        self.db: sqlite3.Connection | None = None
        try:
            if str(path) != ":memory:":
                Path(path).parent.mkdir(parents=True, exist_ok=True)
            self.db = sqlite3.connect(path, timeout=1)
            self.db.executescript(_SCHEMA)
            now = int(time.time())
            with self.db:
                self.db.execute("INSERT OR IGNORE INTO family_stats_meta VALUES (1, ?)", (now,))
                self.db.execute("INSERT OR IGNORE INTO family_key VALUES (1, ?, ?)", (secrets.token_bytes(32), now))
            self._key = self.db.execute("SELECT key FROM family_key").fetchone()[0]
        except (OSError, sqlite3.Error) as error:
            self.db = None
            log.warning("Счётчики выключены: %s", type(error).__name__)

    def pseudonym(self, user_id: int) -> int:
        digest = hmac.new(self._key, str(user_id).encode(), hashlib.sha256).digest()
        return int.from_bytes(digest[:8], "big") >> 1

    def hit(self, kind: str, value: str, now: float | None = None, times: int = 1):
        if self.db is None or times < 1:
            return
        at = int(time.time() if now is None else now)
        hour, who = at // 3600, _who.get()
        try:
            with self.db:
                known = self.db.execute("SELECT 1 FROM family_stats WHERE (hour, kind, value) = (?, ?, ?)", (hour, kind, value))
                if known.fetchone() is None:
                    count = self.db.execute("SELECT COUNT(*) FROM family_stats WHERE hour = ? AND kind = ?", (hour, kind))
                    if count.fetchone()[0] >= MAX_VALUES:
                        value = "other"
                self.db.execute(
                    "INSERT INTO family_stats VALUES (?, ?, ?, ?) ON CONFLICT (hour, kind, value) DO UPDATE SET n = n + excluded.n",
                    (hour, kind, value, times),
                )
                if who is not None and kind != "start":
                    self.db.execute("INSERT INTO events (at, who, what) VALUES (?, ?, ?)", (at, who, f"{kind}:{value}"))
                if hour - self._swept >= 24:
                    self._swept = hour
                    old = at - KEEP_DAYS * 86_400
                    self.db.execute("DELETE FROM family_stats WHERE hour < ?", (hour - KEEP_DAYS * 24,))
                    self.db.execute("DELETE FROM events WHERE at < ?", (old,))
                    self.db.execute("DELETE FROM people WHERE last_at < ?", (old,))
        except sqlite3.Error as error:
            log.warning("Счётчик не записан: %s", type(error).__name__)

    def visit(self, who: int, lang: str | None, source: str, now: float | None = None):
        """A person in private: the day of the first visit and where they came from then, the day of the last one."""
        if self.db is None:
            return
        at, code = int(time.time() if now is None else now), (lang or "").lower()[:2]
        with suppress(sqlite3.Error), self.db:
            self.db.execute(
                "INSERT INTO people VALUES (?, ?, ?, ?, ?)"
                " ON CONFLICT (who) DO UPDATE SET last_at = excluded.last_at, lang = excluded.lang",
                (who, at, at, code if code in LANGS else "other", source),
            )

    def message(self, text: str | None, content_type: str) -> str:
        """A message in private: a command by its name, anything else by its type alone. The tag of /start, «direct» without one."""
        if not (text and text.startswith("/")):
            self.hit("message", str(getattr(content_type, "value", content_type)))
            return "direct"
        head, _, arg = text[1:].partition(" ")
        name = head.partition("@")[0].lower()
        self.hit("command", name if name in self.commands else "other")
        if name != "start":
            return "direct"
        tag = start_tag(arg)
        self.hit("start", tag)
        return tag

    def button(self, data: str | None):
        name = self.press(data or "")
        self.hit("press", name if _WORD.fullmatch(name) else "other")

    async def middleware(self, handler, event, data):
        """An outer middleware of aiogram for messages and buttons; in groups only the buttons are counted, and nobody's."""
        is_message = hasattr(event, "content_type")
        chat = event.chat if is_message else getattr(getattr(event, "message", None), "chat", None)
        user = event.from_user
        private = chat is not None and chat.type == "private"
        token = _who.set(self.pseudonym(user.id) if private and user is not None and not user.is_bot else None)
        try:
            source = "direct"
            if not is_message:
                self.button(event.data)
            elif private:
                source = self.message(event.text, event.content_type)
            if (who := _who.get()) is not None:
                self.visit(who, user.language_code, source)
            return await handler(event, data)
        finally:
            _who.reset(token)
