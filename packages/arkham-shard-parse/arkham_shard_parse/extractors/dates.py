"""Date and time extraction from text."""

import logging
import re
from datetime import datetime
from typing import List

from ..models import DateMention

logger = logging.getLogger(__name__)


class DateExtractor:
    """Extract dates and times from text."""

    def __init__(self):
        """Initialize date extractor."""
        self.dateparser_available = False
        try:
            import dateparser
            self.dateparser = dateparser
            self.dateparser_available = True
            logger.info("dateparser library available")
        except ImportError:
            logger.warning("dateparser not available, using basic patterns")

    def extract(
        self,
        text: str,
        doc_id: str | None = None,
        chunk_id: str | None = None,
    ) -> List[DateMention]:
        """
        Extract date mentions from text.

        Args:
            text: Text to process
            doc_id: Source document ID
            chunk_id: Source chunk ID

        Returns:
            List of date mentions
        """
        mentions = []

        if self.dateparser_available:
            mentions = self._extract_with_dateparser(text, doc_id, chunk_id)
        else:
            mentions = self._extract_with_regex(text, doc_id, chunk_id)

        logger.debug(f"Extracted {len(mentions)} date mentions")
        return mentions

    def _extract_with_dateparser(
        self,
        text: str,
        doc_id: str | None,
        chunk_id: str | None,
    ) -> List[DateMention]:
        """Extract dates using dateparser library."""
        mentions = []

        # Common date patterns to look for
        patterns = [
            r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b',  # MM/DD/YYYY
            r'\b\d{4}[/-]\d{1,2}[/-]\d{1,2}\b',    # YYYY-MM-DD
            r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2},? \d{4}\b',
            r'\b\d{1,2} (?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{4}\b',
        ]

        for pattern in patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                date_text = match.group()

                try:
                    parsed = self.dateparser.parse(date_text)

                    mention = DateMention(
                        text=date_text,
                        normalized_date=parsed,
                        date_type="absolute",
                        confidence=0.9 if parsed else 0.5,
                        start_char=match.start(),
                        end_char=match.end(),
                        source_doc_id=doc_id,
                        source_chunk_id=chunk_id,
                    )
                    mentions.append(mention)
                except Exception as e:
                    logger.debug(f"Could not parse date '{date_text}': {e}")

        return mentions

    def _extract_with_regex(
        self,
        text: str,
        doc_id: str | None,
        chunk_id: str | None,
    ) -> List[DateMention]:
        """Extract dates using simple regex patterns."""
        mentions = []

        # ISO date format YYYY-MM-DD
        pattern = r'\b(\d{4})-(\d{2})-(\d{2})\b'

        for match in re.finditer(pattern, text):
            date_text = match.group()

            try:
                year, month, day = match.groups()
                normalized = datetime(int(year), int(month), int(day))

                mention = DateMention(
                    text=date_text,
                    normalized_date=normalized,
                    date_type="absolute",
                    confidence=0.8,
                    start_char=match.start(),
                    end_char=match.end(),
                    source_doc_id=doc_id,
                    source_chunk_id=chunk_id,
                )
                mentions.append(mention)
            except ValueError:
                continue

        return mentions

    def extract_relative_dates(self, text: str) -> List[DateMention]:
        """
        Extract relative date references like 'yesterday', 'last week'.

        Args:
            text: Text to process

        Returns:
            List of relative date mentions
        """
        mentions = []

        # Patterns for relative dates
        relative_patterns = [
            r'\b(yesterday|today|tomorrow)\b',
            r'\b(last|next) (week|month|year)\b',
            r'\b(\d+) (days?|weeks?|months?|years?) ago\b',
        ]

        for pattern in relative_patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                mention = DateMention(
                    text=match.group(),
                    normalized_date=None,  # Would need reference date
                    date_type="relative",
                    confidence=0.7,
                    start_char=match.start(),
                    end_char=match.end(),
                )
                mentions.append(mention)

        return mentions
