# Paperless-NGX AI Agent - Architektur-Dokumentation

## 📋 Übersicht

Der Paperless-NGX AI Agent besteht aus zwei Hauptsystemen:
1. **Dokumenten-Klassifizierung**: Automatische Metadaten-Extraktion
2. **Q&A-System**: Semantische Suche und natürlichsprachliche Fragen

## 🏗️ System-Architektur

```mermaid
graph TB
    subgraph "Frontend"
        UI[Web Interface<br/>Bootstrap + JavaScript]
    end

    subgraph "Backend - Flask Web App"
        API[Flask REST API<br/>web_app.py]
    end

    subgraph "Klassifizierung"
        DB[(SQLite DB<br/>database.py)]
        CLASSIFIER[Ollama Classifier<br/>ollama_classifier.py]
        PC[Paperless Client<br/>paperless_client.py]
    end

    subgraph "Q&A System"
        QA[QA System<br/>qa_system.py]
        EMB[Embedding Service<br/>embedding_service.py]
        VS[(Vector Store<br/>ChromaDB)]
        IDX[Document Indexer<br/>document_indexer.py]
        META[Metadata Extractor<br/>metadata_extractor.py]
    end

    subgraph "Externe Services"
        PAPERLESS[Paperless-NGX<br/>192.168.2.198:8000]
        OLLAMA[Ollama Server<br/>192.168.2.139:11434]
    end

    UI <-->|HTTP/JSON| API
    API --> DB
    API --> PC
    API --> QA

    PC <-->|REST API| PAPERLESS
    CLASSIFIER <-->|Generate| OLLAMA
    EMB <-->|Embeddings| OLLAMA

    QA --> EMB
    QA --> VS
    QA --> META
    QA --> CLASSIFIER

    IDX --> PC
    IDX --> EMB
    IDX --> VS

    style UI fill:#1e3a8a,stroke:#60a5fa,stroke-width:2px,color:#fff
    style API fill:#ea580c,stroke:#fb923c,stroke-width:2px,color:#fff
    style QA fill:#7e22ce,stroke:#a855f7,stroke-width:2px,color:#fff
    style VS fill:#15803d,stroke:#4ade80,stroke-width:2px,color:#fff
    style OLLAMA fill:#b91c1c,stroke:#f87171,stroke-width:2px,color:#fff
    style PAPERLESS fill:#b91c1c,stroke:#f87171,stroke-width:2px,color:#fff
```

## 🔄 Hauptprozesse

### 1. Dokumenten-Klassifizierung

```mermaid
sequenceDiagram
    participant User
    participant UI as Web Interface
    participant API as Flask API
    participant PC as Paperless Client
    participant CLS as Ollama Classifier
    participant DB as SQLite Database
    participant PL as Paperless-NGX
    participant OL as Ollama Server

    User->>UI: Klick "Dokumente verarbeiten"
    UI->>API: POST /api/documents/process

    API->>DB: Prüfe ob bereits verarbeitet
    DB-->>API: Status

    API->>PC: get_documents_by_tag("KI")
    PC->>PL: GET /api/documents/?tags__id__in=42
    PL-->>PC: Liste von Dokumenten (mit Pagination)
    PC-->>API: Dokumente

    loop Für jedes Dokument
        API->>PC: get_document_content(doc_id)
        PC->>PL: GET /api/documents/{id}/
        PL-->>PC: OCR-Text

        API->>CLS: classify_document(text)
        CLS->>OL: POST /api/generate (qwen2.5:14b)
        OL-->>CLS: JSON mit Metadaten
        CLS-->>API: Klassifizierung

        API->>CLS: validate_classification()
        CLS-->>API: Validierte Daten

        API->>PC: update_document(doc_id, updates)
        PC->>PL: PATCH /api/documents/{id}/
        PL-->>PC: Erfolg

        API->>DB: add_processed_document()
        DB-->>API: Gespeichert
    end

    API-->>UI: Ergebnisse
    UI-->>User: Anzeige Statistiken
```


**Komponenten-Details:**

