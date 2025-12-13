"""
Entity Resolution Service

Handles cross-document entity linking and deduplication.
Uses fuzzy matching and normalization to identify when different mentions
refer to the same real-world entity (e.g., "John Doe" = "J. Doe" = "John D.").
"""

import json
import logging
import re
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class EntityResolver:
    """
    Resolves entity mentions to canonical entities using fuzzy matching.
    """

    # Similarity thresholds for matching
    THRESHOLDS = {
        "PERSON": 0.85,  # Stricter for people (avoid false positives)
        "ORG": 0.80,  # Organizations can have more variations
        "GPE": 0.90,  # Geographic entities should be exact
        "default": 0.85,
    }

    def __init__(self):
        pass

    @staticmethod
    def normalize_text(text: str) -> str:
        """
        Normalize entity text for comparison.
        - Lowercase
        - Remove extra whitespace
        - Remove punctuation except hyphens
        """
        text = text.lower().strip()
        text = re.sub(r"[^\w\s\-]", "", text)  # Keep alphanumeric, spaces, hyphens
        text = re.sub(r"\s+", " ", text)  # Collapse whitespace
        return text

    @staticmethod
    def extract_initials(text: str) -> str:
        """
        Extract initials from a name.
        "John Doe" -> "jd"
        "J. Doe" -> "jd"
        """
        words = text.split()
        initials = "".join([w[0].lower() for w in words if w])
        return initials

    @staticmethod
    def similarity_score(text1: str, text2: str) -> float:
        """
        Calculate similarity between two strings using SequenceMatcher.
        Returns a float between 0 and 1.
        """
        return SequenceMatcher(None, text1, text2).ratio()

    def is_match(
        self,
        mention1: str,
        mention2: str,
        label: str,
        threshold: Optional[float] = None,
    ) -> bool:
        """
        Determine if two entity mentions refer to the same entity.

        Matching strategies:
        1. Exact match (normalized)
        2. Fuzzy string similarity
        3. Initials match (for PERSON)
        4. Substring containment (for ORG)
        """
        # Use label-specific threshold if not provided
        if threshold is None:
            threshold = self.THRESHOLDS.get(label, self.THRESHOLDS["default"])

        norm1 = self.normalize_text(mention1)
        norm2 = self.normalize_text(mention2)

        # 1. Exact match
        if norm1 == norm2:
            return True

        # 2. Fuzzy similarity
        sim = self.similarity_score(norm1, norm2)
        if sim >= threshold:
            return True

        # 3. Initials matching (PERSON only)
        if label == "PERSON":
            init1 = self.extract_initials(mention1)
            init2 = self.extract_initials(mention2)

            # "J. Doe" matches "John Doe" if initials match and last name matches
            words1 = norm1.split()
            words2 = norm2.split()

            # Check if one is abbreviated version of the other
            if len(words1) > 1 and len(words2) > 1:
                # Last name must match
                if words1[-1] == words2[-1]:
                    # First initial must match
                    if init1[0] == init2[0]:
                        return True

        # 4. Substring containment (ORG only, with caution)
        if label == "ORG":
            # "Microsoft" should match "Microsoft Corporation"
            # But "US" should NOT match "US Bank"
            if len(norm1) >= 5 and len(norm2) >= 5:  # Avoid short acronyms
                if norm1 in norm2 or norm2 in norm1:
                    return True

        return False

    def find_canonical_match(
        self,
        mention: str,
        label: str,
        existing_canonicals: List[Dict],
    ) -> Optional[int]:
        """
        Find a matching canonical entity from a list.

        Args:
            mention: The entity mention text
            label: Entity type (PERSON, ORG, GPE, etc.)
            existing_canonicals: List of dicts with 'id', 'canonical_name', 'aliases'

        Returns:
            Canonical entity ID if match found, None otherwise
        """
        for canonical in existing_canonicals:
            # Check canonical name
            if self.is_match(mention, canonical["canonical_name"], label):
                return canonical["id"]

            # Check aliases
            if canonical.get("aliases"):
                try:
                    aliases = json.loads(canonical["aliases"])
                    for alias in aliases:
                        if self.is_match(mention, alias, label):
                            return canonical["id"]
                except json.JSONDecodeError:
                    logger.warning(
                        f"Invalid JSON in aliases for canonical {canonical['id']}"
                    )

        return None

    def select_best_name(self, names: List[str]) -> str:
        """
        Select the best canonical name from a list of variations.
        Prefers longer, more formal names.

        "J. Doe" vs "John Doe" -> "John Doe"
        "Microsoft" vs "Microsoft Corp." -> "Microsoft Corporation"
        """
        if not names:
            return ""

        # Prefer longest name (usually most complete)
        names_sorted = sorted(names, key=len, reverse=True)

        # But avoid names with too many extra characters (noise)
        best = names_sorted[0]
        for name in names_sorted:
            # Prefer name without excessive punctuation
            punct_count = sum(1 for c in name if not c.isalnum() and c != " ")
            best_punct = sum(1 for c in best if not c.isalnum() and c != " ")

            # Only switch to a shorter name with less punctuation if the length difference is small
            # (e.g. "John Doe" vs "John Doe." -> prefer "John Doe")
            # But "Microsoft Corporation" vs "Microsoft" -> prefer "Microsoft Corporation"
            if punct_count < best_punct:
                if len(best) - len(name) < 4:
                    best = name

        return best

    @staticmethod
    def sanitize_for_json(text: str) -> str:
        """
        Sanitize text for JSON storage by removing/replacing control characters.

        Control characters (ASCII 0-31) are invalid inside JSON strings unless escaped.
        Common problematic characters:
        - Newlines (\n, \r) - from multi-line entity extraction
        - Tabs (\t)
        - Null bytes (\x00)

        This prevents "Invalid control character" JSON decode errors.
        """
        if not text:
            return text

        # Replace newlines and tabs with spaces
        text = text.replace("\n", " ").replace("\r", " ").replace("\t", " ")
        # Remove any other control characters (ASCII 0-31 except the ones above)
        text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
        # Collapse multiple spaces
        text = re.sub(r" +", " ", text)
        return text.strip()

    def merge_aliases(self, existing_aliases: str, new_alias: str) -> str:
        """
        Merge a new alias into existing aliases JSON.
        Returns updated JSON string.
        """
        try:
            aliases = json.loads(existing_aliases) if existing_aliases else []
        except json.JSONDecodeError:
            aliases = []

        # Sanitize the new alias before adding
        sanitized_alias = self.sanitize_for_json(new_alias)

        if sanitized_alias and sanitized_alias not in aliases:
            aliases.append(sanitized_alias)

        return json.dumps(aliases)
