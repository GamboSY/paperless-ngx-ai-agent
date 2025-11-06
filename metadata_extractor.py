"""
Metadata Extractor für intelligente Query-Filtering
Extrahiert Filter-Kriterien aus natürlichsprachigen Fragen
"""
import logging
import json
import re
from typing import Dict, Any, Optional
from datetime import datetime
from ollama_classifier import OllamaClassifier

logger = logging.getLogger(__name__)


class MetadataExtractor:
    """Extrahiert Metadata-Filter aus natürlichsprachigen Fragen"""

    def __init__(self, llm: OllamaClassifier):
        """
        Initialisiert den Metadata Extractor

        Args:
            llm: Ollama Classifier für LLM-basierte Extraktion
        """
        self.llm = llm
        logger.info("MetadataExtractor initialisiert")

    def extract_filters(self, query: str, available_metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Extrahiert Filter-Kriterien aus einer Frage

        Args:
            query: Die Suchanfrage
            available_metadata: Verfügbare Metadaten (Tags, Typen, Korrespondenten)

        Returns:
            Dictionary mit ChromaDB-kompatiblen Filtern
        """
        try:
            # Schnelle Regex-basierte Extraktion für häufige Patterns
            regex_filters = self._extract_filters_regex(query)

            # LLM-basierte Extraktion für komplexe Queries
            llm_filters = self._extract_filters_llm(query, available_metadata)

            # Merge beide Filter
            filters = {**regex_filters, **llm_filters}

            if filters:
                logger.info(f"Filter extrahiert: {filters}")
            return filters

        except Exception as e:
            logger.error(f"Fehler bei Filter-Extraktion: {e}")
            return {}

    def _extract_filters_regex(self, query: str) -> Dict[str, Any]:
        """
        Schnelle Regex-basierte Filter-Extraktion

        Args:
            query: Die Suchanfrage

        Returns:
            Dictionary mit Filtern
        """
        filters = {}
        query_lower = query.lower()

        # Jahr-Extraktion (2020-2029)
        year_match = re.search(r'\b(202\d)\b', query)
        if year_match:
            year = year_match.group(1)
            filters['created_year'] = year
            logger.debug(f"Jahr gefunden: {year}")

        # Monat-Extraktion (Januar, Februar, etc.)
        months = {
            'januar': '01', 'februar': '02', 'märz': '03', 'april': '04',
            'mai': '05', 'juni': '06', 'juli': '07', 'august': '08',
            'september': '09', 'oktober': '10', 'november': '11', 'dezember': '12'
        }
        for month_name, month_num in months.items():
            if month_name in query_lower:
                filters['created_month'] = month_num
                logger.debug(f"Monat gefunden: {month_name}")
                break

        return filters

    def _extract_filters_llm(self, query: str, available_metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        LLM-basierte Filter-Extraktion für komplexe Queries

        Args:
            query: Die Suchanfrage
            available_metadata: Verfügbare Metadaten

        Returns:
            Dictionary mit Filtern
        """
        try:
            # Build metadata context
            metadata_context = ""
            if available_metadata:
                if 'document_types' in available_metadata:
                    metadata_context += f"\nVerfügbare Dokumenttypen: {', '.join(available_metadata['document_types'])}"
                if 'correspondents' in available_metadata:
                    metadata_context += f"\nVerfügbare Korrespondenten: {', '.join(available_metadata['correspondents'])}"
                if 'tags' in available_metadata:
                    metadata_context += f"\nVerfügbare Tags: {', '.join(available_metadata['tags'])}"

            prompt = f"""Analysiere diese Suchanfrage und extrahiere Filter-Kriterien.

Suchanfrage: {query}
{metadata_context}

Aufgabe: Extrahiere folgende Filter falls in der Frage enthalten:
- document_type: Dokumenttyp (z.B. "Rechnung", "Vertrag", "Lieferschein")
- correspondent: Absender/Korrespondent (z.B. "Amazon", "Telekom")
- tags: Tags (z.B. "wichtig", "privat")
- year: Jahr (z.B. "2024")

WICHTIG:
- Nutze NUR Werte die in der Frage explizit genannt werden
- Wenn nichts gefunden wurde, gib leeres JSON zurück: {{}}
- Antworte NUR mit JSON, keine Erklärungen!

Beispiele:
Frage: "Zeige mir Rechnungen von Amazon aus 2024"
Antwort: {{"document_type": "Rechnung", "correspondent": "Amazon", "year": "2024"}}

Frage: "Welche Verträge habe ich?"
Antwort: {{"document_type": "Vertrag"}}

Frage: "Was steht in meinen Dokumenten?"
Antwort: {{}}

JSON:"""

            response = self.llm.generate(prompt, temperature=0.1)

            # Parse JSON
            if response:
                # Find JSON in response
                start_idx = response.find('{')
                end_idx = response.rfind('}') + 1

                if start_idx != -1 and end_idx > start_idx:
                    json_str = response[start_idx:end_idx]
                    filters = json.loads(json_str)
                    logger.debug(f"LLM Filter extrahiert: {filters}")
                    return filters

        except Exception as e:
            logger.warning(f"LLM Filter-Extraktion fehlgeschlagen: {e}")

        return {}

    def convert_to_chromadb_filter(self, extracted_filters: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Konvertiert extrahierte Filter in ChromaDB-kompatibles Format

        Args:
            extracted_filters: Extrahierte Filter

        Returns:
            ChromaDB where-clause oder None
        """
        if not extracted_filters:
            return None

        where_conditions = {}

        # Dokumenttyp
        if 'document_type' in extracted_filters:
            where_conditions['document_type'] = extracted_filters['document_type']

        # Korrespondent
        if 'correspondent' in extracted_filters:
            where_conditions['correspondent'] = extracted_filters['correspondent']

        # Tags (contains check)
        if 'tags' in extracted_filters:
            # ChromaDB doesn't support "contains", so we'd need to do this client-side
            # For now, we skip tag filtering in ChromaDB and do it post-search
            pass

        # Jahr
        if 'year' in extracted_filters or 'created_year' in extracted_filters:
            year = extracted_filters.get('year') or extracted_filters.get('created_year')
            # ChromaDB metadata are strings, so we filter by startswith
            # We'll need to do this client-side for now
            pass

        return where_conditions if where_conditions else None
