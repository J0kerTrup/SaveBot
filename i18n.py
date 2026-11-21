"""Тексты бота и профиля на шести языках. Порядок LANGS — порядок флажков в меню."""

LANGS: dict[str, str] = {
    "ru": "🇷🇺 Русский",
    "uk": "🇺🇦 Українська",
    "en": "🇬🇧 English",
    "es": "🇪🇸 Español",
    "pt": "🇧🇷 Português",
    "tr": "🇹🇷 Türkçe",
}
DEFAULT = "en"

TEXTS: dict[str, dict[str, str]] = {
    "ru": {
        "start": "👋 <b>Привет! Я скачиваю видео и музыку из TikTok, Instagram, YouTube и Spotify.</b>\n\n"
        "📎 Пришли ссылку — верну видео без водяного знака и трек отдельным mp3.\n"
        "🎵 Ссылка на трек Spotify — пришлю этот трек в mp3.\n"
        "👥 Добавь меня в группу: буду отвечать на ссылки прямо в чате.\n\n"
        "🌍 Язык можно выбрать ниже.",
        "add": "➕ Добавить в чат",
        "lang_set": "✅ Язык: Русский",
        "admins_only": "Язык чата меняют только администраторы.",
        "private": "Не получилось скачать: пост закрыт или площадка требует вход.",
        "nomedia": "Не получилось скачать: по этой ссылке нет видео или звука.",
        "notfound": "Не нашёл этот трек: попробуй другую ссылку.",
        "failed": "Не получилось скачать: площадка не отдала файл. Попробуй позже.",
        "too_long": "Слишком длинно: больше часа — Telegram не примет такой файл от бота.",
        "too_big": "Видео слишком большое для Telegram — присылаю только звук.",
    },
    "uk": {
        "start": "👋 <b>Привіт! Я завантажую відео та музику з TikTok, Instagram, YouTube і Spotify.</b>\n\n"
        "📎 Надішли посилання — поверну відео без водяного знака і трек окремим mp3.\n"
        "🎵 Посилання на трек Spotify — надішлю цей трек у mp3.\n"
        "👥 Додай мене в групу: відповідатиму на посилання просто в чаті.\n\n"
        "🌍 Мову можна обрати нижче.",
        "add": "➕ Додати в чат",
        "lang_set": "✅ Мова: Українська",
        "admins_only": "Мову чату змінюють лише адміністратори.",
        "private": "Не вдалося завантажити: допис закритий або платформа вимагає вхід.",
        "nomedia": "Не вдалося завантажити: за цим посиланням немає відео чи звуку.",
        "notfound": "Не знайшов цей трек: спробуй інше посилання.",
        "failed": "Не вдалося завантажити: платформа не віддала файл. Спробуй пізніше.",
        "too_long": "Задовго: понад годину — Telegram не прийме такий файл від бота.",
        "too_big": "Відео завелике для Telegram — надсилаю лише звук.",
    },
    "en": {
        "start": "👋 <b>Hi! I download videos and music from TikTok, Instagram, YouTube and Spotify.</b>\n\n"
        "📎 Send a link — I'll reply with the video without watermark and the track as a separate mp3.\n"
        "🎵 A Spotify track link — I'll send that track as mp3.\n"
        "👥 Add me to a group and I'll answer links right in the chat.\n\n"
        "🌍 Pick your language below.",
        "add": "➕ Add to chat",
        "lang_set": "✅ Language: English",
        "admins_only": "Only admins can change the chat language.",
        "private": "Couldn't download: the post is private or requires login.",
        "nomedia": "Couldn't download: there's no video or audio at this link.",
        "notfound": "Couldn't find this track: try another link.",
        "failed": "Couldn't download: the platform didn't return the file. Try again later.",
        "too_long": "Too long: over an hour — Telegram won't accept such a file from a bot.",
        "too_big": "The video is too big for Telegram — sending the audio only.",
    },
    "es": {
        "start": "👋 <b>¡Hola! Descargo videos y música de TikTok, Instagram, YouTube y Spotify.</b>\n\n"
        "📎 Envía un enlace y te devuelvo el video sin marca de agua y la pista en mp3 aparte.\n"
        "🎵 ¿Un enlace de una canción de Spotify? Te envío esa canción en mp3.\n"
        "👥 Agrégame a un grupo y responderé a los enlaces en el chat.\n\n"
        "🌍 Elige tu idioma abajo.",
        "add": "➕ Agregar al chat",
        "lang_set": "✅ Idioma: Español",
        "admins_only": "Solo los administradores pueden cambiar el idioma del chat.",
        "private": "No se pudo descargar: la publicación es privada o requiere iniciar sesión.",
        "nomedia": "No se pudo descargar: este enlace no tiene video ni audio.",
        "notfound": "No encontré esta canción: prueba con otro enlace.",
        "failed": "No se pudo descargar: la plataforma no entregó el archivo. Inténtalo más tarde.",
        "too_long": "Demasiado largo: más de una hora; Telegram no acepta un archivo así de un bot.",
        "too_big": "El video es demasiado grande para Telegram: envío solo el audio.",
    },
    "pt": {
        "start": "👋 <b>Olá! Eu baixo vídeos e músicas do TikTok, Instagram, YouTube e Spotify.</b>\n\n"
        "📎 Envie um link e eu devolvo o vídeo sem marca d'água e a faixa em mp3 separada.\n"
        "🎵 Link de uma música do Spotify? Envio essa música em mp3.\n"
        "👥 Adicione-me a um grupo e responderei aos links direto no chat.\n\n"
        "🌍 Escolha o idioma abaixo.",
        "add": "➕ Adicionar ao chat",
        "lang_set": "✅ Idioma: Português",
        "admins_only": "Só os administradores podem mudar o idioma do chat.",
        "private": "Não foi possível baixar: a publicação é privada ou exige login.",
        "nomedia": "Não foi possível baixar: não há vídeo nem áudio neste link.",
        "notfound": "Não encontrei esta música: tente outro link.",
        "failed": "Não foi possível baixar: a plataforma não entregou o arquivo. Tente mais tarde.",
        "too_long": "Longo demais: mais de uma hora — o Telegram não aceita um arquivo assim de um bot.",
        "too_big": "O vídeo é grande demais para o Telegram — mando só o áudio.",
    },
    "tr": {
        "start": "👋 <b>Merhaba! TikTok, Instagram, YouTube ve Spotify'dan video ve müzik indiriyorum.</b>\n\n"
        "📎 Bir bağlantı gönder — videoyu filigransız, parçayı ayrı mp3 olarak göndereyim.\n"
        "🎵 Spotify şarkı bağlantısı mı? O şarkıyı mp3 olarak gönderirim.\n"
        "👥 Beni bir gruba ekle, bağlantılara doğrudan sohbette yanıt veririm.\n\n"
        "🌍 Dilini aşağıdan seç.",
        "add": "➕ Sohbete ekle",
        "lang_set": "✅ Dil: Türkçe",
        "admins_only": "Sohbet dilini yalnızca yöneticiler değiştirebilir.",
        "private": "İndirilemedi: gönderi gizli ya da giriş gerektiriyor.",
        "nomedia": "İndirilemedi: bu bağlantıda video ya da ses yok.",
        "notfound": "Bu şarkıyı bulamadım: başka bir bağlantı dene.",
        "failed": "İndirilemedi: platform dosyayı vermedi. Daha sonra tekrar dene.",
        "too_long": "Çok uzun: bir saatten fazla — Telegram bir bottan böyle bir dosya kabul etmiyor.",
        "too_big": "Video Telegram için çok büyük — sadece sesi gönderiyorum.",
    },
}

