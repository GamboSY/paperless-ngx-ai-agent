"""
Datenbank für Tracking verarbeiteter Dokumente
"""
import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class DocumentDatabase:
    def __init__(self, db_path: str = 'processed_documents.db'):
        self.db_path = db_path
        self.init_database()

    def init_database(self):
        """Initialisiert die Datenbank-Tabellen"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS processed_documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id INTEGER UNIQUE NOT NULL,
                document_title TEXT,
                processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                classification_result TEXT,
                success BOOLEAN,
                error_message TEXT
            )
        ''')

        conn.commit()
        conn.close()
        logger.info(f"Database initialized at {self.db_path}")

    def add_processed_document(self, document_id: int, document_title: str,
                              classification: Dict, success: bool, error_message: str = None):
        """Fügt ein verarbeitetes Dokument hinzu"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute('''
                INSERT OR REPLACE INTO processed_documents
                (document_id, document_title, processed_at, classification_result, success, error_message)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                document_id,
                document_title,
                datetime.now().isoformat(),
                json.dumps(classification),
                success,
                error_message
            ))
            conn.commit()
            logger.info(f"Document {document_id} added to database")
        except Exception as e:
            logger.error(f"Error adding document to database: {e}")
        finally:
            conn.close()

    def is_document_processed(self, document_id: int) -> bool:
        """Prüft, ob ein Dokument bereits verarbeitet wurde"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            'SELECT COUNT(*) FROM processed_documents WHERE document_id = ?',
            (document_id,)
        )
        count = cursor.fetchone()[0]
        conn.close()

        return count > 0

    def get_all_processed_documents(self) -> List[Dict]:
        """Gibt alle verarbeiteten Dokumente zurück"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM processed_documents
            ORDER BY processed_at DESC
        ''')

        rows = cursor.fetchall()
        conn.close()

        documents = []
        for row in rows:
            doc = dict(row)
            if doc['classification_result']:
                doc['classification_result'] = json.loads(doc['classification_result'])
            documents.append(doc)

        return documents

    def reset_document(self, document_id: int) -> bool:
        """Entfernt ein Dokument aus der Verarbeitungsliste (für erneute Verarbeitung)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute(
                'DELETE FROM processed_documents WHERE document_id = ?',
                (document_id,)
            )
            conn.commit()
            logger.info(f"Document {document_id} reset for reprocessing")
            return True
        except Exception as e:
            logger.error(f"Error resetting document: {e}")
            return False
        finally:
            conn.close()

    def get_statistics(self) -> Dict:
        """Gibt Statistiken über verarbeitete Dokumente zurück"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Gesamt-Anzahl
        cursor.execute('SELECT COUNT(*) FROM processed_documents')
        total = cursor.fetchone()[0]

        # Erfolgreiche Verarbeitungen
        cursor.execute('SELECT COUNT(*) FROM processed_documents WHERE success = 1')
        successful = cursor.fetchone()[0]

        # Fehlerhafte Verarbeitungen
        cursor.execute('SELECT COUNT(*) FROM processed_documents WHERE success = 0')
        failed = cursor.fetchone()[0]

        conn.close()

        return {
            'total': total,
            'successful': successful,
            'failed': failed
        }
