"""
Vector Store für semantische Dokumentensuche
Nutzt ChromaDB für persistente Embedding-Speicherung
"""
import os
import logging
from typing import List, Dict, Any, Optional, Union
import chromadb
from chromadb.config import Settings

logger = logging.getLogger(__name__)


class VectorStore:
    """Vector Store für Dokumenten-Embeddings mit ChromaDB"""

    def __init__(self, persist_directory: str = "data/chromadb"):
        """
        Initialisiert den Vector Store

        Args:
            persist_directory: Verzeichnis für persistente Speicherung
        """
        self.persist_directory = persist_directory
        os.makedirs(persist_directory, exist_ok=True)

        # ChromaDB Client initialisieren
        self.client = chromadb.PersistentClient(
            path=persist_directory,
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )

        # Collection für Dokumente erstellen/laden
        self.collection = self.client.get_or_create_collection(
            name="paperless_documents",
            metadata={"description": "Paperless-NGX Dokumenten-Embeddings"}
        )

        logger.info(f"VectorStore initialisiert: {persist_directory}")
        logger.info(f"Anzahl Dokumente in Collection: {self.collection.count()}")

    def add_document(
        self,
        doc_id: Union[int, str],
        text: str,
        embedding: List[float],
        metadata: Dict[str, Any]
    ) -> bool:
        """
        Fügt ein Dokument zum Vector Store hinzu

        Args:
            doc_id: Paperless Dokument-ID (int) oder Chunk-ID (str wie "123_chunk_0")
            text: Dokumententext (für Anzeige bei Suchergebnissen)
            embedding: Embedding-Vektor
            metadata: Metadaten (title, correspondent, doc_type, etc.)

        Returns:
            True wenn erfolgreich
        """
        try:
            # ChromaDB erwartet strings für alle Metadaten
            safe_metadata = {
                k: str(v) if v is not None else ""
                for k, v in metadata.items()
            }

            # ID formatieren: wenn int, dann "doc_{id}", wenn schon string, dann as-is
            if isinstance(doc_id, int):
                chroma_id = f"doc_{doc_id}"
            else:
                chroma_id = f"doc_{doc_id}"  # String wie "123_chunk_0" → "doc_123_chunk_0"

            self.collection.add(
                ids=[chroma_id],
                embeddings=[embedding],
                documents=[text],
                metadatas=[safe_metadata]
            )

            logger.debug(f"Dokument {doc_id} zum Vector Store hinzugefügt")
            return True

        except Exception as e:
            logger.error(f"Fehler beim Hinzufügen von Dokument {doc_id}: {e}")
            return False

    def add_documents_batch(
        self,
        doc_ids: List[int],
        texts: List[str],
        embeddings: List[List[float]],
        metadatas: List[Dict[str, Any]]
    ) -> bool:
        """
        Fügt mehrere Dokumente in einem Batch hinzu

        Args:
            doc_ids: Liste von Paperless Dokument-IDs
            texts: Liste von Dokumententexten
            embeddings: Liste von Embedding-Vektoren
            metadatas: Liste von Metadaten

        Returns:
            True wenn erfolgreich
        """
        try:
            # Metadaten konvertieren
            safe_metadatas = [
                {k: str(v) if v is not None else "" for k, v in meta.items()}
                for meta in metadatas
            ]

            # IDs erstellen
            ids = [f"doc_{doc_id}" for doc_id in doc_ids]

            self.collection.add(
                ids=ids,
                embeddings=embeddings,
                documents=texts,
                metadatas=safe_metadatas
            )

            logger.info(f"Batch von {len(doc_ids)} Dokumenten zum Vector Store hinzugefügt")
            return True

        except Exception as e:
            logger.error(f"Fehler beim Batch-Hinzufügen: {e}")
            return False

    def search(
        self,
        query_embedding: List[float],
        n_results: int = 5,
        where: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Führt semantische Suche durch

        Args:
            query_embedding: Embedding der Suchanfrage
            n_results: Anzahl der Ergebnisse
            where: Filter-Bedingungen (z.B. {"doc_type": "invoice"})

        Returns:
            Liste von Suchergebnissen mit Dokumenten und Metadaten
        """
        try:
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                where=where
            )

            # Ergebnisse formatieren
            formatted_results = []
            for i in range(len(results['ids'][0])):
                metadata = results['metadatas'][0][i]

                # Doc ID aus Metadaten holen (für Chunk-Support)
                doc_id_str = metadata.get('doc_id_original', '')
                if doc_id_str:
                    try:
                        doc_id = int(doc_id_str)
                    except:
                        # Fallback: parse from ChromaDB ID
                        chroma_id = results['ids'][0][i].replace('doc_', '')
                        doc_id = int(chroma_id.split('_chunk_')[0]) if '_chunk_' in chroma_id else int(chroma_id)
                else:
                    # Fallback für alte Einträge ohne doc_id_original
                    chroma_id = results['ids'][0][i].replace('doc_', '')
                    doc_id = int(chroma_id.split('_chunk_')[0]) if '_chunk_' in chroma_id else int(chroma_id)

                formatted_results.append({
                    'doc_id': doc_id,
                    'chunk_id': results['ids'][0][i],
                    'chunk_number': metadata.get('chunk_number', '0'),
                    'total_chunks': metadata.get('total_chunks', '1'),
                    'text': results['documents'][0][i],
                    'metadata': metadata,
                    'distance': results['distances'][0][i] if 'distances' in results else None
                })

            logger.info(f"Suche abgeschlossen: {len(formatted_results)} Ergebnisse gefunden")
            return formatted_results

        except Exception as e:
            logger.error(f"Fehler bei der Suche: {e}")
            return []

    def document_exists(self, doc_id: Union[int, str]) -> bool:
        """
        Prüft ob ein Dokument bereits im Vector Store existiert

        Args:
            doc_id: Paperless Dokument-ID oder Chunk-ID

        Returns:
            True wenn Dokument existiert
        """
        try:
            if isinstance(doc_id, int):
                chroma_id = f"doc_{doc_id}"
            else:
                chroma_id = f"doc_{doc_id}"

            result = self.collection.get(ids=[chroma_id])
            return len(result['ids']) > 0
        except:
            return False

    def delete_document(self, doc_id: Union[int, str]) -> bool:
        """
        Löscht ein Dokument aus dem Vector Store

        Args:
            doc_id: Paperless Dokument-ID oder Chunk-ID

        Returns:
            True wenn erfolgreich
        """
        try:
            if isinstance(doc_id, int):
                chroma_id = f"doc_{doc_id}"
            else:
                chroma_id = f"doc_{doc_id}"

            self.collection.delete(ids=[chroma_id])
            logger.info(f"Dokument {doc_id} aus Vector Store gelöscht")
            return True
        except Exception as e:
            logger.error(f"Fehler beim Löschen von Dokument {doc_id}: {e}")
            return False

    def delete_all_document_chunks(self, doc_id: int) -> bool:
        """
        Löscht alle Chunks eines Dokuments aus dem Vector Store

        Args:
            doc_id: Paperless Dokument-ID (ohne chunk suffix)

        Returns:
            True wenn erfolgreich
        """
        try:
            # Hole alle Dokumente mit dieser doc_id_original
            all_docs = self.collection.get(
                where={"doc_id_original": str(doc_id)}
            )

            if all_docs['ids']:
                self.collection.delete(ids=all_docs['ids'])
                logger.info(f"Alle {len(all_docs['ids'])} Chunks von Dokument {doc_id} gelöscht")
                return True
            return True
        except Exception as e:
            logger.error(f"Fehler beim Löschen aller Chunks von Dokument {doc_id}: {e}")
            return False

    def get_stats(self) -> Dict[str, Any]:
        """
        Gibt Statistiken über den Vector Store zurück

        Returns:
            Dictionary mit Statistiken
        """
        return {
            "total_documents": self.collection.count(),
            "persist_directory": self.persist_directory
        }

    def reset(self) -> bool:
        """
        Löscht alle Dokumente aus dem Vector Store

        Returns:
            True wenn erfolgreich
        """
        try:
            self.client.delete_collection(name="paperless_documents")
            self.collection = self.client.get_or_create_collection(
                name="paperless_documents",
                metadata={"description": "Paperless-NGX Dokumenten-Embeddings"}
            )
            logger.info("Vector Store wurde zurückgesetzt")
            return True
        except Exception as e:
            logger.error(f"Fehler beim Zurücksetzen: {e}")
            return False
