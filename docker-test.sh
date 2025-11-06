#!/bin/bash
# Testet die Verbindungen

if [ ! -f ".env" ]; then
    echo "FEHLER: .env Datei nicht gefunden!"
    exit 1
fi

echo "Teste Verbindungen..."
docker-compose run --rm paperless-ai-agent python test_connection.py
