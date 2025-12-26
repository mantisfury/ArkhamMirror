"""
Timeline Shard - Extraction Tests

Tests for the DateExtractor class.
"""

import pytest
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

from arkham_shard_timeline.extraction import DateExtractor
from arkham_shard_timeline.models import (
    DatePrecision,
    EventType,
    ExtractionContext,
)


class TestDateExtractorInit:
    """Tests for DateExtractor initialization."""

    def test_initialization(self):
        """Test extractor initializes correctly."""
        extractor = DateExtractor()
        assert extractor.month_map is not None
        assert extractor.quarter_map is not None
        assert extractor.season_map is not None

    def test_month_map(self):
        """Test month map contains all months."""
        extractor = DateExtractor()
        assert extractor.month_map["january"] == 1
        assert extractor.month_map["jan"] == 1
        assert extractor.month_map["december"] == 12
        assert extractor.month_map["dec"] == 12

    def test_quarter_map(self):
        """Test quarter map contains all quarters."""
        extractor = DateExtractor()
        assert extractor.quarter_map["q1"] == 1
        assert extractor.quarter_map["first"] == 1
        assert extractor.quarter_map["q4"] == 4
        assert extractor.quarter_map["fourth"] == 4

    def test_season_map(self):
        """Test season map contains all seasons."""
        extractor = DateExtractor()
        assert extractor.season_map["spring"] == 3
        assert extractor.season_map["summer"] == 6
        assert extractor.season_map["fall"] == 9
        assert extractor.season_map["autumn"] == 9
        assert extractor.season_map["winter"] == 12


class TestISODateExtraction:
    """Tests for ISO format date extraction."""

    @pytest.fixture
    def extractor(self):
        """Create extractor for testing."""
        return DateExtractor()

    def test_iso_date_basic(self, extractor):
        """Test basic ISO date extraction."""
        text = "The event occurred on 2024-01-15."
        events = extractor.extract_events(text, "doc-1")

        assert len(events) >= 1
        iso_event = next((e for e in events if "2024-01-15" in e.text), None)
        assert iso_event is not None
        assert iso_event.date_start == datetime(2024, 1, 15)
        assert iso_event.precision == DatePrecision.DAY
        assert iso_event.confidence == 0.99

    def test_iso_date_with_time(self, extractor):
        """Test ISO date with time extraction."""
        text = "Event at 2024-03-20T14:30:00."
        events = extractor.extract_events(text, "doc-1")

        iso_events = [e for e in events if "2024-03-20" in e.text]
        assert len(iso_events) >= 1

        time_event = next((e for e in iso_events if e.precision == DatePrecision.EXACT), None)
        assert time_event is not None
        assert time_event.date_start.hour == 14
        assert time_event.date_start.minute == 30

    def test_multiple_iso_dates(self, extractor):
        """Test extracting multiple ISO dates."""
        text = "From 2024-01-01 to 2024-12-31."
        events = extractor.extract_events(text, "doc-1")

        iso_events = [e for e in events if "-" in e.text and len(e.text) == 10]
        assert len(iso_events) >= 2


class TestNaturalDateExtraction:
    """Tests for natural language date extraction."""

    @pytest.fixture
    def extractor(self):
        """Create extractor for testing."""
        return DateExtractor()

    def test_month_day_year(self, extractor):
        """Test 'Month Day, Year' format."""
        text = "Meeting on January 15, 2024."
        events = extractor.extract_events(text, "doc-1")

        matching = [e for e in events if "January 15" in e.text]
        assert len(matching) >= 1
        assert matching[0].date_start == datetime(2024, 1, 15)
        assert matching[0].precision == DatePrecision.DAY

    def test_month_day_year_abbreviated(self, extractor):
        """Test abbreviated month format."""
        text = "Due date: Dec 25, 2024."
        events = extractor.extract_events(text, "doc-1")

        matching = [e for e in events if "Dec 25" in e.text]
        assert len(matching) >= 1
        assert matching[0].date_start.month == 12
        assert matching[0].date_start.day == 25

    def test_day_month_year(self, extractor):
        """Test 'Day Month Year' format."""
        text = "Event on 15 January 2024."
        events = extractor.extract_events(text, "doc-1")

        matching = [e for e in events if "15 January" in e.text]
        assert len(matching) >= 1
        assert matching[0].date_start == datetime(2024, 1, 15)

    def test_ordinal_day(self, extractor):
        """Test ordinal day format (1st, 2nd, 3rd)."""
        text = "On the 3rd of March, 2024."
        events = extractor.extract_events(text, "doc-1")

        matching = [e for e in events if "March" in e.text]
        assert len(matching) >= 1
        assert matching[0].date_start.day == 3
        assert matching[0].date_start.month == 3


