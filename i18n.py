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
        "start": "<b>Скачиваю видео и музыку</b>\nПришли ссылку из TikTok, Instagram, YouTube или Spotify.",
        "help": "<b>Как пользоваться</b>\n\nПришли ссылку из TikTok, Instagram, YouTube или Spotify. К видео пришлю ещё MP3 со звуком. Для Spotify найду подходящую запись и пришлю MP3.\n\nРолики YouTube длиннее 10 минут приходят только звуком, длиннее часа не скачиваются. Бот работает и в группах.",
        "language": "🌐 Язык",
        "choose_language": "<b>Выбери язык</b>",
        "back": "⬅️ Назад",
        "rate_limited": "Слишком много ссылок. Попробуй через минуту.",
        "unexpected": "Не удалось скачать файл. Попробуй позже.",
        "add": "➕ Добавить в чат",
        "hub": "🤖 Все наши боты",
        "site": "🌍 Сайт",
        "lang_set": "✅ Язык: Русский",
        "admins_only": "Язык чата меняют только администраторы.",
        "private": "Не получилось скачать: пост закрыт или площадка требует вход.",
        "nomedia": "Не получилось скачать: по этой ссылке нет видео или звука.",
        "notfound": "Не нашёл этот трек: попробуй другую ссылку.",
        "failed": "Не получилось скачать: площадка не отдала файл. Попробуй позже.",
        "too_long": "Слишком длинно: больше часа — Telegram не примет такой файл от бота.",
        "too_big": "Видео слишком большое для Telegram — присылаю только звук.",
        "no_link": "Пришли ссылку на один ролик или трек: TikTok, Instagram, YouTube или Spotify.",
        "live": "Это прямой эфир: его скачать нельзя.",
        "removed": "Ролик удалён или закрыт.",
        "file_too_big": "Файл больше 150 МБ: такой я не скачаю.",
        "long_video": "Ролик длиннее 10 минут: присылаю только звук.",
    },
    "uk": {
        "start": "<b>Завантажую відео та музику</b>\nНадішли посилання з TikTok, Instagram, YouTube або Spotify.",
        "help": "<b>Як користуватися</b>\n\nНадішли посилання з TikTok, Instagram, YouTube або Spotify. До відео надішлю ще MP3 зі звуком. Для Spotify знайду відповідний запис і надішлю MP3.\n\nРолики YouTube довші за 10 хвилин приходять лише звуком, довші за годину не завантажуються. Бот працює і в групах.",
        "language": "🌐 Мова",
        "choose_language": "<b>Обери мову</b>",
        "back": "⬅️ Назад",
        "rate_limited": "Забагато посилань. Спробуй через хвилину.",
        "unexpected": "Не вдалося завантажити файл. Спробуй пізніше.",
        "add": "➕ Додати в чат",
        "hub": "🤖 Усі наші боти",
        "site": "🌍 Сайт",
        "lang_set": "✅ Мова: Українська",
        "admins_only": "Мову чату змінюють лише адміністратори.",
        "private": "Не вдалося завантажити: допис закритий або платформа вимагає вхід.",
        "nomedia": "Не вдалося завантажити: за цим посиланням немає відео чи звуку.",
        "notfound": "Не знайшов цей трек: спробуй інше посилання.",
        "failed": "Не вдалося завантажити: платформа не віддала файл. Спробуй пізніше.",
        "too_long": "Надто довге: понад годину — Telegram не прийме такий файл від бота.",
        "too_big": "Відео завелике для Telegram — надсилаю лише звук.",
        "no_link": "Надішли посилання на один ролик або трек: TikTok, Instagram, YouTube чи Spotify.",
        "live": "Це пряма трансляція: її не можна завантажити.",
        "removed": "Ролик видалено або закрито.",
        "file_too_big": "Файл більший за 150 МБ: такий я не завантажу.",
        "long_video": "Ролик довший за 10 хвилин: надсилаю лише звук.",
    },
    "en": {
        "start": "<b>Download videos and music</b>\nSend a TikTok, Instagram, YouTube, or Spotify link.",
        "help": "<b>How to use</b>\n\nSend a TikTok, Instagram, YouTube, or Spotify link. With a video I also send its audio as an MP3. For Spotify, I'll find a matching recording and send an MP3.\n\nYouTube videos over 10 minutes come as audio only; over an hour can't be downloaded. The bot also works in groups.",
        "language": "🌐 Language",
        "choose_language": "<b>Choose a language</b>",
        "back": "⬅️ Back",
        "rate_limited": "Too many links. Try again in a minute.",
        "unexpected": "Couldn't download the file. Try again later.",
        "add": "➕ Add to chat",
        "hub": "🤖 All our bots",
        "site": "🌍 Website",
        "lang_set": "✅ Language: English",
        "admins_only": "Only admins can change the chat language.",
        "private": "Couldn't download: the post is private or requires login.",
        "nomedia": "Couldn't download: there's no video or audio at this link.",
        "notfound": "Couldn't find this track: try another link.",
        "failed": "Couldn't download: the platform didn't return the file. Try again later.",
        "too_long": "Too long: over an hour — Telegram won't accept such a file from a bot.",
        "too_big": "The video is too big for Telegram — sending the audio only.",
        "no_link": "Send a link to one video or track: TikTok, Instagram, YouTube or Spotify.",
        "live": "This is a live stream: it can't be downloaded.",
        "removed": "The video was removed or made private.",
        "file_too_big": "The file is over 150 MB: I can't download it.",
        "long_video": "The video is longer than 10 minutes: sending the audio only.",
    },
    "es": {
        "start": "<b>Descarga videos y música</b>\nEnvía un enlace de TikTok, Instagram, YouTube o Spotify.",
        "help": "<b>Cómo usarlo</b>\n\nEnvía un enlace de TikTok, Instagram, YouTube o Spotify. Con un video también envío su audio en MP3. Para Spotify buscaré una grabación que coincida y enviaré un MP3.\n\nLos videos de YouTube de más de 10 minutos llegan solo como audio; los de más de una hora no se descargan. El bot también funciona en grupos.",
        "language": "🌐 Idioma",
        "choose_language": "<b>Elige un idioma</b>",
        "back": "⬅️ Volver",
        "rate_limited": "Demasiados enlaces. Inténtalo de nuevo en un minuto.",
        "unexpected": "No se pudo descargar el archivo. Inténtalo más tarde.",
        "add": "➕ Agregar al chat",
        "hub": "🤖 Todos nuestros bots",
        "site": "🌍 Sitio web",
        "lang_set": "✅ Idioma: Español",
        "admins_only": "Solo los administradores pueden cambiar el idioma del chat.",
        "private": "No se pudo descargar: la publicación es privada o requiere iniciar sesión.",
        "nomedia": "No se pudo descargar: este enlace no tiene video ni audio.",
        "notfound": "No encontré esta canción: prueba con otro enlace.",
        "failed": "No se pudo descargar: la plataforma no entregó el archivo. Inténtalo más tarde.",
        "too_long": "Demasiado largo: más de una hora; Telegram no acepta un archivo así de un bot.",
        "too_big": "El video es demasiado grande para Telegram: envío solo el audio.",
        "no_link": "Envía un enlace a un video o una canción: TikTok, Instagram, YouTube o Spotify.",
        "live": "Es una transmisión en vivo: no se puede descargar.",
        "removed": "El video fue eliminado o es privado.",
        "file_too_big": "El archivo pesa más de 150 MB: no puedo descargarlo.",
        "long_video": "El video dura más de 10 minutos: envío solo el audio.",
    },
    "pt": {
        "start": "<b>Baixe vídeos e músicas</b>\nEnvie um link do TikTok, Instagram, YouTube ou Spotify.",
        "help": "<b>Como usar</b>\n\nEnvie um link do TikTok, Instagram, YouTube ou Spotify. Junto com o vídeo também envio o áudio em MP3. Para o Spotify, encontro uma gravação correspondente e envio um MP3.\n\nVídeos do YouTube com mais de 10 minutos chegam só em áudio; com mais de uma hora não são baixados. O bot também funciona em grupos.",
        "language": "🌐 Idioma",
        "choose_language": "<b>Escolha um idioma</b>",
        "back": "⬅️ Voltar",
        "rate_limited": "Links demais. Tente novamente em um minuto.",
        "unexpected": "Não foi possível baixar o arquivo. Tente mais tarde.",
        "add": "➕ Adicionar ao chat",
        "hub": "🤖 Todos os nossos bots",
        "site": "🌍 Site",
        "lang_set": "✅ Idioma: Português",
        "admins_only": "Só os administradores podem mudar o idioma do chat.",
        "private": "Não foi possível baixar: a publicação é privada ou exige login.",
        "nomedia": "Não foi possível baixar: não há vídeo nem áudio neste link.",
        "notfound": "Não encontrei esta música: tente outro link.",
        "failed": "Não foi possível baixar: a plataforma não entregou o arquivo. Tente mais tarde.",
        "too_long": "Longo demais: mais de uma hora — o Telegram não aceita um arquivo assim de um bot.",
        "too_big": "O vídeo é grande demais para o Telegram — mando só o áudio.",
        "no_link": "Envie um link de um vídeo ou de uma música: TikTok, Instagram, YouTube ou Spotify.",
        "live": "É uma transmissão ao vivo: não dá para baixar.",
        "removed": "O vídeo foi removido ou é privado.",
        "file_too_big": "O arquivo tem mais de 150 MB: não consigo baixar.",
        "long_video": "O vídeo tem mais de 10 minutos: envio só o áudio.",
    },
    "tr": {
        "start": "<b>Video ve müzik indir</b>\nTikTok, Instagram, YouTube veya Spotify bağlantısı gönder.",
        "help": "<b>Nasıl kullanılır</b>\n\nTikTok, Instagram, YouTube veya Spotify bağlantısı gönder. Videoyla birlikte sesini de MP3 olarak gönderirim. Spotify için uygun kaydı bulup MP3 gönderirim.\n\n10 dakikadan uzun YouTube videoları sadece ses olarak gelir, bir saatten uzunları indirilemez. Bot gruplarda da çalışır.",
        "language": "🌐 Dil",
        "choose_language": "<b>Dil seç</b>",
        "back": "⬅️ Geri",
        "rate_limited": "Çok fazla bağlantı gönderdin. Bir dakika sonra tekrar dene.",
        "unexpected": "Dosya indirilemedi. Daha sonra tekrar dene.",
        "add": "➕ Sohbete ekle",
        "hub": "🤖 Tüm botlarımız",
        "site": "🌍 Web sitesi",
        "lang_set": "✅ Dil: Türkçe",
        "admins_only": "Sohbet dilini yalnızca yöneticiler değiştirebilir.",
        "private": "İndirilemedi: gönderi gizli ya da giriş gerektiriyor.",
        "nomedia": "İndirilemedi: bu bağlantıda video ya da ses yok.",
        "notfound": "Bu şarkıyı bulamadım: başka bir bağlantı dene.",
        "failed": "İndirilemedi: platform dosyayı vermedi. Daha sonra tekrar dene.",
        "too_long": "Çok uzun: bir saatten fazla — Telegram bir bottan böyle bir dosya kabul etmiyor.",
        "too_big": "Video Telegram için çok büyük — sadece sesi gönderiyorum.",
        "no_link": "Tek bir video ya da şarkı bağlantısı gönder: TikTok, Instagram, YouTube veya Spotify.",
        "live": "Bu canlı yayın: indirilemez.",
        "removed": "Video kaldırılmış veya gizli.",
        "file_too_big": "Dosya 150 MB'tan büyük: indiremem.",
        "long_video": "Video 10 dakikadan uzun: sadece sesi gönderiyorum.",
    },
}

