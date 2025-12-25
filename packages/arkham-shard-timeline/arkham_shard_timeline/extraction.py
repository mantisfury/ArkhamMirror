"""Date extraction and parsing engine."""

import logging
import re
import uuid
from datetime import datetime, timedelta
from typing import Optional

from dateutil import parser as dateutil_parser
from dateutil.relativedelta import relativedelta

from .models import (
    TimelineEvent,
    EventType,
    DatePrecision,
    ExtractionContext,
    NormalizedDate,
)

logger = logging.getLogger(__name__)


class DateExtractor:
    """
    Extracts temporal information from text.

    Handles various date formats including:
    - ISO dates (2024-01-15)
    - Natural language (January 15, 2024)
    - Relative dates (3 days ago, next week)
    - Periods (Q3 2024, summer 2023)
    - Approximate (around 2020, mid-century)
    """

    # Date pattern regexes
    ISO_DATE_PATTERN = re.compile(
        r'\b(\d{4})-(\d{1,2})-(\d{1,2})(?:T(\d{1,2}):(\d{1,2}):(\d{1,2}))?\b'
    )

    MONTH_DAY_YEAR_PATTERN = re.compile(
        r'\b(January|February|March|April|May|June|July|August|September|October|November|December|'
        r'Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})\b',
        re.IGNORECASE
    )

    DAY_MONTH_YEAR_PATTERN = re.compile(
        r'\b(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?(January|February|March|April|May|June|July|August|September|October|November|December|'
        r'Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec),?\s+(\d{4})\b',
        re.IGNORECASE
    )

    NUMERIC_DATE_PATTERN = re.compile(
        r'\b(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{2,4})\b'
    )

    YEAR_ONLY_PATTERN = re.compile(r'\b(19\d{2}|20\d{2})\b')

    QUARTER_PATTERN = re.compile(
        r'\b(Q[1-4]|first|second|third|fourth)\s+quarter\s+(?:of\s+)?(\d{4})\b',
        re.IGNORECASE
    )

    SEASON_PATTERN = re.compile(
        r'\b(spring|summer|fall|autumn|winter)\s+(?:of\s+)?(\d{4})\b',
        re.IGNORECASE
    )

    DECADE_PATTERN = re.compile(
        r'\b(?:the\s+)?(\d{4})s\b|'
        r'\b(early|mid|late)[\s\-]?(\d{2})s\b',
        re.IGNORECASE
    )

    RELATIVE_DAY_PATTERN = re.compile(
        r'\b(yesterday|today|tomorrow)\b',
        re.IGNORECASE
    )

    RELATIVE_WEEK_PATTERN = re.compile(
        r'\b(last|next|this)\s+(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b',
        re.IGNORECASE
    )

    RELATIVE_NUMERIC_PATTERN = re.compile(
        r'\b(\d+)\s+(days?|weeks?|months?|years?)\s+(ago|from\s+now)\b',
        re.IGNORECASE
    )

    APPROXIMATE_PATTERN = re.compile(
        r'\b(around|circa|about|approximately|roughly)\s+(\d{4})\b',
        re.IGNORECASE
    )

    TIME_PERIOD_PATTERN = re.compile(
        r'\b(early|mid|late)\s+(January|February|March|April|May|June|July|August|September|October|November|December|'
        r'Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)(?:\s+(\d{4}))?\b',
        re.IGNORECASE
    )

    def __init__(self):
        """Initialize the date extractor."""
        self.month_map = {
            'january': 1, 'jan': 1,
            'february': 2, 'feb': 2,
            'march': 3, 'mar': 3,
            'april': 4, 'apr': 4,
            'may': 5,
            'june': 6, 'jun': 6,
            'july': 7, 'jul': 7,
            'august': 8, 'aug': 8,
            'september': 9, 'sep': 9, 'sept': 9,
            'october': 10, 'oct': 10,
            'november': 11, 'nov': 11,
            'december': 12, 'dec': 12,
        }

        self.quarter_map = {
            'q1': 1, 'first': 1,
            'q2': 2, 'second': 2,
            'q3': 3, 'third': 3,
            'q4': 4, 'fourth': 4,
        }

        self.season_map = {
            'spring': 3,   # March
            'summer': 6,   # June
            'fall': 9,     # September
            'autumn': 9,   # September
            'winter': 12,  # December
        }

    def extract_events(
        self,
        text: str,
        document_id: str,
        context: Optional[ExtractionContext] = None
    ) -> list[TimelineEvent]:
        """
        Extract all temporal events from text.

        Args:
            text: Text to analyze
            document_id: Source document ID
            context: Extraction context (reference date, etc.)

        Returns:
            List of extracted timeline events
        """
        if context is None:
            context = ExtractionContext(reference_date=datetime.now())

        events = []

        # Try all extraction patterns
        events.extend(self._extract_iso_dates(text, document_id, context))
        events.extend(self._extract_natural_dates(text, document_id, context))
        events.extend(self._extract_numeric_dates(text, document_id, context))
        events.extend(self._extract_quarters(text, document_id, context))
        events.extend(self._extract_seasons(text, document_id, context))
        events.extend(self._extract_decades(text, document_id, context))
        events.extend(self._extract_relative_dates(text, document_id, context))
        events.extend(self._extract_approximate_dates(text, document_id, context))
        events.extend(self._extract_time_periods(text, document_id, context))

        # Sort by position in text
        events.sort(key=lambda e: e.span[0] if e.span else 0)

        return events

    def _extract_iso_dates(
        self,
        text: str,
        document_id: str,
        context: ExtractionContext
    ) -> list[TimelineEvent]:
        """Extract ISO format dates (2024-01-15)."""
        events = []

        for match in self.ISO_DATE_PATTERN.finditer(text):
            year = int(match.group(1))
            month = int(match.group(2))
            day = int(match.group(3))

            try:
                if match.group(4):  # Has time component
                    hour = int(match.group(4))
                    minute = int(match.group(5))
                    second = int(match.group(6))
                    date = datetime(year, month, day, hour, minute, second)
                    precision = DatePrecision.EXACT
                else:
                    date = datetime(year, month, day)
                    precision = DatePrecision.DAY

                event = TimelineEvent(
                    id=str(uuid.uuid4()),
                    document_id=document_id,
                    text=match.group(0),
                    date_start=date,
                    precision=precision,
                    confidence=0.99,  # ISO dates are very reliable
                    event_type=EventType.REFERENCE,
                    span=(match.start(), match.end()),
                )
                events.append(event)

            except ValueError as e:
                logger.debug(f"Invalid ISO date: {match.group(0)} - {e}")
                continue

        return events

    def _extract_natural_dates(
        self,
        text: str,
        document_id: str,
        context: ExtractionContext
    ) -> list[TimelineEvent]:
        """Extract natural language dates (January 15, 2024)."""
        events = []

        # Month Day, Year format
        for match in self.MONTH_DAY_YEAR_PATTERN.finditer(text):
            month_str = match.group(1).lower()
            day = int(match.group(2))
            year = int(match.group(3))

            month = self.month_map.get(month_str)
            if month:
                try:
                    date = datetime(year, month, day)
                    event = TimelineEvent(
                        id=str(uuid.uuid4()),
                        document_id=document_id,
                        text=match.group(0),
                        date_start=date,
                        precision=DatePrecision.DAY,
                        confidence=0.95,
                        event_type=EventType.REFERENCE,
                        span=(match.start(), match.end()),
                    )
                    events.append(event)
                except ValueError as e:
                    logger.debug(f"Invalid date: {match.group(0)} - {e}")

        # Day Month Year format
        for match in self.DAY_MONTH_YEAR_PATTERN.finditer(text):
            day = int(match.group(1))
            month_str = match.group(2).lower()
            year = int(match.group(3))

            month = self.month_map.get(month_str)
            if month:
                try:
                    date = datetime(year, month, day)
                    event = TimelineEvent(
                        id=str(uuid.uuid4()),
                        document_id=document_id,
                        text=match.group(0),
                        date_start=date,
                        precision=DatePrecision.DAY,
                        confidence=0.95,
                        event_type=EventType.REFERENCE,
                        span=(match.start(), match.end()),
                    )
                    events.append(event)
                except ValueError as e:
                    logger.debug(f"Invalid date: {match.group(0)} - {e}")

        return events

    def _extract_numeric_dates(
        self,
        text: str,
        document_id: str,
        context: ExtractionContext
    ) -> list[TimelineEvent]:
        """Extract numeric dates (01/15/2024 or 15/01/2024)."""
        events = []

        for match in self.NUMERIC_DATE_PATTERN.finditer(text):
            part1 = int(match.group(1))
            part2 = int(match.group(2))
            year = int(match.group(3))

            # Handle 2-digit years
            if year < 100:
                year = 2000 + year if year < 50 else 1900 + year

            # Try both MM/DD/YYYY and DD/MM/YYYY
            dates_to_try = []
            if part1 <= 12 and part2 <= 31:  # Could be MM/DD
                dates_to_try.append((part1, part2, 0.8))  # month, day, confidence
            if part2 <= 12 and part1 <= 31:  # Could be DD/MM
                dates_to_try.append((part2, part1, 0.7))  # month, day, confidence

            for month, day, confidence in dates_to_try:
                try:
                    date = datetime(year, month, day)
                    event = TimelineEvent(
                        id=str(uuid.uuid4()),
                        document_id=document_id,
                        text=match.group(0),
                        date_start=date,
                        precision=DatePrecision.DAY,
                        confidence=confidence,
                        event_type=EventType.REFERENCE,
                        span=(match.start(), match.end()),
                        metadata={"ambiguous_format": True}
                    )
                    events.append(event)
                    break  # Only add first valid interpretation
                except ValueError:
                    continue

        return events

    def _extract_quarters(
        self,
        text: str,
        document_id: str,
        context: ExtractionContext
    ) -> list[TimelineEvent]:
        """Extract quarter references (Q3 2024)."""
        events = []

        for match in self.QUARTER_PATTERN.finditer(text):
            quarter_str = match.group(1).lower()
            year = int(match.group(2))

            quarter_num = self.quarter_map.get(quarter_str)
            if quarter_num:
                # Start of quarter
                month = (quarter_num - 1) * 3 + 1
                date_start = datetime(year, month, 1)

                # End of quarter
                end_month = quarter_num * 3
                if end_month == 12:
                    date_end = datetime(year, 12, 31)
                else:
                    date_end = datetime(year, end_month + 1, 1) - timedelta(days=1)

                event = TimelineEvent(
                    id=str(uuid.uuid4()),
                    document_id=document_id,
                    text=match.group(0),
                    date_start=date_start,
                    date_end=date_end,
                    precision=DatePrecision.QUARTER,
                    confidence=0.9,
                    event_type=EventType.PERIOD,
                    span=(match.start(), match.end()),
                )
                events.append(event)

        return events

    def _extract_seasons(
        self,
        text: str,
        document_id: str,
        context: ExtractionContext
    ) -> list[TimelineEvent]:
        """Extract season references (summer 2024)."""
        events = []

        for match in self.SEASON_PATTERN.finditer(text):
            season_str = match.group(1).lower()
            year = int(match.group(2))

            start_month = self.season_map.get(season_str)
            if start_month:
                date_start = datetime(year, start_month, 1)
                date_end = datetime(year, start_month, 1) + relativedelta(months=3) - timedelta(days=1)

                event = TimelineEvent(
                    id=str(uuid.uuid4()),
                    document_id=document_id,
                    text=match.group(0),
                    date_start=date_start,
                    date_end=date_end,
                    precision=DatePrecision.QUARTER,
                    confidence=0.75,
                    event_type=EventType.PERIOD,
                    span=(match.start(), match.end()),
                )
                events.append(event)

        return events

    def _extract_decades(
        self,
        text: str,
        document_id: str,
        context: ExtractionContext
    ) -> list[TimelineEvent]:
        """Extract decade references (the 1990s, mid-90s)."""
        events = []

        for match in self.DECADE_PATTERN.finditer(text):
            if match.group(1):  # Full decade (1990s)
                decade_start = int(match.group(1))
            else:  # Short form (mid-90s)
                qualifier = match.group(2).lower()
                short_year = int(match.group(3))
                decade_start = 1900 + short_year if short_year >= 50 else 2000 + short_year

            date_start = datetime(decade_start, 1, 1)
            date_end = datetime(decade_start + 9, 12, 31)

            # Adjust for early/mid/late qualifier
            precision = DatePrecision.DECADE
            if match.group(2):
                qualifier = match.group(2).lower()
                if qualifier == 'early':
                    date_end = datetime(decade_start + 3, 12, 31)
                    precision = DatePrecision.YEAR
                elif qualifier == 'mid':
                    date_start = datetime(decade_start + 3, 1, 1)
                    date_end = datetime(decade_start + 6, 12, 31)
                    precision = DatePrecision.YEAR
                elif qualifier == 'late':
                    date_start = datetime(decade_start + 7, 1, 1)
                    precision = DatePrecision.YEAR

            event = TimelineEvent(
                id=str(uuid.uuid4()),
                document_id=document_id,
                text=match.group(0),
                date_start=date_start,
                date_end=date_end,
                precision=precision,
                confidence=0.7,
                event_type=EventType.PERIOD,
                span=(match.start(), match.end()),
            )
            events.append(event)

        return events

    def _extract_relative_dates(
        self,
        text: str,
        document_id: str,
        context: ExtractionContext
    ) -> list[TimelineEvent]:
        """Extract relative dates (yesterday, 3 days ago, next week)."""
        events = []
        ref_date = context.reference_date or datetime.now()

        # Simple relative days
        for match in self.RELATIVE_DAY_PATTERN.finditer(text):
            day_str = match.group(1).lower()

            if day_str == 'yesterday':
                date = ref_date - timedelta(days=1)
            elif day_str == 'today':
                date = ref_date
            elif day_str == 'tomorrow':
                date = ref_date + timedelta(days=1)
            else:
                continue

            event = TimelineEvent(
                id=str(uuid.uuid4()),
                document_id=document_id,
                text=match.group(0),
                date_start=date,
                precision=DatePrecision.DAY,
                confidence=0.85,
                event_type=EventType.REFERENCE,
                span=(match.start(), match.end()),
                metadata={"relative_to": ref_date.isoformat()}
            )
            events.append(event)

        # Relative weeks (last Tuesday, next Friday)
        for match in self.RELATIVE_WEEK_PATTERN.finditer(text):
            direction = match.group(1).lower()
            weekday_str = match.group(2)

            weekday_map = {
                'monday': 0, 'tuesday': 1, 'wednesday': 2,
                'thursday': 3, 'friday': 4, 'saturday': 5, 'sunday': 6
            }
            target_weekday = weekday_map.get(weekday_str.lower())

            if target_weekday is not None:
                current_weekday = ref_date.weekday()

                if direction == 'last':
                    days_back = (current_weekday - target_weekday) % 7
                    if days_back == 0:
                        days_back = 7
                    date = ref_date - timedelta(days=days_back)
                elif direction == 'next':
                    days_forward = (target_weekday - current_weekday) % 7
                    if days_forward == 0:
                        days_forward = 7
                    date = ref_date + timedelta(days=days_forward)
                else:  # this
                    days_diff = target_weekday - current_weekday
                    date = ref_date + timedelta(days=days_diff)

                event = TimelineEvent(
                    id=str(uuid.uuid4()),
                    document_id=document_id,
                    text=match.group(0),
                    date_start=date,
                    precision=DatePrecision.DAY,
                    confidence=0.8,
                    event_type=EventType.REFERENCE,
                    span=(match.start(), match.end()),
                    metadata={"relative_to": ref_date.isoformat()}
                )
                events.append(event)

        # Numeric relative (3 days ago, 2 weeks from now)
        for match in self.RELATIVE_NUMERIC_PATTERN.finditer(text):
            amount = int(match.group(1))
            unit = match.group(2).lower().rstrip('s')  # Remove plural 's'
            direction = match.group(3).lower()

            multiplier = -1 if direction == 'ago' else 1

            if unit == 'day':
                date = ref_date + timedelta(days=amount * multiplier)
                precision = DatePrecision.DAY
            elif unit == 'week':
                date = ref_date + timedelta(weeks=amount * multiplier)
                precision = DatePrecision.WEEK
            elif unit == 'month':
                date = ref_date + relativedelta(months=amount * multiplier)
                precision = DatePrecision.MONTH
            elif unit == 'year':
                date = ref_date + relativedelta(years=amount * multiplier)
                precision = DatePrecision.YEAR
            else:
                continue

            event = TimelineEvent(
                id=str(uuid.uuid4()),
                document_id=document_id,
                text=match.group(0),
                date_start=date,
                precision=precision,
                confidence=0.75,
                event_type=EventType.REFERENCE,
                span=(match.start(), match.end()),
                metadata={"relative_to": ref_date.isoformat()}
            )
            events.append(event)

        return events

    def _extract_approximate_dates(
        self,
        text: str,
        document_id: str,
        context: ExtractionContext
    ) -> list[TimelineEvent]:
        """Extract approximate dates (around 2020, circa 1995)."""
        events = []

        for match in self.APPROXIMATE_PATTERN.finditer(text):
            year = int(match.group(2))

            # Use mid-year for approximate dates
            date = datetime(year, 6, 30)

            event = TimelineEvent(
                id=str(uuid.uuid4()),
                document_id=document_id,
                text=match.group(0),
                date_start=date,
                precision=DatePrecision.APPROXIMATE,
                confidence=0.6,
                event_type=EventType.REFERENCE,
                span=(match.start(), match.end()),
                metadata={"qualifier": match.group(1)}
            )
            events.append(event)

        return events

    def _extract_time_periods(
        self,
        text: str,
        document_id: str,
        context: ExtractionContext
    ) -> list[TimelineEvent]:
        """Extract time periods (early January, late 2024)."""
        events = []

        for match in self.TIME_PERIOD_PATTERN.finditer(text):
            qualifier = match.group(1).lower()
            month_str = match.group(2).lower()
            year = int(match.group(3)) if match.group(3) else datetime.now().year

            month = self.month_map.get(month_str)
            if month:
                # Determine date range based on qualifier
                if qualifier == 'early':
                    date_start = datetime(year, month, 1)
                    date_end = datetime(year, month, 10)
                elif qualifier == 'mid':
                    date_start = datetime(year, month, 11)
                    date_end = datetime(year, month, 20)
                else:  # late
                    date_start = datetime(year, month, 21)
                    # Last day of month
                    next_month = datetime(year, month, 1) + relativedelta(months=1)
                    date_end = next_month - timedelta(days=1)

                event = TimelineEvent(
                    id=str(uuid.uuid4()),
                    document_id=document_id,
                    text=match.group(0),
                    date_start=date_start,
                    date_end=date_end,
                    precision=DatePrecision.WEEK,
                    confidence=0.7,
                    event_type=EventType.PERIOD,
                    span=(match.start(), match.end()),
                )
                events.append(event)

        return events

    def normalize_date(
        self,
        date_str: str,
        context: Optional[ExtractionContext] = None
    ) -> Optional[NormalizedDate]:
        """
        Normalize a date string to standard format.

        Args:
            date_str: Date string to normalize
            context: Extraction context

        Returns:
            NormalizedDate object or None if parsing fails
        """
        if context is None:
            context = ExtractionContext(reference_date=datetime.now())

        # Try extracting with our patterns first
        dummy_doc_id = "temp"
        events = self.extract_events(date_str, dummy_doc_id, context)

        if events:
            event = events[0]
            return NormalizedDate(
                original=date_str,
                normalized=event.date_start,
                precision=event.precision,
                confidence=event.confidence,
                is_range=(event.date_end is not None),
                range_end=event.date_end,
            )

        # Fallback to dateutil parser
        try:
            parsed = dateutil_parser.parse(date_str, fuzzy=True, default=context.reference_date)
            return NormalizedDate(
                original=date_str,
                normalized=parsed,
                precision=DatePrecision.DAY,
                confidence=0.7,
            )
        except (ValueError, TypeError) as e:
            logger.debug(f"Failed to parse date: {date_str} - {e}")
            return None