- **paperless_client.py**: Kommunikation mit Paperless-NGX API
  - `get_documents_by_tag()`: Holt Dokumente mit "KI" Tag (mit Pagination)
  - `get_document_content()`: Holt OCR-Text
  - `update_document()`: Aktualisiert Metadaten
  - `get_all_tags/correspondents/document_types()`: Metadaten-Verwaltung

- **ollama_classifier.py**: LLM-Integration
  - `classify_document()`: Sendet Text an Ollama für Klassifizierung
  - `validate_classification()`: Prüft ob Werte in config.py existieren
  - `generate()`: Allgemeine Text-Generierung für Q&A

- **database.py**: Persistenz
  - Speichert verarbeitete Dokumente (keine Duplikate)
  - Tracking von Erfolg/Fehler
  - Statistiken für Dashboard

### 2. Q&A-System - Dokumenten-Indexierung

```mermaid
sequenceDiagram
    participant User
    participant UI as Web Interface
    participant API as Flask API
    participant IDX as Document Indexer
    participant PC as Paperless Client
    participant EMB as Embedding Service
    participant VS as Vector Store (ChromaDB)
    participant PL as Paperless-NGX
    participant OL as Ollama Server

    User->>UI: Klick "Dokumente indexieren"
    UI->>API: POST /api/qa/index-documents

    API->>IDX: index_all_documents()
    IDX->>PC: get_all_documents()
    PC->>PL: GET /api/documents/ (alle, mit Pagination)
    PL-->>PC: Alle Dokumente
    PC-->>IDX: Dokumenten-Liste

    loop Für jedes Dokument
        IDX->>VS: document_exists(doc_id_chunk_0)?
        VS-->>IDX: Nein

        IDX->>PC: get_document(doc_id)
        PC->>PL: GET /api/documents/{id}/
        PL-->>PC: Dokument mit Content

        IDX->>IDX: _chunk_text(content)<br/>Teilt in 1500-Zeichen-Chunks<br/>mit 200 Zeichen Überlappung

        loop Für jeden Chunk
            IDX->>EMB: generate_embedding(chunk_text)
            EMB->>OL: POST /api/embeddings<br/>(mxbai-embed-large)
            OL-->>EMB: Embedding-Vektor [1024D]
            EMB-->>IDX: Embedding

            IDX->>VS: add_document(doc_id_chunk_X, text, embedding, metadata)
            VS-->>IDX: Gespeichert in ChromaDB
        end
    end

    API-->>UI: Statistiken (indexed/skipped/failed)
    UI-->>User: Anzeige Status
```

**Komponenten-Details:**

- **document_indexer.py**: Dokument-Indexierung
  - `index_all_documents()`: Indexiert alle Paperless-Dokumente
  - `_chunk_text()`: Teilt lange Dokumente in überlappende Chunks
  - `index_document()`: Indexiert einzelnes Dokument mit allen Chunks
  - Smart Chunking bei Satzgrenzen (`.` und `\n`)

- **embedding_service.py**: Embedding-Generierung
  - Kommuniziert mit Ollama Embedding API
  - Unterstützt verschiedene Modelle (mxbai-embed-large, nomic-embed-text)
  - Caching für Performance

- **vector_store.py**: Persistente Vektor-Datenbank
  - ChromaDB für semantische Suche
  - Speichert Embeddings + Metadaten + Text
  - Unterstützt Chunk-basierte Dokumente
  - Deduplizierung basierend auf doc_id_original

### 3. Q&A-System - Frage beantworten