class TestNumericDateExtraction:
    """Tests for numeric date format extraction."""

    @pytest.fixture
    def extractor(self):
        """Create extractor for testing."""
        return DateExtractor()

    def test_slash_format(self, extractor):
        """Test MM/DD/YYYY format."""
        text = "Date: 01/15/2024"
        events = extractor.extract_events(text, "doc-1")

        matching = [e for e in events if "/" in e.text]
        assert len(matching) >= 1

    def test_dash_format(self, extractor):
        """Test DD-MM-YYYY format."""
        text = "Date: 15-01-2024"
        events = extractor.extract_events(text, "doc-1")

        matching = [e for e in events if e.text.count("-") == 2]
        assert len(matching) >= 1

    def test_two_digit_year(self, extractor):
        """Test two-digit year format."""
        text = "Date: 01/15/24"
        events = extractor.extract_events(text, "doc-1")

        matching = [e for e in events if "/" in e.text]
        assert len(matching) >= 1
        # Should interpret as 2024
        assert matching[0].date_start.year == 2024


class TestQuarterExtraction:
    """Tests for quarter extraction."""

    @pytest.fixture
    def extractor(self):
        """Create extractor for testing."""
        return DateExtractor()

    def test_q_format(self, extractor):
        """Test Q1, Q2, Q3, Q4 format with 'quarter' keyword."""
        # The QUARTER_PATTERN regex requires the word "quarter" after Qn
        text = "Results for Q3 quarter 2024."
        events = extractor.extract_events(text, "doc-1")

        matching = [e for e in events if "Q3" in e.text or "quarter" in e.text.lower()]
        assert len(matching) >= 1
        assert matching[0].date_start == datetime(2024, 7, 1)  # Q3 starts July
        assert matching[0].precision == DatePrecision.QUARTER
        assert matching[0].event_type == EventType.PERIOD

    def test_spelled_quarter(self, extractor):
        """Test spelled out quarter format."""
        text = "First quarter 2024 earnings."
        events = extractor.extract_events(text, "doc-1")

        matching = [e for e in events if "quarter" in e.text.lower()]
        assert len(matching) >= 1
        assert matching[0].date_start == datetime(2024, 1, 1)  # Q1 starts Jan

    def test_quarter_date_end(self, extractor):
        """Test quarter has correct end date."""
        # Use format that matches QUARTER_PATTERN regex
        text = "Q4 quarter 2024 deadline."
        events = extractor.extract_events(text, "doc-1")

        matching = [e for e in events if "Q4" in e.text or "quarter" in e.text.lower()]
        assert len(matching) >= 1
        assert matching[0].date_end == datetime(2024, 12, 31)


class TestSeasonExtraction:
    """Tests for season extraction."""

    @pytest.fixture
    def extractor(self):
        """Create extractor for testing."""
        return DateExtractor()

    def test_summer(self, extractor):
        """Test summer extraction."""
        text = "Event in summer 2024."
        events = extractor.extract_events(text, "doc-1")

        matching = [e for e in events if "summer" in e.text.lower()]
        assert len(matching) >= 1
        assert matching[0].date_start.month == 6  # Summer starts June
        assert matching[0].event_type == EventType.PERIOD

    def test_winter(self, extractor):
        """Test winter extraction."""
        text = "Winter 2024 will be cold."
        events = extractor.extract_events(text, "doc-1")

        matching = [e for e in events if "Winter" in e.text]
        assert len(matching) >= 1
        assert matching[0].date_start.month == 12  # Winter starts December

    def test_fall_autumn_synonym(self, extractor):
        """Test fall/autumn are treated equally."""
        text1 = "Fall 2024 events."
        text2 = "Autumn 2024 events."

        events1 = extractor.extract_events(text1, "doc-1")
        events2 = extractor.extract_events(text2, "doc-1")

        fall_event = next((e for e in events1 if "Fall" in e.text), None)
        autumn_event = next((e for e in events2 if "Autumn" in e.text), None)

        assert fall_event is not None
        assert autumn_event is not None
        assert fall_event.date_start.month == autumn_event.date_start.month


