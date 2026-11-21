FROM python:3.13-slim

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY bot.py downloader.py emoji.py i18n.py setup_profile.py family_lang.py ./
COPY assets/banners ./assets/banners

RUN useradd -u 10001 bot
USER bot
CMD ["/app/.venv/bin/python", "bot.py"]
