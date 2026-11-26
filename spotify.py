"""Spotify как в spotdl: треки, альбомы, плейлисты и топ исполнителя — с названием, исполнителями, альбомом, номером, годом
и обложкой в самом файле.

Звук Spotify закрыт DRM, его бот не трогает. Списки треков берутся со встраиваемых страниц open.spotify.com/embed (без ключей
API), сведения о треке — из метатегов его страницы, а запись ищется на YouTube Music по названию, исполнителю и длительности.
"""

import difflib
import html
import json
import logging
import re
import subprocess
import unicodedata
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger("savebot.spotify")

LINK = re.compile(r"https?://open\.spotify\.com/(?:intl-[a-z-]+/)?(track|album|playlist|artist)/([A-Za-z0-9]{10,})", re.IGNORECASE)
# С полным User-Agent браузера Spotify отдаёт страницу без метатегов, с коротким — с ними.
USER_AGENT = "Mozilla/5.0"
# Подпись семьи ботов в названии каждой дорожки: «Название | @HUBPIXELBOT» — в Telegram и в тегах файла (решение владельца).
BRAND = "@HUBPIXELBOT"


def branded(title: str | None) -> str | None:
    if not title or title.endswith(BRAND):
        return title
    return f"{title} | {BRAND}"


# Запись дальше этого от длительности трека — другая версия (live, extended, клип с интро).
DURATION_SLACK = 12


class SpotifyError(Exception):
    """Код из i18n: notfound, nomedia, failed."""


@dataclass
class Track:
    id: str
    title: str
    artists: list[str]
    album: str | None = None
    number: int | None = None
    date: str | None = None
    duration: int | None = None
    cover: str | None = None

    @property
    def artist(self) -> str:
        return ", ".join(self.artists)


@dataclass
class Tracklist:
    kind: str  # album, playlist, artist
    title: str
    owner: str | None
    ids: list[str] = field(default_factory=list)
    # (название, исполнители, длительность в секундах) — для списка, из которого человек выбирает треки
    names: list[tuple[str, str, int | None]] = field(default_factory=list)


def _get(url: str, limit: int = 3_000_000) -> tuple[str, bytes]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "en"})
    with urllib.request.urlopen(request, timeout=15) as response:
        return response.geturl(), response.read(limit)


def _page(url: str) -> tuple[str, str]:
    try:
        final, body = _get(url)
    except TimeoutError as e:
        raise SpotifyError("failed") from e
    except OSError as e:
        raise SpotifyError("failed") from e
    return final, body.decode("utf-8", "replace")


def resolve(url: str) -> tuple[str, str]:
    """(track|album|playlist|artist, id); spotify.link ведёт на open.spotify.com — идём по редиректу."""
    m = LINK.match(url)
    if not m:
        final, _ = _page(url)
        m = LINK.match(final)
    if not m:
        raise SpotifyError("nomedia")  # подкаст, эпизод, профиль
    return m.group(1).lower(), m.group(2)


def _metas(page: str) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for name, value in re.findall(r'<meta[^>]+(?:property|name)="([^"]+)"[^>]+content="([^"]*)"', page):
        found.setdefault(name, []).append(html.unescape(value).strip())
    return found


def track(track_id: str) -> Track:
    """Сведения о треке со страницы open.spotify.com/track/ID."""
    _, page = _page(f"https://open.spotify.com/track/{track_id}")
    meta = _metas(page)
    title = (meta.get("og:title") or [None])[0]
    if not title:
        raise SpotifyError("notfound")
    # og:description: «Исполнитель, Ещё один · Альбом · Song · 1987»
    parts = [p.strip() for p in ((meta.get("og:description") or [""])[0]).split("·")]
    # «Pitbull, Sensato» in one tag, with a music:musician link per artist: split it only then — «Tyler, The Creator» is one.
    names = meta.get("music:musician_description") or parts[:1]
    artists = names
    if len(names) == 1 and len(meta.get("music:musician") or []) > 1:
        artists = [a.strip() for a in names[0].split(", ")]
    artists = [a for a in artists if a]
    album = parts[1] if len(parts) >= 4 else None
    number = (meta.get("music:album:track") or [""])[0]
    length = (meta.get("music:duration") or [""])[0]
    return Track(
        id=track_id,
        title=title,
        artists=artists or [],
        album=album,
        number=int(number) if number.isdigit() else None,
        date=((meta.get("music:release_date") or [None])[0] or None),
        duration=int(length) if length.isdigit() else None,
        cover=(meta.get("og:image") or [None])[0],
    )


def tracklist(kind: str, list_id: str) -> Tracklist:
    """Треки альбома, плейлиста (первые 50 — столько отдаёт встраиваемая страница) или топ-10 исполнителя."""
    _, page = _page(f"https://open.spotify.com/embed/{kind}/{list_id}")
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', page, re.DOTALL)
    try:
        entity = json.loads(m.group(1))["props"]["pageProps"]["state"]["data"]["entity"] if m else None
    except (ValueError, KeyError, TypeError):
        entity = None
    if not entity:
        raise SpotifyError("notfound")
    tracks = [t for t in entity.get("trackList") or [] if str(t.get("uri", "")).startswith("spotify:track:")]
    if not tracks:
        raise SpotifyError("nomedia")
    ids = [t["uri"].rsplit(":", 1)[-1] for t in tracks]
    names = [
        (t.get("title") or "?", " ".join((t.get("subtitle") or "").split()), round(t["duration"] / 1000) if t.get("duration") else None)
        for t in tracks
    ]
    return Tracklist(kind, entity.get("title") or entity.get("name") or "Spotify", entity.get("subtitle"), ids, names)


