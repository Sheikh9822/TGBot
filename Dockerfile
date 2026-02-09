FROM python:3.11-slim-bookworm
RUN apt-get update && apt-get install -y \
    python3-libtorrent \
    ffmpeg \
    mediainfo \
    && rm -rf /var/lib/apt/lists/*
ENV PYTHONPATH="/usr/lib/python3/dist-packages"
ENV PYTHONUNBUFFERED=1
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir -r requirements.txt
CMD gunicorn app:app --bind 0.0.0.0:$PORT --daemon && python3 bot.py
