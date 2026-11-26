"""Скачивание по ссылке: yt-dlp достаёт ролик, ffmpeg вынимает из него звук; Instagram — instaloader (instagram.py),
Spotify — сведения со страниц Spotify и запись с YouTube Music (spotify.py), фото-посты TikTok — слайды и трек.

Spotify отдаёт звук только под DRM, его не обходим. Закрытые профили, платный доступ и DRM бот не обходит.
"""

import json
import re
import shutil
import subprocess
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import yt_dlp

import instagram
import spotify
from instagram import Instagram, InstagramError
from spotify import SpotifyError, Tracklist

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
TIKTOK_PHOTO = re.compile(r"https?://(?:www\.)?tiktok\.com/@([\w.-]+)/photo/(\d+)", re.IGNORECASE)

# Через Bot API бот отправляет файлы до 50 МБ, по MTProto — до 2 ГБ (uploader.py). limit в download() — из uploader.
SMALL_LIMIT = 49 * 1024 * 1024
# С лимитом 50 МБ: длиннее 10 минут — только звук, длиннее часа не влезет и звук.
SMALL_VIDEO_DURATION, SMALL_DURATION = 10 * 60, 60 * 60
# С MTProto: видео до 3 часов (720p — около 1,5 ГБ), звук до 5 часов.
BIG_VIDEO_DURATION, BIG_DURATION = 3 * 60 * 60, 5 * 60 * 60
# С лимитом 50 МБ yt-dlp всё же качает до 150 МБ: из большого ролика достаётся звук.
SMALL_DOWNLOAD = 150 * 1024 * 1024
# Свободное место, которое скачивание не трогает: автодеплою нужно 2 ГБ, логам и базам — ещё немного.
DISK_RESERVE = 2_500 * 1024 * 1024
GALLERY_ITEM_MAX = 200 * 1024 * 1024  # один файл из поста или сторис
PLAYLIST_MAX = 50  # треков в списке плейлиста

SOCIAL_FORMAT = (
    # H.264 играет во всех клиентах Telegram; формат download у TikTok — с водяным знаком. Нет ролика (фото-пост) — один звук.
    "b[vcodec^=avc][format_id!=download]/b[vcodec^=h264][format_id!=download]/bv*[vcodec^=avc]+ba/b[format_id!=download]/bv*+ba/ba/b*"
)
AUDIO_FORMAT = "ba[ext=m4a]/ba/b"
USER_AGENT = "Mozilla/5.0"
BROWSER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"


def youtube_format(limit: int) -> str:
    """До 720p в H.264; каждая дорожка — не больше лимита отправки (размер неизвестен — не мешает)."""
    cap = f"[filesize<?{limit}][filesize_approx<?{limit}]"
    return (
        f"bv*[height<=720][vcodec^=avc]{cap}+ba[ext=m4a]/b[height<=720][vcodec^=avc]{cap}/"
        f"bv*[height<=720]{cap}+ba/b[height<=720]{cap}/bv*[height<=480]+ba/b"
    )


# What a refusal is, for the analytics: the source, the size, the download, the processing or the time (family_stats.REASONS).
WHY = {
    "private": "unavailable",
    "removed": "unavailable",
    "notfound": "unavailable",
    "live": "unavailable",
    "nomedia": "unavailable",
    "login": "unavailable",
    "expired": "unavailable",
    "busy": "download",
    "too_long": "too_big",
    "file_too_big": "too_big",
    "failed": "download",
}


class DownloadError(Exception):
    """Причина отказа: код из i18n (private, nomedia, notfound, failed, too_long, live, removed, file_too_big, login, busy,
    expired). `why` — для счёта: тот же текст человеку бывает у разных причин (площадка не поддерживается и ролика нет — оба
    «nomedia»)."""

    def __init__(self, code: str, why: str | None = None):
        super().__init__(code)
        self.code, self.why = code, why or WHY.get(code, "download")


@dataclass
class File:
    """Один файл для отправки: video, audio или photo."""

    path: Path
    kind: str
    title: str | None = None
    performer: str | None = None
    duration: int | None = None
    width: int | None = None
    height: int | None = None
    thumb: Path | None = None
    filename: str | None = None


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
    # YouTube longer than the video limit: only the audio is sent, and the person is told why.
    long_video: bool = False
    # A carousel, slides, stories or a profile: photos and videos sent as albums before the audio.
    gallery: list[File] = field(default_factory=list)
    audio_name: str | None = None


