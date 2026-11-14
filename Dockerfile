# One image for Docker/Dockge and the Home Assistant app. The two small stages below only
# add the architecture label Home Assistant's Supervisor reads (io.hass.arch); Home Assistant
# calls arm64 "aarch64". Docker picks the stage that matches the platform being built.
FROM python:3.13-slim AS base-amd64
LABEL io.hass.arch="amd64"

FROM python:3.13-slim AS base-arm64
LABEL io.hass.arch="aarch64"

FROM base-${TARGETARCH}

ARG VERSION=dev

# io.hass.* labels: what the Supervisor expects on an app image that is not built with
# Home Assistant's own builder (https://contributors.home-assistant.io/apps/guides/dockerfile/).
LABEL org.opencontainers.image.source="https://github.com/sevagjb/TileMark" \
      org.opencontainers.image.description="A tiny self-hosted page for your links, with thumbnails and groups" \
      org.opencontainers.image.licenses="MIT" \
      io.hass.type="app" \
      io.hass.version="${VERSION}"

ENV TILEMARK_VERSION=$VERSION
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DATA_DIR=/data
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY pages ./pages

VOLUME /data
EXPOSE 8080

# Marks the container unhealthy when TileMark stops answering. Docker/Dockge show it, and
# Home Assistant's Supervisor restarts the app when it is unhealthy (its watchdog uses this
# check, so the app's config.yaml needs no "watchdog" line).
HEALTHCHECK --interval=60s --timeout=5s --start-period=30s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=4)"]

# One worker on purpose: thumbnail fetching runs in a thread pool inside it.
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "--threads", "8", "--timeout", "120", "app:app"]