```mermaid
sequenceDiagram
    participant User
    participant UI as Web Interface
    participant API as Flask API
    participant QA as QA System
    participant META as Metadata Extractor
    participant EMB as Embedding Service
    participant VS as Vector Store
    participant CLS as Ollama Classifier
    participant OL as Ollama Server

    User->>UI: Stellt Frage:<br/>"Welche Steuer-ID hat MAX?"
    UI->>API: POST /api/qa/ask

    API->>QA: answer_question(question, n_context_docs=5)

    alt Multi-Query aktiviert (USE_MULTI_QUERY=true)
        QA->>QA: _generate_multi_queries(question, n=2)
        QA->>CLS: Generiere alternative Formulierungen
        CLS->>OL: POST /api/generate<br/>Prompt: "Generiere 2 Varianten"
        OL-->>CLS: Varianten
        CLS-->>QA: ["Original", "Variante 1", "Variante 2"]
    end

    QA->>QA: _expand_query(question)
    Note over QA: Synonym-Map: "steuer id" →<br/>["Steuer-ID", "Steuernummer",<br/>"Tax ID", "TIN"]

    loop Für jede Query-Variante
        QA->>EMB: generate_embedding(expanded_query)
        EMB->>OL: POST /api/embeddings
        OL-->>EMB: Query-Embedding [1024D]

        QA->>VS: search(query_embedding, n_results=10)
        Note over VS: Cosine-Similarity-Suche<br/>über alle Chunks
        VS-->>QA: Relevante Chunks mit Distances
    end

    QA->>QA: Deduplizierung nach doc_id
    QA->>QA: Re-Ranking nach Distance
    QA->>QA: Top N Dokumente auswählen

    QA->>QA: _create_rag_prompt(question, context)
    Note over QA: Erstellt strukturierten Prompt<br/>mit allen relevanten Chunks

    QA->>CLS: generate(rag_prompt)
    CLS->>OL: POST /api/generate<br/>(qwen2.5:14b)
    OL-->>CLS: Antwort

    QA->>QA: _estimate_confidence(docs, answer)
    Note over QA: Multi-Faktor-Analyse:<br/>- Avg Distance (40%)<br/>- Best Match (30%)<br/>- Anzahl Docs (15%)<br/>- Antwort-Qualität (15%)

    QA-->>API: {answer, sources, confidence}
    API-->>UI: JSON Response
    UI-->>User: Anzeige Antwort + Quellen + Konfidenz
```

**Komponenten-Details:**

- **qa_system.py**: Hauptlogik für Q&A
  - `answer_question()`: RAG-Pipeline (Retrieval + Augmentation + Generation)
  - `_generate_multi_queries()`: Generiert alternative Frageformulierungen
  - `_expand_query()`: Synonym-Expansion (hardcoded + optional LLM)
  - `search_documents()`: Semantische Suche mit Filtern
  - `search_documents_multi()`: Multi-Query mit Deduplizierung
  - `_estimate_confidence()`: 4-Faktor Konfidenz-Bewertung

- **metadata_extractor.py**: Intelligente Filter-Extraktion
  - Extrahiert Filter aus natürlichsprachigen Fragen
  - Hybrid: Regex (schnell) + LLM (intelligent)
  - Erkennt: Dokumenttyp, Korrespondent, Jahr, Tags

### 4. Erweiterte Suche mit Filtern

```mermaid
sequenceDiagram
    participant User
    participant UI as Web Interface
    participant API as Flask API
    participant QA as QA System
    participant VS as Vector Store

    User->>UI: Wählt Filter:<br/>Typ="Rechnung"<br/>Korrespondent="Amazon"<br/>Jahr=2024
    User->>UI: Fragt: "Wie viel bezahlt?"

    UI->>API: POST /api/qa/ask<br/>{question, filters}

    API->>QA: search_documents_multi(query, filters)

    QA->>VS: search(embedding, where={<br/>document_type: "Rechnung",<br/>correspondent: "Amazon"})
    Note over VS: ChromaDB native Filterung
    VS-->>QA: Gefilterte Ergebnisse

    QA->>QA: Post-Filterung für Jahr & Tags
    Note over QA: Jahr: metadata.created startsWith "2024"<br/>Tags: metadata.tags contains filter_tags

    QA-->>API: Gefilterte + deduplizierte Ergebnisse

    API->>API: RAG mit gefilterten Dokumenten
    API-->>UI: Antwort nur basierend auf<br/>Amazon-Rechnungen aus 2024
    UI-->>User: Präzise, gefilterte Antwort
```

