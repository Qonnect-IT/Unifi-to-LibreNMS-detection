FROM python:3.12-alpine

LABEL org.opencontainers.image.authors="Qonnect-IT <info@qonnect-it.nl>"
LABEL org.opencontainers.image.title="unifi-librenms-discovery"
LABEL org.opencontainers.image.description="LibreNMS helper container for UniFi AP discovery and polling"
LABEL org.opencontainers.image.source="https://github.com/Qonnect-IT/Unifi-to-LibreNMS-detection"
LABEL org.opencontainers.image.licenses="MIT"

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apk upgrade --no-cache \
    && python -m pip install --no-cache-dir --upgrade "pip==26.1.2" \
    && adduser -D -h /app appuser

COPY requirements.txt .
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY sync.py .

USER appuser

CMD ["python", "/app/sync.py"]
