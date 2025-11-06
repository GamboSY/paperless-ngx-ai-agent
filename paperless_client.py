"""
Paperless-NGX API Client
"""
import requests
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class PaperlessClient:
    def __init__(self, base_url: str, token: str):
        self.base_url = base_url.rstrip('/')
        self.token = token
        self.headers = {
            'Authorization': f'Token {token}',
            'Content-Type': 'application/json'
        }

    def get_documents_by_tag(self, tag_name: str) -> List[Dict]:
        """
        Holt alle Dokumente mit einem bestimmten Tag (mit Pagination)
        """
        try:
            # Erst Tag-ID finden
            tags_response = requests.get(
                f'{self.base_url}/api/tags/',
                headers=self.headers
            )
            tags_response.raise_for_status()
            tags = tags_response.json()['results']

            tag_id = None
            for tag in tags:
                if tag['name'].lower() == tag_name.lower():
                    tag_id = tag['id']
                    break

            if not tag_id:
                logger.warning(f"Tag '{tag_name}' nicht gefunden")
                return []

            # Dokumente mit diesem Tag holen (MIT PAGINATION!)
            all_documents = []
            page = 1
            page_size = 100

            while True:
                params = {
                    'tags__id__in': tag_id,
                    'page': page,
                    'page_size': page_size
                }

                docs_response = requests.get(
                    f'{self.base_url}/api/documents/',
                    headers=self.headers,
                    params=params
                )
                docs_response.raise_for_status()
                data = docs_response.json()

                all_documents.extend(data['results'])

                # Prüfe ob weitere Seiten vorhanden sind
                if not data.get('next'):
                    break

                page += 1

            logger.info(f"{len(all_documents)} Dokumente mit Tag '{tag_name}' gefunden")
            return all_documents

        except requests.exceptions.RequestException as e:
            logger.error(f"Fehler beim Abrufen der Dokumente: {e}")
            return []

    def get_document(self, document_id: int) -> Optional[Dict]:
        """
        Holt ein einzelnes Dokument mit allen Metadaten
        """
        try:
            response = requests.get(
                f'{self.base_url}/api/documents/{document_id}/',
                headers=self.headers
            )
            response.raise_for_status()
            doc = response.json()

            # Füge Namen statt nur IDs hinzu für bessere Lesbarkeit
            if doc.get('correspondent'):
                doc['correspondent_name'] = self._get_correspondent_name(doc['correspondent'])
            if doc.get('document_type'):
                doc['document_type_name'] = self._get_document_type_name(doc['document_type'])
            if doc.get('tags'):
                doc['tag_names'] = [self._get_tag_name(tag_id) for tag_id in doc['tags']]

            return doc
        except requests.exceptions.RequestException as e:
            logger.error(f"Fehler beim Abrufen des Dokuments {document_id}: {e}")
            return None

    def get_document_content(self, document_id: int) -> Optional[str]:
        """
        Holt den OCR-Text eines Dokuments
        """
        try:
            response = requests.get(
                f'{self.base_url}/api/documents/{document_id}/',
                headers=self.headers
            )
            response.raise_for_status()
            return response.json().get('content', '')
        except requests.exceptions.RequestException as e:
            logger.error(f"Fehler beim Abrufen des Dokument-Inhalts: {e}")
            return None

    def get_all_documents(self, page_size: int = 100) -> List[Dict]:
        """
        Holt alle Dokumente von Paperless (mit Pagination)
        """
        all_documents = []
        page = 1

        try:
            while True:
                response = requests.get(
                    f'{self.base_url}/api/documents/',
                    headers=self.headers,
                    params={
                        'page': page,
                        'page_size': page_size
                    }
                )
                response.raise_for_status()
                data = response.json()

                documents = data.get('results', [])
                all_documents.extend(documents)

                # Prüfe ob es weitere Seiten gibt
                if not data.get('next'):
                    break

                page += 1

            logger.info(f"{len(all_documents)} Dokumente insgesamt gefunden")
            return all_documents

        except requests.exceptions.RequestException as e:
            logger.error(f"Fehler beim Abrufen aller Dokumente: {e}")
            return all_documents  # Gib zurück was wir haben

    def _get_tag_name(self, tag_id: int) -> str:
        """Hilfsmethode: Holt Tag-Namen von ID"""
        try:
            response = requests.get(
                f'{self.base_url}/api/tags/{tag_id}/',
                headers=self.headers
            )
            response.raise_for_status()
            return response.json().get('name', '')
        except:
            return ''

    def _get_correspondent_name(self, correspondent_id: int) -> str:
        """Hilfsmethode: Holt Korrespondent-Namen von ID"""
        try:
            response = requests.get(
                f'{self.base_url}/api/correspondents/{correspondent_id}/',
                headers=self.headers
            )
            response.raise_for_status()
            return response.json().get('name', '')
        except:
            return ''

    def _get_document_type_name(self, doc_type_id: int) -> str:
        """Hilfsmethode: Holt Dokumenttyp-Namen von ID"""
        try:
            response = requests.get(
                f'{self.base_url}/api/document_types/{doc_type_id}/',
                headers=self.headers
            )
            response.raise_for_status()
            return response.json().get('name', '')
        except:
            return ''

    def get_all_tags(self) -> Dict[str, int]:
        """
        Holt alle verfügbaren Tags (Name -> ID)
        """
        try:
            response = requests.get(
                f'{self.base_url}/api/tags/',
                headers=self.headers
            )
            response.raise_for_status()
            tags = response.json()['results']
            return {tag['name']: tag['id'] for tag in tags}
        except requests.exceptions.RequestException as e:
            logger.error(f"Fehler beim Abrufen der Tags: {e}")
            return {}

    def get_all_document_types(self) -> Dict[str, int]:
        """
        Holt alle verfügbaren Dokumententypen (Name -> ID)
        """
        try:
            response = requests.get(
                f'{self.base_url}/api/document_types/',
                headers=self.headers
            )
            response.raise_for_status()
            doc_types = response.json()['results']
            return {dt['name']: dt['id'] for dt in doc_types}
        except requests.exceptions.RequestException as e:
            logger.error(f"Fehler beim Abrufen der Dokumententypen: {e}")
            return {}

    def get_all_correspondents(self) -> Dict[str, int]:
        """
        Holt alle verfügbaren Korrespondenten (Name -> ID)
        """
        try:
            response = requests.get(
                f'{self.base_url}/api/correspondents/',
                headers=self.headers
            )
            response.raise_for_status()
            correspondents = response.json()['results']
            return {c['name']: c['id'] for c in correspondents}
        except requests.exceptions.RequestException as e:
            logger.error(f"Fehler beim Abrufen der Korrespondenten: {e}")
            return {}

    def create_tag(self, name: str) -> Optional[int]:
        """
        Erstellt einen neuen Tag
        """
        try:
            response = requests.post(
                f'{self.base_url}/api/tags/',
                headers=self.headers,
                json={'name': name}
            )
            response.raise_for_status()
            tag_id = response.json()['id']
            logger.info(f"Tag '{name}' erstellt mit ID {tag_id}")
            return tag_id
        except requests.exceptions.RequestException as e:
            logger.error(f"Fehler beim Erstellen des Tags '{name}': {e}")
            return None

    def create_document_type(self, name: str) -> Optional[int]:
        """
        Erstellt einen neuen Dokumententyp
        """
        try:
            response = requests.post(
                f'{self.base_url}/api/document_types/',
                headers=self.headers,
                json={'name': name}
            )
            response.raise_for_status()
            dt_id = response.json()['id']
            logger.info(f"Dokumententyp '{name}' erstellt mit ID {dt_id}")
            return dt_id
        except requests.exceptions.RequestException as e:
            logger.error(f"Fehler beim Erstellen des Dokumententyps '{name}': {e}")
            return None

    def create_correspondent(self, name: str) -> Optional[int]:
        """
        Erstellt einen neuen Korrespondenten
        """
        try:
            response = requests.post(
                f'{self.base_url}/api/correspondents/',
                headers=self.headers,
                json={'name': name}
            )
            response.raise_for_status()
            corr_id = response.json()['id']
            logger.info(f"Korrespondent '{name}' erstellt mit ID {corr_id}")
            return corr_id
        except requests.exceptions.RequestException as e:
            logger.error(f"Fehler beim Erstellen des Korrespondenten '{name}': {e}")
            return None

    def update_document(self, document_id: int, updates: Dict) -> bool:
        """
        Aktualisiert ein Dokument mit neuen Metadaten
        """
        try:
            # Erst aktuelles Dokument holen
            response = requests.get(
                f'{self.base_url}/api/documents/{document_id}/',
                headers=self.headers
            )
            response.raise_for_status()
            current_doc = response.json()

            # Updates anwenden
            current_doc.update(updates)

            # Dokument aktualisieren
            response = requests.patch(
                f'{self.base_url}/api/documents/{document_id}/',
                headers=self.headers,
                json=updates
            )
            response.raise_for_status()
            logger.info(f"Dokument {document_id} erfolgreich aktualisiert")
            return True

        except requests.exceptions.RequestException as e:
            logger.error(f"Fehler beim Aktualisieren des Dokuments {document_id}: {e}")
            return False