@dataclass
class Playlist:
    """Альбом, плейлист или топ исполнителя Spotify: треки качаются по одному (spotify_track)."""

    kind: str
    title: str
    owner: str | None
    ids: list[str]
    names: list[tuple[str, str, int | None]] = field(default_factory=list)


ig: Instagram | None = None


def setup(cookies: str | None) -> None:
    global ig
    ig = Instagram(cookies)


def _instagram() -> Instagram:
    global ig
    if ig is None:
        ig = Instagram(None)
    return ig


def kind(url: str) -> str | None:
    """youtube, spotify, instagram, tiktok или None — такую ссылку бот пропускает молча."""
    host = (urlparse(url).hostname or "").lower()
    if host.endswith(("youtube.com", "youtu.be")):
        return "youtube" if YOUTUBE_VIDEO.match(url) or youtube_list_id(url) else None
    if host.endswith("spotify.com"):
        return "spotify" if spotify.LINK.match(url) else None
    if host == "spotify.link":
        return "spotify"
    if host.endswith(("instagram.com", "instagr.am")):
        return "instagram" if instagram.target(url) else None
    return "tiktok"


def is_profile(url: str) -> bool:
    """Ссылка на профиль Instagram: в группах её просто упоминают в разговоре, скачивать по ней — только в личке."""
    return kind(url) == "instagram" and (instagram.target(url) or ("",))[0] == "profile"


def find_links(text: str | None, extra: list[str] | None = None) -> list[str]:
    """Ссылки на поддерживаемые площадки из текста и скрытых ссылок, без повторов."""
    found = [m.group(0).rstrip(").,!?»") for m in LINK_RE.finditer(text or "")]
    found += [u for u in extra or [] if LINK_RE.fullmatch(u)]
    return [u for u in dict.fromkeys(found) if kind(u)]