# --- поиск записи --------------------------------------------------------------


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).casefold()
    text = re.sub(r"\((?:feat|ft|with)\.?[^)]*\)|\[(?:feat|ft)\.?[^\]]*\]", " ", text)
    text = re.sub(r"\b(?:official|video|audio|lyrics?|music|hd|hq|4k|mv|visualizer|remaster(?:ed)?(?: \d{4})?)\b", " ", text)
    return " ".join(re.sub(r"[^\w]+", " ", text).split())


def _score(want: Track, title: str, artists: list[str], duration: int | None) -> float:
    """0…1: похоже ли название, есть ли исполнитель, совпадает ли длительность. Как в spotdl, проще."""
    if want.duration and duration and abs(duration - want.duration) > max(DURATION_SLACK, want.duration * 0.05):
        return 0.0
    name = difflib.SequenceMatcher(None, _norm(want.title), _norm(title)).ratio()
    theirs = _norm(" ".join(artists) + " " + title)
    artist = max((1.0 if _norm(a) and _norm(a) in theirs else 0.0 for a in want.artists), default=0.5)
    timing = 1.0 if not (want.duration and duration) else 1 - abs(duration - want.duration) / max(DURATION_SLACK, 1) * 0.5
    # A live, remix, cover or karaoke the track itself does not name is another recording.
    for word in ("live", "remix", "cover", "karaoke", "instrumental", "sped up", "slowed", "8d", "nightcore"):
        if word in _norm(title) and word not in _norm(want.title):
            return 0.0
    return 0.5 * name + 0.3 * artist + 0.2 * timing


_ytmusic = None


def _music():
    global _ytmusic
    if _ytmusic is None:
        from ytmusicapi import YTMusic

        _ytmusic = YTMusic()
    return _ytmusic


def match(want: Track) -> str | None:
    """Ссылка на запись: сначала песни YouTube Music (официальные аудио), затем обычный поиск YouTube."""
    query = f"{want.artist} {want.title}".strip()
    best: tuple[float, str] | None = None
    try:
        for kind in ("songs", "videos"):
            for hit in _music().search(query, filter=kind, limit=5)[:5]:
                video = hit.get("videoId")
                if not video:
                    continue
                score = _score(
                    want, hit.get("title") or "", [a.get("name") or "" for a in hit.get("artists") or []], hit.get("duration_seconds")
                )
                if kind == "videos":
                    score -= 0.05  # клип чаще с интро и шумом, чем «песня»
                if score > (best[0] if best else 0.55):
                    best = (score, f"https://music.youtube.com/watch?v={video}")
            if best and best[0] > 0.8:
                break
    except Exception:
        log.warning("YouTube Music не ответил на «%s»", query, exc_info=True)
    if best:
        return best[1]

    import yt_dlp

    try:
        with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "extract_flat": "in_playlist", "skip_download": True}) as ydl:
            found = ydl.extract_info(f"ytsearch5:{query}", download=False)
    except yt_dlp.utils.DownloadError:
        return None
    scored = [
        (_score(want, e.get("title") or "", [e.get("channel") or ""], e.get("duration")), e["url"])
        for e in found.get("entries") or []
        if e.get("url")
    ]
    scored = [s for s in scored if s[0] > 0.45]
    return max(scored)[1] if scored else None


# --- файл ----------------------------------------------------------------------


def tag(src: Path, dst_dir: Path, want: Track, cover: Path | None, source: str | None = None) -> Path:
    """Файл с тегами и обложкой внутри: m4a — без перекодирования; другой звук (opus) — в mp3 192 кбит/с."""
    stem = (
        re.sub(r'[\\/:*?"<>|]+', " ", f"{want.artist} - {want.title}" if want.artist else want.title).strip().rstrip(".")[:120].strip()
        or "track"
    )
    copy = src.suffix.lower() in (".m4a", ".mp4", ".aac")
    dst = dst_dir / f"{stem}.{'m4a' if copy else 'mp3'}"
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", str(src)]
    if cover:
        cmd += ["-i", str(cover), "-map", "0:a:0", "-map", "1:v:0", "-disposition:v:0", "attached_pic"]
    else:
        cmd += ["-map", "0:a:0"]
    cmd += ["-c:a", "copy"] if copy else ["-c:a", "libmp3lame", "-b:a", "192k", "-id3v2_version", "3"]
    if cover:
        cmd += ["-c:v", "mjpeg" if not copy else "copy"]
    tags = {
        "title": branded(want.title),
        "artist": want.artist,
        "album_artist": want.artists[0] if want.artists else None,
        "album": want.album,
        "track": str(want.number) if want.number else None,
        "date": want.date,
        "comment": source or f"https://open.spotify.com/track/{want.id}",
    }
    for key, value in tags.items():
        if value:
            cmd += ["-metadata", f"{key}={value}"]
    if copy:
        cmd += ["-movflags", "+faststart"]
    subprocess.run([*cmd, str(dst)], capture_output=True, timeout=600, check=True)
    return dst
