#!/usr/bin/env python3
"""
Test-Skript um die Verbindungen zu Paperless-NGX und Ollama zu prüfen
"""
import os
import sys
from dotenv import load_dotenv
import requests

def test_paperless_connection(url, token):
    """
    Testet Verbindung zu Paperless-NGX
    """
    print(f"\n[1] Teste Paperless-NGX Verbindung: {url}")
    try:
        headers = {'Authorization': f'Token {token}'}
        response = requests.get(f'{url}/api/documents/', headers=headers, timeout=10)
        response.raise_for_status()

        doc_count = response.json()['count']
        print(f"    ✓ Verbindung erfolgreich!")
        print(f"    ✓ {doc_count} Dokumente gefunden")
        return True
    except requests.exceptions.RequestException as e:
        print(f"    ✗ Fehler: {e}")
        return False

def test_ollama_connection(url, model):
    """
    Testet Verbindung zu Ollama
    """
    print(f"\n[2] Teste Ollama Verbindung: {url}")
    try:
        # Teste API Verfügbarkeit
        response = requests.get(f'{url}/api/tags', timeout=10)
        response.raise_for_status()

        models = response.json().get('models', [])
        model_names = [m['name'] for m in models]

        print(f"    ✓ Verbindung erfolgreich!")
        print(f"    ✓ {len(models)} Modelle verfügbar: {', '.join(model_names)}")

        # Prüfe ob gewünschtes Modell verfügbar ist
        if model in model_names:
            print(f"    ✓ Modell '{model}' ist verfügbar")
        else:
            print(f"    ✗ WARNUNG: Modell '{model}' nicht gefunden!")
            print(f"    Verfügbare Modelle: {', '.join(model_names)}")
            return False

        # Teste einfache Generation
        print(f"    Teste Generierung mit {model}...")
        test_response = requests.post(
            f'{url}/api/generate',
            json={
                'model': model,
                'prompt': 'Sage nur "OK"',
                'stream': False
            },
            timeout=30
        )
        test_response.raise_for_status()
        result = test_response.json().get('response', '').strip()
        print(f"    ✓ Test-Generierung erfolgreich: '{result}'")

        return True
    except requests.exceptions.RequestException as e:
        print(f"    ✗ Fehler: {e}")
        return False

def main():
    """
    Hauptfunktion
    """
    print("=" * 60)
    print("Paperless-NGX AI Agent - Verbindungstest")
    print("=" * 60)

    # Lade .env
    if not os.path.exists('.env'):
        print("\n✗ FEHLER: .env Datei nicht gefunden!")
        print("  Erstellen Sie eine .env Datei basierend auf .env.example")
        sys.exit(1)

    load_dotenv()

    # Hole Konfiguration
    paperless_url = os.getenv('PAPERLESS_URL')
    paperless_token = os.getenv('PAPERLESS_TOKEN')
    ollama_url = os.getenv('OLLAMA_URL')
    ollama_model = os.getenv('OLLAMA_MODEL')

    # Prüfe ob alle Variablen gesetzt sind
    missing = []
    if not paperless_url:
        missing.append('PAPERLESS_URL')
    if not paperless_token:
        missing.append('PAPERLESS_TOKEN')
    if not ollama_url:
        missing.append('OLLAMA_URL')
    if not ollama_model:
        missing.append('OLLAMA_MODEL')

    if missing:
        print(f"\n✗ FEHLER: Fehlende Umgebungsvariablen in .env:")
        for var in missing:
            print(f"  - {var}")
        sys.exit(1)

    # Teste Verbindungen
    paperless_ok = test_paperless_connection(paperless_url, paperless_token)
    ollama_ok = test_ollama_connection(ollama_url, ollama_model)

    # Zusammenfassung
    print("\n" + "=" * 60)
    print("Zusammenfassung")
    print("=" * 60)

    if paperless_ok and ollama_ok:
        print("✓ Alle Tests erfolgreich!")
        print("\nSie können jetzt den Agent starten mit:")
        print("  python main.py --dry-run    # Zum Testen ohne Änderungen")
        print("  python main.py              # Für echte Verarbeitung")
        sys.exit(0)
    else:
        print("✗ Einige Tests sind fehlgeschlagen")
        print("  Bitte beheben Sie die Fehler und versuchen Sie es erneut")
        sys.exit(1)

if __name__ == '__main__':
    main()
