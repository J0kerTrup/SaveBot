"""Instagram через instaloader: посты, карусели, reels, сторис, хайлайты и профили.

Сторис, хайлайты и профили Instagram отдаёт только после входа, а с серверного адреса и посты тоже. Вход — сессия отдельного
аккаунта, которым владелец бота вправе управлять: cookies.txt (формат Netscape) с sessionid (COOKIES_FILE, тот же файл берёт
yt-dlp). Пароль бот не знает и сам не входит. Запросы идут в API приложения (i.instagram.com) через instaloader: веб-запросы
с сессией приложения Instagram отклоняет. Закрытые профили бот не скачивает, даже если аккаунт на них подписан. На
ограничение Instagram (429, feedback_required) бот отвечает отказом, а не ждёт и не повторяет.
"""

import base64
import binascii
import http.cookiejar
import logging
import re
import secrets
import threading
import time
from dataclasses import dataclass, field
from urllib.parse import urlparse

import instaloader
from instaloader.exceptions import (
    AbortDownloadException,
    ConnectionException,
    InstaloaderException,
    LoginRequiredException,
    QueryReturnedNotFoundException,
    TooManyRequestsException,
)

log = logging.getLogger("savebot.instagram")

# Не все пути instagram.com/<имя>/ — профили.
RESERVED = frozenset(
    [
        "p",
        "reel",
        "reels",
        "tv",
        "stories",
        "explore",
        "accounts",
        "direct",
        "about",
        "legal",
        "developer",
        "web",
        "emails",
        "challenge",
        "s",
        "audio",
        "music",
        "privacy",
        "terms",
        "session",
        "login",
        "signup",
    ]
)
PROFILE_POSTS = 12  # профиль: аватарка и столько последних постов
MAX_ITEMS = 30  # файлов из одной ссылки (профиль, сторис, хайлайт)
SESSION_CHECK = 3600  # раз в час проверяем, что вход ещё действует
# После отказа Instagram (ограничение, выход из сессии) аккаунт отдыхает: новые запросы не идут, человек получает «позже».
COOLDOWN = 30 * 60


class InstagramError(Exception):
    """Код из i18n: private, login, removed, nomedia, busy, expired, failed."""


@dataclass
class Gallery:
    """Что отдала ссылка: файлы по порядку (photo или video, адрес) и подпись."""

    title: str | None
    items: list[tuple[str, str]] = field(default_factory=list)


def target(url: str) -> tuple[str, str] | None:
    """(post|story|stories|highlight|profile|audio, ключ) для ссылки на instagram.com; None — не наше."""
    parts = [p for p in urlparse(url).path.split("/") if p]
    if not parts:
        return None
    if parts[0] == "s" and len(parts) > 1:
        # Ссылка «поделиться» на хайлайт: /s/<base64 «highlight:ID»>
        try:
            raw = base64.urlsafe_b64decode(parts[1] + "=" * (-len(parts[1]) % 4)).decode()
        except (binascii.Error, UnicodeDecodeError, ValueError):
            return None
        return ("highlight", raw[10:]) if raw.startswith("highlight:") and raw[10:].isdigit() else None
    if parts[0] == "stories" and len(parts) > 1:
        if parts[1] == "highlights":
            return ("highlight", parts[2]) if len(parts) > 2 and parts[2].isdigit() else None
        if len(parts) > 2 and parts[2].isdigit():
            return "story", f"{parts[1]}/{parts[2]}"
        return "stories", parts[1]
    # /p/SC, /reel/SC, /reels/SC, /tv/SC и /<имя>/p/SC; /reels/audio/ID — страница звука, не пост
    for i, part in enumerate(parts[:2]):
        if part in ("p", "reel", "reels", "tv") and len(parts) > i + 1:
            return ("audio", "") if parts[i + 1] == "audio" else ("post", parts[i + 1])
    if len(parts) == 1 and parts[0] not in RESERVED and re.fullmatch(r"[A-Za-z0-9._]{1,30}", parts[0]):
        return "profile", parts[0].lower()
    return None


