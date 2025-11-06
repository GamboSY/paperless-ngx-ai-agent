#!/usr/bin/env python3
"""
Paperless-NGX AI Agent
Verarbeitet Dokumente mit dem Tag "KI" und klassifiziert sie automatisch
"""
import os
import sys
import logging
from dotenv import load_dotenv
from paperless_client import PaperlessClient
from ollama_classifier import OllamaClassifier
from config import DOCUMENT_TYPES, PERSON_TAGS, CORRESPONDENTS
from database import DocumentDatabase

# Logging konfigurieren
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('paperless_ai_agent.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def ensure_metadata_exists(paperless: PaperlessClient):
    """
    Stellt sicher, dass alle benötigten Tags, Dokumententypen und Korrespondenten existieren
    """
    logger.info("Prüfe vorhandene Metadaten in Paperless-NGX...")

    # Tags prüfen und erstellen
    existing_tags = paperless.get_all_tags()
    for tag_name in PERSON_TAGS + ['KI']:
        if tag_name not in existing_tags:
            logger.info(f"Erstelle Tag: {tag_name}")
            paperless.create_tag(tag_name)

    # Dokumententypen prüfen und erstellen
    existing_doc_types = paperless.get_all_document_types()
    for doc_type in DOCUMENT_TYPES:
        if doc_type not in existing_doc_types:
            logger.info(f"Erstelle Dokumententyp: {doc_type}")
            paperless.create_document_type(doc_type)

    # Korrespondenten prüfen und erstellen
    existing_correspondents = paperless.get_all_correspondents()
    for correspondent in CORRESPONDENTS:
        if correspondent not in existing_correspondents:
            logger.info(f"Erstelle Korrespondent: {correspondent}")
            paperless.create_correspondent(correspondent)


def process_document(doc_id: int, paperless: PaperlessClient, classifier: OllamaClassifier,
                     db: DocumentDatabase, dry_run: bool = False):
    """
    Verarbeitet ein einzelnes Dokument
    """
    logger.info(f"Verarbeite Dokument {doc_id}...")

    # Dokument-Inhalt abrufen
    content = paperless.get_document_content(doc_id)
    if not content:
        logger.warning(f"Kein Inhalt für Dokument {doc_id} gefunden")
        db.add_processed_document(doc_id, 'Unbekannt', {}, False, 'Kein Inhalt gefunden')
        return False

    # Klassifizierung durchführen
    classification = classifier.classify_document(content)
    if not classification:
        logger.error(f"Klassifizierung fehlgeschlagen für Dokument {doc_id}")
        db.add_processed_document(doc_id, 'Unbekannt', {}, False, 'Klassifizierung fehlgeschlagen')
        return False

    # Validieren
    validated = classifier.validate_classification(classification)
    if not validated:
        logger.warning(f"Keine gültigen Klassifizierungen für Dokument {doc_id}")
        db.add_processed_document(doc_id, 'Unbekannt', classification, False, 'Keine gültigen Klassifizierungen')
        return False

    logger.info(f"Klassifizierung: {validated}")

    # Metadaten vorbereiten
    updates = {}

    # Dokumententyp
    if 'document_type' in validated:
        doc_types = paperless.get_all_document_types()
        doc_type_id = doc_types.get(validated['document_type'])
        if doc_type_id:
            updates['document_type'] = doc_type_id

    # Korrespondent
    if 'correspondent' in validated:
        correspondents = paperless.get_all_correspondents()
        correspondent_id = correspondents.get(validated['correspondent'])
        if correspondent_id:
            updates['correspondent'] = correspondent_id

    # Tags (Personen)
    if 'person_tags' in validated and validated['person_tags']:
        all_tags = paperless.get_all_tags()
        tag_ids = [all_tags[tag] for tag in validated['person_tags'] if tag in all_tags]

        # Hole aktuelle Tags des Dokuments
        current_doc = paperless.get_document_content(doc_id)

        # KI-Tag beibehalten, neue Tags hinzufügen
        ki_tag_id = all_tags.get('KI')
        if ki_tag_id:
            tag_ids.append(ki_tag_id)

        if tag_ids:
            updates['tags'] = list(set(tag_ids))  # Duplikate entfernen

    # Datum
    if 'date' in validated:
        updates['created'] = validated['date']

    # Titel generieren: datum_dokumenttyp_korrespondent_person
    title_parts = []

    # Datum (falls vorhanden)
    if 'date' in validated:
        title_parts.append(validated['date'])

    # Dokumententyp (falls vorhanden)
    if 'document_type' in validated:
        title_parts.append(validated['document_type'].lower().replace(' ', '_'))

    # Korrespondent (falls vorhanden)
    if 'correspondent' in validated:
        title_parts.append(validated['correspondent'].lower().replace(' ', '_'))

    # Personen-Tags (falls vorhanden)
    if 'person_tags' in validated and validated['person_tags']:
        # Alle Personen mit _ verbinden
        persons = '_'.join([p.lower() for p in validated['person_tags']])
        title_parts.append(persons)

    # Titel zusammensetzen
    if title_parts:
        new_title = '_'.join(title_parts)
        updates['title'] = new_title
        logger.info(f"Generiere Titel: {new_title}")

    # Updates anwenden
    if not updates:
        logger.info(f"Keine Updates für Dokument {doc_id}")
        db.add_processed_document(doc_id, 'Unbekannt', validated, True)
        return True

    if dry_run:
        logger.info(f"DRY-RUN: Würde Dokument {doc_id} aktualisieren mit: {updates}")
        db.add_processed_document(doc_id, updates.get('title', 'Unbekannt'), validated, True)
        return True

    success = paperless.update_document(doc_id, updates)
    if success:
        logger.info(f"Dokument {doc_id} erfolgreich aktualisiert")
        db.add_processed_document(doc_id, updates.get('title', 'Unbekannt'), validated, True)
    else:
        logger.error(f"Fehler beim Aktualisieren von Dokument {doc_id}")
        db.add_processed_document(doc_id, updates.get('title', 'Unbekannt'), validated, False, 'Update fehlgeschlagen')

    return success


def main():
    """
    Hauptfunktion
    """
    # Umgebungsvariablen laden
    load_dotenv()

    # Konfiguration
    paperless_url = os.getenv('PAPERLESS_URL')
    paperless_token = os.getenv('PAPERLESS_TOKEN')
    ollama_url = os.getenv('OLLAMA_URL')
    ollama_model = os.getenv('OLLAMA_MODEL')

    if not all([paperless_url, paperless_token, ollama_url, ollama_model]):
        logger.error("Fehlende Umgebungsvariablen! Bitte .env-Datei prüfen.")
        sys.exit(1)

    # Dry-run Modus?
    dry_run = '--dry-run' in sys.argv

    logger.info("=" * 60)
    logger.info("Paperless-NGX AI Agent gestartet")
    logger.info(f"Paperless-NGX: {paperless_url}")
    logger.info(f"Ollama: {ollama_url} (Model: {ollama_model})")
    logger.info(f"Dry-Run Modus: {dry_run}")
    logger.info("=" * 60)

    # Clients initialisieren
    paperless = PaperlessClient(paperless_url, paperless_token)
    classifier = OllamaClassifier(ollama_url, ollama_model)

    # Datenverzeichnis erstellen falls nicht vorhanden
    data_dir = os.path.join(os.path.dirname(__file__), 'data')
    os.makedirs(data_dir, exist_ok=True)
    db_path = os.path.join(data_dir, 'processed_documents.db')
    db = DocumentDatabase(db_path=db_path)

    # Metadaten sicherstellen
    ensure_metadata_exists(paperless)

    # Dokumente mit Tag "KI" abrufen
    all_documents = paperless.get_documents_by_tag('KI')

    if not all_documents:
        logger.info("Keine Dokumente mit Tag 'KI' gefunden")
        return

    # Filtere bereits verarbeitete Dokumente heraus
    documents = [doc for doc in all_documents if not db.is_document_processed(doc['id'])]

    if not documents:
        logger.info(f"Alle {len(all_documents)} Dokumente wurden bereits verarbeitet")
        logger.info("Verwende --force um alle Dokumente erneut zu verarbeiten")
        return

    logger.info(f"Gefunden: {len(documents)} neue Dokumente zur Verarbeitung ({len(all_documents)} gesamt)")

    # Dokumente verarbeiten
    success_count = 0
    error_count = 0

    for doc in documents:
        doc_id = doc['id']
        doc_title = doc.get('title', 'Unbekannt')
        logger.info(f"\n--- Dokument {doc_id}: {doc_title} ---")

        try:
            if process_document(doc_id, paperless, classifier, db, dry_run):
                success_count += 1
            else:
                error_count += 1
        except Exception as e:
            logger.error(f"Unerwarteter Fehler bei Dokument {doc_id}: {e}")
            db.add_processed_document(doc_id, doc_title, {}, False, f"Unerwarteter Fehler: {str(e)}")
            error_count += 1

    # Zusammenfassung
    logger.info("\n" + "=" * 60)
    logger.info("Verarbeitung abgeschlossen")
    logger.info(f"Erfolgreich: {success_count}")
    logger.info(f"Fehler: {error_count}")
    logger.info("=" * 60)


if __name__ == '__main__':
    main()
