FROM python:3.12-slim

# ffmpeg makes thumbnails for videos you import/upload, and renders the studio's clips
# (fontconfig lets libass find caption fonts)
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg fontconfig && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml README.md ./
COPY noze ./noze
# drop ",transcribe" for a smaller image if you always provide .srt/.vtt subtitles
ARG EXTRAS=all,transcribe
RUN pip install --no-cache-dir ".[${EXTRAS}]"

ENV NOZE_DATA_DIR=/data \
    NOZE_HOST=0.0.0.0 \
    NOZE_PORT=8787
VOLUME ["/data"]
EXPOSE 8787
CMD ["noze", "serve"]