# Профиль бота: имя (до 64), короткое описание (до 120) и описание (до 512) — по ним бота находит поиск Telegram.
PROFILE: dict[str, tuple[str, str, str]] = {
    "ru": (
        "Pixel Saver — скачать TikTok, Instagram, YouTube, Spotify",
        "Скачать видео и музыку из TikTok, Instagram, YouTube и Spotify без водяного знака. Работает в группах.",
        (
            "Pixel Saver — бот для скачивания видео и музыки из TikTok, Instagram (Reels), YouTube (Shorts) и Spotify.\n\n"
            "• Доступное видео или аудио по ссылке\n"
            "• Музыка в mp3, у треков Spotify с обложкой\n"
            "• Если в посте нет видео — пришлю музыку\n"
            "• В группах отвечает на ссылки поддерживаемых сервисов\n"
            "• Бесплатно, без рекламы и подписок\n\n"
            "Просто пришли ссылку 👇"
        ),
    ),
    "uk": (
        "Pixel Saver — завантажити TikTok, Instagram, YouTube, Spotify",
        "Завантажити відео та музику з TikTok, Instagram, YouTube і Spotify без водяного знака. Працює в групах.",
        (
            "Pixel Saver — бот для завантаження відео та музики з TikTok, Instagram (Reels), YouTube (Shorts) і Spotify.\n\n"
            "• Доступне відео або аудіо за посиланням\n"
            "• Музика в mp3, у треків Spotify з обкладинкою\n"
            "• Якщо в дописі немає відео — надішлю музику\n"
            "• У групах відповідає на посилання підтримуваних сервісів\n"
            "• Безкоштовно, без реклами та підписок\n\n"
            "Просто надішли посилання 👇"
        ),
    ),
    "en": (
        "Pixel Saver — TikTok, Instagram, YouTube, Spotify downloader",
        "Download videos and music from TikTok, Instagram, YouTube and Spotify without watermark. Works in groups.",
        (
            "Pixel Saver is a bot that downloads videos and music from TikTok, Instagram (Reels), YouTube (Shorts) and Spotify.\n\n"
            "• Available video or audio from a supported link\n"
            "• Music as mp3, Spotify tracks with cover art\n"
            "• No video in the post? You get the music\n"
            "• In groups, it replies to links from supported services\n"
            "• Free, no ads, no subscriptions\n\n"
            "Just send a link 👇"
        ),
    ),
    "es": (
        "Pixel Saver — descargar TikTok, Instagram, YouTube, Spotify",
        "Descarga videos y música de TikTok, Instagram, YouTube y Spotify sin marca de agua. Funciona en grupos.",
        (
            "Pixel Saver es un bot para descargar videos y música de TikTok, Instagram (Reels), YouTube (Shorts) y Spotify.\n\n"
            "• Video o audio disponible desde un enlace compatible\n"
            "• Música en mp3; las canciones de Spotify, con portada\n"
            "• ¿La publicación no tiene video? Recibes la música\n"
            "• En grupos responde a enlaces de servicios compatibles\n"
            "• Gratis, sin anuncios ni suscripciones\n\n"
            "Solo envía un enlace 👇"
        ),
    ),
    "pt": (
        "Pixel Saver — baixar TikTok, Instagram, YouTube, Spotify",
        "Baixe vídeos e músicas do TikTok, Instagram, YouTube e Spotify sem marca d'água. Funciona em grupos.",
        (
            "Pixel Saver é um bot para baixar vídeos e músicas do TikTok, Instagram (Reels), YouTube (Shorts) e Spotify.\n\n"
            "• Vídeo ou áudio disponível de um link compatível\n"
            "• Músicas em mp3; as do Spotify com capa\n"
            "• O post não tem vídeo? Você recebe a música\n"
            "• Em grupos responde a links de serviços compatíveis\n"
            "• Grátis, sem anúncios nem assinaturas\n\n"
            "É só enviar um link 👇"
        ),
    ),
    "tr": (
        "Pixel Saver — TikTok, Instagram, YouTube, Spotify indirici",
        "TikTok, Instagram, YouTube ve Spotify'dan video ve müzikleri filigransız indir. Gruplarda çalışır.",
        (
            "Pixel Saver, TikTok, Instagram (Reels), YouTube (Shorts) ve Spotify'dan video ve müzik indiren bir bot.\n\n"
            "• Desteklenen bağlantıdan uygun video veya ses\n"
            "• Müzikler mp3 olarak, Spotify şarkıları kapaklı\n"
            "• Gönderide video yoksa müziği alırsın\n"
            "• Gruplarda desteklenen servislerin bağlantılarına yanıt verir\n"
            "• Ücretsiz, reklamsız, abonelik yok\n\n"
            "Bir bağlantı gönder yeter 👇"
        ),
    ),
}

