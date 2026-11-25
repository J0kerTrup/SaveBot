"""What people do in the bot and by which links they come, for the analytics and the map of Pixel Hub's admin.

Two things are kept, KEEP_DAYS of each. Counters: (hour, what, how many times). Events: (time, who, what, in which chat), where
«who» is not a Telegram ID but a keyed hash of it with a key of this database alone: a person can be counted once and their way
through the screens seen, but not named, and not matched with another bot. No name, text, link or file ever gets here: a command is
counted by its name if the bot has it, a button by the first word of its data, a message by its type, /start by its short tag.
In a group only what the bot did for somebody is an event: a command, a press, a result. Who just talks there is not seen at all. Of
a group its title is kept, and whether the bot is still in it; its ID is hashed as a person's is.
Counting never breaks an answer: an error of the database is one line in the log.

A try (`attempt`) is one thing the bot is asked to do, followed from the request to its end: accepted → started → done with an outcome
and a reason. It has a random number of its own; the same update delivered again is the same try (a keyed hash of its chat, message
and link, nothing of them is kept). A transition from a card of Pixel Hub (`/start hc_<id>`) is counted as the tag «hub_card», and
its random id is kept for two days, without a person, so that the hub's collector can tell how many card opens ended here.

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
_CODE = re.compile(r"[0-9a-z]{6,13}")
_DIGITS = "0123456789abcdefghijklmnopqrstuvwxyz"
_SCHEMA = """
CREATE TABLE IF NOT EXISTS family_stats (hour INTEGER NOT NULL, kind TEXT NOT NULL, value TEXT NOT NULL, n INTEGER NOT NULL,
    PRIMARY KEY (hour, kind, value)) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS family_stats_meta (id INTEGER PRIMARY KEY CHECK (id = 1), since INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS family_key (id INTEGER PRIMARY KEY CHECK (id = 1), key BLOB NOT NULL, since INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS people (who INTEGER PRIMARY KEY, first_at INTEGER NOT NULL, last_at INTEGER NOT NULL, lang TEXT NOT NULL,
    source TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, at INTEGER NOT NULL, who INTEGER NOT NULL, what TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS events_at ON events (at);
CREATE TABLE IF NOT EXISTS invites (invitee INTEGER PRIMARY KEY, inviter INTEGER NOT NULL, at INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS invites_inviter ON invites (inviter);
CREATE TABLE IF NOT EXISTS chats (chat INTEGER PRIMARY KEY, title TEXT NOT NULL, first_at INTEGER NOT NULL, last_at INTEGER NOT NULL,
    inside INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS family_meta (name TEXT PRIMARY KEY, since INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS attempts (id TEXT PRIMARY KEY, mark INTEGER NOT NULL UNIQUE, who INTEGER, chat INTEGER,
    accepted_ms INTEGER NOT NULL, started_ms INTEGER, done_ms INTEGER, outcome TEXT, reason TEXT, detail TEXT);
CREATE INDEX IF NOT EXISTS attempts_accepted ON attempts (accepted_ms);
CREATE TABLE IF NOT EXISTS handoffs (tid TEXT PRIMARY KEY, at INTEGER NOT NULL);
"""
# The outcomes of a try and why it ended so; the collector counts only these words.
OUTCOMES = ("ok", "fail")
REASONS = ("timeout", "unsupported", "unavailable", "too_big", "download", "processing", "delivery", "other")
_DETAIL = re.compile(r"[a-z_]{1,24}")
# A card of Pixel Hub: the random id of one opening of a card (HubBot catalog), kept HANDOFF_DAYS here.
_HANDOFF = re.compile(r"hc_([a-z2-7]{10})")
HANDOFF_DAYS = 2
# Whose update is being answered: an explicit hit() of a handler belongs to them. None in groups and outside of updates.
_who: ContextVar[int | None] = ContextVar("family_stats_who", default=None)
# In which group it is, if it is one.
_chat: ContextVar[int | None] = ContextVar("family_stats_chat", default=None)
# The group of a message nobody has asked the bot to answer yet.
_title: ContextVar[tuple[int, str | None] | None] = ContextVar("family_stats_title", default=None)
GROUPS = ("group", "supergroup")
TITLE_MAX = 64


def start_tag(arg: str) -> str:
    """The argument of /start → «organic» without one, its tag, or «unknown». A tag starts with a letter: a bare number could be
    somebody's ID and is never kept. «ref_…» is an invitation: whose, is not kept either."""
    arg = arg.strip().lower()
    if not arg:
        return "organic"
    if _HANDOFF.fullmatch(arg):
        return "hub_card"
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
            if "chat" not in {row[1] for row in self.db.execute("PRAGMA table_info(events)")}:
                self.db.execute("ALTER TABLE events ADD COLUMN chat INTEGER")
            now = int(time.time())
            with self.db:
                self.db.execute("INSERT OR IGNORE INTO family_stats_meta VALUES (1, ?)", (now,))
                # Since when tries and card transitions are followed: before it, there are only the counters of results.
                self.db.execute("INSERT OR IGNORE INTO family_meta VALUES ('attempts', ?)", (now,))
                self.db.execute("INSERT OR IGNORE INTO family_meta VALUES ('handoffs', ?)", (now,))
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
        hour, who, chat = at // 3600, _who.get(), _chat.get()
        if chat is not None and (found := _title.get()):
            _title.set(None)
            self.group(*found)
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
                    self.db.execute("INSERT INTO events (at, who, what, chat) VALUES (?, ?, ?, ?)", (at, who, f"{kind}:{value}", chat))
                    if chat is not None:
                        self.db.execute("UPDATE chats SET last_at = ? WHERE chat = ?", (at, chat))
                if hour - self._swept >= 24:
                    self._swept = hour
                    old = at - KEEP_DAYS * 86_400
                    self.db.execute("DELETE FROM family_stats WHERE hour < ?", (hour - KEEP_DAYS * 24,))
                    self.db.execute("DELETE FROM events WHERE at < ?", (old,))
                    self.db.execute("DELETE FROM people WHERE last_at < ?", (old,))
                    self.db.execute("DELETE FROM chats WHERE last_at < ? AND NOT inside", (old,))
                    self.db.execute("DELETE FROM attempts WHERE accepted_ms < ?", (old * 1000,))
                    self.db.execute("DELETE FROM handoffs WHERE at < ?", (at - HANDOFF_DAYS * 86_400,))
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

    def group(self, chat_id: int, title: str | None, inside: bool = True, now: float | None = None) -> int:
        """A group the bot is in, or has just left; its number here."""
        chat, at = self.pseudonym(chat_id), int(time.time() if now is None else now)
        if self.db is not None:
            with suppress(sqlite3.Error), self.db:
                self.db.execute(
                    "INSERT INTO chats VALUES (?, ?, ?, ?, ?)"
                    " ON CONFLICT (chat) DO UPDATE SET title = excluded.title, inside = excluded.inside",
                    (chat, " ".join((title or "").split())[:TITLE_MAX], at, at, int(inside)),
                )
        return chat

    async def membership(self, event):
        """my_chat_member: the bot was added to a group or taken out of it."""
        if event.chat.type in GROUPS:
            status = event.new_chat_member.status
            self.group(event.chat.id, event.chat.title, str(getattr(status, "value", status)) in ("member", "administrator", "restricted"))

    # -- invitations (family_refs.py): who invited whom, by the numbers of this bot, never by Telegram IDs --------------------------

    def invite_code(self, user_id: int) -> str:
        number, code = self.pseudonym(user_id), ""
        while number:
            number, digit = divmod(number, 36)
            code = _DIGITS[digit] + code
        return f"ref_{code}"

    def invited(self, user_id: int) -> int:
        if self.db is None:
            return 0
        with suppress(sqlite3.Error):
            return self.db.execute("SELECT COUNT(*) FROM invites WHERE inviter = ?", (self.pseudonym(user_id),)).fetchone()[0]
        return 0

    def invite(self, arg: str, who: int, now: float | None = None):
        """/start ref_<code> of someone new to the bot: counted once, not for oneself, only from someone the bot knows."""
        code = arg.strip().lower().removeprefix("ref_")
        if self.db is None or not arg.strip().lower().startswith("ref_") or not _CODE.fullmatch(code):
            return
        inviter = int(code, 36)
        with suppress(sqlite3.Error), self.db:
            known = "SELECT 1 FROM people WHERE who = ?"
            if inviter != who and not self.db.execute(known, (who,)).fetchone() and self.db.execute(known, (inviter,)).fetchone():
                at = int(time.time() if now is None else now)
                self.db.execute("INSERT OR IGNORE INTO invites VALUES (?, ?, ?)", (who, inviter, at))

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
        if found := _HANDOFF.fullmatch(arg.strip().lower()):
            self.handoff(found.group(1))
        if (who := _who.get()) is not None:
            self.invite(arg, who)
        return tag

    def handoff(self, tid: str, now: float | None = None):
        """A card of Pixel Hub led here: its id, once, with the time; no person."""
        if self.db is None:
            return
        with suppress(sqlite3.Error), self.db:
            self.db.execute("INSERT OR IGNORE INTO handoffs VALUES (?, ?)", (tid, int(time.time() if now is None else now)))

    # -- tries: a request followed to its end ----------------------------------------------------------------------------------------

    def attempt(self, key: str, now: float | None = None) -> tuple[str | None, str]:
        """A try of `key` (chat, message, link): its id, and «new», «open» (the same update again, not finished) or «done»
        (finished already: do not do it again). None without a database: the bot works on, unfollowed."""
        if self.db is None:
            return None, "new"
        ms = int((time.time() if now is None else now) * 1000)
        mark = int.from_bytes(hmac.new(self._key, b"attempt:" + key.encode(), hashlib.sha256).digest()[:8], "big") >> 1
        try:
            with self.db:
                made = self.db.execute(
                    "INSERT OR IGNORE INTO attempts (id, mark, who, chat, accepted_ms) VALUES (?, ?, ?, ?, ?)",
                    (secrets.token_hex(8), mark, _who.get(), _chat.get(), ms),
                ).rowcount
                id_, outcome = self.db.execute("SELECT id, outcome FROM attempts WHERE mark = ?", (mark,)).fetchone()
        except sqlite3.Error as error:
            log.warning("Попытка не записана: %s", type(error).__name__)
            return None, "new"
        return id_, "new" if made else ("done" if outcome else "open")

    def started(self, id_: str | None, now: float | None = None):
        """The work began (a slot was free): the first time only."""
        if self.db is None or id_ is None:
            return
        ms = int((time.time() if now is None else now) * 1000)
        with suppress(sqlite3.Error), self.db:
            self.db.execute("UPDATE attempts SET started_ms = ? WHERE id = ? AND started_ms IS NULL", (ms, id_))

    def finished(self, id_: str | None, outcome: str, reason: str | None = None, detail: str | None = None, now: float | None = None):
        """The end of a try: the first end stays, a later one (a repeated update) changes nothing."""
        if self.db is None or id_ is None or outcome not in OUTCOMES:
            return
        if outcome == "fail" and reason not in REASONS:
            reason = "other"
        detail = detail if detail and _DETAIL.fullmatch(detail) else None
        ms = int((time.time() if now is None else now) * 1000)
        with suppress(sqlite3.Error), self.db:
            self.db.execute(
                "UPDATE attempts SET started_ms = coalesce(started_ms, ?), done_ms = ?, outcome = ?, reason = ?, detail = ?"
                " WHERE id = ? AND outcome IS NULL",
                (ms, ms, outcome, reason if outcome == "fail" else None, detail, id_),
            )

    def button(self, data: str | None):
        name = self.press(data or "")
        self.hit("press", name if _WORD.fullmatch(name) else "other")

    async def middleware(self, handler, event, data):
        """An outer middleware of aiogram for messages and buttons."""
        is_message = hasattr(event, "content_type")
        chat = event.chat if is_message else getattr(getattr(event, "message", None), "chat", None)
        user, kind = event.from_user, getattr(chat, "type", None)
        private, group = kind == "private", kind in GROUPS
        known = user is not None and not user.is_bot and (private or group)
        who = _who.set(self.pseudonym(user.id) if known else None)
        place = _chat.set(self.pseudonym(chat.id) if group else None)
        title = _title.set(None)
        try:
            command = (
                (event.text or "")[1:].split(" ")[0].partition("@")[0].lower() if is_message and (event.text or "").startswith("/") else ""
            )
            if not is_message:
                if group:
                    self.group(chat.id, chat.title)
                self.button(event.data)
            elif private:
                source = self.message(event.text, event.content_type)
            elif group and command in self.commands:
                self.group(chat.id, chat.title)
                self.hit("command", command)
            elif group:
                # Nothing yet: only if the bot answers it, `hit` makes the row of the group.
                _title.set((chat.id, chat.title))
            if private and known:
                self.visit(_who.get(), user.language_code, source if is_message else "direct")
            return await handler(event, data)
        finally:
            _who.reset(who)
            _chat.reset(place)
            _title.reset(title)