## 📁 Datei-Struktur & Verantwortlichkeiten

```
paperless_ai_agent/
│
├── 🌐 Frontend
│   ├── templates/index.html          # Web-UI (Bootstrap 5)
│   └── static/js/app.js               # Frontend-Logik (JavaScript)
│
├── 🔧 Backend Core
│   ├── web_app.py                     # Flask REST API (Haupteinstieg)
│   ├── main.py                        # CLI für Batch-Verarbeitung
│   └── config.py                      # Konfiguration (Typen, Tags, etc.)
│
├── 📄 Klassifizierung
│   ├── paperless_client.py            # Paperless-NGX API Client
│   ├── ollama_classifier.py           # Ollama LLM Integration
│   └── database.py                    # SQLite für verarbeitete Dokumente
│
├── 🤖 Q&A System
│   ├── qa_system.py                   # Hauptlogik (RAG, Multi-Query)
│   ├── embedding_service.py           # Ollama Embeddings
│   ├── vector_store.py                # ChromaDB Wrapper
│   ├── document_indexer.py            # Dokument-Chunking & Indexierung
│   └── metadata_extractor.py          # Filter-Extraktion aus Queries
│
├── 🐳 Deployment
│   ├── Dockerfile                     # Container-Image
│   ├── docker-compose.yml             # Service-Definition
│   ├── docker-entrypoint.sh           # Startup-Script
│   └── requirements.txt               # Python Dependencies
│
└── 📝 Dokumentation
    ├── README.md                      # Benutzer-Dokumentation
    ├── ARCHITECTURE.md                # Diese Datei
    └── .env.example                   # Konfigurations-Template
```

## 🔀 Datenflüsse

### Klassifizierungs-Datenfluss

```mermaid
graph LR
    A[Paperless-NGX<br/>Tag: KI] -->|OCR-Text| B[Ollama Classifier]
    B -->|JSON Metadaten| C[Validation]
    C -->|Dokument Updates| D[Paperless-NGX]
    C -->|Tracking| E[(SQLite DB)]

    style A fill:#b91c1c,stroke:#f87171,stroke-width:2px,color:#fff
    style B fill:#1e3a8a,stroke:#60a5fa,stroke-width:2px,color:#fff
    style C fill:#ea580c,stroke:#fb923c,stroke-width:2px,color:#fff
    style D fill:#b91c1c,stroke:#f87171,stroke-width:2px,color:#fff
    style E fill:#15803d,stroke:#4ade80,stroke-width:2px,color:#fff
```

### Q&A Datenfluss

```mermaid
graph TB
    A[Paperless Dokument] -->|OCR-Text| B[Text Chunking]
    B -->|Chunks| C[Embedding Service]
    C -->|Vektoren| D[(ChromaDB<br/>Vector Store)]

    E[User Frage] -->|Text| F[Query Expansion<br/>+ Multi-Query]
    F -->|Erweiterte Queries| G[Embedding Service]
    G -->|Query Vektoren| H[Semantic Search]
    D -->|Similarity| H

    H -->|Top N Chunks| I[RAG Prompt]
    I -->|Context + Question| J[Ollama LLM]
    J -->|Antwort| K[Confidence Scoring]
    K -->|Final Result| L[User]

    style D fill:#15803d,stroke:#4ade80,stroke-width:2px,color:#fff
    style J fill:#1e3a8a,stroke:#60a5fa,stroke-width:2px,color:#fff
    style K fill:#7e22ce,stroke:#a855f7,stroke-width:2px,color:#fff
```

## 🧩 Komponenten-Interaktionen

### Web Interface → Backend

```mermaid
graph LR
    subgraph "Frontend (Browser)"
        UI[JavaScript]
    end

    subgraph "Backend API Endpoints"
        A[api/settings]
        B[api/documents/process]
        C[api/qa/ask]
        D[api/qa/search]
        E[api/qa/index-documents]
        F[api/qa/metadata-options]
    end

    UI -->|GET/POST| A
    UI -->|POST| B
    UI -->|POST| C
    UI -->|POST| D
    UI -->|POST| E
    UI -->|GET| F

    style UI fill:#1e3a8a,stroke:#60a5fa,stroke-width:2px,color:#fff
```

