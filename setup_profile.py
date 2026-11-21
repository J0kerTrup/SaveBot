"""Один раз после смены текстов: имя, описания и команды бота на всех языках (их индексирует поиск Telegram).

Запуск в контейнере: docker compose -p savebot exec savebot /app/.venv/bin/python setup_profile.py
"""

import asyncio
import os

from aiogram import Bot
from aiogram.exceptions import TelegramRetryAfter
from aiogram.methods import SetMyCommands, SetMyDescription, SetMyName, SetMyShortDescription, TelegramMethod
from aiogram.types import BotCommand

from i18n import COMMANDS, DEFAULT, PROFILE, PROFILE_FOOTER


async def call(bot: Bot, method: TelegramMethod) -> None:
    """Telegram строго ограничивает смену имени: при FloodWait ждём и пробуем ещё раз, один раз."""
    try:
        await bot(method)
    except TelegramRetryAfter as e:
        print(f"  FloodWait {e.retry_after} с, жду")
        await asyncio.sleep(e.retry_after + 1)
        await bot(method)


async def main() -> None:
    bot = Bot(os.environ["BOT_TOKEN"])
    # None — профиль по умолчанию для языков, которых нет в списке.
    for code in [None, *PROFILE]:
        name, short, full = PROFILE[code or DEFAULT]
        start_desc, lang_desc, help_desc = COMMANDS[code or DEFAULT]
        commands = [
            BotCommand(command="start", description=start_desc),
            BotCommand(command="help", description=help_desc),
            BotCommand(command="lang", description=lang_desc),
        ]
        await call(bot, SetMyName(name=name, language_code=code))
        await call(bot, SetMyShortDescription(short_description=short, language_code=code))
        await call(bot, SetMyDescription(description=full + PROFILE_FOOTER[code or DEFAULT], language_code=code))
        await call(bot, SetMyCommands(commands=commands, language_code=code))
        print(f"{code or 'default'}: {name}")
    await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
