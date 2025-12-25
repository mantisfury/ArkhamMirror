"""Named Entity Recognition using spaCy."""

import logging
import uuid
from typing import List

from ..models import EntityMention, EntityType

logger = logging.getLogger(__name__)


class NERExtractor:
    """
    Extract named entities from text using spaCy.

    This is a lightweight wrapper that dispatches heavy NER work
    to cpu-ner worker pool for parallel processing.
    """

    def __init__(self, model_name: str = "en_core_web_sm"):
        """
        Initialize NER extractor.

        Args:
            model_name: spaCy model to use
        """
        self.model_name = model_name
        self.nlp = None

    def initialize(self):
        """
        Load spaCy model.

        NOTE: In production, this should be called in worker process,
        not in main process. For now, we mock it.
        """
        try:
            import spacy
            self.nlp = spacy.load(self.model_name)
            logger.info(f"Loaded spaCy model: {self.model_name}")
        except Exception as e:
            logger.warning(f"Could not load spaCy model: {e}")
            logger.warning("NER will run in mock mode")
            self.nlp = None

    def extract(
        self,
        text: str,
        doc_id: str | None = None,
        chunk_id: str | None = None,
    ) -> List[EntityMention]:
        """
        Extract entities from text.

        Args:
            text: Text to process
            doc_id: Source document ID
            chunk_id: Source chunk ID

        Returns:
            List of entity mentions
        """
        if not self.nlp:
            logger.debug("NER running in mock mode")
            return self._mock_extract(text, doc_id, chunk_id)

        doc = self.nlp(text)
        mentions = []

        for ent in doc.ents:
            try:
                entity_type = EntityType[ent.label_]
            except KeyError:
                entity_type = EntityType.OTHER

            # Get sentence context
            sentence = ent.sent.text if hasattr(ent, 'sent') else None

            mention = EntityMention(
                text=ent.text,
                entity_type=entity_type,
                start_char=ent.start_char,
                end_char=ent.end_char,
                confidence=0.85,  # spaCy doesn't provide confidence scores
                sentence=sentence,
                source_doc_id=doc_id,
                source_chunk_id=chunk_id,
            )
            mentions.append(mention)

        logger.debug(f"Extracted {len(mentions)} entities from text")
        return mentions

    def _mock_extract(
        self,
        text: str,
        doc_id: str | None = None,
        chunk_id: str | None = None,
    ) -> List[EntityMention]:
        """
        Mock entity extraction for testing without spaCy.

        Looks for simple patterns like capitalized words.
        """
        mentions = []

        # Very simple heuristic: consecutive capitalized words
        words = text.split()
        i = 0

        while i < len(words):
            word = words[i]

            # Skip if first word of sentence or single letter
            if word and word[0].isupper() and len(word) > 1:
                entity_text = word
                start = i

                # Look for consecutive capitalized words
                j = i + 1
                while j < len(words) and words[j] and words[j][0].isupper():
                    entity_text += " " + words[j]
                    j += 1

                # Guess entity type based on context
                entity_type = EntityType.PERSON  # Default guess

                mention = EntityMention(
                    text=entity_text,
                    entity_type=entity_type,
                    start_char=0,  # Would need proper calculation
                    end_char=0,
                    confidence=0.5,  # Low confidence for mock
                    source_doc_id=doc_id,
                    source_chunk_id=chunk_id,
                )
                mentions.append(mention)

                i = j
            else:
                i += 1

        return mentions

    async def extract_async(
        self,
        text: str,
        worker_service=None,
        doc_id: str | None = None,
    ) -> List[EntityMention]:
        """
        Extract entities asynchronously using worker pool.

        Args:
            text: Text to process
            worker_service: Worker service for dispatching
            doc_id: Source document ID

        Returns:
            List of entity mentions
        """
        if not worker_service:
            # Fallback to synchronous
            return self.extract(text, doc_id)

        # Dispatch to cpu-ner worker pool
        job_id = str(uuid.uuid4())
        await worker_service.enqueue(
            pool="cpu-ner",
            job_id=job_id,
            payload={
                "text": text,
                "doc_id": doc_id,
                "model": self.model_name,
            },
            priority=2,
        )

        logger.debug(f"Dispatched NER job {job_id} to cpu-ner pool")

        # In real implementation, would wait for result
        # For now, return empty - result will come via event bus
        return []
