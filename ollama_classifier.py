"""
Ollama-basierte Dokumentenklassifizierung
"""
import requests
import json
import logging
from typing import Dict, List, Optional
from config import DOCUMENT_TYPES, PERSON_TAGS, CORRESPONDENTS

logger = logging.getLogger(__name__)


class OllamaClassifier:
    def __init__(self, base_url: str, model: str):
        self.base_url = base_url.rstrip('/')
        self.model = model

    def _call_ollama(self, prompt: str) -> Optional[str]:
        """
        Ruft Ollama API auf
        """
        try:
            response = requests.post(
                f'{self.base_url}/api/generate',
                json={
                    'model': self.model,
                    'prompt': prompt,
                    'stream': False,
                    'options': {
                        'temperature': 0.05,  # Sehr niedrige Temperatur für präzise Klassifizierung
                    }
                },
                timeout=180
            )
            response.raise_for_status()
            return response.json().get('response', '').strip()
        except requests.exceptions.RequestException as e:
            logger.error(f"Fehler beim Aufruf von Ollama: {e}")
            return None

    def classify_document(self, content: str) -> Dict:
        """
        Klassifiziert ein Dokument und extrahiert Metadaten
        """
        prompt = f"""Analysiere das folgende Dokument und extrahiere die Metadaten SEHR GENAU.

DOKUMENTENTEXT:
{content[:3000]}

WICHTIG: Sei KONSERVATIV bei der Klassifizierung. Wenn du dir nicht SICHER bist, setze null!

AUFGABE:
Extrahiere folgende Informationen im JSON-Format:

1. DOKUMENTENTYP - Wähle NUR EINEN aus dieser exakten Liste (oder null wenn NICHTS passt):
{', '.join(DOCUMENT_TYPES)}

2. PERSONEN-TAGS - Wähle NUR Namen die SOWOHL im Dokument vorkommen ALS AUCH in dieser Liste stehen:
{', '.join(PERSON_TAGS)}
WICHTIG: Wenn ein Name im Dokument ist aber NICHT in dieser Liste -> IGNORIERE ihn!

3. KORRESPONDENT - Wähle EINEN aus dieser exakten Liste (oder null wenn unsicher):
{', '.join(CORRESPONDENTS)}

4. AUSSTELLDATUM - Extrahiere das Datum im Format YYYY-MM-DD (oder null wenn nicht gefunden)

REGELN:
- Verwende NUR Werte aus den Listen oben
- Wenn der Dokumententyp nicht EINDEUTIG einer Kategorie entspricht -> null
- Wenn kein Korrespondent aus der Liste im Dokument vorkommt -> null
- Sei VORSICHTIG: Lieber null als falsche Zuordnung!

ANTWORTFORMAT (nur JSON, keine Erklärungen):
{{
    "document_type": "Rechnung",
    "person_tags": ["Fahad"],
    "correspondent": "Amazon",
    "date": "2024-03-15"
}}

Antworte NUR mit dem JSON-Objekt.
"""

        logger.info("Sende Dokument an Ollama zur Klassifizierung...")
        response = self._call_ollama(prompt)

        if not response:
            logger.error("Keine Antwort von Ollama erhalten")
            return {}

        # Versuche JSON zu extrahieren
        try:
            # Finde JSON im Response (falls Text drum herum ist)
            start_idx = response.find('{')
            end_idx = response.rfind('}') + 1

            if start_idx != -1:
                if end_idx > start_idx:
                    json_str = response[start_idx:end_idx]
                else:
                    # Keine schließende Klammer gefunden - versuche zu reparieren
                    json_str = response[start_idx:] + '\n}'
                    logger.warning("Unvollständiges JSON - versuche Reparatur")

                result = json.loads(json_str)
                logger.info(f"Klassifizierung erfolgreich: {result}")
                return result
            else:
                logger.error(f"Kein JSON im Response gefunden: {response}")
                return {}

        except json.JSONDecodeError as e:
            logger.error(f"Fehler beim Parsen der Ollama-Antwort: {e}")
            logger.error(f"Response: {response}")

            # Letzter Versuch: Versuche nochmal mit zusätzlichen Reparaturen
            try:
                # Entferne Trailing Kommas und füge } hinzu
                json_str = response[start_idx:]
                json_str = json_str.rstrip().rstrip(',') + '\n}'
                result = json.loads(json_str)
                logger.warning(f"JSON mit Reparatur erfolgreich geparst: {result}")
                return result
            except:
                return {}

    def generate(self, prompt: str, temperature: float = 0.7) -> str:
        """
        Generiert Text basierend auf einem Prompt (für Q&A/RAG)

        Args:
            prompt: Der Prompt für die Generierung
            temperature: Temperatur für die Generierung (0.0-1.0)

        Returns:
            Generierter Text
        """
        try:
            response = requests.post(
                f'{self.base_url}/api/generate',
                json={
                    'model': self.model,
                    'prompt': prompt,
                    'stream': False,
                    'options': {
                        'temperature': temperature,
                    }
                },
                timeout=180
            )
            response.raise_for_status()
            return response.json().get('response', '').strip()
        except requests.exceptions.RequestException as e:
            logger.error(f"Fehler beim Generieren: {e}")
            return ""

    def validate_classification(self, classification: Dict) -> Dict:
        """
        Validiert und bereinigt die Klassifizierung
        """
        validated = {}

        # Dokumententyp validieren
        doc_type = classification.get('document_type')
        if doc_type and doc_type in DOCUMENT_TYPES:
            validated['document_type'] = doc_type
        else:
            logger.warning(f"Ungültiger Dokumententyp: {doc_type}")

        # Personen-Tags validieren
        person_tags = classification.get('person_tags', [])
        if isinstance(person_tags, list):
            validated['person_tags'] = [
                tag for tag in person_tags if tag in PERSON_TAGS
            ]
        elif isinstance(person_tags, str):
            # Falls als String zurückgegeben
            if person_tags in PERSON_TAGS:
                validated['person_tags'] = [person_tags]

        # Korrespondent validieren
        correspondent = classification.get('correspondent')
        if correspondent and correspondent in CORRESPONDENTS:
            validated['correspondent'] = correspondent
        else:
            if correspondent:
                logger.warning(f"Ungültiger Korrespondent: {correspondent}")

        # Datum validieren
        date = classification.get('date')
        if date and date != 'null' and len(date) >= 10:
            validated['date'] = date[:10]  # YYYY-MM-DD Format

        return validated
