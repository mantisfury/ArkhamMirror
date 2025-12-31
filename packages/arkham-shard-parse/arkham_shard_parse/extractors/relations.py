"""Entity relationship extraction."""

import logging
from typing import List

from ..models import EntityRelationship, EntityMention

logger = logging.getLogger(__name__)


class RelationExtractor:
    """
    Extract relationships between entities.

    Examples:
    - "John works for Microsoft"
    - "Apple acquired Beats"
    - "CEO of Tesla"
    """

    CO_OCCURRENCE_DISTANCE = 150

    def __init__(self, enable_co_occurrence: bool = True):
        """Initialize relation extractor."""
        self.patterns = self._load_patterns()
        self.enable_co_occurrence = enable_co_occurrence

    def _load_patterns(self) -> dict:
        """
        Load relation extraction patterns.

        In production, this would load from config or model.
        """
        return {
            "employment": [
                "works for", "worked for", "employed by",
                "employee of", "CEO of", "founder of",
                "president of", "director of", "manager of",
            ],
            "ownership": [
                "owns", "owned by", "acquired",
                "purchased", "bought", "sold to",
            ],
            "association": [
                "member of", "part of", "partner of",
                "affiliated with", "associated with",
            ],
            "location": [
                "based in", "located in", "headquartered in",
                "office in", "resides in", "from",
            ],
            "transaction": [
                "paid", "received", "transferred",
                "sent to", "received from",
            ],
            "communication": [
                "contacted", "called", "emailed",
                "met with", "spoke with",
            ],
        }

    def extract(
        self,
        text: str,
        entities: List[EntityMention],
        doc_id: str | None = None,
    ) -> List[EntityRelationship]:
        """
        Extract relationships between entities in text.

        Args:
            text: Text to analyze
            entities: Entities found in the text
            doc_id: Source document ID

        Returns:
            List of entity relationships
        """
        relationships = []

        # For each pair of entities, check if there's a relation
        for i, entity1 in enumerate(entities):
            for entity2 in entities[i+1:]:
                relation = self._find_relation(text, entity1, entity2)

                if relation:
                    relationships.append(
                        EntityRelationship(
                            source_entity_id=entity1.text,  # Would be canonical ID
                            target_entity_id=entity2.text,
                            relation_type=relation["type"],
                            confidence=relation["confidence"],
                            evidence_text=relation.get("evidence"),
                            source_doc_id=doc_id,
                        )
                    )

        logger.debug(f"Extracted {len(relationships)} relationships")
        return relationships

    def _find_relation(
        self,
        text: str,
        entity1: EntityMention,
        entity2: EntityMention,
    ) -> dict | None:
        """Check if two entities have a relationship."""
        start = min(entity1.end_char, entity2.end_char)
        end = max(entity1.start_char, entity2.start_char)

        if start >= end or start < 0 or end > len(text):
            distance = abs(entity1.start_char - entity2.start_char)
            if self.enable_co_occurrence and distance <= self.CO_OCCURRENCE_DISTANCE:
                return {
                    "type": "co_occurrence",
                    "confidence": max(0.3, 0.5 - distance / 500),
                    "evidence": f"Entities within {distance} chars",
                }
            return None

        between_text = text[start:end].lower()
        distance = end - start

        # Check explicit patterns first
        for rel_type, patterns in self.patterns.items():
            for pattern in patterns:
                if pattern in between_text:
                    return {
                        "type": rel_type,
                        "confidence": 0.75,
                        "evidence": between_text.strip()[:200],
                    }

        # Check for co-occurrence
        if self.enable_co_occurrence and distance <= self.CO_OCCURRENCE_DISTANCE:
            return {
                "type": "co_occurrence",
                "confidence": max(0.3, 0.5 - distance / 500),
                "evidence": between_text.strip()[:200] or f"Entities within {distance} chars",
            }

        return None
