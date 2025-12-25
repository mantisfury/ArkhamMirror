"""Entity linking - map mentions to canonical entities."""

import logging
from typing import List

from ..models import EntityMention, Entity, EntityLinkingResult

logger = logging.getLogger(__name__)


class EntityLinker:
    """
    Link entity mentions to canonical entities.

    Example:
    - "Apple", "AAPL", "the company" -> Apple Inc. (canonical)
    - "John", "Mr. Smith", "he" -> John Smith (canonical)
    """

    def __init__(self, database_service=None):
        """
        Initialize entity linker.

        Args:
            database_service: Database service for canonical entities
        """
        self.db = database_service
        self.entity_cache = {}

    async def link_mentions(
        self,
        mentions: List[EntityMention],
    ) -> List[EntityLinkingResult]:
        """
        Link entity mentions to canonical entities.

        Args:
            mentions: List of entity mentions to link

        Returns:
            List of linking results
        """
        results = []

        for mention in mentions:
            result = await self._link_single_mention(mention)
            results.append(result)

        return results

    async def _link_single_mention(
        self,
        mention: EntityMention,
    ) -> EntityLinkingResult:
        """
        Link a single mention to a canonical entity.

        Args:
            mention: Entity mention to link

        Returns:
            Linking result with canonical entity ID
        """
        # Try exact match first
        canonical_id = await self._exact_match(mention.text)
        if canonical_id:
            return EntityLinkingResult(
                mention=mention,
                canonical_entity_id=canonical_id,
                confidence=1.0,
                reason="exact_match",
            )

        # Try fuzzy match
        canonical_id, confidence = await self._fuzzy_match(mention.text)
        if canonical_id:
            return EntityLinkingResult(
                mention=mention,
                canonical_entity_id=canonical_id,
                confidence=confidence,
                reason="fuzzy_match",
            )

        # No match - create new canonical entity
        return EntityLinkingResult(
            mention=mention,
            canonical_entity_id=None,
            confidence=0.0,
            reason="no_match",
        )

    async def _exact_match(self, text: str) -> str | None:
        """
        Find exact match in canonical entities.

        Args:
            text: Entity text to match

        Returns:
            Canonical entity ID, or None
        """
        if not self.db:
            return None

        # Query database for exact match
        # In production: SELECT id FROM canonical_entities WHERE name = text
        return None

    async def _fuzzy_match(self, text: str) -> tuple[str | None, float]:
        """
        Find fuzzy match using string similarity.

        Args:
            text: Entity text to match

        Returns:
            (canonical_entity_id, confidence) or (None, 0.0)
        """
        if not self.db:
            return None, 0.0

        # In production: Use Levenshtein distance or embeddings
        # For now, return no match
        return None, 0.0

    async def create_canonical_entity(
        self,
        mention: EntityMention,
    ) -> str:
        """
        Create a new canonical entity from a mention.

        Args:
            mention: Entity mention to canonicalize

        Returns:
            New canonical entity ID
        """
        if not self.db:
            # Generate temporary ID
            return f"temp_{hash(mention.text)}"

        # In production: INSERT INTO canonical_entities
        entity_id = f"entity_{hash(mention.text)}"

        logger.info(f"Created canonical entity {entity_id} for '{mention.text}'")
        return entity_id
