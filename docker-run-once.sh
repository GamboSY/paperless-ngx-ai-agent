#!/bin/bash
# Führt den Agent einmalig aus (nicht als Daemon)

# Prüfe ob .env existiert
if [ ! -f ".env" ]; then
    echo "FEHLER: .env Datei nicht gefunden!"
    exit 1
fi

# Erstelle logs Verzeichnis
mkdir -p logs

echo "Führe Paperless AI Agent einmalig aus..."
echo ""

docker-compose run --rm paperless-ai-agent python main.py "$@"
