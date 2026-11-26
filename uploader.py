"""Файлы больше лимита Bot API (50 МБ) уходят по MTProto под токеном самого бота: так бот отправляет до 2 ГБ.

Личный аккаунт для этого не нужен: Telethon входит как бот (API_ID и API_HASH с my.telegram.org, BOT_TOKEN), файл приходит от
@pixelsaversbot ответом на сообщение со ссылкой. Апдейты эта сессия не принимает — их по-прежнему читает aiogram. Сессия бота
лежит в data/ (MTPROTO_SESSION) и переиспользуется: вход по токену Telegram ограничивает, повторять его на каждом старте нельзя.
Без API_ID и API_HASH бот работает как раньше, с лимитом 50 МБ.
"""

import asyncio
import logging
import mimetypes
import os
import random
from collections.abc import Awaitable, Callable
from pathlib import Path

log = logging.getLogger("savebot.mtproto")

API_ID = int(os.environ.get("API_ID") or 0)
API_HASH = os.environ.get("API_HASH") or ""
SESSION = os.environ.get("MTPROTO_SESSION") or str(Path(os.environ.get("DB_PATH", "data/savebot.sqlite3")).parent / "mtproto")

# Bot API принимает от бота файлы до 50 МБ; запас — на заголовки multipart.
BOT_API_LIMIT = 49 * 1024 * 1024
# MTProto: не больше 4000 частей по 512 КБ — ровно 2000 МБ; запас на округление.
MTPROTO_LIMIT = 1990 * 1024 * 1024
# Telegram сам ждёт короткий FloodWait; длинный — отказ, а не сон на полчаса посреди загрузки.
FLOOD_SLEEP = 60
PART = 512 * 1024
# Частей в полёте одновременно; больше — выше пик памяти (WINDOW × 512 КБ) и риск FloodWait на загрузке.
WINDOW = int(os.environ.get("MTPROTO_WINDOW", "8"))

Progress = Callable[[int, int], Awaitable[None] | None]


class Uploader:
    def __init__(self, token: str):
        self.token = token
        self.client = None
        # Большие файлы — по одному: на сервере одно ядро, а канал общий с другими ботами.
        self.lock = asyncio.Semaphore(1)

    @property
    def enabled(self) -> bool:
        return self.client is not None

    @property
    def limit(self) -> int:
        return MTPROTO_LIMIT if self.enabled else BOT_API_LIMIT

    async def start(self) -> None:
        if not (API_ID and API_HASH):
            log.info("MTProto выключен (нет API_ID/API_HASH): файлы до 50 МБ")
            return
        from telethon import TelegramClient

        client = TelegramClient(
            SESSION,
            API_ID,
            API_HASH,
            receive_updates=False,
            flood_sleep_threshold=FLOOD_SLEEP,
            connection_retries=3,
            request_retries=3,
            device_model="PixelSaver",
            app_version="1.0",
        )
        try:
            await client.start(bot_token=self.token)
        except Exception:
            # Without MTProto the bot still works with the Bot API: a failed login must not stop it.
            log.exception("MTProto не запустился: файлы до 50 МБ")
            await client.disconnect()
            return
        session_file = Path(SESSION + ".session")
        if session_file.exists():
            session_file.chmod(0o600)
        self.client = client
        log.info("MTProto включён: файлы до %d МБ", MTPROTO_LIMIT // 2**20)

    async def stop(self) -> None:
        if self.client:
            await self.client.disconnect()

    async def send(
        self,
        chat_id: int,
        reply_to: int | None,
        path: Path,
        kind: str,
        caption: str,
        *,
        title: str | None = None,
        performer: str | None = None,
        duration: int | None = None,
        width: int | None = None,
        height: int | None = None,
        thumb: Path | None = None,
        filename: str | None = None,
        progress: Progress | None = None,
    ) -> int:
        """Отправить файл в чат; вернуть id сообщения (тот же, что видит Bot API: по нему бот потом копирует файл)."""
        from telethon.tl.types import DocumentAttributeAudio, DocumentAttributeFilename, DocumentAttributeVideo

        assert self.client is not None
        name = filename or path.name
        attributes = [DocumentAttributeFilename(name)]
        if kind == "video":
            attributes.append(DocumentAttributeVideo(duration or 0, width or 0, height or 0, supports_streaming=True))
        elif kind == "audio":
            attributes.append(DocumentAttributeAudio(duration or 0, title=title, performer=performer))
        mime = mimetypes.guess_type(name)[0] or ("video/mp4" if kind == "video" else "application/octet-stream")
        if name.endswith(".m4a"):
            mime = "audio/mp4"

        async with self.lock:
            entity = await self.client.get_input_entity(chat_id)
            handle = await self._upload(path, name, progress)
            sent = await self.client.send_file(
                entity,
                handle,
                caption=caption,
                parse_mode="html",
                reply_to=reply_to,
                attributes=attributes,
                mime_type=mime,
                thumb=str(thumb) if thumb else None,
                supports_streaming=kind == "video",
                force_document=kind == "document",
            )
        return sent.id

    async def _upload(self, path: Path, name: str, progress: Progress | None):
        """Части файла по 512 КБ, по WINDOW запросов в полёте в одном соединении: Telethon сам шлёт их по одной, и
        загрузка упирается в задержку до серверов Telegram, а не в канал."""
        from telethon.tl.functions.upload import SaveBigFilePartRequest, SaveFilePartRequest
        from telethon.tl.types import InputFile, InputFileBig

        assert self.client is not None
        size = path.stat().st_size
        parts = max(1, -(-size // PART))
        big = size > 10 * 1024 * 1024
        file_id = random.getrandbits(63)
        window = asyncio.Semaphore(WINDOW)
        done = 0

        async def put(index: int, data: bytes) -> None:
            nonlocal done
            try:
                request = SaveBigFilePartRequest(file_id, index, parts, data) if big else SaveFilePartRequest(file_id, index, data)
                for attempt in range(3):
                    try:
                        if await self.client(request):
                            break
                    except (ConnectionError, TimeoutError):
                        if attempt == 2:
                            raise
                        await asyncio.sleep(1 + attempt)
                else:
                    raise RuntimeError(f"Telegram не принял часть {index}")
                done += len(data)
                if progress:
                    result = progress(done, size)
                    if asyncio.iscoroutine(result):
                        await result
            finally:
                window.release()

        tasks = []
        try:
            with path.open("rb") as source:
                for index in range(parts):
                    await window.acquire()
                    failed = next((t for t in tasks if t.done() and t.exception()), None)
                    if failed:
                        window.release()
                        raise failed.exception()
                    tasks.append(asyncio.create_task(put(index, source.read(PART))))
            await asyncio.gather(*tasks)
        except BaseException:
            for task in tasks:
                task.cancel()
            raise
        return InputFileBig(file_id, parts, name) if big else InputFile(file_id, parts, name, "")
