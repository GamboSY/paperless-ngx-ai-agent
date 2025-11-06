# Paperless-NGX AI Agent 🤖

Intelligenter AI Agent für Paperless-NGX mit automatischer Dokumentenklassifizierung und natürlichsprachlichem Q&A-System. 100% lokal mit Ollama.

## 🌟 Features

- **Automatische Dokumenten-Klassifizierung**: Dokumententyp, Korrespondent, Person-Tags und Datum
- **Semantische Suche**: RAG-basiertes Q&A über alle Dokumente
- **Multi-Query Approach**: Verbesserte Suchgenauigkeit durch alternative Frageformulierungen
- **Erweiterte Filter**: Suche nach Dokumenttyp, Korrespondent, Tags und Jahr
- **Web-Oberfläche**: Einfache Verwaltung und Überwachung
- **100% Lokal**: Keine Cloud-Anbindung, alle Daten auf Ihrem Server

## Voraussetzungen

- Docker & Docker Compose
- Paperless-NGX Installation
- Ollama Server (kann auf separatem Server laufen)

## 🚀 Schnellstart

### 1. Repository clonen

```bash
cd /opt
git clone <REPOSITORY_URL> paperless-ai-agent
cd paperless-ai-agent
```

### 2. Konfiguration erstellen

```bash
cp .env.example .env
nano .env
```

**Wichtige Einstellungen:**
```env
PAPERLESS_URL=http://localhost:8000
PAPERLESS_TOKEN=your_token_here
OLLAMA_URL=http://your-ollama-server:11434
OLLAMA_MODEL=qwen2.5:14b-instruct
EMBEDDING_MODEL=mxbai-embed-large
```

**API Token erstellen:**
1. In Paperless-NGX einloggen
2. Settings → Profile → API Token
3. Token generieren und in `.env` eintragen

### 3. Metadaten konfigurieren

Bearbeiten Sie `config.py` und tragen Sie Ihre eigenen Werte ein:

```python
DOCUMENT_TYPES = [
    "Rechnung",
    "Vertrag",
    # Ihre Dokumenttypen...
]

PERSON_TAGS = [
    "Person1",
    "Person2",
    # Ihre Person-Tags...
]

CORRESPONDENTS = [
    "Amazon",
    "Bank",
    # Ihre Korrespondenten...
]
```

### 4. Ollama Modelle installieren

```bash
ollama pull qwen2.5:14b-instruct
ollama pull mxbai-embed-large
```

### 5. Agent starten

```bash
chmod +x *.sh
./docker-build.sh
docker-compose up -d
```

**Web-Oberfläche:** http://localhost:5000

## 📖 Verwendung

### Dokumenten-Klassifizierung

1. Laden Sie ein Dokument in Paperless-NGX hoch
2. Vergeben Sie den Tag **"KI"**
3. Öffnen Sie die Web-Oberfläche (http://localhost:5000)
4. Klicken Sie auf "Alle verarbeiten" im Tab "Dokumente"
5. Das Dokument wird automatisch klassifiziert

### Dokumenten-Chat & Q&A

**1. Dokumente indexieren:**
- Gehen Sie zum Tab "Dokumenten-Chat"
- Klicken Sie auf "Dokumente indexieren"
- Warten Sie bis die Indexierung abgeschlossen ist

**2. Fragen stellen:**
```
"Welche Steuer-ID hat Person X?"
"Wie viel habe ich bei Amazon ausgegeben?"
"Zeige mir alle Verträge von 2024"
```

**3. Erweiterte Suche mit Filtern:**
- Tab "Erweiterte Suche"
- Filter setzen (Dokumenttyp, Korrespondent, Tags, Jahr)
- Gefilterte Suche oder Q&A

## ⚙️ Empfohlene Modelle

### LLM-Modell (Klassifizierung & Q&A)

**qwen2.5:14b-instruct** ⭐ EMPFOHLEN
- Beste Balance zwischen Qualität und Geschwindigkeit
- Exzellentes JSON-Verständnis
- Hervorragend für Q&A und RAG
- Läuft auf 16GB RAM

**qwen2.5:32b-instruct-q4_K_M** ⭐⭐ Höchste Qualität
- Beste Genauigkeit
- Benötigt ~14GB RAM

### Embedding-Modell (Semantische Suche)

**mxbai-embed-large** ⭐ BESTE Qualität
- 334M Parameter
- Höchste Präzision bei semantischer Suche

**nomic-embed-text** - Gute Alternative
- Schneller, gute Balance

## 🔧 Docker Befehle

```bash
# Logs ansehen
docker-compose logs -f

# Status prüfen
docker-compose ps

# Neustarten
docker-compose restart

# Stoppen
docker-compose stop

# Entfernen
docker-compose down

# Updates durchführen
git pull
./docker-build.sh
docker-compose restart
```

## 🛠️ Troubleshooting

### Keine Dokumente gefunden
- Tag "KI" in Paperless-NGX vergeben?
- API-Token korrekt in `.env`?

### Ollama Verbindung fehlgeschlagen
- Ollama Server läuft? `curl http://your-ollama:11434/api/tags`
- URL in `.env` korrekt?

### Docker Container startet nicht
```bash
docker-compose logs paperless-ai-agent
cat .env  # Konfiguration prüfen
```

### Q&A liefert schlechte Ergebnisse
- Multi-Query aktiviert? `USE_MULTI_QUERY=true` in `.env`
- Richtiges Embedding-Modell? `mxbai-embed-large` empfohlen
- Dokumente indexiert?

## 📚 Weitere Informationen

**Features:**
- Tracking bereits verarbeiteter Dokumente (keine Duplikate)
- Vollständige Dokumenten-Abdeckung mit Chunking
- Multi-Faktor Konfidenz-Bewertung
- Query Expansion für Synonyme
- Persistente Vector-Datenbank (ChromaDB)

**Performance-Optimierungen:**
- Chunk-Größe: 1500 Zeichen mit 200 Zeichen Überlappung
- Multi-Query Approach: ~20-30% bessere Recall-Rate
- Vollständige Pagination für >1000 Dokumente

## 🔒 Sicherheit

- ✅ 100% lokal - keine Cloud
- ✅ Token-basierte Authentifizierung
- ✅ `.env` Datei nicht in Git (automatisch ignoriert)

## Support

Bei Problemen:
1. Logs prüfen: `docker-compose logs -f`
2. Verbindung testen: Web-UI → "Test"-Buttons
3. GitHub Issues: [Repository URL]

## Lizenz

MIT