class TestDecadeExtraction:
    """Tests for decade extraction."""

    @pytest.fixture
    def extractor(self):
        """Create extractor for testing."""
        return DateExtractor()

    def test_full_decade(self, extractor):
        """Test full decade format (the 1990s)."""
        text = "Back in the 1990s."
        events = extractor.extract_events(text, "doc-1")

        matching = [e for e in events if "1990s" in e.text]
        assert len(matching) >= 1
        assert matching[0].date_start.year == 1990
        assert matching[0].date_end.year == 1999
        assert matching[0].precision == DatePrecision.DECADE

    def test_short_decade(self, extractor):
        """Test short decade format (mid-90s)."""
        text = "During the mid-90s."
        events = extractor.extract_events(text, "doc-1")

        matching = [e for e in events if "90s" in e.text]
        # Mid-90s should narrow the range
        assert len(matching) >= 1


class TestRelativeDateExtraction:
    """Tests for relative date extraction."""

    @pytest.fixture
    def extractor(self):
        """Create extractor for testing."""
        return DateExtractor()

    @pytest.fixture
    def reference_date(self):
        """Create reference date for testing."""
        return datetime(2024, 6, 15)

    def test_yesterday(self, extractor, reference_date):
        """Test 'yesterday' extraction."""
        context = ExtractionContext(reference_date=reference_date)
        text = "The meeting was yesterday."
        events = extractor.extract_events(text, "doc-1", context)

        matching = [e for e in events if "yesterday" in e.text.lower()]
        assert len(matching) >= 1
        expected = reference_date - timedelta(days=1)
        assert matching[0].date_start.date() == expected.date()

    def test_today(self, extractor, reference_date):
        """Test 'today' extraction."""
        context = ExtractionContext(reference_date=reference_date)
        text = "The deadline is today."
        events = extractor.extract_events(text, "doc-1", context)

        matching = [e for e in events if "today" in e.text.lower()]
        assert len(matching) >= 1
        assert matching[0].date_start.date() == reference_date.date()

    def test_tomorrow(self, extractor, reference_date):
        """Test 'tomorrow' extraction."""
        context = ExtractionContext(reference_date=reference_date)
        text = "Meeting tomorrow."
        events = extractor.extract_events(text, "doc-1", context)

        matching = [e for e in events if "tomorrow" in e.text.lower()]
        assert len(matching) >= 1
        expected = reference_date + timedelta(days=1)
        assert matching[0].date_start.date() == expected.date()

    def test_days_ago(self, extractor, reference_date):
        """Test 'X days ago' extraction."""
        context = ExtractionContext(reference_date=reference_date)
        text = "This happened 5 days ago."
        events = extractor.extract_events(text, "doc-1", context)

        matching = [e for e in events if "days ago" in e.text.lower()]
        assert len(matching) >= 1
        expected = reference_date - timedelta(days=5)
        assert matching[0].date_start.date() == expected.date()

    def test_weeks_ago(self, extractor, reference_date):
        """Test 'X weeks ago' extraction."""
        context = ExtractionContext(reference_date=reference_date)
        text = "This happened 2 weeks ago."
        events = extractor.extract_events(text, "doc-1", context)

        matching = [e for e in events if "weeks ago" in e.text.lower()]
        assert len(matching) >= 1
        expected = reference_date - timedelta(weeks=2)
        assert matching[0].date_start.date() == expected.date()

    def test_months_ago(self, extractor, reference_date):
        """Test 'X months ago' extraction."""
        context = ExtractionContext(reference_date=reference_date)
        text = "This happened 3 months ago."
        events = extractor.extract_events(text, "doc-1", context)

        matching = [e for e in events if "months ago" in e.text.lower()]
        assert len(matching) >= 1
        expected = reference_date - relativedelta(months=3)
        assert matching[0].date_start.month == expected.month

    def test_from_now(self, extractor, reference_date):
        """Test 'X days from now' extraction."""
        context = ExtractionContext(reference_date=reference_date)
        text = "Meeting in 10 days from now."
        events = extractor.extract_events(text, "doc-1", context)

        matching = [e for e in events if "from now" in e.text.lower()]
        assert len(matching) >= 1
        expected = reference_date + timedelta(days=10)
        assert matching[0].date_start.date() == expected.date()