def room(workdir: Path, limit: int) -> int:
    """Сколько можно скачать, не съев место на диске: файл и его копия при склейке, плюс запас для сервера."""
    free = shutil.disk_usage(workdir).free - DISK_RESERVE
    return max(SMALL_LIMIT, min(limit, free // 2))


# --- yt-dlp ------------------------------------------------------------------


def _options(workdir: Path, cookies: str | None, fmt: str, max_size: int = SMALL_DOWNLOAD) -> dict:
    opts = {
        "outtmpl": str(workdir / "%(id).60s.%(ext)s"),
        "format": fmt,
        "merge_output_format": "mp4",
        "noplaylist": True,
        "playlist_items": "1",
        "max_filesize": max_size,
        "socket_timeout": 20,
        "retries": 2,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
    }
    if cookies:
        # yt-dlp writes the jar back on close: it gets a copy, the session file stays as the owner put it.
        copy = workdir / "cookies.txt"
        if not copy.exists():
            shutil.copyfile(cookies, copy)
        opts["cookiefile"] = str(copy)
    return opts


def _ydl_error(e: Exception) -> DownloadError:
    msg = str(e).lower()
    if "timed out" in msg or "timeout" in msg:
        return DownloadError("failed", "timeout")
    if "unsupported url" in msg:
        return DownloadError("nomedia", "unsupported")
    if "live event" in msg or "is live" in msg or "premieres in" in msg:
        return DownloadError("live")
    if any(w in msg for w in ("removed", "deleted", "no longer available", "video unavailable", "terminated", "does not exist")):
        return DownloadError("removed")
    if "429" in msg or "too many requests" in msg or "rate-limit" in msg:
        return DownloadError("busy")
    if "login" in msg or "private" in msg or "cookies" in msg or "sign in" in msg:
        return DownloadError("private")
    if "no video formats" in msg or "unavailable" in msg:
        return DownloadError("nomedia")
    return DownloadError("failed")


def _first(info: dict) -> dict:
    return next(iter(info["entries"]), None) or {} if info.get("entries") else info


def _info(url: str, workdir: Path, cookies: str | None) -> dict:
    """Сведения о ролике без скачивания: длительность решает, качать ли видео."""
    try:
        with yt_dlp.YoutubeDL({**_options(workdir, cookies, "b"), "skip_download": True, "ignore_no_formats_error": True}) as ydl:
            return _first(ydl.extract_info(url, download=False))
    except yt_dlp.utils.DownloadError as e:
        raise _ydl_error(e) from e


def _download(url: str, workdir: Path, cookies: str | None, fmt: str, max_size: int = SMALL_DOWNLOAD) -> tuple[dict, Path]:
    try:
        with yt_dlp.YoutubeDL(_options(workdir, cookies, fmt, max_size)) as ydl:
            info = _first(ydl.extract_info(url, download=True))
    except yt_dlp.utils.DownloadError as e:
        raise _ydl_error(e) from e
    files = [Path(d["filepath"]) for d in info.get("requested_downloads") or [] if d.get("filepath")]
    if not files or not files[0].exists():
        # yt-dlp skips a file over max_filesize without an error: say so instead of a vague failure.
        size = max((d.get("filesize") or d.get("filesize_approx") or 0) for d in info.get("requested_downloads") or [info])
        raise DownloadError("file_too_big" if size > max_size else "failed")
    return info, files[0]


# --- ffmpeg ------------------------------------------------------------------


def _probe(path: Path) -> dict:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,codec_name,width,height:format=duration", "-of", "json", str(path)],
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
    return json.loads(out.stdout)


def _extract_audio(src: Path, workdir: Path, duration: float | None, codec: str | None, limit: int) -> Path:
    """Звук из ролика: AAC — без перекодирования в m4a (секунды даже для часа), иначе — mp3, сжатый под лимит."""
    if codec == "aac":
        dst = workdir / "audio.m4a"
        cmd = ["ffmpeg", "-y", "-v", "error", "-i", str(src), "-vn", "-map", "0:a:0", "-c:a", "copy", "-movflags", "+faststart"]
    else:
        dst = workdir / "audio.mp3"
        kbps = 192 if not duration else max(48, min(192, int(limit * 8 * 0.95 / duration / 1000)))
        cmd = ["ffmpeg", "-y", "-v", "error", "-i", str(src), "-vn", "-map", "0:a:0", "-c:a", "libmp3lame", "-b:a", f"{kbps}k"]
    subprocess.run([*cmd, str(dst)], capture_output=True, timeout=1800, check=True)
    return dst


def _short(text: str | None, limit: int = 64) -> str | None:
    if not text:
        return None
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _finish(info: dict, src: Path, workdir: Path, audio_only: bool = False, limit: int = SMALL_LIMIT) -> Media:
    probe = _probe(src)
    streams = probe.get("streams", [])
    vstream = None if audio_only else next((s for s in streams if s.get("codec_type") == "video" and s.get("width")), None)
    astream = next((s for s in streams if s.get("codec_type") == "audio"), None)
    raw = probe.get("format", {}).get("duration") or info.get("duration")
    duration = float(raw) if raw else None

    audio = None
    if astream:
        audio = _extract_audio(src, workdir, duration, astream.get("codec_name"), limit)
        if audio.stat().st_size > limit:
            audio = None

    video = None
    too_big = audio_only
    if vstream:
        if src.stat().st_size <= limit:
            video = src
        else:
            too_big = True

    if not video and not audio:
        raise DownloadError("too_long" if astream else "nomedia")

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


def _processed(info: dict, src: Path, workdir: Path, audio_only: bool = False, limit: int = SMALL_LIMIT) -> Media:
    """_finish, whose failures of ffmpeg are a failure of processing, not of the download."""
    try:
        return _finish(info, src, workdir, audio_only, limit)
    except subprocess.TimeoutExpired as e:
        raise DownloadError("failed", "timeout") from e
    except (subprocess.SubprocessError, OSError, ValueError, KeyError) as e:
        raise DownloadError("failed", "processing") from e


def _fetch(url: str, dst: Path, limit: int, agent: str = BROWSER_AGENT) -> Path:
    """Файл по прямому адресу (CDN Instagram, TikTok, Spotify), не больше limit байт."""
    request = urllib.request.Request(url, headers={"User-Agent": agent})
    size = 0
    with urllib.request.urlopen(request, timeout=30) as response, dst.open("wb") as out:
        while chunk := response.read(1 << 16):
            size += len(chunk)
            if size > limit:
                raise DownloadError("file_too_big")
            out.write(chunk)
    return dst


def _photo(src: Path, dst: Path) -> File:
    """Фото для Telegram: JPEG, большая сторона не больше 2560 px (webp и heic Telegram как фото не берёт)."""
    scale = "scale='min(2560,iw)':'min(2560,ih)':force_original_aspect_ratio=decrease"
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", str(src), "-vf", scale, "-frames:v", "1", "-q:v", "3", str(dst)],
        capture_output=True,
        timeout=120,
        check=True,
    )
    return File(dst, "photo")


def _video_file(path: Path) -> File:
    probe = _probe(path)
    v = next((s for s in probe.get("streams", []) if s.get("codec_type") == "video"), {})
    raw = probe.get("format", {}).get("duration")
    return File(path, "video", duration=round(float(raw)) if raw else None, width=v.get("width"), height=v.get("height"))


def _gallery(items: list[tuple[str, str]], workdir: Path, limit: int) -> list[File]:
    files = []
    for i, (what, url) in enumerate(items):
        try:
            raw = _fetch(url, workdir / f"item{i}.src", min(limit, GALLERY_ITEM_MAX))
            if what == "photo":
                files.append(_photo(raw, workdir / f"item{i}.jpg"))
            else:
                files.append(_video_file(raw.rename(workdir / f"item{i}.mp4")))
        except (OSError, subprocess.SubprocessError, ValueError, DownloadError):
            continue  # один битый слайд не отменяет остальные
    return files


# --- Spotify -----------------------------------------------------------------


# Обложка трека квадратная: превью YouTube (16:9) обрезается по центру.
SQUARE = "crop='min(iw,ih)':'min(iw,ih)',scale=320:320"


def _cover(url: str | None, workdir: Path, name: str = "cover") -> tuple[Path | None, Path | None]:
    """Обложка: полная (640 px, внутрь файла) и миниатюра для Telegram (JPEG до 320 px и 200 КБ)."""
    if not url or not url.startswith("https://"):
        return None, None
    try:
        full = _fetch(url, workdir / f"{name}.jpg", 5_000_000, USER_AGENT)
        thumb = workdir / f"{name}-thumb.jpg"
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-i", str(full), "-vf", SQUARE, "-q:v", "4", str(thumb)],
            capture_output=True,
            timeout=60,
            check=True,
        )
        return full, thumb if thumb.stat().st_size < 200_000 else None
    except (OSError, subprocess.SubprocessError, DownloadError):
        return None, None