class _NoWait(instaloader.RateController):
    """Не спать минутами на ограничении Instagram: бот отвечает отказом, человек пробует позже."""

    def sleep(self, secs: float) -> None:
        if secs > 20:
            raise TooManyRequestsException("rate limited")
        time.sleep(secs)

    def handle_429(self, query_type: str) -> None:
        raise TooManyRequestsException("429")


class Instagram:
    def __init__(self, cookies: str | None):
        self.cookies = cookies
        # instaloader не рассчитан на потоки: один запрос к Instagram за раз.
        self.lock = threading.Lock()
        self.loader: instaloader.Instaloader | None = None
        self.user: str | None = None
        self.checked = 0.0
        self.resting_until = 0.0

    def _loader(self) -> instaloader.Instaloader:
        now = time.monotonic()
        if self.loader and now - self.checked < SESSION_CHECK:
            return self.loader
        loader = instaloader.Instaloader(
            quiet=True,
            max_connection_attempts=1,
            request_timeout=20,
            rate_controller=lambda ctx: _NoWait(ctx),
            download_comments=False,
            save_metadata=False,
        )
        user = None
        jar = self._cookies()
        if jar:
            loader.load_session("", jar)
            user = self._who(loader)
            if user:
                loader.context.username = user
            else:
                log.warning("Вход в Instagram не действует: нужен новый cookies.txt")
        self.loader, self.user, self.checked = loader, user, now
        return loader

    @staticmethod
    def _who(loader: instaloader.Instaloader) -> str | None:
        """Имя аккаунта сессии или None, если вход не действует (API приложения: веб-запрос с сессией приложения — отказ)."""
        loader.context.username = "?"  # get_iphone_json добавляет токен только залогиненному контексту
        try:
            data = loader.context.get_iphone_json("api/v1/accounts/current_user/", {"edit": "true"})
            return (data.get("user") or {}).get("username")
        except (InstaloaderException, AbortDownloadException, KeyError, TypeError):
            return None
        finally:
            loader.context.username = None

    def _cookies(self) -> dict[str, str] | None:
        if not self.cookies:
            return None
        jar = http.cookiejar.MozillaCookieJar(self.cookies)
        try:
            jar.load(ignore_discard=True, ignore_expires=True)
        except (OSError, http.cookiejar.LoadError):
            log.warning("cookies.txt не читается")
            return None
        found = {c.name: c.value for c in jar if c.domain.endswith("instagram.com")}
        if "sessionid" not in found:
            return None
        # A session taken from the app has no csrftoken; reading needs none, but instaloader sends the header.
        found.setdefault("csrftoken", secrets.token_hex(16))
        return found

    @property
    def logged_in(self) -> bool:
        with self.lock:
            self._loader()
            return bool(self.user)

    def fetch(self, kind: str, key: str) -> Gallery:
        with self.lock:
            if time.monotonic() < self.resting_until:
                raise InstagramError("busy")
            loader = self._loader()
            if not self.user:
                raise InstagramError("login")
            try:
                return self._fetch(loader, kind, key)
            except QueryReturnedNotFoundException as e:
                raise InstagramError("removed") from e
            except TooManyRequestsException as e:
                self._rest("429")
                raise InstagramError("busy") from e
            except AbortDownloadException as e:
                # «Redirected to login page», «checkpoint»: Instagram просит человека; аккаунт отдыхает, а не долбит дальше.
                self._rest(str(e)[:80])
                self.checked = 0
                raise InstagramError("busy") from e
            except LoginRequiredException as e:
                self.checked = 0
                raise InstagramError("login") from e
            except (InstaloaderException, KeyError, TypeError, ValueError) as e:
                text = str(e).lower()
                if "feedback_required" in text or "please wait" in text or "429" in text:
                    self._rest("feedback_required")
                    raise InstagramError("busy") from e
                if "not found" in text or "404" in text or "media_not_found" in text:
                    raise InstagramError("removed") from e
                log.warning("Instagram %s: %s", kind, type(e).__name__)
                raise InstagramError("failed") from e

    def _rest(self, why: str) -> None:
        self.resting_until = time.monotonic() + COOLDOWN
        log.warning("Instagram ограничил запросы (%s): пауза %d мин", why, COOLDOWN // 60)

    def _api(self, loader: instaloader.Instaloader, path: str, params: dict | None = None) -> dict:
        data = loader.context.get_iphone_json(path, params or {})
        if data.get("status") == "fail":
            raise ConnectionException(str(data.get("message") or "fail"))
        return data

    def _user(self, loader: instaloader.Instaloader, username: str) -> dict:
        """Профиль по имени — запросом самого приложения (web_profile_info с серверного адреса Instagram быстро ограничивает)."""
        user = self._api(loader, f"api/v1/users/{username}/usernameinfo/").get("user")
        if not user or not (user.get("pk") or user.get("id")):
            raise InstagramError("removed")
        user["id"] = str(user.get("pk") or user.get("id"))
        return user

    def _fetch(self, loader: instaloader.Instaloader, kind: str, key: str) -> Gallery:
        if kind == "post":
            media_id = instaloader.Post.shortcode_to_mediaid(key)
            items = self._api(loader, f"api/v1/media/{media_id}/info/").get("items") or []
            if not items:
                raise InstagramError("removed")
            item = items[0]
            if (item.get("user") or {}).get("is_private"):
                raise InstagramError("private")
            caption = (item.get("caption") or {}).get("text")
            return Gallery(caption, _media(item))

        if kind == "highlight":
            reel = self._api(loader, "api/v1/feed/reels_media/", {"reel_ids": f"highlight:{key}"}).get("reels", {}).get(f"highlight:{key}")
            if not reel:
                raise InstagramError("removed")
            if (reel.get("user") or {}).get("is_private"):
                raise InstagramError("private")
            return Gallery(reel.get("title"), [m for i in reel.get("items") or [] for m in _media(i)][:MAX_ITEMS])

        username = key.split("/", 1)[0].lower()
        user = self._user(loader, username)
        if user.get("is_private"):
            raise InstagramError("private")
        userid = user["id"]

        if kind in ("story", "stories"):
            reel = self._api(loader, "api/v1/feed/reels_media/", {"reel_ids": userid}).get("reels", {}).get(userid) or {}
            items = reel.get("items") or []
            if kind == "story":
                wanted = key.split("/", 1)[1]
                items = [i for i in items if str(i.get("pk")) == wanted]
            if not items:
                raise InstagramError("expired")
            return Gallery(f"@{user.get('username') or username}", [m for i in items for m in _media(i)][:MAX_ITEMS])

        # profile: аватарка в полном размере и последние посты
        found: list[tuple[str, str]] = []
        pic = (user.get("hd_profile_pic_url_info") or {}).get("url") or user.get("profile_pic_url_hd") or user.get("profile_pic_url")
        if pic:
            found.append(("photo", pic))
        feed = self._api(loader, f"api/v1/feed/user/{userid}/", {"count": PROFILE_POSTS}).get("items") or []
        for item in feed[:PROFILE_POSTS]:
            found += _media(item)
            if len(found) >= MAX_ITEMS:
                break
        name = user.get("full_name") or user.get("username") or username
        return Gallery(f"{name} (@{user.get('username') or username})", found[:MAX_ITEMS])


def _media(item: dict) -> list[tuple[str, str]]:
    """Файлы одного элемента API: карусель — все её фото и видео, иначе одно видео или фото наибольшего размера."""
    if item.get("carousel_media"):
        return [m for c in item["carousel_media"] for m in _media(c)]
    videos = item.get("video_versions") or []
    if videos:
        best = max(videos, key=lambda v: (v.get("width") or 0) * (v.get("height") or 0))
        return [("video", best["url"])]
    candidates = (item.get("image_versions2") or {}).get("candidates") or []
    if not candidates:
        return []
    best = max(candidates, key=lambda c: (c.get("width") or 0) * (c.get("height") or 0))
    return [("photo", best["url"])]
