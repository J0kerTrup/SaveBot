"""«Invite friends» of a bot of the family: the personal link, how many came by it, the button to share it. Six languages.

The link holds no Telegram ID: its code is the person's number in this bot (family_stats.Stats.pseudonym). Nothing is paid for an
invitation, it is only counted: once, and only for someone new to the bot. The file is the same in SaveBot, CircleBot, StickerBot and
ParserPixel; Pixel Hub, Pixel Radio and the anonymous chat have invitations of their own.
"""

import html
from urllib.parse import quote

BUTTON = {
    "ru": "👥 Пригласить друзей",
    "uk": "👥 Запросити друзів",
    "en": "👥 Invite friends",
    "es": "👥 Invitar amigos",
    "pt": "👥 Convidar amigos",
    "tr": "👥 Arkadaşlarını davet et",
}
SHARE = {
    "ru": "🔗 Отправить другу",
    "uk": "🔗 Надіслати другу",
    "en": "🔗 Send to a friend",
    "es": "🔗 Enviar a un amigo",
    "pt": "🔗 Enviar a um amigo",
    "tr": "🔗 Arkadaşına gönder",
}
SCREEN = {
    "ru": "👥 <b>Пригласить друзей</b>\n\nТвоя ссылка:\n<code>{link}</code>\n\nПришли по ней: <b>{n}</b>",
    "uk": "👥 <b>Запросити друзів</b>\n\nТвоє посилання:\n<code>{link}</code>\n\nПрийшли за ним: <b>{n}</b>",
    "en": "👥 <b>Invite friends</b>\n\nYour link:\n<code>{link}</code>\n\nCame by it: <b>{n}</b>",
    "es": "👥 <b>Invitar amigos</b>\n\nTu enlace:\n<code>{link}</code>\n\nHan venido por él: <b>{n}</b>",
    "pt": "👥 <b>Convidar amigos</b>\n\nSeu link:\n<code>{link}</code>\n\nVieram por ele: <b>{n}</b>",
    "tr": "👥 <b>Arkadaşlarını davet et</b>\n\nBağlantın:\n<code>{link}</code>\n\nBu bağlantıyla gelenler: <b>{n}</b>",
}
PRIVATE = {
    "ru": "Личная ссылка — в личном чате с ботом.",
    "uk": "Особисте посилання — в особистому чаті з ботом.",
    "en": "Your link is in the private chat with the bot.",
    "es": "Tu enlace está en el chat privado con el bot.",
    "pt": "Seu link está no chat privado com o bot.",
    "tr": "Bağlantın botla özel sohbette.",
}


def _in(texts: dict[str, str], lang: str) -> str:
    return texts.get(lang, texts["en"])


def link(stats, username: str, user_id: int) -> str:
    return f"https://t.me/{username}?start={stats.invite_code(user_id)}"


def screen(stats, username: str, user_id: int, lang: str) -> str:
    return _in(SCREEN, lang).format(link=html.escape(link(stats, username, user_id)), n=stats.invited(user_id))


def share_url(stats, username: str, user_id: int) -> str:
    return f"https://t.me/share/url?url={quote(link(stats, username, user_id), safe='')}"


def button(lang: str) -> str:
    return _in(BUTTON, lang)


def share(lang: str) -> str:
    return _in(SHARE, lang)


def private_only(lang: str) -> str:
    return _in(PRIVATE, lang)
