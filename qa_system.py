"""
Q&A System mit RAG (Retrieval Augmented Generation)
Beantwortet Fragen basierend auf indexierten Dokumenten
"""
import os
import re
import logging
from typing import List, Dict, Any, Optional
from embedding_service import EmbeddingService
from vector_store import VectorStore
from ollama_classifier import OllamaClassifier
from metadata_extractor import MetadataExtractor

logger = logging.getLogger(__name__)

# Synonym-Map für Query Expansion (Deutsche Dokumente)
SYNONYM_MAP = {
    'steuer id': ['Steuer-ID', 'Steuer-Identifikationsnummer', 'Steuernummer', 'Tax ID', 'TIN'],
    'steuernummer': ['Steuer-ID', 'Steuer-Identifikationsnummer', 'Tax ID', 'TIN'],
    'rechnung': ['Rechnung', 'Invoice', 'Faktura', 'Beleg'],
    'lieferschein': ['Lieferschein', 'Delivery Note', 'Warenbegleitschein'],
    'vertrag': ['Vertrag', 'Contract', 'Vereinbarung'],
    'adresse': ['Adresse', 'Address', 'Anschrift', 'Wohnort'],
    'telefon': ['Telefon', 'Telefonnummer', 'Phone', 'Tel', 'Mobil'],
    'email': ['E-Mail', 'Email', 'Mailadresse', 'Elektronische Post'],
    'geburtsdatum': ['Geburtsdatum', 'Geburtstag', 'Date of Birth', 'DOB'],
    'gehalt': ['Gehalt', 'Lohn', 'Vergütung', 'Salary', 'Verdienst'],
    'versicherung': ['Versicherung', 'Insurance', 'Police'],
}