# Профиль бота: имя (до 64), короткое описание (до 120) и описание (до 512) — по ним бота находит поиск Telegram.
PROFILE: dict[str, tuple[str, str, str]] = {
    "ru": (
        "Pixel Saver — скачать TikTok, Instagram, YouTube, Spotify",
        "Скачать видео и музыку из TikTok, Instagram, YouTube и Spotify без водяного знака. Работает в группах.",
        (
            "Pixel Saver — бот для скачивания видео и музыки из TikTok, Instagram (Reels), YouTube (Shorts) и Spotify.\n\n"
            "• Видео без водяного знака и трек отдельным mp3\n"
            "• Музыка из Spotify и YouTube в mp3 с обложкой\n"
            "• Если в посте нет видео — пришлю музыку\n"
            "• Работает в группах: добавь бота, и он ответит на любую ссылку в чате\n"
            "• Бесплатно, без рекламы и подписок\n\n"
            "Просто пришли ссылку 👇"
        ),
    ),
    "uk": (
        "Pixel Saver — завантажити TikTok, Instagram, YouTube, Spotify",
        "Завантажити відео та музику з TikTok, Instagram, YouTube і Spotify без водяного знака. Працює в групах.",
        (
            "Pixel Saver — бот для завантаження відео та музики з TikTok, Instagram (Reels), YouTube (Shorts) і Spotify.\n\n"
            "• Відео без водяного знака і трек окремим mp3\n"
            "• Музика зі Spotify та YouTube у mp3 з обкладинкою\n"
            "• Якщо в дописі немає відео — надішлю музику\n"
            "• Працює в групах: додай бота, і він відповість на будь-яке посилання в чаті\n"
            "• Безкоштовно, без реклами та підписок\n\n"
            "Просто надішли посилання 👇"
        ),
    ),
    "en": (
        "Pixel Saver — TikTok, Instagram, YouTube, Spotify downloader",
        "Download videos and music from TikTok, Instagram, YouTube and Spotify without watermark. Works in groups.",
        (
            "Pixel Saver is a bot that downloads videos and music from TikTok, Instagram (Reels), YouTube (Shorts) and Spotify.\n\n"
            "• Video without watermark plus the track as a separate mp3\n"
            "• Spotify and YouTube music as mp3 with cover art\n"
            "• No video in the post? You get the music\n"
            "• Works in groups: add the bot and it replies to any link in the chat\n"
            "• Free, no ads, no subscriptions\n\n"
            "Just send a link 👇"
        ),
    ),
    "es": (
        "Pixel Saver — descargar TikTok, Instagram, YouTube, Spotify",
        "Descarga videos y música de TikTok, Instagram, YouTube y Spotify sin marca de agua. Funciona en grupos.",
        (
            "Pixel Saver es un bot para descargar videos y música de TikTok, Instagram (Reels), YouTube (Shorts) y Spotify.\n\n"
            "• Video sin marca de agua y la pista en mp3 aparte\n"
            "• Música de Spotify y YouTube en mp3 con portada\n"
            "• ¿La publicación no tiene video? Recibes la música\n"
            "• Funciona en grupos: agrega el bot y responderá a cualquier enlace del chat\n"
            "• Gratis, sin anuncios ni suscripciones\n\n"
            "Solo envía un enlace 👇"
        ),
    ),
    "pt": (
        "Pixel Saver — baixar TikTok, Instagram, YouTube, Spotify",
        "Baixe vídeos e músicas do TikTok, Instagram, YouTube e Spotify sem marca d'água. Funciona em grupos.",
        (
            "Pixel Saver é um bot para baixar vídeos e músicas do TikTok, Instagram (Reels), YouTube (Shorts) e Spotify.\n\n"
            "• Vídeo sem marca d'água e a faixa em mp3 separada\n"
            "• Músicas do Spotify e do YouTube em mp3 com capa\n"
            "• O post não tem vídeo? Você recebe a música\n"
            "• Funciona em grupos: adicione o bot e ele responde a qualquer link no chat\n"
            "• Grátis, sem anúncios nem assinaturas\n\n"
            "É só enviar um link 👇"
        ),
    ),
    "tr": (
        "Pixel Saver — TikTok, Instagram, YouTube, Spotify indirici",
        "TikTok, Instagram, YouTube ve Spotify'dan video ve müzikleri filigransız indir. Gruplarda çalışır.",
        (
            "Pixel Saver, TikTok, Instagram (Reels), YouTube (Shorts) ve Spotify'dan video ve müzik indiren bir bot.\n\n"
            "• Filigransız video ve ayrı mp3 olarak parça\n"
            "• Spotify ve YouTube müzikleri kapaklı mp3 olarak\n"
            "• Gönderide video yoksa müziği alırsın\n"
            "• Gruplarda çalışır: botu ekle, sohbetteki her bağlantıya yanıt versin\n"
            "• Ücretsiz, reklamsız, abonelik yok\n\n"
            "Bir bağlantı gönder yeter 👇"
        ),
    ),
}

COMMANDS: dict[str, tuple[str, str]] = {
    "ru": ("Как пользоваться", "Выбрать язык"),
    "uk": ("Як користуватися", "Обрати мову"),
    "en": ("How to use", "Choose language"),
    "es": ("Cómo usar", "Elegir idioma"),
    "pt": ("Como usar", "Escolher idioma"),
    "tr": ("Nasıl kullanılır", "Dil seç"),
}


def pick(code: str | None) -> str:
    """Код языка Telegram (ru, pt-br, uk…) → один из наших; иначе английский."""
    base = (code or "").split("-")[0].lower()
    return base if base in LANGS else DEFAULT


def t(lang: str, key: str) -> str:
    return TEXTS.get(lang, TEXTS[DEFAULT])[key]