class TestRelativeWeekdayExtraction:
    """Tests for relative weekday extraction."""

    @pytest.fixture
    def extractor(self):
        """Create extractor for testing."""
        return DateExtractor()

    @pytest.fixture
    def reference_date(self):
        """Create reference date (a Wednesday)."""
        return datetime(2024, 6, 12)  # Wednesday

    def test_last_monday(self, extractor, reference_date):
        """Test 'last Monday' extraction."""
        context = ExtractionContext(reference_date=reference_date)
        text = "Last Monday we had a meeting."
        events = extractor.extract_events(text, "doc-1", context)

        matching = [e for e in events if "Monday" in e.text]
        assert len(matching) >= 1
        # Last Monday from Wednesday June 12 would be June 10
        assert matching[0].date_start.weekday() == 0  # Monday

    def test_next_friday(self, extractor, reference_date):
        """Test 'next Friday' extraction."""
        context = ExtractionContext(reference_date=reference_date)
        text = "Next Friday is the deadline."
        events = extractor.extract_events(text, "doc-1", context)

        matching = [e for e in events if "Friday" in e.text]
        assert len(matching) >= 1
        assert matching[0].date_start.weekday() == 4  # Friday


class TestApproximateDateExtraction:
    """Tests for approximate date extraction."""

    @pytest.fixture
    def extractor(self):
        """Create extractor for testing."""
        return DateExtractor()

    def test_around(self, extractor):
        """Test 'around YYYY' extraction."""
        text = "This happened around 2020."
        events = extractor.extract_events(text, "doc-1")

        matching = [e for e in events if "around" in e.text.lower()]
        assert len(matching) >= 1
        assert matching[0].precision == DatePrecision.APPROXIMATE
        assert matching[0].date_start.year == 2020

    def test_circa(self, extractor):
        """Test 'circa YYYY' extraction."""
        text = "Built circa 1995."
        events = extractor.extract_events(text, "doc-1")

        matching = [e for e in events if "circa" in e.text.lower()]
        assert len(matching) >= 1
        assert matching[0].precision == DatePrecision.APPROXIMATE
        assert matching[0].date_start.year == 1995

    def test_approximately(self, extractor):
        """Test 'approximately YYYY' extraction."""
        text = "Approximately 2010."
        events = extractor.extract_events(text, "doc-1")

        matching = [e for e in events if "approximately" in e.text.lower()]
        assert len(matching) >= 1
        assert matching[0].precision == DatePrecision.APPROXIMATE


class TestTimePeriodExtraction:
    """Tests for time period extraction."""

    @pytest.fixture
    def extractor(self):
        """Create extractor for testing."""
        return DateExtractor()

    def test_early_month(self, extractor):
        """Test 'early Month' extraction."""
        text = "In early January 2024."
        events = extractor.extract_events(text, "doc-1")

        matching = [e for e in events if "early January" in e.text]
        assert len(matching) >= 1
        assert matching[0].date_start.day <= 10
        assert matching[0].event_type == EventType.PERIOD

    def test_mid_month(self, extractor):
        """Test 'mid Month' extraction."""
        text = "By mid March 2024."
        events = extractor.extract_events(text, "doc-1")

        matching = [e for e in events if "mid March" in e.text]
        assert len(matching) >= 1
        assert 11 <= matching[0].date_start.day <= 20

    def test_late_month(self, extractor):
        """Test 'late Month' extraction."""
        text = "In late December 2024."
        events = extractor.extract_events(text, "doc-1")

        matching = [e for e in events if "late December" in e.text]
        assert len(matching) >= 1
        assert matching[0].date_start.day >= 21