def spotify_track(track_id: str, workdir: Path, cookies: str | None = None, limit: int = SMALL_LIMIT) -> File:
    """Один трек Spotify файлом с тегами и обложкой. Синхронно."""
    try:
        want = spotify.track(track_id)
    except SpotifyError as e:
        raise DownloadError(str(e)) from e
    if want.duration and want.duration > BIG_DURATION:
        raise DownloadError("too_long")
    found = spotify.match(want)
    if not found:
        raise DownloadError("notfound")
    sub = workdir / track_id
    sub.mkdir(exist_ok=True)
    _, src = _download(found, sub, cookies, AUDIO_FORMAT, max(limit, SMALL_DOWNLOAD))
    cover, thumb = _cover(want.cover, sub)
    try:
        path = spotify.tag(src, sub, want, cover)
    except subprocess.TimeoutExpired as e:
        raise DownloadError("failed", "timeout") from e
    except (subprocess.SubprocessError, OSError) as e:
        raise DownloadError("failed", "processing") from e
    if path.stat().st_size > limit:
        raise DownloadError("file_too_big")
    return File(path, "audio", title=_short(want.title, 128), performer=_short(want.artist, 128), duration=want.duration, thumb=thumb,
                filename=path.name)  # fmt: skip


# --- YouTube: плейлисты ---------------------------------------------------------


def youtube_list_id(url: str) -> str | None:
    """Плейлист в ссылке YouTube (list=…): обычный, микс (RD…) или альбом YouTube Music."""
    found = parse_qs(urlparse(url).query).get("list")
    value = found[0] if found else None
    return value if value and re.fullmatch(r"[\w-]{10,}", value) and value not in ("WL", "LL") else None


def youtube_video_id(url: str) -> str | None:
    parsed = urlparse(url)
    if (parsed.hostname or "").endswith("youtu.be"):
        return parsed.path.strip("/").split("/")[0] or None
    found = parse_qs(parsed.query).get("v")
    if found:
        return found[0]
    m = re.search(r"/(?:shorts|embed|live)/([\w-]{6,})", parsed.path)
    return m.group(1) if m else None


