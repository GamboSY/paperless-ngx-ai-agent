"""
Document Indexer für semantische Suche
Lädt Dokumente aus Paperless und indexiert sie im Vector Store
"""
import logging
from typing import List, Dict, Any, Optional
from paperless_client import PaperlessClient
from embedding_service import EmbeddingService
from vector_store import VectorStore

logger = logging.getLogger(__name__)


class DocumentIndexer:
    """Indexiert Paperless Dokumente für semantische Suche"""

    def __init__(
        self,
        paperless_client: PaperlessClient,
        embedding_service: EmbeddingService,
        vector_store: VectorStore
    ):
        """
        Initialisiert den Document Indexer

        Args:
            paperless_client: Client für Paperless-NGX API
            embedding_service: Service für Embedding-Generierung
            vector_store: Vector Store für Dokumente
        """
        self.paperless = paperless_client
        self.embeddings = embedding_service
        self.vector_store = vector_store

        logger.info("DocumentIndexer initialisiert")

    def _chunk_text(self, text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
        """
        Teilt Text in Chunks auf (für bessere Embeddings)

        Args:
            text: Text zum Aufteilen
            chunk_size: Größe eines Chunks in Zeichen
            overlap: Überlappung zwischen Chunks

        Returns:
            Liste von Text-Chunks
        """
        if not text or len(text) <= chunk_size:
            return [text]

        chunks = []
        start = 0

        while start < len(text):
            end = start + chunk_size
            chunk = text[start:end]

            # Versuche bei Satzende zu teilen
            if end < len(text):
                last_period = chunk.rfind('.')
                last_newline = chunk.rfind('\n')
                split_point = max(last_period, last_newline)

                if split_point > chunk_size * 0.5:  # Nur wenn Split-Punkt nicht zu früh
                    chunk = chunk[:split_point + 1]
                    end = start + split_point + 1

            chunks.append(chunk.strip())
            start = end - overlap

        return chunks

    def index_document(self, doc_id: int, force_reindex: bool = False) -> bool:
        """
        Indexiert ein einzelnes Dokument

        Args:
            doc_id: Paperless Dokument-ID
            force_reindex: Wenn True, wird Dokument neu indexiert auch wenn bereits vorhanden

        Returns:
            True wenn erfolgreich indexiert
        """
        try:
            # Prüfe ob bereits indexiert (check first chunk)
            first_chunk_id = f"{doc_id}_chunk_0"
            if not force_reindex and self.vector_store.document_exists(first_chunk_id):
                logger.debug(f"Dokument {doc_id} bereits indexiert (überspringe)")
                return True

            # Dokument von Paperless laden
            document = self.paperless.get_document(doc_id)
            if not document:
                logger.error(f"Dokument {doc_id} konnte nicht geladen werden")
                return False

            # Text extrahieren
            content = document.get('content', '')
            if not content:
                logger.warning(f"Dokument {doc_id} hat keinen Inhalt")
                return False

            # Metadaten sammeln
            metadata = {
                'title': document.get('title', ''),
                'correspondent': document.get('correspondent_name', ''),
                'document_type': document.get('document_type_name', ''),
                'created': document.get('created', ''),
                'tags': ','.join(document.get('tag_names', [])),
                'archive_serial_number': document.get('archive_serial_number', '')
            }

            # Text in Chunks aufteilen (auch für kurze Dokumente einheitlich)
            chunks = self._chunk_text(content, chunk_size=1500, overlap=200)
            total_chunks = len(chunks)

            logger.debug(f"Dokument {doc_id}: {total_chunks} Chunks erstellt")

            # Alle Chunks indexieren
            all_success = True
            for chunk_idx, chunk_text in enumerate(chunks):
                # Metadaten für diesen Chunk
                chunk_metadata = metadata.copy()
                chunk_metadata['chunk_number'] = str(chunk_idx)
                chunk_metadata['total_chunks'] = str(total_chunks)
                chunk_metadata['doc_id_original'] = str(doc_id)  # Original Doc ID für Deduplizierung

                # Embedding für Chunk erstellen
                embedding = self.embeddings.generate_embedding(chunk_text)
                if not embedding:
                    logger.error(f"Embedding für Dokument {doc_id}, Chunk {chunk_idx} fehlgeschlagen")
                    all_success = False
                    continue

                # Chunk-ID: doc_123_chunk_0
                chunk_doc_id = f"{doc_id}_chunk_{chunk_idx}"

                # Chunk indexieren
                success = self.vector_store.add_document(
                    doc_id=chunk_doc_id,
                    text=chunk_text[:500],  # Preview für Anzeige
                    embedding=embedding,
                    metadata=chunk_metadata
                )

                if not success:
                    all_success = False

            success = all_success

            if success:
                logger.info(f"✓ Dokument {doc_id} erfolgreich indexiert")
            return success

        except Exception as e:
            logger.error(f"Fehler beim Indexieren von Dokument {doc_id}: {e}")
            return False

    def index_all_documents(self, batch_size: int = 10) -> Dict[str, int]:
        """
        Indexiert alle Dokumente aus Paperless

        Args:
            batch_size: Anzahl Dokumente die gleichzeitig verarbeitet werden

        Returns:
            Dictionary mit Statistiken (indexed, skipped, failed)
        """
        stats = {
            'indexed': 0,
            'skipped': 0,
            'failed': 0
        }

        try:
            # Alle Dokumente von Paperless holen
            logger.info("Lade alle Dokumente von Paperless...")
            all_documents = self.paperless.get_all_documents()
            total = len(all_documents)

            logger.info(f"Starte Indexierung von {total} Dokumenten...")

            for i, doc in enumerate(all_documents, 1):
                doc_id = doc['id']

                # Fortschritt anzeigen
                if i % 10 == 0 or i == total:
                    logger.info(f"Fortschritt: {i}/{total} ({i*100//total}%)")

                # Prüfe ob bereits indexiert
                if self.vector_store.document_exists(doc_id):
                    stats['skipped'] += 1
                    continue

                # Indexieren
                success = self.index_document(doc_id, force_reindex=False)
                if success:
                    stats['indexed'] += 1
                else:
                    stats['failed'] += 1

            logger.info("=" * 60)
            logger.info("Indexierung abgeschlossen!")
            logger.info(f"  Neu indexiert: {stats['indexed']}")
            logger.info(f"  Übersprungen:  {stats['skipped']}")
            logger.info(f"  Fehlgeschlagen: {stats['failed']}")
            logger.info("=" * 60)

            return stats

        except Exception as e:
            logger.error(f"Fehler bei der Indexierung aller Dokumente: {e}")
            return stats

    def reindex_document(self, doc_id: int) -> bool:
        """
        Indexiert ein Dokument neu (löscht alte Version zuerst)

        Args:
            doc_id: Paperless Dokument-ID

        Returns:
            True wenn erfolgreich
        """
        # Lösche alle Chunks des Dokuments
        self.vector_store.delete_all_document_chunks(doc_id)
        return self.index_document(doc_id, force_reindex=True)

    def get_indexing_stats(self) -> Dict[str, Any]:
        """
        Gibt Statistiken über den Indexierungs-Status zurück

        Returns:
            Dictionary mit Statistiken
        """
        try:
            vector_stats = self.vector_store.get_stats()
            all_docs = self.paperless.get_all_documents()

            return {
                'total_paperless_documents': len(all_docs),
                'indexed_documents': vector_stats['total_documents'],
                'indexing_progress': f"{vector_stats['total_documents']}/{len(all_docs)}"
            }
        except Exception as e:
            logger.error(f"Fehler beim Abrufen der Statistiken: {e}")
            return {}
