#!/bin/bash
# Startet den Agent Container

# Prüfe ob .env existiert
if [ ! -f ".env" ]; then
    echo "FEHLER: .env Datei nicht gefunden!"
    echo "Bitte erstellen Sie eine .env Datei:"
    echo "  cp .env.example .env"
    echo "  nano .env"
    exit 1
fi

# Erstelle logs Verzeichnis
mkdir -p logs

echo "Starte Paperless AI Agent Container..."
docker-compose up -d

echo ""
echo "Container gestartet!"
echo ""
echo "Nützliche Befehle:"
echo "  docker-compose logs -f     # Logs anzeigen"
echo "  docker-compose ps          # Status prüfen"
echo "  docker-compose stop        # Container stoppen"
echo "  docker-compose down        # Container entfernen"
