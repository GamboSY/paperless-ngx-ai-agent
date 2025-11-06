#!/bin/bash
set -e

echo "========================================"
echo "Paperless-NGX AI Agent"
echo "========================================"

# Prüfe ob .env existiert
if [ ! -f "/app/.env" ]; then
    echo "WARNUNG: Keine .env Datei gefunden!"
    echo "Bitte mounten Sie eine .env Datei nach /app/.env"
    exit 1
fi

# Zeige Konfiguration (ohne Secrets)
echo "Konfiguration:"
source /app/.env
echo "  Paperless-NGX: ${PAPERLESS_URL}"
echo "  Ollama: ${OLLAMA_URL}"
echo "  Modell: ${OLLAMA_MODEL}"
echo "========================================"

# Führe übergebenen Befehl aus
exec "$@"