### Backend → Externe Services

```mermaid
graph TB
    subgraph "Backend Services"
        PC[Paperless Client]
        CLS[Ollama Classifier]
        EMB[Embedding Service]
    end

    subgraph "Externe APIs"
        PL[Paperless-NGX<br/>:8000/api/]
        OL1[Ollama<br/>:11434/api/generate]
        OL2[Ollama<br/>:11434/api/embeddings]
    end

    PC -->|REST API| PL
    CLS -->|HTTP POST| OL1
    EMB -->|HTTP POST| OL2

    style PL fill:#b91c1c,stroke:#f87171,stroke-width:2px,color:#fff
    style OL1 fill:#b91c1c,stroke:#f87171,stroke-width:2px,color:#fff
    style OL2 fill:#b91c1c,stroke:#f87171,stroke-width:2px,color:#fff
```

## 🗄️ Datenbanken & Persistenz

### SQLite Database Schema (database.py)

```sql
CREATE TABLE processed_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL UNIQUE,
    document_title TEXT,
    classification_result TEXT,  -- JSON
    success BOOLEAN,
    error_message TEXT,
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_document_id ON processed_documents(document_id);
CREATE INDEX idx_success ON processed_documents(success);
```

**Zweck:** Verhindert doppelte Verarbeitung, speichert Klassifizierungs-Historie

### ChromaDB Collections (vector_store.py)

```
Collection: "paperless_documents"
├── Documents (Chunks)
│   ├── id: "doc_123_chunk_0", "doc_123_chunk_1", ...
│   ├── embedding: [1024D float vector]
│   ├── document: "Text preview (500 chars)"
│   └── metadata:
│       ├── title: "2024-01-15_rechnung_amazon_MAX"
│       ├── correspondent: "Amazon"
│       ├── document_type: "Rechnung"
│       ├── created: "2024-01-15"
│       ├── tags: "MAX,wichtig"
│       ├── chunk_number: "0"
│       ├── total_chunks: "3"
│       └── doc_id_original: "123"
```

**Zweck:** Semantische Suche, RAG Context Retrieval

## ⚙️ Konfiguration & Environment

### Wichtige .env Variablen

```bash
# Paperless-NGX
PAPERLESS_URL=http://192.168.2.198:8000
PAPERLESS_TOKEN=your_token_here

# Ollama Server
OLLAMA_URL=http://192.168.2.139:11434
OLLAMA_MODEL=qwen2.5:14b-instruct       # LLM für Klassifizierung + Q&A
EMBEDDING_MODEL=mxbai-embed-large       # Embedding-Modell

# Q&A Features
USE_LLM_EXPANSION=false                 # LLM-basierte Query Expansion
USE_MULTI_QUERY=true                    # Multi-Query Approach (empfohlen!)
```

### Docker-Konfiguration

```yaml
# docker-compose.yml
services:
  paperless-ai-agent:
    build: .
    network_mode: host                  # Zugriff auf localhost:8000
    environment:
      - TZ=Europe/Berlin                # Timezone
    volumes:
      - ./data:/app/data                # Persistente Daten
      - ./logs:/app/logs                # Logs
    restart: unless-stopped
```

## 🚀 Performance-Optimierungen

### 1. Chunking-Strategie
- **Chunk-Größe**: 1500 Zeichen
- **Überlappung**: 200 Zeichen
- **Splitting**: An Satzgrenzen (`.` oder `\n`)
- **Vorteil**: 100% Dokument-Abdeckung, keine Information verloren

### 2. Multi-Query Approach
- **Varianten**: 2 alternative Formulierungen
- **Deduplizierung**: Nach `doc_id_original`
- **Re-Ranking**: Nach Similarity-Distance
- **Vorteil**: ~20-30% bessere Recall-Rate

