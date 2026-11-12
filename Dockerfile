FROM python:3.13-slim

LABEL org.opencontainers.image.source="https://github.com/sevagjb/linkboard" \
      org.opencontainers.image.description="A tiny self-hosted page for your links, with thumbnails and groups" \
      org.opencontainers.image.licenses="MIT"

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DATA_DIR=/data
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY pages ./pages

VOLUME /data
EXPOSE 8080

# One worker on purpose: thumbnail fetching runs in a thread pool inside it.
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "--threads", "8", "--timeout", "120", "app:app"]
