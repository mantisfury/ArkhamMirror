"""
NERWorker - Named Entity Recognition worker for the cpu-ner pool.

Extracts named entities from text using spaCy's en_core_web_sm model.
Returns entity text, type, position, and confidence scores.
"""

from typing import Dict, Any
import logging

from arkham_frame.workers.base import BaseWorker

logger = logging.getLogger(__name__)


# Entity type mapping from spaCy to standard types
ENTITY_TYPES = {
    "PERSON": "person",
    "ORG": "organization",
    "GPE": "location",  # Geopolitical entity
    "LOC": "location",
    "DATE": "date",
    "TIME": "time",
    "MONEY": "money",
    "PERCENT": "percent",
    "FAC": "facility",
    "PRODUCT": "product",
    "EVENT": "event",
    "WORK_OF_ART": "work",
    "LAW": "law",
    "LANGUAGE": "language",
    "NORP": "group",  # Nationalities, religious, political groups
}


class NERWorker(BaseWorker):
    """
    Named Entity Recognition worker.

    Processes text to extract named entities using spaCy.

    Payload format:
        {
            "text": "Document text to process...",
            "doc_id": "optional-document-id",
            "chunk_id": "optional-chunk-id"
        }

    Returns:
        {
            "entities": [
                {
                    "text": "Entity text",
                    "label": "person|organization|location|date|...",
                    "start": 0,  # Character offset
                    "end": 10,   # Character offset
                    "confidence": 0.95
                }
            ],
            "success": True
        }
    """

    pool = "cpu-ner"
    name = "NERWorker"
    job_timeout = 30.0  # NER is usually fast

    # Class-level spaCy model (loaded once)
    _nlp = None
    _model_error = None

    @classmethod
    def _get_nlp(cls):
        """
        Lazy-load spaCy model.

        Returns:
            spaCy language model or None if unavailable.
        """
        if cls._nlp is not None:
            return cls._nlp

        if cls._model_error is not None:
            # Already tried and failed
            return None

        try:
            import spacy

            logger.info("Loading spaCy model en_core_web_sm...")
            cls._nlp = spacy.load("en_core_web_sm")
            logger.info("spaCy model loaded successfully")
            return cls._nlp

        except ImportError:
            cls._model_error = "spaCy not installed. Install with: pip install spacy"
            logger.error(cls._model_error)
            return None

        except OSError:
            cls._model_error = (
                "spaCy model 'en_core_web_sm' not found. "
                "Install with: python -m spacy download en_core_web_sm"
            )
            logger.error(cls._model_error)
            return None

        except Exception as e:
            cls._model_error = f"Failed to load spaCy model: {str(e)}"
            logger.error(cls._model_error)
            return None

    async def process_job(self, job_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract named entities from text.

        Args:
            job_id: Unique job identifier
            payload: Job data with text, doc_id, chunk_id

        Returns:
            Result dict with entities list and success status.

        Raises:
            ValueError: If text is missing or model unavailable.
        """
        # Validate payload
        text = payload.get("text")
        if not text:
            raise ValueError("Missing required field: text")

        doc_id = payload.get("doc_id", "")
        chunk_id = payload.get("chunk_id", "")

        # Get spaCy model
        nlp = self._get_nlp()
        if nlp is None:
            return {
                "success": False,
                "error": self._model_error,
                "entities": [],
            }

        # Process text with spaCy
        try:
            doc = nlp(text)

            # Extract entities
            entities = []
            for ent in doc.ents:
                # Map spaCy type to standard type
                standard_type = ENTITY_TYPES.get(ent.label_, "other")

                entity = {
                    "text": ent.text,
                    "label": standard_type,
                    "start": ent.start_char,
                    "end": ent.end_char,
                    "confidence": self._get_entity_confidence(ent),
                }

                # Include original spaCy label for debugging
                if ent.label_ not in ENTITY_TYPES:
                    entity["spacy_label"] = ent.label_

                entities.append(entity)

            logger.info(
                f"Extracted {len(entities)} entities from text "
                f"(doc_id={doc_id}, chunk_id={chunk_id})"
            )

            return {
                "success": True,
                "entities": entities,
                "doc_id": doc_id,
                "chunk_id": chunk_id,
                "entity_count": len(entities),
            }

        except Exception as e:
            logger.error(f"NER processing failed: {e}")
            raise

    @staticmethod
    def _get_entity_confidence(ent) -> float:
        """
        Get confidence score for an entity.

        spaCy's en_core_web_sm doesn't provide confidence scores directly,
        so we use a heuristic based on entity length and capitalization.

        Args:
            ent: spaCy entity object

        Returns:
            Confidence score between 0.0 and 1.0
        """
        # Base confidence
        confidence = 0.8

        # Boost for proper capitalization (first letter uppercase)
        if ent.text and ent.text[0].isupper():
            confidence += 0.1

        # Boost for multi-word entities (often more reliable)
        if len(ent.text.split()) > 1:
            confidence += 0.05

        # Cap at 1.0
        return min(confidence, 1.0)
