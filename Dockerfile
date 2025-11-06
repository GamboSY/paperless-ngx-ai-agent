# Paperless-NGX AI Agent Docker Image
FROM python:3.11-slim

# Metadaten
LABEL maintainer="Paperless AI Agent"
LABEL description="Automatische Dokumentenklassifizierung für Paperless-NGX mit Ollama"

# Arbeitsverzeichnis erstellen
WORKDIR /app

# System-Dependencies installieren (falls benötigt)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    curl \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# Python Dependencies kopieren und installieren
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Anwendungscode kopieren
COPY config.py .
COPY paperless_client.py .
COPY ollama_classifier.py .
COPY main.py .
COPY test_connection.py .
COPY database.py .
COPY web_app.py .
COPY embedding_service.py .
COPY vector_store.py .
COPY document_indexer.py .
COPY qa_system.py .
COPY metadata_extractor.py .

# Web-Interface Dateien kopieren
COPY templates/ templates/
COPY static/ static/

# Entrypoint-Skript kopieren
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Log-Verzeichnis erstellen
RUN mkdir -p /app/logs

# Non-root User erstellen
RUN useradd -m -u 1000 paperless && \
    chown -R paperless:paperless /app

USER paperless

# Healthcheck
HEALTHCHECK --interval=5m --timeout=10s --start-period=30s --retries=3 \
    CMD python test_connection.py || exit 1

# Entrypoint
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]

# Default Command - Starte Web-Interface
CMD ["python", "web_app.py"]
