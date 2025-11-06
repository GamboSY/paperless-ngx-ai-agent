"""
Flask Web Interface für Paperless-NGX AI Agent
"""
import os
import json
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv, set_key, find_dotenv
from database import DocumentDatabase
from config import DOCUMENT_TYPES, PERSON_TAGS, CORRESPONDENTS
from paperless_client import PaperlessClient
from ollama_classifier import OllamaClassifier
from embedding_service import EmbeddingService
from vector_store import VectorStore
from document_indexer import DocumentIndexer
from qa_system import QASystem
import logging

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Flask App
app = Flask(__name__)
CORS(app)

# Datenverzeichnis erstellen falls nicht vorhanden
DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
os.makedirs(DATA_DIR, exist_ok=True)

# Database
DB_PATH = os.path.join(DATA_DIR, 'processed_documents.db')
db = DocumentDatabase(db_path=DB_PATH)

# .env Datei laden
load_dotenv()
ENV_FILE = find_dotenv()

# Q&A Services (lazy initialization - wird bei Bedarf initialisiert)
embedding_service = None
vector_store = None
document_indexer = None
qa_system = None


def get_qa_services():
    """Initialisiert Q&A Services wenn benötigt"""
    global embedding_service, vector_store, document_indexer, qa_system

    if qa_system is None:
        ollama_url = os.getenv('OLLAMA_URL', 'http://localhost:11434')
        embedding_model = os.getenv('EMBEDDING_MODEL', 'nomic-embed-text')

        # Embedding Service
        logger.info(f"Initialisiere Embedding Service mit Modell: {embedding_model}")
        embedding_service = EmbeddingService(ollama_url=ollama_url, model=embedding_model)

        # Vector Store
        vector_store_path = os.path.join(DATA_DIR, 'chromadb')
        vector_store = VectorStore(persist_directory=vector_store_path)

        # Document Indexer
        paperless_url = os.getenv('PAPERLESS_URL')
        paperless_token = os.getenv('PAPERLESS_TOKEN')
        if paperless_url and paperless_token:
            paperless_client = PaperlessClient(paperless_url, paperless_token)
            document_indexer = DocumentIndexer(paperless_client, embedding_service, vector_store)

        # Q&A System
        ollama_model = os.getenv('OLLAMA_MODEL', 'qwen2.5:14b-instruct')
        ollama_classifier = OllamaClassifier(ollama_url, ollama_model)
        qa_system = QASystem(embedding_service, vector_store, ollama_classifier)

        logger.info("Q&A Services initialisiert")

    return {
        'embedding_service': embedding_service,
        'vector_store': vector_store,
        'document_indexer': document_indexer,
        'qa_system': qa_system
    }


@app.route('/')
def index():
    """Hauptseite"""
    return render_template('index.html')


@app.route('/api/settings', methods=['GET'])
def get_settings():
    """Gibt aktuelle Einstellungen zurück"""
    settings = {
        'PAPERLESS_URL': os.getenv('PAPERLESS_URL', ''),
        'PAPERLESS_TOKEN': os.getenv('PAPERLESS_TOKEN', ''),
        'OLLAMA_URL': os.getenv('OLLAMA_URL', 'http://localhost:11434'),
        'OLLAMA_MODEL': os.getenv('OLLAMA_MODEL', 'qwen2.5:14b-instruct')
    }
    return jsonify(settings)


