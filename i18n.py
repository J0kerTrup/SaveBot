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
        "help": "<b>Как пользоваться</b>\n\nПришли ссылку — пришлю файл ответом:\n• TikTok — видео, фото-посты слайдами и звук;\n• Instagram — посты, карусели, reels, сторис, хайлайты, профиль (в личке);\n• YouTube — видео до 3 часов, длиннее — звуком;\n• Spotify — трек, альбом, плейлист или топ исполнителя: найду записи и пришлю с обложкой и тегами.\n\nФайлы до 2 ГБ. Закрытые профили и платный контент не скачиваю. Бот работает и в группах.",
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
        "too_long": "Слишком длинно: такой файл больше, чем Telegram примет от бота.",
        "too_big": "Видео слишком большое для Telegram — присылаю только звук.",
        "no_link": "Пришли ссылку на один ролик или трек: TikTok, Instagram, YouTube или Spotify.",
        "live": "Это прямой эфир: его скачать нельзя.",
        "removed": "Ролик удалён или закрыт.",
        "file_too_big": "Файл больше, чем Telegram примет от бота: такой я не скачаю.",
        "long_video": "Ролик слишком длинный для видео: присылаю только звук.",
        "login": "Instagram отдаёт это только после входа, а он у бота сейчас не работает. Попробуй позже.",
        "busy": "Площадка ограничила запросы. Попробуй через полчаса.",
        "expired": "Сейчас у этого профиля нет сторис или эта сторис уже исчезла.",
        "uploading": "Загружаю файл {size}: {percent}%",
        "playlist": "<b>{title}</b>: скачано {done} из {total}",
        "playlist_done": "<b>{title}</b>: прислал {sent} из {total}",
        "playlist_missed": "Не нашёл записей: {n}.",
        "playlist_cut_group": "В группе присылаю первые {n} треков — весь список пришлю в личке.",
        "playlist_cut_private": "Прислал первые {n} треков.",
        "playlist_busy": "Подожди, пока закончу предыдущий список.",
    },
    "uk": {
        "start": "<b>Завантажую відео та музику</b>\nНадішли посилання з TikTok, Instagram, YouTube або Spotify.",
        "help": "<b>Як користуватися</b>\n\nНадішли посилання — надішлю файл у відповідь:\n• TikTok — відео, фото-дописи слайдами і звук;\n• Instagram — дописи, каруселі, reels, сторіс, хайлайти, профіль (в особистих);\n• YouTube — відео до 3 годин, довші — звуком;\n• Spotify — трек, альбом, плейлист або топ виконавця: знайду записи й надішлю з обкладинкою та тегами.\n\nФайли до 2 ГБ. Закриті профілі й платний контент не завантажую. Бот працює і в групах.",
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
        "too_long": "Надто довге: такий файл більший, ніж Telegram прийме від бота.",
        "too_big": "Відео завелике для Telegram — надсилаю лише звук.",
        "no_link": "Надішли посилання на один ролик або трек: TikTok, Instagram, YouTube чи Spotify.",
        "live": "Це пряма трансляція: її не можна завантажити.",
        "removed": "Ролик видалено або закрито.",
        "file_too_big": "Файл більший, ніж Telegram прийме від бота: такий я не завантажу.",
        "long_video": "Ролик задовгий для відео: надсилаю лише звук.",
        "login": "Instagram віддає це лише після входу, а він у бота зараз не працює. Спробуй пізніше.",
        "busy": "Платформа обмежила запити. Спробуй за пів години.",
        "expired": "Зараз у цього профілю немає сторіс або ця сторіс уже зникла.",
        "uploading": "Завантажую файл {size}: {percent}%",
        "playlist": "<b>{title}</b>: завантажено {done} з {total}",
        "playlist_done": "<b>{title}</b>: надіслав {sent} з {total}",
        "playlist_missed": "Не знайшов записів: {n}.",
        "playlist_cut_group": "У групі надсилаю перші {n} треків — увесь список надішлю в особистих.",
        "playlist_cut_private": "Надіслав перші {n} треків.",
        "playlist_busy": "Зачекай, поки закінчу попередній список.",
    },
    "en": {
        "start": "<b>Download videos and music</b>\nSend a TikTok, Instagram, YouTube, or Spotify link.",
        "help": "<b>How to use</b>\n\nSend a link and I'll reply with the file:\n• TikTok — videos, photo posts as slides, and the sound;\n• Instagram — posts, carousels, reels, stories, highlights, profiles (in private chat);\n• YouTube — videos up to 3 hours, longer ones as audio;\n• Spotify — a track, album, playlist or artist's top: I'll find the recordings and send them with cover and tags.\n\nFiles up to 2 GB. I don't download private profiles or paid content. The bot also works in groups.",
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
        "too_long": "Too long: such a file is bigger than Telegram accepts from a bot.",
        "too_big": "The video is too big for Telegram — sending the audio only.",
        "no_link": "Send a link to one video or track: TikTok, Instagram, YouTube or Spotify.",
        "live": "This is a live stream: it can't be downloaded.",
        "removed": "The video was removed or made private.",
        "file_too_big": "The file is bigger than Telegram accepts from a bot: I can't download it.",
        "long_video": "The video is too long to send as video: sending the audio only.",
        "login": "Instagram only shows this after login, and the bot's login isn't working right now. Try again later.",
        "busy": "The platform is limiting requests. Try again in half an hour.",
        "expired": "This profile has no stories right now, or this story is gone.",
        "uploading": "Uploading {size}: {percent}%",
        "playlist": "<b>{title}</b>: downloaded {done} of {total}",
        "playlist_done": "<b>{title}</b>: sent {sent} of {total}",
        "playlist_missed": "No recordings found: {n}.",
        "playlist_cut_group": "In a group I send the first {n} tracks — I'll send the full list in private chat.",
        "playlist_cut_private": "Sent the first {n} tracks.",
        "playlist_busy": "Wait until I finish the previous list.",
    },
    "es": {
        "start": "<b>Descarga videos y música</b>\nEnvía un enlace de TikTok, Instagram, YouTube o Spotify.",
        "help": "<b>Cómo usarlo</b>\n\nEnvía un enlace y te respondo con el archivo:\n• TikTok — videos, publicaciones de fotos como diapositivas y el sonido;\n• Instagram — publicaciones, carruseles, reels, historias, destacadas, perfiles (en privado);\n• YouTube — videos de hasta 3 horas, los más largos como audio;\n• Spotify — una canción, álbum, playlist o el top de un artista: encuentro las grabaciones y las envío con portada y etiquetas.\n\nArchivos de hasta 2 GB. No descargo perfiles privados ni contenido de pago. El bot también funciona en grupos.",
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
        "too_long": "Demasiado largo: el archivo supera lo que Telegram acepta de un bot.",
        "too_big": "El video es demasiado grande para Telegram: envío solo el audio.",
        "no_link": "Envía un enlace a un video o una canción: TikTok, Instagram, YouTube o Spotify.",
        "live": "Es una transmisión en vivo: no se puede descargar.",
        "removed": "El video fue eliminado o es privado.",
        "file_too_big": "El archivo supera lo que Telegram acepta de un bot: no puedo descargarlo.",
        "long_video": "El video es demasiado largo para enviarlo como video: envío solo el audio.",
        "login": "Instagram solo muestra esto con sesión iniciada, y la del bot no funciona ahora. Inténtalo más tarde.",
        "busy": "La plataforma está limitando las solicitudes. Inténtalo en media hora.",
        "expired": "Este perfil no tiene historias ahora, o esta historia ya desapareció.",
        "uploading": "Subiendo {size}: {percent}%",
        "playlist": "<b>{title}</b>: descargadas {done} de {total}",
        "playlist_done": "<b>{title}</b>: envié {sent} de {total}",
        "playlist_missed": "Sin grabaciones encontradas: {n}.",
        "playlist_cut_group": "En un grupo envío las primeras {n} canciones; la lista completa, en privado.",
        "playlist_cut_private": "Envié las primeras {n} canciones.",
        "playlist_busy": "Espera a que termine la lista anterior.",
    },
    "pt": {
        "start": "<b>Baixe vídeos e músicas</b>\nEnvie um link do TikTok, Instagram, YouTube ou Spotify.",
        "help": "<b>Como usar</b>\n\nEnvie um link e respondo com o arquivo:\n• TikTok — vídeos, posts de fotos em slides e o som;\n• Instagram — posts, carrosséis, reels, stories, destaques, perfis (no privado);\n• YouTube — vídeos de até 3 horas, os mais longos em áudio;\n• Spotify — uma faixa, álbum, playlist ou top do artista: encontro as gravações e envio com capa e tags.\n\nArquivos de até 2 GB. Não baixo perfis privados nem conteúdo pago. O bot também funciona em grupos.",
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
        "too_long": "Longo demais: o arquivo passa do que o Telegram aceita de um bot.",
        "too_big": "O vídeo é grande demais para o Telegram — mando só o áudio.",
        "no_link": "Envie um link de um vídeo ou de uma música: TikTok, Instagram, YouTube ou Spotify.",
        "live": "É uma transmissão ao vivo: não dá para baixar.",
        "removed": "O vídeo foi removido ou é privado.",
        "file_too_big": "O arquivo passa do que o Telegram aceita de um bot: não consigo baixar.",
        "long_video": "O vídeo é longo demais para enviar como vídeo: envio só o áudio.",
        "login": "O Instagram só mostra isso com login, e o do bot não está funcionando agora. Tente mais tarde.",
        "busy": "A plataforma está limitando os pedidos. Tente em meia hora.",
        "expired": "Este perfil não tem stories agora, ou este story já sumiu.",
        "uploading": "Enviando {size}: {percent}%",
        "playlist": "<b>{title}</b>: baixadas {done} de {total}",
        "playlist_done": "<b>{title}</b>: enviei {sent} de {total}",
        "playlist_missed": "Gravações não encontradas: {n}.",
        "playlist_cut_group": "No grupo envio as primeiras {n} faixas — a lista completa, no privado.",
        "playlist_cut_private": "Enviei as primeiras {n} faixas.",
        "playlist_busy": "Espere eu terminar a lista anterior.",
    },
    "tr": {
        "start": "<b>Video ve müzik indir</b>\nTikTok, Instagram, YouTube veya Spotify bağlantısı gönder.",
        "help": "<b>Nasıl kullanılır</b>\n\nBir bağlantı gönder, dosyayla cevap vereyim:\n• TikTok — videolar, slayt halinde fotoğraf gönderileri ve ses;\n• Instagram — gönderiler, karuseller, reels, hikâyeler, öne çıkanlar, profiller (özelde);\n• YouTube — 3 saate kadar videolar, daha uzunları ses olarak;\n• Spotify — şarkı, albüm, çalma listesi ya da sanatçının en iyileri: kayıtları bulup kapak ve etiketlerle gönderirim.\n\nDosyalar 2 GB'a kadar. Gizli profilleri ve ücretli içeriği indirmem. Bot gruplarda da çalışır.",
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
        "too_long": "Çok uzun: böyle bir dosya Telegram'ın bir bottan kabul ettiğinden büyük.",
        "too_big": "Video Telegram için çok büyük — sadece sesi gönderiyorum.",
        "no_link": "Tek bir video ya da şarkı bağlantısı gönder: TikTok, Instagram, YouTube veya Spotify.",
        "live": "Bu canlı yayın: indirilemez.",
        "removed": "Video kaldırılmış veya gizli.",
        "file_too_big": "Dosya Telegram'ın bir bottan kabul ettiğinden büyük: indiremem.",
        "long_video": "Video, video olarak göndermek için çok uzun: sadece sesi gönderiyorum.",
        "login": "Instagram bunu sadece girişle gösteriyor ve botun girişi şu an çalışmıyor. Sonra tekrar dene.",
        "busy": "Platform istekleri sınırlıyor. Yarım saat sonra tekrar dene.",
        "expired": "Bu profilin şu an hikâyesi yok ya da bu hikâye kaybolmuş.",
        "uploading": "Yükleniyor {size}: %{percent}",
        "playlist": "<b>{title}</b>: {total} parçadan {done} indirildi",
        "playlist_done": "<b>{title}</b>: {total} parçadan {sent} gönderildi",
        "playlist_missed": "Bulunamayan kayıt: {n}.",
        "playlist_cut_group": "Grupta ilk {n} parçayı gönderiyorum — tüm listeyi özelden gönderirim.",
        "playlist_cut_private": "İlk {n} parçayı gönderdim.",
        "playlist_busy": "Önceki listeyi bitirmemi bekle.",
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