class QASystem:
    """Question & Answer System mit RAG für Paperless Dokumente"""

    def __init__(
        self,
        embedding_service: EmbeddingService,
        vector_store: VectorStore,
        ollama_classifier: OllamaClassifier
    ):
        """
        Initialisiert das Q&A System

        Args:
            embedding_service: Service für Embedding-Generierung
            vector_store: Vector Store für semantische Suche
            ollama_classifier: Ollama Client für Text-Generierung
        """
        self.embeddings = embedding_service
        self.vector_store = vector_store
        self.llm = ollama_classifier
        self.metadata_extractor = MetadataExtractor(ollama_classifier)

        logger.info("QASystem initialisiert")

    def _expand_query_llm(self, query: str) -> str:
        """
        Erweitert die Suchanfrage mit LLM-generierten Synonymen (dynamisch!)

        Args:
            query: Ursprüngliche Suchanfrage

        Returns:
            Erweiterte Suchanfrage mit Synonymen
        """
        try:
            # Kurzer Prompt für schnelle Synonym-Generierung
            synonym_prompt = f"""Generiere Synonyme und alternative Schreibweisen für die Suchbegriffe in dieser Frage.

Frage: {query}

Aufgabe: Extrahiere die wichtigsten Suchbegriffe und gib 2-4 Synonyme oder alternative Schreibweisen pro Begriff.

Beispiele:
- "Steuer ID" → Steuer-Identifikationsnummer, Steuernummer, Tax ID
- "Rechnung" → Invoice, Faktura, Beleg
- "Adresse" → Anschrift, Wohnort, Address

WICHTIG: Antworte NUR mit den Synonymen, durch Komma getrennt, KEINE Erklärungen!

Synonyme:"""

            # Generiere Synonyme mit niedriger Temperatur (präzise)
            synonyms_text = self.llm.generate(synonym_prompt, temperature=0.3)

            if synonyms_text and len(synonyms_text) > 0:
                # Kombiniere Original-Query mit Synonymen
                expanded = f"{query} {synonyms_text}"
                logger.info(f"Query erweitert (LLM): '{query}' → '{expanded[:100]}...'")
                return expanded

        except Exception as e:
            logger.warning(f"LLM Query-Expansion fehlgeschlagen: {e}")

        # Fallback auf Original-Query
        return query

    def _expand_query(self, query: str) -> str:
        """
        Erweitert die Suchanfrage mit Synonymen (Hybrid: Hardcoded + LLM)

        Args:
            query: Ursprüngliche Suchanfrage

        Returns:
            Erweiterte Suchanfrage mit Synonymen
        """
        query_lower = query.lower()
        expanded_terms = []

        # 1. Schnelle hardcoded Synonyme (für häufige Begriffe)
        for key, synonyms in SYNONYM_MAP.items():
            if key in query_lower:
                expanded_terms.extend(synonyms)
                logger.debug(f"Query-Expansion (hardcoded): '{key}' → {synonyms}")

        if expanded_terms:
            # Nutze hardcoded Synonyme
            expanded = f"{query} {' '.join(expanded_terms)}"
            logger.info(f"Query erweitert (hardcoded): '{query}' → '{expanded[:100]}...'")
            return expanded

        # 2. Fallback: LLM-basierte Expansion (für andere Begriffe)
        # Konfigurierbar über .env: USE_LLM_EXPANSION=true
        use_llm = os.getenv('USE_LLM_EXPANSION', 'false').lower() == 'true'
        if use_llm:
            logger.info("Nutze LLM-basierte Query Expansion (konfiguriert via .env)")
            return self._expand_query_llm(query)

        return query

    def _generate_multi_queries(self, original_query: str, n_variants: int = 2) -> List[str]:
        """
        Generiert alternative Formulierungen einer Frage (Multi-Query Approach)

        Args:
            original_query: Die ursprüngliche Frage
            n_variants: Anzahl der Varianten (default: 2)

        Returns:
            Liste von Fragen (inkl. Original)
        """
        try:
            prompt = f"""Generiere {n_variants} alternative Formulierungen für diese Frage.
Die Varianten sollen die gleiche Information suchen, aber anders formuliert sein.

Original-Frage: {original_query}

Aufgabe:
- Erstelle {n_variants} alternative Formulierungen
- Behalte die Kernintention bei
- Variiere Wortstellung, Synonyme, Perspektive
- Antworte NUR mit den Fragen, eine pro Zeile, KEINE Nummerierung!

Varianten:"""

            response = self.llm.generate(prompt, temperature=0.7)

            if response:
                # Parse Varianten (eine pro Zeile)
                variants = [q.strip() for q in response.split('\n') if q.strip()]
                # Entferne Nummerierungen falls vorhanden
                variants = [re.sub(r'^\d+[\.\)]\s*', '', q) for q in variants]
                # Nehme nur die gewünschte Anzahl
                variants = variants[:n_variants]

                # Füge Original hinzu
                all_queries = [original_query] + variants
                logger.info(f"Multi-Query: {len(all_queries)} Varianten generiert")
                return all_queries

        except Exception as e:
            logger.warning(f"Multi-Query Generierung fehlgeschlagen: {e}")

        # Fallback: nur Original-Query
        return [original_query]

    def search_documents(
        self,
        query: str,
        n_results: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Führt semantische Dokumentensuche durch

        Args:
            query: Suchanfrage
            n_results: Anzahl der Ergebnisse
            filters: Optional filter (z.B. {"document_type": "invoice"})

        Returns:
            Liste von relevanten Dokumenten mit Metadaten
        """
        try:
            # Auto-Filter-Extraktion wenn keine Filter gegeben
            if filters is None:
                extracted_filters = self.metadata_extractor.extract_filters(query)
                filters = self.metadata_extractor.convert_to_chromadb_filter(extracted_filters)
                if filters:
                    logger.info(f"Auto-Filter aktiviert: {filters}")

            # Query mit Synonymen erweitern
            expanded_query = self._expand_query(query)

            # Query-Embedding erstellen (mit erweiterter Query)
            logger.info(f"Suche nach: '{query}'")
            query_embedding = self.embeddings.generate_embedding(expanded_query)

            if not query_embedding:
                logger.error("Konnte kein Embedding für Query erstellen")
                return []

            # Semantische Suche durchführen
            results = self.vector_store.search(
                query_embedding=query_embedding,
                n_results=n_results,
                where=filters
            )

            logger.info(f"Gefunden: {len(results)} relevante Dokumente")
            return results

        except Exception as e:
            logger.error(f"Fehler bei der Dokumentensuche: {e}")
            return []

    def search_documents_multi(
        self,
        query: str,
        n_results: int = 10,
        use_multi_query: bool = True,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Erweiterte Suche mit Multi-Query Approach

        Args:
            query: Suchanfrage
            n_results: Gesamt-Anzahl der Ergebnisse
            use_multi_query: Ob Multi-Query verwendet werden soll
            filters: Optional filter

        Returns:
            Deduplizierte Liste von relevanten Dokumenten
        """
        try:
            # Generiere mehrere Varianten der Frage
            if use_multi_query and os.getenv('USE_MULTI_QUERY', 'true').lower() == 'true':
                queries = self._generate_multi_queries(query, n_variants=2)
            else:
                queries = [query]

            # Suche mit allen Query-Varianten
            all_results = []
            results_per_query = max(n_results // len(queries), 3)

            for q in queries:
                results = self.search_documents(q, n_results=results_per_query, filters=filters)
                all_results.extend(results)

            # Deduplizierung basierend auf doc_id
            seen_docs = set()
            dedup_results = []

            for result in all_results:
                doc_id = result['doc_id']
                if doc_id not in seen_docs:
                    seen_docs.add(doc_id)
                    dedup_results.append(result)

            # Sortiere nach Distance (beste zuerst)
            dedup_results.sort(key=lambda x: x.get('distance', 999))

            # Limitiere auf n_results
            final_results = dedup_results[:n_results]

            logger.info(f"Multi-Query Suche: {len(all_results)} gesamt, {len(final_results)} nach Deduplizierung")
            return final_results

        except Exception as e:
            logger.error(f"Fehler bei Multi-Query Suche: {e}")
            # Fallback auf normale Suche
            return self.search_documents(query, n_results, filters)

    def answer_question(
        self,
        question: str,
        n_context_docs: int = 3,
        include_sources: bool = True
    ) -> Dict[str, Any]:
        """
        Beantwortet eine Frage basierend auf den indexierten Dokumenten (RAG)

        Args:
            question: Die zu beantwortende Frage
            n_context_docs: Anzahl der Kontext-Dokumente für RAG
            include_sources: Ob Quellen-Dokumente zurückgegeben werden sollen

        Returns:
            Dictionary mit Antwort und optional Quellen
        """
        try:
            # 1. Relevante Dokumente finden (Retrieval) mit Multi-Query
            logger.info(f"Beantworte Frage: '{question}'")

            # Nutze Multi-Query für bessere Ergebnisse
            use_multi = os.getenv('USE_MULTI_QUERY', 'true').lower() == 'true'
            if use_multi:
                relevant_docs = self.search_documents_multi(query=question, n_results=n_context_docs * 2)
                # Nehme nur die besten n_context_docs
                relevant_docs = relevant_docs[:n_context_docs]
            else:
                relevant_docs = self.search_documents(query=question, n_results=n_context_docs)

            if not relevant_docs:
                return {
                    'answer': "Ich konnte keine relevanten Dokumente finden, um diese Frage zu beantworten.",
                    'sources': [],
                    'confidence': 'low'
                }

            # 2. Kontext aus Dokumenten erstellen
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

                # Quellen sammeln
                if include_sources:
                    sources.append({
                        'doc_id': doc['doc_id'],
                        'title': doc['metadata'].get('title', 'Unbekannt'),
                        'correspondent': doc['metadata'].get('correspondent', ''),
                        'document_type': doc['metadata'].get('document_type', ''),
                        'relevance_score': 1 - (doc.get('distance', 0) / 2) if doc.get('distance') else None
                    })

            context = "\n\n".join(context_parts)

            # 3. Prompt für LLM erstellen (Augmentation)
            prompt = self._create_rag_prompt(question, context)

            # 4. Antwort generieren (Generation)
            logger.info("Generiere Antwort mit LLM...")
            answer = self.llm.generate(prompt)

            if not answer:
                return {
                    'answer': "Entschuldigung, ich konnte keine Antwort generieren.",
                    'sources': sources if include_sources else [],
                    'confidence': 'low'
                }

            # 5. Antwort zurückgeben
            result = {
                'answer': answer.strip(),
                'sources': sources if include_sources else [],
                'confidence': self._estimate_confidence(relevant_docs, answer)
            }

            logger.info("Antwort erfolgreich generiert")
            return result

        except Exception as e:
            logger.error(f"Fehler beim Beantworten der Frage: {e}")
            return {
                'answer': f"Es ist ein Fehler aufgetreten: {str(e)}",
                'sources': [],
                'confidence': 'low'
            }

    def _create_rag_prompt(self, question: str, context: str) -> str:
        """
        Erstellt einen RAG-Prompt für das LLM

        Args:
            question: Die Frage
            context: Der Kontext aus relevanten Dokumenten

        Returns:
            Formatierter Prompt
        """
        prompt = f"""Du bist ein hilfreicher Assistent, der Fragen über Dokumente beantwortet.

Kontext aus relevanten Dokumenten:
{context}

Frage: {question}

Anleitung:
- Beantworte die Frage basierend NUR auf den bereitgestellten Dokumenten
- WICHTIG: Verstehe Synonyme! Beispiele:
  * "Steuer ID" = "Steuer-Identifikationsnummer" = "Steuernummer" = "Tax ID"
  * "Rechnung" = "Invoice" = "Faktura"
  * "Adresse" = "Anschrift" = "Wohnort"
- Wenn die Dokumente die Information unter einem anderen Namen enthalten, nutze sie trotzdem!
- Wenn die Dokumente keine Antwort enthalten, sage das ehrlich
- Sei präzise und konkret - zitiere die genaue Fundstelle
- Gib Dokumentnummer an wenn du etwas zitierst (z.B. "laut Dokument 2")
- Antworte auf Deutsch in vollständigen Sätzen

Antwort:"""

        return prompt

    def _estimate_confidence(self, relevant_docs: List[Dict], answer: str) -> str:
        """
        Schätzt die Konfidenz der Antwort basierend auf mehreren Faktoren

        Args:
            relevant_docs: Die verwendeten Dokumente
            answer: Die generierte Antwort

        Returns:
            'high', 'medium', oder 'low'
        """
        if not relevant_docs:
            return 'low'

        score = 0
        max_score = 100

        # Faktor 1: Durchschnittliche Distanz der Top-3 Dokumente (40 Punkte)
        top_distances = [doc.get('distance', 1.0) for doc in relevant_docs[:3]]
        avg_distance = sum(top_distances) / len(top_distances)

        if avg_distance < 0.3:
            score += 40
        elif avg_distance < 0.5:
            score += 30
        elif avg_distance < 0.7:
            score += 15
        else:
            score += 5

        # Faktor 2: Beste Übereinstimmung (30 Punkte)
        best_distance = relevant_docs[0].get('distance', 1.0)

        if best_distance < 0.2:
            score += 30
        elif best_distance < 0.4:
            score += 20
        elif best_distance < 0.6:
            score += 10
        else:
            score += 3

        # Faktor 3: Anzahl relevanter Dokumente (15 Punkte)
        num_docs = len(relevant_docs)
        if num_docs >= 3:
            score += 15
        elif num_docs >= 2:
            score += 10
        else:
            score += 5

        # Faktor 4: Antwort-Qualität (15 Punkte)
        answer_lower = answer.lower()

        # Negativ-Indikatoren
        negative_phrases = [
            'keine antwort',
            'nicht beantworten',
            'keine information',
            'nicht gefunden',
            'konnte nicht',
            'keine relevanten dokumente',
            'ich weiß nicht',
            'unklar'
        ]

        has_negative = any(phrase in answer_lower for phrase in negative_phrases)

        if has_negative:
            score += 0  # Keine Punkte bei negativen Phrasen
        elif len(answer) > 100:  # Detaillierte Antwort
            score += 15
        elif len(answer) > 50:
            score += 10
        else:
            score += 5

        # Konfidenz-Level basierend auf Gesamtpunktzahl
        confidence_percent = (score / max_score) * 100

        if confidence_percent >= 70:
            return 'high'
        elif confidence_percent >= 45:
            return 'medium'
        else:
            return 'low'

    def get_conversation_context(
        self,
        conversation_history: List[Dict[str, str]],
        current_question: str
    ) -> str:
        """
        Erstellt Kontext aus Konversationshistorie für Follow-up Fragen

        Args:
            conversation_history: Liste von {"role": "user/assistant", "content": "..."}
            current_question: Aktuelle Frage

        Returns:
            Formatierter Konversations-Kontext
        """
        context_parts = ["Bisherige Konversation:"]

        for msg in conversation_history[-3:]:  # Nur letzte 3 Nachrichten
            role = "Nutzer" if msg['role'] == 'user' else "Assistent"
            context_parts.append(f"{role}: {msg['content']}")

        context_parts.append(f"\nAktuelle Frage: {current_question}")

        return "\n".join(context_parts)
