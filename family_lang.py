"""The language of a person across all the bots of Pixel Radio: chosen in one bot, spoken by every one.

The common store is the family's service (FAMILY_LANG_URL, FAMILY_LANG_TOKEN, run by pixel-parser). A bot asks it at most once a
minute per person and never waits for it longer than two seconds: without an answer the bot keeps its own setting. Without the
two variables the bot simply works on its own.
"""

import logging
import os
import time

import aiohttp

log = logging.getLogger("family")
LANGS = frozenset({"ru", "uk", "en", "es", "pt", "tr"})
TTL = 60
MAX_CACHED = 20_000


class Family:
    def __init__(self, agent: str, url: str | None = None, token: str | None = None):
        self.url = (os.getenv("FAMILY_LANG_URL", "") if url is None else url).rstrip("/")
        self.token = os.getenv("FAMILY_LANG_TOKEN", "") if token is None else token
        self.agent = agent
        self._cache: dict[int, tuple[str | None, float]] = {}
        self._session: aiohttp.ClientSession | None = None

    @property
    def enabled(self) -> bool:
        return bool(self.url and self.token)

    def _client(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            # Cloudflare in front of the service refuses an empty or a "Python-urllib" User-Agent: the bot names itself.
            headers = {"Authorization": f"Bearer {self.token}", "User-Agent": self.agent}
            self._session = aiohttp.ClientSession(headers=headers, timeout=aiohttp.ClientTimeout(total=2))
        return self._session

    def _remember(self, user_id: int, lang: str | None) -> None:
        if len(self._cache) > MAX_CACHED:
            self._cache.clear()
        self._cache[user_id] = (lang, time.monotonic() + TTL)

    async def get(self, user_id: int) -> str | None:
        """The language the person chose in any bot of the family; None if none, or if the service did not answer."""
        if not self.enabled:
            return None
        cached = self._cache.get(user_id)
        if cached and cached[1] > time.monotonic():
            return cached[0]
        try:
            async with self._client().get(f"{self.url}/{user_id}") as response:
                if response.status not in (200, 404):
                    log.warning("Общий язык: ответ %s", response.status)
                    return None
                lang = (await response.json(content_type=None)).get("lang") if response.status == 200 else None
        except (aiohttp.ClientError, TimeoutError, ValueError) as error:
            log.warning("Общий язык недоступен: %s", type(error).__name__)
            return None
        lang = lang if lang in LANGS else None
        self._remember(user_id, lang)
        return lang

    async def put(self, user_id: int, lang: str) -> None:
        """The person chose a language here: every bot of the family speaks it from now on."""
        if not self.enabled or lang not in LANGS:
            return
        self._remember(user_id, lang)
        try:
            async with self._client().put(f"{self.url}/{user_id}", json={"lang": lang}) as response:
                if response.status != 204:
                    log.warning("Общий язык не записан: ответ %s", response.status)
        except (aiohttp.ClientError, TimeoutError) as error:
            log.warning("Общий язык не записан: %s", type(error).__name__)

    async def close(self) -> None:
        if self._session is not None:
            await self._session.close()


async def sync_private(family: Family, user_id: int, local: str | None, set_local) -> None:
    """Before a bot answers a person in private: their family language becomes the bot's own setting; a bot's own choice made
    before the family had one is given to the family, so nobody loses what they chose."""
    shared = await family.get(user_id)
    if shared and shared != local:
        set_local(shared)
    elif shared is None and local:
        await family.put(user_id, local)
