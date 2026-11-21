"""Скачивание по ссылке: yt-dlp достаёт ролик, ffmpeg вынимает из него звук.

Spotify отдаёт звук только под DRM, его не обходим: со страницы трека берём название, исполнителя, длительность
и обложку, а сам трек ищем на YouTube.
"""

import html
import json
import re
import subprocess
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import yt_dlp

# Ссылки, на которые бот реагирует. Добавить площадку — дописать домен сюда и в kind().
LINK_RE = re.compile(
    r"https?://(?:[a-z0-9-]+\.)*(?:tiktok\.com|instagram\.com|instagr\.am|youtube\.com|youtu\.be|spotify\.com|spotify\.link)/[^\s<>\"']+",
    re.IGNORECASE,
)
# С YouTube — только ролики: ссылка на канал или плейлист не должна запускать скачивание.
YOUTUBE_VIDEO = re.compile(
    r"https?://(?:[a-z0-9-]+\.)*(?:youtu\.be/[\w-]{6,}|youtube\.com/(?:watch\?(?:\S*&)?v=|shorts/|embed/|live/)[\w-]{6,})",
    re.IGNORECASE,
)
SPOTIFY_TRACK = re.compile(r"https?://open\.spotify\.com/(?:intl-[a-z-]+/)?track/[A-Za-z0-9]{10,}", re.IGNORECASE)

# Бот через обычный Bot API отправляет файлы до 50 МБ.
TELEGRAM_LIMIT = 49 * 1024 * 1024
VIDEO_MAX_DURATION = 10 * 60  # длиннее — только звук: видео не влезет в 50 МБ
MAX_DURATION = 60 * 60  # длиннее не влезет и звук

SOCIAL_FORMAT = (
    # H.264 играет во всех клиентах Telegram; формат download у TikTok — с водяным знаком. Нет ролика (фото-пост) — один звук.
    "b[vcodec^=avc][format_id!=download]/b[vcodec^=h264][format_id!=download]/bv*[vcodec^=avc]+ba/b[format_id!=download]/bv*+ba/ba/b*"
)
YOUTUBE_FORMAT = "bv*[height<=720][vcodec^=avc]+ba[ext=m4a]/b[height<=720][vcodec^=avc]/bv*[height<=720]+ba/b[height<=720]/b"
AUDIO_FORMAT = "ba[ext=m4a]/ba/b"
# С полным User-Agent браузера Spotify отдаёт страницу без метатегов, с коротким — с ними.
USER_AGENT = "Mozilla/5.0"


class DownloadError(Exception):
    """Причина отказа: код из i18n (private, nomedia, notfound, failed, too_long)."""


@dataclass
class Media:
    video: Path | None
    audio: Path | None
    title: str
    performer: str | None
    duration: int | None
    width: int | None
    height: int | None
    video_too_big: bool = False
    thumb: Path | None = None


def kind(url: str) -> str | None:
    """youtube, spotify, social (TikTok, Instagram) или None — такую ссылку бот пропускает молча."""
    host = (urlparse(url).hostname or "").lower()
    if host.endswith(("youtube.com", "youtu.be")):
        return "youtube" if YOUTUBE_VIDEO.match(url) else None
    if host.endswith("spotify.com"):
        return "spotify" if SPOTIFY_TRACK.match(url) else None
    if host == "spotify.link":
        return "spotify"
    return "social"


def find_links(text: str | None, extra: list[str] | None = None) -> list[str]:
    """Ссылки на поддерживаемые площадки из текста и скрытых ссылок, без повторов."""
    found = [m.group(0).rstrip(").,!?»") for m in LINK_RE.finditer(text or "")]
    found += [u for u in extra or [] if LINK_RE.fullmatch(u)]
    return [u for u in dict.fromkeys(found) if kind(u)]


# --- yt-dlp ------------------------------------------------------------------


