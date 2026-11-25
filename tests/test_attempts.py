"""Tries of a link: one per link of a message, followed to a file or to a reason, never counted twice."""

import os
import sqlite3
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

os.environ.setdefault("BOT_TOKEN", "1:test")

import bot
import downloader
import family_stats
from downloader import DownloadError, Media
from family_stats import Stats, start_tag


@pytest.fixture
def stats(monkeypatch):
    made = Stats(":memory:")
    monkeypatch.setattr(bot, "stats", made)
    bot.cache.clear()
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE chat_lang (chat_id INTEGER PRIMARY KEY, lang TEXT NOT NULL)")
    monkeypatch.setattr(bot, "db", db, raising=False)
    return made


def rows(stats: Stats) -> list[tuple]:
    return stats.db.execute("SELECT outcome, reason, detail, started_ms IS NOT NULL, done_ms IS NOT NULL FROM attempts").fetchall()


def message(chat=5, message_id=7):
    sent = SimpleNamespace(video=SimpleNamespace(file_id="v"), audio=SimpleNamespace(file_id="a"))
    return SimpleNamespace(
        chat=SimpleNamespace(id=chat, type="private"),
        message_id=message_id,
        message_thread_id=None,
        from_user=SimpleNamespace(language_code="ru"),
        text="https://www.tiktok.com/@a/video/1",
        caption=None,
        entities=None,
        caption_entities=None,
        reply=AsyncMock(),
        reply_video=AsyncMock(return_value=sent),
        reply_audio=AsyncMock(return_value=sent),
        answer=AsyncMock(),
    )


class Sender:
    """ChatActionSender without Telegram."""

    def __init__(self, **_):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return False


@pytest.fixture(autouse=True)
def quiet(monkeypatch):
    monkeypatch.setattr(bot.ChatActionSender, "upload_video", lambda **kw: Sender())
    bot.recent.clear()


def test_the_same_update_again_is_the_same_try():
    stats = Stats(":memory:")
    first, state = stats.attempt("5:7:https://x.test/a", now=100)
    again, state2 = stats.attempt("5:7:https://x.test/a", now=101)
    other, state3 = stats.attempt("5:8:https://x.test/a", now=102)
    assert state == "new" and state2 == "open" and again == first and state3 == "new" and other != first
    assert len(first) == 16 and int(first, 16) >= 0, "a random id"
    stats.finished(first, "ok", detail="video", now=110)
    stats.finished(first, "fail", "download", now=120)
    assert stats.attempt("5:7:https://x.test/a")[1] == "done"
    assert stats.db.execute("SELECT outcome, done_ms FROM attempts WHERE id = ?", (first,)).fetchone() == ("ok", 110_000)
    # The link itself is never kept, only a keyed hash of it.
    assert "x.test" not in str(stats.db.execute("SELECT * FROM attempts").fetchall())


def test_reasons_are_only_known_words():
    stats = Stats(":memory:")
    id_, _ = stats.attempt("k")
    stats.finished(id_, "fail", "Something odd", "Some Text With Spaces")
    assert stats.db.execute("SELECT reason, detail FROM attempts").fetchone() == ("other", None)


async def test_a_file_is_a_success_with_its_times(stats, monkeypatch, tmp_path):
    video = tmp_path / "v.mp4"
    video.write_bytes(b"x")
    monkeypatch.setattr(bot, "download", lambda *a: Media(video, None, "t", None, 3, 1, 1))
    await bot.on_message(message(), None)
    assert rows(stats) == [("ok", None, "video", 1, 1)]
    # The same message delivered again: no second download, no second try.
    again = message()
    await bot.on_message(again, None)
    again.reply_video.assert_not_called()
    assert len(rows(stats)) == 1
    assert stats.db.execute("SELECT SUM(n) FROM family_stats WHERE kind = 'result' AND value = 'link'").fetchone()[0] == 1


async def test_the_same_link_later_is_a_new_try_served_from_the_cache(stats, monkeypatch, tmp_path):
    video = tmp_path / "v.mp4"
    video.write_bytes(b"x")
    monkeypatch.setattr(bot, "download", lambda *a: Media(video, None, "t", None, 3, 1, 1))
    await bot.on_message(message(message_id=1), None)
    await bot.on_message(message(message_id=2), None)
    assert sorted(rows(stats)) == [("ok", None, "cached", 1, 1), ("ok", None, "video", 1, 1)]


