"""Counters for the map of Pixel Hub's admin: what people do in the bot and by which links they come, in numbers only.

A row is (hour, what, how many times). No Telegram ID, no name, no text, no link and no file ever gets here: a command is counted by
its name if the bot has it, a button by the first word of its data, a message by its type, /start by its short tag. Rows live
KEEP_DAYS. Counting never breaks an answer: an error of the database is one line in the log.

The file is the same in every bot of the family (SaveBot, CircleBot, StickerBot, ParserPixel); the hub's collector reads
stats.sqlite3 next to the bot's own database.
"""

import logging
import re
import sqlite3
import time
from pathlib import Path

log = logging.getLogger("family_stats")
KEEP_DAYS = 90
# So many different values of one kind in an hour: /start tags and referrers come from outside and must not fill the disk.
MAX_VALUES = 200
_TAG = re.compile(r"[a-z][a-z0-9_-]{0,31}")
_WORD = re.compile(r"[a-z_]{1,16}")
_SCHEMA = """
CREATE TABLE IF NOT EXISTS family_stats (hour INTEGER NOT NULL, kind TEXT NOT NULL, value TEXT NOT NULL, n INTEGER NOT NULL,
    PRIMARY KEY (hour, kind, value)) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS family_stats_meta (id INTEGER PRIMARY KEY CHECK (id = 1), since INTEGER NOT NULL);
"""


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
        self.db: sqlite3.Connection | None = None
        try:
            if str(path) != ":memory:":
                Path(path).parent.mkdir(parents=True, exist_ok=True)
            self.db = sqlite3.connect(path, timeout=1)
            self.db.executescript(_SCHEMA)
            with self.db:
                self.db.execute("INSERT OR IGNORE INTO family_stats_meta VALUES (1, ?)", (int(time.time()),))
        except (OSError, sqlite3.Error) as error:
            self.db = None
            log.warning("Счётчики выключены: %s", type(error).__name__)

    def hit(self, kind: str, value: str, now: float | None = None):
        if self.db is None:
            return
        hour = int(time.time() if now is None else now) // 3600
        try:
            with self.db:
                known = self.db.execute("SELECT 1 FROM family_stats WHERE (hour, kind, value) = (?, ?, ?)", (hour, kind, value))
                if known.fetchone() is None:
                    count = self.db.execute("SELECT COUNT(*) FROM family_stats WHERE hour = ? AND kind = ?", (hour, kind))
                    if count.fetchone()[0] >= MAX_VALUES:
                        value = "other"
                self.db.execute(
                    "INSERT INTO family_stats VALUES (?, ?, ?, 1) ON CONFLICT (hour, kind, value) DO UPDATE SET n = n + 1",
                    (hour, kind, value),
                )
                if hour - self._swept >= 24:
                    self._swept = hour
                    self.db.execute("DELETE FROM family_stats WHERE hour < ?", (hour - KEEP_DAYS * 24,))
        except sqlite3.Error as error:
            log.warning("Счётчик не записан: %s", type(error).__name__)

    def message(self, text: str | None, content_type: str):
        """A message in private: a command by its name, anything else by its type alone."""
        if text and text.startswith("/"):
            head, _, arg = text[1:].partition(" ")
            name = head.partition("@")[0].lower()
            self.hit("command", name if name in self.commands else "other")
            if name == "start":
                self.hit("start", start_tag(arg))
        else:
            self.hit("message", str(getattr(content_type, "value", content_type)))

    def button(self, data: str | None):
        name = self.press(data or "")
        self.hit("press", name if _WORD.fullmatch(name) else "other")

    async def middleware(self, handler, event, data):
        """An outer middleware of aiogram for messages and buttons; in groups only the buttons are counted."""
        if hasattr(event, "content_type"):
            if event.chat.type == "private":
                self.message(event.text, event.content_type)
        else:
            self.button(event.data)
        return await handler(event, data)