def youtube_list(url: str) -> Playlist:
    """Треки плейлиста YouTube без скачивания: названия, авторы и длительность — для списка, из которого выбирают. Синхронно."""
    list_id = youtube_list_id(url)
    if not list_id:
        raise DownloadError("nomedia", "unsupported")
    video = youtube_video_id(url)
    # Микс (RD…) существует только вместе с роликом, с которого начат; обычный плейлист — сам по себе.
    target = (
        f"https://www.youtube.com/watch?v={video}&list={list_id}"
        if video and list_id.startswith("RD")
        else (f"https://www.youtube.com/playlist?list={list_id}")
    )
    opts = {"quiet": True, "no_warnings": True, "extract_flat": "in_playlist", "skip_download": True, "playlistend": PLAYLIST_MAX}
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(target, download=False)
    except yt_dlp.utils.DownloadError as e:
        raise _ydl_error(e) from e
    entries = [e for e in info.get("entries") or [] if e and e.get("id") and (e.get("duration") or 0) <= BIG_DURATION]
    entries = [e for e in entries if e.get("title") not in ("[Private video]", "[Deleted video]")][:PLAYLIST_MAX]
    if not entries:
        raise DownloadError("nomedia")
    names = [
        (e.get("title") or "?", (e.get("channel") or e.get("uploader") or "").removesuffix(" - Topic"), e.get("duration")) for e in entries
    ]
    title = info.get("title") or "YouTube"
    return Playlist("youtube", title, info.get("channel") or info.get("uploader"), [e["id"] for e in entries], names)


def youtube_track(video_id: str, workdir: Path, cookies: str | None = None, limit: int = SMALL_LIMIT) -> File:
    """Один ролик плейлиста звуком (m4a без перекодирования) с названием, исполнителем и обложкой. Синхронно."""
    sub = workdir / video_id
    sub.mkdir(exist_ok=True)
    info, src = _download(f"https://www.youtube.com/watch?v={video_id}", sub, cookies, AUDIO_FORMAT, max(limit, SMALL_DOWNLOAD))
    if info.get("is_live"):
        raise DownloadError("live")
    artist = info.get("artist") or ((info.get("artists") or [None])[0]) or (info.get("uploader") or "").removesuffix(" - Topic")
    want = spotify.Track(video_id, info.get("track") or info.get("title") or "audio", [artist] if artist else [], album=info.get("album"),
                         duration=round(info["duration"]) if info.get("duration") else None)  # fmt: skip
    _, thumb = _cover(info.get("thumbnail"), sub)
    try:
        path = spotify.tag(src, sub, want, thumb, source=f"https://youtu.be/{video_id}")
    except subprocess.TimeoutExpired as e:
        raise DownloadError("failed", "timeout") from e
    except (subprocess.SubprocessError, OSError) as e:
        raise DownloadError("failed", "processing") from e
    if path.stat().st_size > limit:
        raise DownloadError("file_too_big")
    return File(path, "audio", title=_short(want.title, 128), performer=_short(want.artist, 128), duration=want.duration, thumb=thumb,
                filename=path.name)  # fmt: skip


def playlist_track(playlist: Playlist, item_id: str, workdir: Path, cookies: str | None = None, limit: int = SMALL_LIMIT) -> File:
    """Трек списка: Spotify — найти и скачать запись, YouTube — звук ролика."""
    fetch = youtube_track if playlist.kind == "youtube" else spotify_track
    return fetch(item_id, workdir, cookies, limit)


def _spotify(url: str, workdir: Path, cookies: str | None, limit: int) -> Media | Playlist:
    try:
        what, ident = spotify.resolve(url)
        if what != "track":
            listed: Tracklist = spotify.tracklist(what, ident)
            return Playlist(listed.kind, listed.title, listed.owner, listed.ids, listed.names)
    except SpotifyError as e:
        raise DownloadError(str(e), "unsupported" if str(e) == "nomedia" else None) from e
    file = spotify_track(ident, workdir, cookies, limit)
    return Media(
        None, file.path, file.title or "audio", file.performer, file.duration, None, None, thumb=file.thumb, audio_name=file.filename
    )


# --- TikTok ------------------------------------------------------------------


def _resolve(url: str) -> str:
    """vm.tiktok.com, vt.tiktok.com и tiktok.com/t/… — короткие ссылки: куда они ведут (фото-пост или ролик)."""
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if host.startswith(("vm.", "vt.")) or parsed.path.startswith("/t/"):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": BROWSER_AGENT}, method="HEAD")
            with urllib.request.urlopen(request, timeout=15) as response:
                return response.geturl()
        except OSError:
            return url
    return url


