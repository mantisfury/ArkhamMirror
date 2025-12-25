"""Coreference resolution - resolve pronouns to entities."""

import logging
from typing import List, Dict

from ..models import EntityMention

logger = logging.getLogger(__name__)


class CoreferenceResolver:
    """
    Resolve coreferences - pronouns and references to entities.

    Example:
    "John Smith announced he would resign." -> "he" = John Smith
    "Apple launched a new product. The company said..." -> "The company" = Apple
    """

    def __init__(self):
        """Initialize coreference resolver."""
        self.pronouns = {
            "he", "him", "his",
            "she", "her", "hers",
            "they", "them", "their",
            "it", "its",
        }

        self.generic_refs = {
            "the company", "the organization",
            "the person", "the individual",
            "the agency", "the department",
        }

    def resolve(
        self,
        text: str,
        entities: List[EntityMention],
    ) -> Dict[str, str]:
        """
        Resolve coreferences in text.

        Args:
            text: Text to analyze
            entities: Known entities in the text

        Returns:
            Dict mapping coreference text to entity text
        """
        resolutions = {}

        # Very simple heuristic: pronouns refer to nearest entity
        words = text.split()
        last_person = None
        last_org = None

        for i, word in enumerate(words):
            word_lower = word.lower().strip('.,;:!?')

            # Check if it's a pronoun
            if word_lower in {"he", "him", "his", "she", "her"}:
                if last_person:
                    resolutions[word] = last_person.text

            elif word_lower in {"it", "its"}:
                if last_org:
                    resolutions[word] = last_org.text

            # Update last seen entities
            for entity in entities:
                entity_words = entity.text.split()
                if all(w in words[i:i+len(entity_words)] for w in entity_words):
                    if entity.entity_type.value in ["PERSON"]:
                        last_person = entity
                    elif entity.entity_type.value in ["ORG", "GPE"]:
                        last_org = entity

        logger.debug(f"Resolved {len(resolutions)} coreferences")
        return resolutions

    def resolve_chains(
        self,
        text: str,
        entities: List[EntityMention],
    ) -> List[List[str]]:
        """
        Build coreference chains.

        Args:
            text: Text to analyze
            entities: Known entities

        Returns:
            List of coreference chains (each chain is a list of mentions)

        Example:
            [["John Smith", "he", "John"], ["Apple Inc.", "the company", "it"]]
        """
        chains = []

        # Group entities by canonical name
        entity_groups = {}
        for entity in entities:
            key = entity.text.lower()
            if key not in entity_groups:
                entity_groups[key] = []
            entity_groups[key].append(entity)

        # Each group becomes a chain
        for mentions in entity_groups.values():
            chain = [m.text for m in mentions]
            chains.append(chain)

        return chains
