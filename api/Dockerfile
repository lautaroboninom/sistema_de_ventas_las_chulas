FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /code

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    # Runtime libs for Pillow/Pillow-HEIF (Debian 12/Bookworm)
    libheif1 libde265-0 libx265-199 \
    libjpeg62-turbo libpng16-16 zlib1g libopenjp2-7 libtiff6 libwebp7 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . /code