def _tiktok_photos(user: str, post: str, workdir: Path, cookies: str | None, limit: int) -> Media:
    """Фото-пост TikTok: слайды со страницы поста и звук — тот же пост как «ролик» отдаёт yt-dlp."""
    page = f"https://www.tiktok.com/@{user}/video/{post}"
    try:
        with yt_dlp.YoutubeDL(_options(workdir, cookies, "b")) as ydl:
            data, _status = ydl.get_info_extractor("TikTok")._extract_web_data_and_status(page, post)
    except (yt_dlp.utils.DownloadError, yt_dlp.utils.ExtractorError) as e:
        raise _ydl_error(e) from e
    images = ((data or {}).get("imagePost") or {}).get("images") or []
    urls = [(img.get("imageURL") or {}).get("urlList") or [] for img in images]
    gallery = _gallery([("photo", u[0]) for u in urls if u], workdir, limit)
    if not gallery:
        raise DownloadError("nomedia")
    media = Media(None, None, _short(data.get("desc")) or "TikTok", None, None, None, None, gallery=gallery)
    music = data.get("music") or {}
    try:
        info, src = _download(page, workdir, cookies, "ba/b", max(limit, SMALL_DOWNLOAD))
        sound = _processed(info, src, workdir, True, limit)
        media.audio, media.duration = sound.audio, sound.duration
        media.title = _short(music.get("title")) or sound.title
        media.performer = _short(music.get("authorName")) or sound.performer
    except DownloadError:
        pass  # слайды без звука — тоже результат
    return media


# --- Instagram ---------------------------------------------------------------


def _instagram_link(url: str, workdir: Path, cookies: str | None, limit: int) -> Media:
    what, key = instagram.target(url) or ("", "")
    if what == "audio":
        raise DownloadError("nomedia", "unsupported")
    loader = _instagram()
    if what == "post" and not loader.logged_in:
        # Без входа reels часто отдаёт yt-dlp; фото и карусели — нет.
        try:
            info, src = _download(url, workdir, cookies, SOCIAL_FORMAT, max(limit, SMALL_DOWNLOAD))
            return _processed(info, src, workdir, limit=limit)
        except DownloadError as e:
            if e.code not in ("nomedia", "private", "failed", "busy"):
                raise
    try:
        gallery = loader.fetch(what, key)
    except InstagramError as e:
        raise DownloadError(str(e)) from e
    files = _gallery(gallery.items, workdir, limit)
    if not files:
        raise DownloadError("nomedia")
    if what == "post" and len(files) == 1 and files[0].kind == "video":
        # Один ролик — как раньше: видео и его звук отдельным треком.
        media = _processed({"title": gallery.title}, files[0].path, workdir, limit=limit)
        media.title = _short(gallery.title) or "Instagram"
        return media
    return Media(None, None, _short(gallery.title, 200) or "Instagram", None, None, None, None, gallery=files)


# --- вход --------------------------------------------------------------------


def download(url: str, workdir: Path, cookies: str | None = None, limit: int = SMALL_LIMIT) -> Media | Playlist:
    """Синхронно: вызывать через asyncio.to_thread. limit — сколько бот может отправить одним файлом."""
    big = limit > SMALL_LIMIT
    if big:
        limit = room(workdir, limit)
    match kind(url):
        case "spotify":
            return _spotify(url, workdir, cookies, limit)
        case "instagram":
            return _instagram_link(url, workdir, cookies, limit)
        case "youtube":
            info = _info(url, workdir, cookies)
            if info.get("is_live") or info.get("live_status") in ("is_live", "is_upcoming"):
                raise DownloadError("live")
            duration = info.get("duration") or 0
            if duration > (BIG_DURATION if big else SMALL_DURATION):
                raise DownloadError("too_long")
            audio_only = duration > (BIG_VIDEO_DURATION if big else SMALL_VIDEO_DURATION)
            target = info.get("webpage_url") or url
            fmt = AUDIO_FORMAT if audio_only else youtube_format(limit)
            info, src = _download(target, workdir, cookies, fmt, max(limit, SMALL_DOWNLOAD))
            media = _processed(info, src, workdir, audio_only, limit)
            if audio_only:
                media.video_too_big, media.long_video = False, True
            return media
        case _:
            url = _resolve(url)
            photo = TIKTOK_PHOTO.match(url)
            if photo:
                return _tiktok_photos(photo.group(1), photo.group(2), workdir, cookies, limit)
            info, src = _download(url, workdir, cookies, SOCIAL_FORMAT, max(limit, SMALL_DOWNLOAD))
            return _processed(info, src, workdir, limit=limit)