def _options(workdir: Path, cookies: str | None, fmt: str) -> dict:
    opts = {
        "outtmpl": str(workdir / "%(id).60s.%(ext)s"),
        "format": fmt,
        "merge_output_format": "mp4",
        "noplaylist": True,
        "playlist_items": "1",
        "max_filesize": 150 * 1024 * 1024,
        "socket_timeout": 20,
        "retries": 2,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
    }
    if cookies:
        opts["cookiefile"] = cookies
    return opts


def _ydl_error(e: Exception) -> DownloadError:
    msg = str(e).lower()
    if "login" in msg or "private" in msg or "cookies" in msg or "sign in" in msg:
        return DownloadError("private")
    if "unsupported url" in msg or "no video formats" in msg or "unavailable" in msg:
        return DownloadError("nomedia")
    return DownloadError("failed")


def _first(info: dict) -> dict:
    return next(iter(info["entries"]), None) or {} if info.get("entries") else info


def _info(url: str, cookies: str | None) -> dict:
    """Сведения о ролике без скачивания: длительность решает, качать ли видео."""
    try:
        with yt_dlp.YoutubeDL({**_options(Path("."), cookies, "b"), "skip_download": True, "ignore_no_formats_error": True}) as ydl:
            return _first(ydl.extract_info(url, download=False))
    except yt_dlp.utils.DownloadError as e:
        raise _ydl_error(e) from e


def _download(url: str, workdir: Path, cookies: str | None, fmt: str) -> tuple[dict, Path]:
    try:
        with yt_dlp.YoutubeDL(_options(workdir, cookies, fmt)) as ydl:
            info = _first(ydl.extract_info(url, download=True))
    except yt_dlp.utils.DownloadError as e:
        raise _ydl_error(e) from e
    files = [Path(d["filepath"]) for d in info.get("requested_downloads") or [] if d.get("filepath")]
    if not files or not files[0].exists():
        raise DownloadError("failed")
    return info, files[0]


# --- ffmpeg ------------------------------------------------------------------


def _probe(path: Path) -> dict:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height:format=duration", "-of", "json", str(path)],
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
    return json.loads(out.stdout)


def _extract_audio(src: Path, dst: Path, duration: float | None) -> None:
    # Длинный трек сжимаем сильнее, чтобы mp3 влез в 50 МБ: час — около 100 кбит/с.
    kbps = 192 if not duration else max(48, min(192, int(TELEGRAM_LIMIT * 8 * 0.95 / duration / 1000)))
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", str(src), "-vn", "-map", "0:a:0", "-c:a", "libmp3lame", "-b:a", f"{kbps}k", str(dst)],
        capture_output=True,
        timeout=600,
        check=True,
    )


def _short(text: str | None, limit: int = 64) -> str | None:
    if not text:
        return None
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _finish(info: dict, src: Path, workdir: Path, audio_only: bool = False) -> Media:
    probe = _probe(src)
    streams = probe.get("streams", [])
    vstream = None if audio_only else next((s for s in streams if s.get("codec_type") == "video" and s.get("width")), None)
    has_audio = any(s.get("codec_type") == "audio" for s in streams)
    raw = probe.get("format", {}).get("duration") or info.get("duration")
    duration = float(raw) if raw else None

    audio = None
    if has_audio:
        audio = workdir / "audio.mp3"
        _extract_audio(src, audio, duration)
        if audio.stat().st_size > TELEGRAM_LIMIT:
            audio = None

    video = None
    too_big = audio_only
    if vstream:
        if src.stat().st_size <= TELEGRAM_LIMIT:
            video = src
        else:
            too_big = True

    if not video and not audio:
        raise DownloadError("too_long" if has_audio else "nomedia")

    artists = info.get("artists") or []
    uploader = (info.get("uploader") or "").removesuffix(" - Topic") or None
    return Media(
        video=video,
        audio=audio,
        title=_short(info.get("track") or info.get("title") or info.get("description")) or "audio",
        performer=_short(info.get("artist") or (artists[0] if artists else None) or uploader),
        duration=round(duration) if duration else None,
        width=vstream.get("width") if vstream else None,
        height=vstream.get("height") if vstream else None,
        video_too_big=too_big and video is None,
    )