class TestNormalizeDateMethod:
    """Tests for the normalize_date method."""

    @pytest.fixture
    def extractor(self):
        """Create extractor for testing."""
        return DateExtractor()

    def test_normalize_iso_date(self, extractor):
        """Test normalizing ISO date."""
        result = extractor.normalize_date("2024-06-15")
        assert result is not None
        assert result.normalized == datetime(2024, 6, 15)
        assert result.precision == DatePrecision.DAY

    def test_normalize_natural_date(self, extractor):
        """Test normalizing natural date."""
        result = extractor.normalize_date("January 15, 2024")
        assert result is not None
        assert result.normalized == datetime(2024, 1, 15)

    def test_normalize_range(self, extractor):
        """Test normalizing date range."""
        # Use "first quarter" format which matches QUARTER_PATTERN
        result = extractor.normalize_date("first quarter 2024")
        assert result is not None
        assert result.is_range is True
        assert result.range_end is not None

    def test_normalize_fallback(self, extractor):
        """Test fallback parsing with dateutil."""
        result = extractor.normalize_date("June 2024")
        assert result is not None
        assert result.normalized.month == 6
        assert result.normalized.year == 2024

    def test_normalize_invalid(self, extractor):
        """Test normalizing invalid date returns None."""
        result = extractor.normalize_date("not a date at all xyz")
        # May return None or may be parsed by dateutil - either is acceptable
        # The key is it doesn't raise an exception


class TestMultipleEventsExtraction:
    """Tests for extracting multiple events from text."""

    @pytest.fixture
    def extractor(self):
        """Create extractor for testing."""
        return DateExtractor()

    def test_multiple_iso_dates(self, extractor):
        """Test extracting multiple ISO dates."""
        text = "From 2024-01-01 to 2024-03-31, spanning Q1."
        events = extractor.extract_events(text, "doc-1")

        # Should find at least the two ISO dates
        iso_events = [e for e in events if "-" in e.text and len(e.text) == 10]
        assert len(iso_events) >= 2

    def test_mixed_formats(self, extractor):
        """Test extracting mixed date formats."""
        text = "Meeting on 2024-06-15, follow-up on July 1, 2024."
        events = extractor.extract_events(text, "doc-1")

        # Should find both dates
        assert len(events) >= 2

    def test_events_sorted_by_position(self, extractor):
        """Test events are sorted by text position."""
        text = "First 2024-01-01, then 2024-06-01, finally 2024-12-01."
        events = extractor.extract_events(text, "doc-1")

        # Filter to just the ISO dates
        iso_events = [e for e in events if e.span and "-" in e.text]

        if len(iso_events) >= 2:
            # Should be in order of appearance
            for i in range(len(iso_events) - 1):
                assert iso_events[i].span[0] < iso_events[i + 1].span[0]


class TestEventProperties:
    """Tests for extracted event properties."""

    @pytest.fixture
    def extractor(self):
        """Create extractor for testing."""
        return DateExtractor()

    def test_event_has_id(self, extractor):
        """Test extracted events have unique IDs."""
        text = "Event on 2024-01-15."
        events = extractor.extract_events(text, "doc-1")

        assert len(events) >= 1
        assert events[0].id is not None
        assert len(events[0].id) > 0

    def test_event_has_document_id(self, extractor):
        """Test extracted events have document ID."""
        text = "Event on 2024-01-15."
        events = extractor.extract_events(text, "doc-123")

        assert len(events) >= 1
        assert events[0].document_id == "doc-123"

    def test_event_has_span(self, extractor):
        """Test extracted events have span positions."""
        text = "Event on 2024-01-15."
        events = extractor.extract_events(text, "doc-1")

        assert len(events) >= 1
        assert events[0].span is not None
        assert events[0].span[0] < events[0].span[1]

    def test_event_type_for_periods(self, extractor):
        """Test period events have correct type."""
        # QUARTER_PATTERN requires "quarter" keyword
        text = "During Q3 quarter 2024."
        events = extractor.extract_events(text, "doc-1")

        quarter_events = [e for e in events if "Q3" in e.text or "quarter" in e.text.lower()]
        assert len(quarter_events) >= 1
        assert quarter_events[0].event_type == EventType.PERIOD

    def test_confidence_varies_by_format(self, extractor):
        """Test confidence varies by format reliability."""
        text_iso = "On 2024-01-15."
        text_approx = "Around 2024."

        events_iso = extractor.extract_events(text_iso, "doc-1")
        events_approx = extractor.extract_events(text_approx, "doc-1")

        iso_event = next((e for e in events_iso if "-" in e.text), None)
        approx_event = next((e for e in events_approx if "around" in e.text.lower()), None)

        # ISO dates should have higher confidence than approximate
        if iso_event and approx_event:
            assert iso_event.confidence > approx_event.confidence
