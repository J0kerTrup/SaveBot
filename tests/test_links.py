"""Ссылки, подбор записи для Spotify и отправка альбомами — без сети."""

import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

os.environ.setdefault("BOT_TOKEN", "1:test")

import bot
import downloader
import instagram
import spotify
from downloader import File


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://www.instagram.com/p/DgKsi15RjRh/", ("post", "DgKsi15RjRh")),
        ("https://www.instagram.com/reel/DgKsi15RjRh/?igsh=x", ("post", "DgKsi15RjRh")),
        ("https://www.instagram.com/nasa/p/DgKsi15RjRh/", ("post", "DgKsi15RjRh")),
        ("https://www.instagram.com/stories/nasa/3712345678901234567/", ("story", "nasa/3712345678901234567")),
        ("https://www.instagram.com/stories/nasa/", ("stories", "nasa")),
        ("https://www.instagram.com/stories/highlights/17912345678901234/", ("highlight", "17912345678901234")),
        ("https://www.instagram.com/s/aGlnaGxpZ2h0OjE3OTEyMzQ1Njc4OTAxMjM0?story_media_id=1", ("highlight", "17912345678901234")),
        ("https://www.instagram.com/NASA/", ("profile", "nasa")),
        ("https://www.instagram.com/reels/audio/608057181693092", ("audio", "")),
        ("https://www.instagram.com/explore/", None),
        ("https://www.instagram.com/accounts/login/", None),
    ],
)
def test_instagram_links(url, expected):
    assert instagram.target(url) == expected


def test_which_links_the_bot_takes():
    text = (
        "смотри https://youtube.com/@channel и https://open.spotify.com/album/4aawyAB9vmqN3uQ7FjRGTy?si=1 "
        "https://open.spotify.com/episode/abcdefghij12 https://www.tiktok.com/@a/photo/123 https://www.instagram.com/explore/"
    )
    assert downloader.find_links(text) == [
        "https://open.spotify.com/album/4aawyAB9vmqN3uQ7FjRGTy?si=1",
        "https://www.tiktok.com/@a/photo/123",
    ]
    assert downloader.is_profile("https://www.instagram.com/nasa/") and not downloader.is_profile("https://www.instagram.com/p/x/")


def test_a_recording_is_chosen_by_name_artist_and_length():
    want = spotify.Track("id", "Never Gonna Give You Up", ["Rick Astley"], duration=214)
    right = spotify._score(want, "Never Gonna Give You Up", ["Rick Astley"], 214)
    cover = spotify._score(want, "Never Gonna Give You Up (Cover)", ["Someone"], 214)
    longer = spotify._score(want, "Never Gonna Give You Up", ["Rick Astley"], 260)
    live = spotify._score(want, "Never Gonna Give You Up (Live)", ["Rick Astley"], 216)
    assert right > 0.9 and cover == 0 and longer == 0 and live == 0


def test_artists_of_a_track_page(monkeypatch):
    page = (
        '<meta property="og:title" content="Global Warming (feat. Sensato)"/>'
        '<meta property="og:description" content="Pitbull, Sensato · Global Warming · Song · 2012"/>'
        '<meta name="music:musician_description" content="Pitbull, Sensato"/>'
        '<meta name="music:musician" content="https://open.spotify.com/artist/1"/>'
        '<meta name="music:musician" content="https://open.spotify.com/artist/2"/>'
        '<meta name="music:album:track" content="1"/><meta name="music:duration" content="85"/>'
        '<meta name="music:release_date" content="2012-11-16"/>'
    )
    monkeypatch.setattr(spotify, "_page", lambda url: (url, page))
    track = spotify.track("x")
    assert track.artists == ["Pitbull", "Sensato"] and track.album == "Global Warming" and track.number == 1 and track.duration == 85
    solo = page.replace('<meta name="music:musician" content="https://open.spotify.com/artist/2"/>', "").replace(
        "Pitbull, Sensato", "Tyler, The Creator"
    )
    monkeypatch.setattr(spotify, "_page", lambda url: (url, solo))
    assert spotify.track("x").artists == ["Tyler, The Creator"]


def message():
    def group(media):
        return [SimpleNamespace(video=None, audio=None, photo=[SimpleNamespace(file_id=f"p{i}")]) for i, _ in enumerate(media)]

    return SimpleNamespace(
        chat=SimpleNamespace(id=5, type="private"),
        message_id=7,
        message_thread_id=None,
        from_user=SimpleNamespace(language_code="ru"),
        reply_media_group=AsyncMock(side_effect=group),
        reply_photo=AsyncMock(return_value=SimpleNamespace(photo=[SimpleNamespace(file_id="one")])),
        reply_audio=AsyncMock(return_value=SimpleNamespace(audio=SimpleNamespace(file_id="a"))),
    )


async def test_a_gallery_goes_in_albums_of_ten_and_audio_apart(tmp_path):
    files = []
    for i in range(12):
        path = tmp_path / f"{i}.jpg"
        path.write_bytes(b"x")
        files.append(File(path, "photo"))
    track = tmp_path / "t.m4a"
    track.write_bytes(b"x")
    files.append(File(track, "audio", "t"))
    sent = message()
    refs = await bot.send_many(sent, files, "ru")
    assert [len(c.args[0]) for c in sent.reply_media_group.call_args_list] == [10, 2]
    sent.reply_audio.assert_awaited_once()
    assert len(refs) == 13 and refs[-1] == ("audio", "a")


async def test_a_big_file_goes_by_mtproto_and_comes_back_as_a_copy(tmp_path, monkeypatch):
    big = tmp_path / "v.mp4"
    with big.open("wb") as f:
        f.truncate(bot.SMALL_LIMIT + 1)
    monkeypatch.setattr(bot.uploader, "client", object())
    monkeypatch.setattr(bot.uploader, "send", AsyncMock(return_value=99))
    status = SimpleNamespace(edit_text=AsyncMock(), delete=AsyncMock())
    sent = message()
    sent.reply = AsyncMock(return_value=status)
    ref = await bot.send_one(sent, File(big, "video", thumb=Path("t.jpg")), "ru")
    assert ref == ("copy", 5, 99)
    status.delete.assert_awaited_once()
    sent.bot = SimpleNamespace(copy_message=AsyncMock(return_value=SimpleNamespace(message_id=100)))
    assert await bot.send_ref(sent, ref) == ("copy", 5, 100)


def test_yt_dlp_gets_a_copy_of_the_cookies(tmp_path):
    session = tmp_path / "cookies.txt"
    session.write_text("# Netscape HTTP Cookie File\n")
    work = tmp_path / "work"
    work.mkdir()
    opts = downloader._options(work, str(session), "b")
    assert opts["cookiefile"] == str(work / "cookies.txt") and (work / "cookies.txt").exists()