# --- Spotify -----------------------------------------------------------------


def _get(url: str, limit: int = 3_000_000) -> tuple[str, bytes]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "en"})
    with urllib.request.urlopen(request, timeout=15) as response:
        return response.geturl(), response.read(limit)


def _meta(page: str, name: str) -> str | None:
    m = re.search(rf'<meta[^>]+(?:property|name)="{re.escape(name)}"[^>]+content="([^"]*)"', page)
    return html.unescape(m.group(1)).strip() if m else None


def _spotify(url: str, workdir: Path, cookies: str | None) -> Media:
    try:
        final, body = _get(url)
    except OSError as e:
        raise DownloadError("failed") from e
    if not SPOTIFY_TRACK.match(final):
        raise DownloadError("nomedia")  # spotify.link вёл на альбом, плейлист или подкаст
    page = body.decode("utf-8", "replace")
    title = _meta(page, "og:title")
    artist = _meta(page, "music:musician_description") or (_meta(page, "og:description") or "").split(" · ")[0] or None
    length = _meta(page, "music:duration")
    duration = int(length) if length and length.isdigit() else None
    if not title:
        raise DownloadError("notfound")

    query = f"{artist} - {title}" if artist else title
    try:
        with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "extract_flat": "in_playlist", "skip_download": True}) as ydl:
            found = ydl.extract_info(f"ytsearch5:{query}", download=False)
    except yt_dlp.utils.DownloadError as e:
        raise DownloadError("failed") from e
    entries = [e for e in found.get("entries") or [] if e.get("url") and (e.get("duration") or 0) <= MAX_DURATION]
    if not entries:
        raise DownloadError("notfound")
    best = entries[0]
    if duration:
        # Среди первых результатов — самый близкий по длительности: клип с интро и часовая версия проигрывают.
        close = [e for e in entries if e.get("duration") and abs(e["duration"] - duration) <= 15]
        if close:
            best = min(close, key=lambda e: abs(e["duration"] - duration))

    info, src = _download(best["url"], workdir, cookies, AUDIO_FORMAT)
    media = _finish(info, src, workdir, audio_only=True)
    media.video_too_big = False
    media.title = _short(title) or media.title
    media.performer = _short(artist) or media.performer
    media.thumb = _cover(_meta(page, "og:image"), workdir)
    return media


def _cover(url: str | None, workdir: Path) -> Path | None:
    """Обложка для mp3: Telegram берёт JPEG до 320 px и 200 КБ."""
    if not url or not url.startswith("https://"):
        return None
    try:
        _, data = _get(url, 5_000_000)
        raw = workdir / "cover.src"
        raw.write_bytes(data)
        thumb = workdir / "cover.jpg"
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-i", str(raw), "-vf", "scale=320:320", "-q:v", "4", str(thumb)],
            capture_output=True,
            timeout=60,
            check=True,
        )
        return thumb if thumb.stat().st_size < 200_000 else None
    except (OSError, subprocess.SubprocessError):
        return None


# --- вход --------------------------------------------------------------------


def download(url: str, workdir: Path, cookies: str | None = None) -> Media:
    """Синхронно: вызывать через asyncio.to_thread."""
    match kind(url):
        case "spotify":
            return _spotify(url, workdir, cookies)
        case "youtube":
            info = _info(url, cookies)
            if info.get("is_live") or info.get("live_status") in ("is_live", "is_upcoming"):
                raise DownloadError("nomedia")
            duration = info.get("duration") or 0
            if duration > MAX_DURATION:
                raise DownloadError("too_long")
            audio_only = duration > VIDEO_MAX_DURATION
            target = info.get("webpage_url") or url
            info, src = _download(target, workdir, cookies, AUDIO_FORMAT if audio_only else YOUTUBE_FORMAT)
            return _finish(info, src, workdir, audio_only)
        case _:
            info, src = _download(url, workdir, cookies, SOCIAL_FORMAT)
            return _finish(info, src, workdir)
