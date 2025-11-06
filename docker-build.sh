#!/bin/bash
# Baut das Docker Image

echo "Building Paperless AI Agent Docker Image..."
docker-compose build

echo ""
echo "Image erfolgreich gebaut!"
echo ""
echo "Nächste Schritte:"
echo "  1. Erstellen Sie .env Datei (cp .env.example .env)"
echo "  2. Tragen Sie Ihre Konfiguration ein"
echo "  3. Starten Sie mit: ./docker-start.sh"
