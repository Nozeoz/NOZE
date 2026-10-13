FROM python:3.12-slim

# ffmpeg makes thumbnails for videos you import/upload
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml README.md ./
COPY noze ./noze
RUN pip install --no-cache-dir ".[all]"

ENV NOZE_DATA_DIR=/data \
    NOZE_HOST=0.0.0.0 \
    NOZE_PORT=8787
VOLUME ["/data"]
EXPOSE 8787
CMD ["noze", "serve"]
