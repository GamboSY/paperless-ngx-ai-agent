"""
Embedding Service für semantische Suche
Nutzt Ollama nomic-embed-text Modell
"""
import requests
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Service für die Generierung von Text-Embeddings via Ollama"""

    def __init__(self, ollama_url: str, model: str = "nomic-embed-text"):
        """
        Initialisiert den Embedding Service

        Args:
            ollama_url: URL des Ollama Servers (z.B. http://192.168.2.139:11434)
            model: Embedding Modell (default: nomic-embed-text)
        """
        self.ollama_url = ollama_url.rstrip('/')
        self.model = model
        self.embed_endpoint = f"{self.ollama_url}/api/embeddings"

        logger.info(f"EmbeddingService initialisiert: {self.ollama_url} (Model: {self.model})")

    def generate_embedding(self, text: str) -> List[float]:
        """
        Generiert Embedding für einen einzelnen Text

        Args:
            text: Text für den ein Embedding erstellt werden soll

        Returns:
            Liste von float-Werten (Embedding-Vektor)
        """
        try:
            response = requests.post(
                self.embed_endpoint,
                json={
                    "model": self.model,
                    "prompt": text
                },
                timeout=30
            )
            response.raise_for_status()

            result = response.json()
            embedding = result.get("embedding", [])

            if not embedding:
                logger.error(f"Kein Embedding erhalten für Text: {text[:100]}...")
                return []

            logger.debug(f"Embedding generiert: {len(embedding)} Dimensionen")
            return embedding

        except requests.exceptions.RequestException as e:
            logger.error(f"Fehler bei Embedding-Generierung: {e}")
            return []

    def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generiert Embeddings für mehrere Texte

        Args:
            texts: Liste von Texten

        Returns:
            Liste von Embedding-Vektoren
        """
        embeddings = []
        total = len(texts)

        for i, text in enumerate(texts, 1):
            if i % 10 == 0:
                logger.info(f"Embedding-Progress: {i}/{total}")

            embedding = self.generate_embedding(text)
            embeddings.append(embedding)

        logger.info(f"Batch-Embedding abgeschlossen: {len(embeddings)} Embeddings erstellt")
        return embeddings

    def test_connection(self) -> bool:
        """
        Testet die Verbindung zum Ollama Server und ob das Embedding-Modell verfügbar ist

        Returns:
            True wenn Verbindung erfolgreich, sonst False
        """
        try:
            # Test mit kurzem Text
            test_embedding = self.generate_embedding("Test")

            if test_embedding and len(test_embedding) > 0:
                logger.info(f"✓ Embedding Service erfolgreich getestet: {len(test_embedding)} Dimensionen")
                return True
            else:
                logger.error("✗ Embedding Service Test fehlgeschlagen: Kein Embedding erhalten")
                return False

        except Exception as e:
            logger.error(f"✗ Embedding Service Test fehlgeschlagen: {e}")
            return False