@app.route('/api/settings', methods=['POST'])
def update_settings():
    """Aktualisiert Einstellungen"""
    try:
        data = request.json

        if ENV_FILE:
            for key in ['PAPERLESS_URL', 'PAPERLESS_TOKEN', 'OLLAMA_URL', 'OLLAMA_MODEL']:
                if key in data:
                    set_key(ENV_FILE, key, data[key])

            # Umgebungsvariablen neu laden
            load_dotenv(override=True)

            return jsonify({'success': True, 'message': 'Einstellungen gespeichert'})
        else:
            return jsonify({'success': False, 'message': '.env Datei nicht gefunden'}), 404
    except Exception as e:
        logger.error(f"Error updating settings: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/config', methods=['GET'])
def get_config():
    """Gibt Konfiguration zurück (Dokumententypen, Tags, Korrespondenten)"""
    return jsonify({
        'document_types': DOCUMENT_TYPES,
        'person_tags': PERSON_TAGS,
        'correspondents': CORRESPONDENTS
    })


@app.route('/api/processed-documents', methods=['GET'])
def get_processed_documents():
    """Gibt alle verarbeiteten Dokumente zurück"""
    try:
        documents = db.get_all_processed_documents()
        stats = db.get_statistics()
        return jsonify({
            'documents': documents,
            'statistics': stats
        })
    except Exception as e:
        logger.error(f"Error getting processed documents: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/documents/reset/<int:document_id>', methods=['POST'])
def reset_document(document_id):
    """Setzt ein Dokument zurück für erneute Verarbeitung"""
    try:
        success = db.reset_document(document_id)
        if success:
            return jsonify({'success': True, 'message': f'Dokument {document_id} zurückgesetzt'})
        else:
            return jsonify({'success': False, 'message': 'Fehler beim Zurücksetzen'}), 500
    except Exception as e:
        logger.error(f"Error resetting document: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/documents/pending', methods=['GET'])
def get_pending_documents():
    """Gibt unverarbeitete Dokumente mit KI-Tag zurück"""
    try:
        paperless_url = os.getenv('PAPERLESS_URL')
        paperless_token = os.getenv('PAPERLESS_TOKEN')

        if not paperless_url or not paperless_token:
            return jsonify({'error': 'Paperless-Einstellungen nicht konfiguriert'}), 400

        paperless = PaperlessClient(paperless_url, paperless_token)
        all_ki_documents = paperless.get_documents_by_tag('KI')

        # Filtere bereits verarbeitete Dokumente heraus
        pending = []
        for doc in all_ki_documents:
            if not db.is_document_processed(doc['id']):
                pending.append({
                    'id': doc['id'],
                    'title': doc.get('title', 'Unbekannt'),
                    'created': doc.get('created', ''),
                    'added': doc.get('added', '')
                })

        return jsonify({'pending_documents': pending, 'count': len(pending)})
    except Exception as e:
        logger.error(f"Error getting pending documents: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/documents/process', methods=['POST'])
def process_documents():
    """Verarbeitet ausstehende Dokumente"""
    try:
        data = request.json
        document_ids = data.get('document_ids', [])

        if not document_ids:
            return jsonify({'error': 'Keine Dokument-IDs angegeben'}), 400

        # Konfiguration prüfen
        paperless_url = os.getenv('PAPERLESS_URL')
        paperless_token = os.getenv('PAPERLESS_TOKEN')
        ollama_url = os.getenv('OLLAMA_URL')
        ollama_model = os.getenv('OLLAMA_MODEL')

        if not all([paperless_url, paperless_token, ollama_url, ollama_model]):
            return jsonify({'error': 'Konfiguration unvollständig'}), 400

        # Clients initialisieren
        paperless = PaperlessClient(paperless_url, paperless_token)
        classifier = OllamaClassifier(ollama_url, ollama_model)

        results = []
        for doc_id in document_ids:
            try:
                # Dokument-Inhalt abrufen
                content = paperless.get_document_content(doc_id)
                if not content:
                    results.append({
                        'document_id': doc_id,
                        'success': False,
                        'error': 'Kein Inhalt gefunden'
                    })
                    db.add_processed_document(doc_id, 'Unbekannt', {}, False, 'Kein Inhalt gefunden')
                    continue

                # Klassifizierung
                classification = classifier.classify_document(content)
                validated = classifier.validate_classification(classification)

                if not validated:
                    results.append({
                        'document_id': doc_id,
                        'success': False,
                        'error': 'Klassifizierung fehlgeschlagen'
                    })
                    db.add_processed_document(doc_id, 'Unbekannt', {}, False, 'Klassifizierung fehlgeschlagen')
                    continue

                # Metadaten vorbereiten (wie in main.py)
                updates = {}

                if 'document_type' in validated:
                    doc_types = paperless.get_all_document_types()
                    doc_type_id = doc_types.get(validated['document_type'])
                    if doc_type_id:
                        updates['document_type'] = doc_type_id

                if 'correspondent' in validated:
                    correspondents = paperless.get_all_correspondents()
                    correspondent_id = correspondents.get(validated['correspondent'])
                    if correspondent_id:
                        updates['correspondent'] = correspondent_id

                if 'person_tags' in validated and validated['person_tags']:
                    all_tags = paperless.get_all_tags()
                    tag_ids = [all_tags[tag] for tag in validated['person_tags'] if tag in all_tags]
                    ki_tag_id = all_tags.get('KI')
                    if ki_tag_id:
                        tag_ids.append(ki_tag_id)
                    if tag_ids:
                        updates['tags'] = list(set(tag_ids))

                if 'date' in validated:
                    updates['created'] = validated['date']

                # Titel generieren
                title_parts = []
                if 'date' in validated:
                    title_parts.append(validated['date'])
                if 'document_type' in validated:
                    title_parts.append(validated['document_type'].lower().replace(' ', '_'))
                if 'correspondent' in validated:
                    title_parts.append(validated['correspondent'].lower().replace(' ', '_'))
                if 'person_tags' in validated and validated['person_tags']:
                    persons = '_'.join([p.lower() for p in validated['person_tags']])
                    title_parts.append(persons)

                if title_parts:
                    new_title = '_'.join(title_parts)
                    updates['title'] = new_title

                # Updates anwenden
                if updates:
                    success = paperless.update_document(doc_id, updates)
                    results.append({
                        'document_id': doc_id,
                        'success': success,
                        'classification': validated,
                        'updates': updates
                    })
                    db.add_processed_document(doc_id, updates.get('title', 'Unbekannt'), validated, success)
                else:
                    results.append({
                        'document_id': doc_id,
                        'success': True,
                        'classification': validated,
                        'message': 'Keine Updates notwendig'
                    })
                    db.add_processed_document(doc_id, 'Unbekannt', validated, True)

            except Exception as e:
                logger.error(f"Error processing document {doc_id}: {e}")
                results.append({
                    'document_id': doc_id,
                    'success': False,
                    'error': str(e)
                })
                db.add_processed_document(doc_id, 'Unbekannt', {}, False, str(e))

        return jsonify({'results': results})

    except Exception as e:
        logger.error(f"Error in process_documents: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/test-connection', methods=['POST'])
def test_connection():
    """Testet die Verbindung zu Paperless und Ollama"""
    try:
        data = request.json
        test_type = data.get('type')

        if test_type == 'paperless':
            url = data.get('url')
            token = data.get('token')

            if not url or not token:
                return jsonify({'success': False, 'message': 'URL und Token erforderlich'}), 400

            try:
                import requests
                response = requests.get(f"{url}/api/documents/",
                                       headers={'Authorization': f'Token {token}'},
                                       timeout=10)
                response.raise_for_status()
                return jsonify({'success': True, 'message': 'Verbindung erfolgreich'})
            except Exception as e:
                return jsonify({'success': False, 'message': f'Verbindung fehlgeschlagen: {str(e)}'}), 400

        elif test_type == 'ollama':
            url = data.get('url')
            model = data.get('model')

            if not url:
                return jsonify({'success': False, 'message': 'URL erforderlich'}), 400

            try:
                import requests
                # Test Ollama API
                response = requests.get(f"{url}/api/tags", timeout=10)
                response.raise_for_status()

                # Check if model exists
                models = response.json().get('models', [])
                model_names = [m.get('name', '') for m in models]

                if model and model not in model_names:
                    return jsonify({
                        'success': False,
                        'message': f'Model {model} nicht gefunden. Verfügbare Modelle: {", ".join(model_names)}'
                    }), 400

                return jsonify({'success': True, 'message': 'Verbindung erfolgreich', 'available_models': model_names})
            except Exception as e:
                return jsonify({'success': False, 'message': f'Verbindung fehlgeschlagen: {str(e)}'}), 400

        return jsonify({'success': False, 'message': 'Ungültiger Test-Typ'}), 400

    except Exception as e:
        logger.error(f"Error in test_connection: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


# ============================================================
# Q&A / Semantic Search Endpunkte
# ============================================================

@app.route('/api/qa/index-status', methods=['GET'])
def get_index_status():
    """Gibt den Status der Dokumenten-Indexierung zurück"""
    try:
        services = get_qa_services()
        indexer = services['document_indexer']

        if not indexer:
            return jsonify({'error': 'Document Indexer nicht verfügbar'}), 500

        stats = indexer.get_indexing_stats()
        return jsonify(stats)

    except Exception as e:
        logger.error(f"Error getting index status: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/qa/index-documents', methods=['POST'])
def index_documents():
    """Startet die Indexierung aller Dokumente"""
    try:
        services = get_qa_services()
        indexer = services['document_indexer']

        if not indexer:
            return jsonify({'error': 'Document Indexer nicht verfügbar'}), 500

        # Indexierung im Hintergrund starten (für MVP: synchron)
        logger.info("Starte Dokument-Indexierung...")
        stats = indexer.index_all_documents()

        return jsonify({
            'success': True,
            'stats': stats,
            'message': f"Indexierung abgeschlossen: {stats['indexed']} neu indexiert, {stats['skipped']} übersprungen"
        })

    except Exception as e:
        logger.error(f"Error indexing documents: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/qa/metadata-options', methods=['GET'])
def get_metadata_options():
    """Gibt verfügbare Metadaten-Optionen für Filter zurück"""
    try:
        paperless_url = os.getenv('PAPERLESS_URL')
        paperless_token = os.getenv('PAPERLESS_TOKEN')

        if not paperless_url or not paperless_token:
            return jsonify({'error': 'Paperless-Einstellungen nicht konfiguriert'}), 400

        paperless = PaperlessClient(paperless_url, paperless_token)

        # Hole alle verfügbaren Metadaten
        all_document_types = paperless.get_all_document_types()
        all_correspondents = paperless.get_all_correspondents()
        all_tags = paperless.get_all_tags()

        return jsonify({
            'document_types': list(all_document_types.keys()),
            'correspondents': list(all_correspondents.keys()),
            'tags': list(all_tags.keys())
        })

    except Exception as e:
        logger.error(f"Error getting metadata options: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/qa/search', methods=['POST'])
def semantic_search():
    """Führt semantische Dokumentensuche durch"""
    try:
        data = request.json
        query = data.get('query')
        n_results = data.get('n_results', 5)
        filters = data.get('filters', {})

        if not query:
            return jsonify({'error': 'Query erforderlich'}), 400

        services = get_qa_services()
        qa = services['qa_system']

        if not qa:
            return jsonify({'error': 'Q&A System nicht verfügbar'}), 500

        # Konvertiere Filter in ChromaDB-Format
        chroma_filters = None
        if filters:
            # Konvertiere Filter (Jahr, Tags werden später clientseitig gefiltert)
            chroma_filters = {}
            if 'document_type' in filters:
                chroma_filters['document_type'] = filters['document_type']
            if 'correspondent' in filters:
                chroma_filters['correspondent'] = filters['correspondent']

        # Suche durchführen (mit Multi-Query wenn aktiviert)
        use_multi = os.getenv('USE_MULTI_QUERY', 'true').lower() == 'true'
        if use_multi:
            results = qa.search_documents_multi(query=query, n_results=n_results, filters=chroma_filters)
        else:
            results = qa.search_documents(query=query, n_results=n_results, filters=chroma_filters)

        # Post-filtering für Jahr und Tags (da ChromaDB keine complex queries unterstützt)
        if 'year' in filters:
            year = str(filters['year'])
            results = [r for r in results if r['metadata'].get('created', '').startswith(year)]

        if 'tags' in filters and filters['tags']:
            filter_tags = set(filters['tags'])
            results = [
                r for r in results
                if any(tag in r['metadata'].get('tags', '') for tag in filter_tags)
            ]

        return jsonify({
            'success': True,
            'query': query,
            'results': results,
            'count': len(results)
        })

    except Exception as e:
        logger.error(f"Error in semantic search: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/qa/ask', methods=['POST'])
def ask_question():
    """Beantwortet eine Frage basierend auf Dokumenten (RAG)"""
    try:
        data = request.json
        question = data.get('question')
        n_context_docs = data.get('n_context_docs', 3)
        filters = data.get('filters', {})

        if not question:
            return jsonify({'error': 'Frage erforderlich'}), 400

        services = get_qa_services()
        qa = services['qa_system']

        if not qa:
            return jsonify({'error': 'Q&A System nicht verfügbar'}), 500

        # Konvertiere Filter in ChromaDB-Format
        chroma_filters = None
        if filters:
            chroma_filters = {}
            if 'document_type' in filters:
                chroma_filters['document_type'] = filters['document_type']
            if 'correspondent' in filters:
                chroma_filters['correspondent'] = filters['correspondent']

        # Frage beantworten (answer_question nutzt intern search_documents_multi)
        logger.info(f"Beantworte Frage: {question}")

        # Hole relevante Dokumente mit Filtern
        use_multi = os.getenv('USE_MULTI_QUERY', 'true').lower() == 'true'
        if use_multi:
            relevant_docs = qa.search_documents_multi(query=question, n_results=n_context_docs * 2, filters=chroma_filters)
            relevant_docs = relevant_docs[:n_context_docs]
        else:
            relevant_docs = qa.search_documents(query=question, n_results=n_context_docs, filters=chroma_filters)

        # Post-filtering für Jahr und Tags
        if 'year' in filters:
            year = str(filters['year'])
            relevant_docs = [r for r in relevant_docs if r['metadata'].get('created', '').startswith(year)]

        if 'tags' in filters and filters['tags']:
            filter_tags = set(filters['tags'])
            relevant_docs = [
                r for r in relevant_docs
                if any(tag in r['metadata'].get('tags', '') for tag in filter_tags)
            ]

        # Wenn keine Dokumente gefunden wurden
        if not relevant_docs:
            return jsonify({
                'success': True,
                'question': question,
                'answer': "Ich konnte keine relevanten Dokumente mit den angegebenen Filtern finden.",
                'sources': [],
                'confidence': 'low'
            })

        # Kontext aus gefilterten Dokumenten erstellen
        context_parts = []
        sources = []

        for i, doc in enumerate(relevant_docs, 1):
            doc_info = f"[Dokument {i}]\n"
            doc_info += f"Titel: {doc['metadata'].get('title', 'Unbekannt')}\n"
            if doc['metadata'].get('correspondent'):
                doc_info += f"Von: {doc['metadata']['correspondent']}\n"
            if doc['metadata'].get('document_type'):
                doc_info += f"Typ: {doc['metadata']['document_type']}\n"
            doc_info += f"Inhalt: {doc['text']}\n"

            context_parts.append(doc_info)

            sources.append({
                'doc_id': doc['doc_id'],
                'title': doc['metadata'].get('title', 'Unbekannt'),
                'correspondent': doc['metadata'].get('correspondent', ''),
                'document_type': doc['metadata'].get('document_type', ''),
                'relevance_score': 1 - (doc.get('distance', 0) / 2) if doc.get('distance') else None
            })

        context = "\n\n".join(context_parts)

        # Prompt erstellen und Antwort generieren
        prompt = qa._create_rag_prompt(question, context)
        answer = qa.llm.generate(prompt)

        if not answer:
            return jsonify({
                'success': True,
                'question': question,
                'answer': "Entschuldigung, ich konnte keine Antwort generieren.",
                'sources': sources,
                'confidence': 'low'
            })

        result = {
            'answer': answer.strip(),
            'sources': sources,
            'confidence': qa._estimate_confidence(relevant_docs, answer)
        }

        return jsonify({
            'success': True,
            'question': question,
            'answer': result['answer'],
            'sources': result['sources'],
            'confidence': result['confidence']
        })

    except Exception as e:
        logger.error(f"Error answering question: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/qa/test-embedding', methods=['POST'])
def test_embedding():
    """Testet den Embedding Service"""
    try:
        services = get_qa_services()
        embedding_svc = services['embedding_service']

        if not embedding_svc:
            return jsonify({'error': 'Embedding Service nicht verfügbar'}), 500

        # Test durchführen
        success = embedding_svc.test_connection()

        return jsonify({
            'success': success,
            'message': 'Embedding Service funktioniert' if success else 'Embedding Service Test fehlgeschlagen'
        })

    except Exception as e:
        logger.error(f"Error testing embedding service: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/qa/reset-index', methods=['POST'])
def reset_index():
    """Löscht den Vector Store Index (für Embedding-Modell Wechsel)"""
    try:
        services = get_qa_services()
        vector_store_svc = services['vector_store']

        if not vector_store_svc:
            return jsonify({'error': 'Vector Store nicht verfügbar'}), 500

        # Index zurücksetzen
        success = vector_store_svc.reset()

        if success:
            logger.info("Vector Store wurde erfolgreich zurückgesetzt")
            return jsonify({
                'success': True,
                'message': 'Index wurde zurückgesetzt. Bitte indexieren Sie die Dokumente neu.'
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Fehler beim Zurücksetzen des Index'
            }), 500

    except Exception as e:
        logger.error(f"Error resetting index: {e}")
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