### 3. Query Expansion
- **Hardcoded**: Schnelle Synonym-Map für häufige Begriffe
- **LLM-basiert**: Optional für unbekannte Begriffe
- **Vorteil**: Erkennt "Steuer-ID" = "Steuernummer" = "Tax ID"

### 4. Confidence Scoring
- **Multi-Faktor**: 4 unabhängige Metriken
- **Thresholds**: high ≥70%, medium ≥45%
- **Vorteil**: Zuverlässige Qualitäts-Einschätzung

### 5. Pagination
- **Alle API-Calls**: Vollständige Pagination
- **Page-Size**: 100 Dokumente pro Request
- **Vorteil**: Funktioniert mit >1000 Dokumenten

## 🔒 Sicherheit & Datenschutz

### Datenschutz
- ✅ **100% Lokal**: Alle Daten bleiben auf Ihrem Server
- ✅ **Keine Cloud**: Kein externes API-Gateway
- ✅ **Ollama Self-Hosted**: LLM läuft auf eigenem Server

### Sicherheits-Features
- ✅ **Token-basierte Auth**: Paperless-NGX API Token
- ✅ **Network Isolation**: Docker host network mode
- ✅ **Non-Root User**: Container läuft als User 1000
- ✅ **.env Protection**: Secrets nicht in Git

## 📊 Monitoring & Debugging

### Logging-Strategie

```python
# Alle Module nutzen Python logging
import logging
logger = logging.getLogger(__name__)

# Log-Level
logger.info("Normale Operation")
logger.warning("Warnung, aber fortsetzbar")
logger.error("Fehler, Dokument übersprungen")
logger.debug("Detaillierte Debug-Info")
```

### Log-Ausgaben

```bash
# Docker Logs
docker-compose logs -f

# Filterte Logs
docker-compose logs | grep "QASystem"
docker-compose logs | grep "ERROR"

# Log-Dateien
./logs/paperless_ai_agent.log
./data/processed_documents.db
./data/chromadb/
```

### Health Checks

```bash
# Container Status
docker-compose ps

# Embedding Test
curl http://localhost:5000/api/qa/test-embedding

# Paperless Connection
curl http://192.168.2.198:8000/api/documents/ \
  -H "Authorization: Token YOUR_TOKEN"

# Ollama Status
curl http://192.168.2.139:11434/api/tags
```

## 🎯 Best Practices

### Für Klassifizierung
1. **Modell**: qwen2.5:14b-instruct (beste Balance)
2. **Batch-Size**: 10-20 Dokumente pro Durchlauf
3. **Validation**: Immer config.py prüfen
4. **Error Handling**: Dokumente bei Fehler nicht blockieren

### Für Q&A
1. **Embedding-Modell**: mxbai-embed-large (beste Qualität)
2. **Multi-Query**: Aktiviert lassen (USE_MULTI_QUERY=true)
3. **Context Docs**: 3-5 Dokumente für Kontext
4. **Re-Indexierung**: Nach Embedding-Modell-Wechsel notwendig

### Für Performance
1. **Ollama RAM**: Mind. 8GB für qwen2.5:14b
2. **ChromaDB**: SSD für schnelle Vector-Suche
3. **Pagination**: Überall implementiert
4. **Caching**: Embedding-Service cached Requests

## 🔄 Update-Strategie

```bash
# 1. Neue Version pullen
git pull origin master

# 2. Dependencies aktualisieren
pip install -r requirements.txt

# 3. Docker neu bauen
docker-compose build

# 4. Migration falls nötig
# (z.B. ChromaDB Schema-Änderungen)

# 5. Container neu starten
docker-compose down
docker-compose up -d

# 6. Logs prüfen
docker-compose logs -f
```

## 📚 Weitere Ressourcen

- **GitHub**: https://github.com/GamboSY/paperless_ai_agent
- **Paperless-NGX Docs**: https://docs.paperless-ngx.com/
- **Ollama Docs**: https://ollama.com/
- **ChromaDB Docs**: https://docs.trychroma.com/

---

**Version**: 1.0.0
**Letzte Aktualisierung**: 2025-01-06
**Maintainer**: GamboSY