COMMANDS: dict[str, tuple[str, str, str]] = {
    "ru": ("Главное меню", "Выбрать язык", "Как пользоваться"),
    "uk": ("Головне меню", "Обрати мову", "Як користуватися"),
    "en": ("Main menu", "Choose language", "How to use"),
    "es": ("Menú principal", "Elegir idioma", "Cómo usar"),
    "pt": ("Menu principal", "Escolher idioma", "Como usar"),
    "tr": ("Ana menü", "Dil seç", "Nasıl kullanılır"),
}


def pick(code: str | None) -> str:
    """Код языка Telegram (ru, pt-br, uk…) → один из наших; иначе английский."""
    base = (code or "").split("-")[0].lower()
    return base if base in LANGS else DEFAULT


def t(lang: str, key: str) -> str:
    return TEXTS.get(lang, TEXTS[DEFAULT])[key]


# The last lines of every profile: the bot's own site and the catalog of all the bots of Pixel Radio.
SITE = "save.pixelradio.app"
PROFILE_FOOTER: dict[str, str] = {
    "ru": "\n\n🌍 save.pixelradio.app\n🤖 Все наши боты: @HUBPIXELBOT",
    "uk": "\n\n🌍 save.pixelradio.app\n🤖 Усі наші боти: @HUBPIXELBOT",
    "en": "\n\n🌍 save.pixelradio.app\n🤖 All our bots: @HUBPIXELBOT",
    "es": "\n\n🌍 save.pixelradio.app\n🤖 Todos nuestros bots: @HUBPIXELBOT",
    "pt": "\n\n🌍 save.pixelradio.app\n🤖 Todos os nossos bots: @HUBPIXELBOT",
    "tr": "\n\n🌍 save.pixelradio.app\n🤖 Tüm botlarımız: @HUBPIXELBOT",
}