@pytest.mark.parametrize(
    ("error", "reason", "detail"),
    [
        (DownloadError("private"), "unavailable", "private"),
        (DownloadError("file_too_big"), "too_big", "file_too_big"),
        (DownloadError("nomedia", "unsupported"), "unsupported", "nomedia"),
        (DownloadError("failed", "timeout"), "timeout", "failed"),
        (DownloadError("failed", "processing"), "processing", "failed"),
        (DownloadError("failed"), "download", "failed"),
        (RuntimeError("?"), "other", "unexpected"),
    ],
)
async def test_failures_have_their_reasons(stats, monkeypatch, error, reason, detail):
    def broken(*_):
        raise error

    monkeypatch.setattr(bot, "download", broken)
    await bot.on_message(message(), None)
    assert rows(stats) == [("fail", reason, detail, 1, 1)]


async def test_a_failed_delivery_is_not_a_file(stats, monkeypatch, tmp_path):
    from aiogram.exceptions import TelegramBadRequest, TelegramNetworkError

    video = tmp_path / "v.mp4"
    video.write_bytes(b"x")
    monkeypatch.setattr(bot, "download", lambda *a: Media(video, None, "t", None, 3, 1, 1))
    sent = message()
    sent.reply_video.side_effect = TelegramBadRequest(method=None, message="file is too big")
    await bot.on_message(sent, None)
    late = message(message_id=8)
    late.reply_video.side_effect = TelegramNetworkError(method=None, message="Request timeout error")
    await bot.on_message(late, None)
    assert sorted(rows(stats)) == [("fail", "delivery", "telegram", 1, 1), ("fail", "timeout", "delivery", 1, 1)]


async def test_nothing_sent_is_a_failure_and_not_cached(stats, monkeypatch):
    monkeypatch.setattr(bot, "download", lambda *a: Media(None, None, "t", None, 3, 1, 1, video_too_big=True))
    await bot.on_message(message(), None)
    assert rows(stats) == [("fail", "too_big", "no_file", 1, 1)] and not bot.cache


async def test_an_open_try_without_an_end_stays_open(stats, monkeypatch):
    """A restart in the middle: the try has no outcome; the collector counts it as «no result» after an hour."""
    id_, _ = stats.attempt("5:7:https://www.tiktok.com/@a/video/1")
    assert rows(stats) == [(None, None, None, 0, 0)] and id_


def test_downloader_says_why(monkeypatch):
    assert downloader._ydl_error(Exception("ERROR: Unsupported URL: https://x")).why == "unsupported"
    assert downloader._ydl_error(Exception("Read timed out")).why == "timeout"
    assert downloader._ydl_error(Exception("Private video. Sign in")).why == "unavailable"
    assert str(downloader._ydl_error(Exception("Unsupported URL"))) == "nomedia", "the person reads the same text as before"

    def finish(error):
        def raise_(*_a, **_k):
            raise error

        return raise_

    for error, why in ((subprocess.TimeoutExpired("ffmpeg", 600), "timeout"), (subprocess.CalledProcessError(1, "ffmpeg"), "processing")):
        monkeypatch.setattr(downloader, "_finish", finish(error))
        with pytest.raises(DownloadError) as caught:
            downloader._processed({}, Path("x"), Path("."))
        assert caught.value.why == why
    monkeypatch.setattr(downloader, "_finish", finish(DownloadError("too_long")))
    with pytest.raises(DownloadError) as caught:
        downloader._processed({}, Path("x"), Path("."))
    assert caught.value.why == "too_big"


def test_a_card_of_the_hub_is_counted_by_its_tag_and_its_id_kept():
    stats = Stats(":memory:")
    assert start_tag("hc_abcdefgh23") == "hub_card" and start_tag("hub") == "hub" and start_tag("hc_short") == "hc_short"
    stats.message("/start hc_abcdefgh23", "text")
    stats.message("/start hc_abcdefgh23", "text")
    assert stats.db.execute("SELECT tid FROM handoffs").fetchall() == [("abcdefgh23",)]
    assert stats.db.execute("SELECT value, n FROM family_stats WHERE kind = 'start'").fetchall() == [("hub_card", 2)]
    old = family_stats.HANDOFF_DAYS * 86_400 + 10
    stats.handoff("zzzzzzzzzz", now=1_000)
    stats._swept = 0
    stats.hit("press", "x", now=1_000 + old)
    assert [row[0] for row in stats.db.execute("SELECT tid FROM handoffs")] == ["abcdefgh23"]
