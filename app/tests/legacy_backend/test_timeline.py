"""
Unit tests for Timeline Analysis functionality (v0.3).

Tests cover:
- Date extraction from text
- Event extraction with LLM
- Timeline gap analysis
- Database models
"""

import pytest
from datetime import datetime, timedelta
from app.arkham.services.timeline_service import (
    extract_date_mentions,
    determine_date_precision,
    analyze_timeline_gaps
)


class TestDateExtraction:
    """Tests for date mention extraction."""

    def test_extract_full_dates(self):
        """Test extraction of full dates in various formats."""
        text = "The meeting was held on March 15, 2023 and then on 03/20/2023."

        mentions = extract_date_mentions(text)

        assert len(mentions) >= 2
        date_texts = [m["date_text"] for m in mentions]
        assert any("March 15, 2023" in dt for dt in date_texts)
        assert any("03/20/2023" in dt for dt in date_texts)

    def test_extract_years_only(self):
        """Test extraction of year-only mentions."""
        text = "The investigation started in 2019 and continued through 2023."

        mentions = extract_date_mentions(text)

        years = [m["date_text"] for m in mentions]
        assert "2019" in years
        assert "2023" in years

    def test_extract_month_year(self):
        """Test extraction of month and year."""
        text = "Documents from January 2022 show evidence."

        mentions = extract_date_mentions(text)

        assert len(mentions) > 0
        assert any("January 2022" in m["date_text"] for m in mentions)

    def test_extract_relative_dates(self):
        """Test extraction of relative dates."""
        text = "The deal happened yesterday and will close next week."

        mentions = extract_date_mentions(text)

        relative_mentions = [m for m in mentions if m["date_type"] == "relative"]
        assert len(relative_mentions) >= 1

    def test_context_extraction(self):
        """Test that context before/after is captured."""
        text = "The critical meeting on March 15, 2023 revealed new evidence."

        mentions = extract_date_mentions(text, context_chars=20)

        march_mention = next((m for m in mentions if "March" in m["date_text"]), None)
        assert march_mention is not None
        assert len(march_mention["context_before"]) > 0
        assert len(march_mention["context_after"]) > 0

    def test_parsed_date_conversion(self):
        """Test that extracted dates are parsed to datetime objects."""
        text = "Meeting on March 15, 2023"

        mentions = extract_date_mentions(text)

        march_mention = next((m for m in mentions if "March" in m["date_text"]), None)
        assert march_mention is not None
        assert march_mention["parsed_date"] is not None
        assert isinstance(march_mention["parsed_date"], datetime)
        assert march_mention["parsed_date"].year == 2023
        assert march_mention["parsed_date"].month == 3
        assert march_mention["parsed_date"].day == 15

    def test_no_dates_in_text(self):
        """Test behavior when no dates are present."""
        text = "This text has no temporal information at all."

        mentions = extract_date_mentions(text)

        assert len(mentions) == 0


class TestDatePrecision:
    """Tests for date precision determination."""

    def test_day_precision(self):
        """Test identification of day-level precision."""
        assert determine_date_precision("March 15, 2023") == "day"
        assert determine_date_precision("03/15/2023") == "day"
        assert determine_date_precision("2023-03-15") == "day"

    def test_month_precision(self):
        """Test identification of month-level precision."""
        assert determine_date_precision("March 2023") == "month"
        assert determine_date_precision("03/2023") == "month"

    def test_year_precision(self):
        """Test identification of year-level precision."""
        assert determine_date_precision("2023") == "year"

    def test_approximate_precision(self):
        """Test identification of approximate/relative dates."""
        assert determine_date_precision("last week") == "approximate"
        assert determine_date_precision("yesterday") == "approximate"
        assert determine_date_precision("two months ago") == "approximate"


class TestTimelineGapAnalysis:
    """Tests for timeline gap detection."""

    def test_detect_significant_gap(self):
        """Test detection of gaps exceeding threshold."""
        events = [
            {
                "event_date": datetime(2023, 1, 1),
                "description": "First event"
            },
            {
                "event_date": datetime(2023, 1, 15),
                "description": "Second event"
            },
            {
                "event_date": datetime(2023, 3, 1),
                "description": "Third event after gap"
            }
        ]

        gaps = analyze_timeline_gaps(events, gap_threshold_days=30)

        assert len(gaps) == 1
        assert gaps[0]["duration_days"] > 30

    def test_no_gaps_below_threshold(self):
        """Test that small gaps are not flagged."""
        events = [
            {
                "event_date": datetime(2023, 1, 1),
                "description": "Event 1"
            },
            {
                "event_date": datetime(2023, 1, 10),
                "description": "Event 2"
            },
            {
                "event_date": datetime(2023, 1, 20),
                "description": "Event 3"
            }
        ]

        gaps = analyze_timeline_gaps(events, gap_threshold_days=30)

        assert len(gaps) == 0

    def test_multiple_gaps(self):
        """Test detection of multiple gaps."""
        events = [
            {"event_date": datetime(2023, 1, 1), "description": "E1"},
            {"event_date": datetime(2023, 3, 1), "description": "E2"},
            {"event_date": datetime(2023, 6, 1), "description": "E3"},
            {"event_date": datetime(2023, 10, 1), "description": "E4"}
        ]

        gaps = analyze_timeline_gaps(events, gap_threshold_days=30)

        assert len(gaps) >= 2

    def test_insufficient_events(self):
        """Test behavior with insufficient events for gap analysis."""
        events = [{"event_date": datetime(2023, 1, 1), "description": "Only one"}]

        gaps = analyze_timeline_gaps(events, gap_threshold_days=30)

        assert len(gaps) == 0

    def test_events_without_dates_ignored(self):
        """Test that events without dates don't break analysis."""
        events = [
            {"event_date": datetime(2023, 1, 1), "description": "E1"},
            {"event_date": None, "description": "Undated event"},
            {"event_date": datetime(2023, 3, 1), "description": "E2"}
        ]

        gaps = analyze_timeline_gaps(events, gap_threshold_days=30)

        # Should still detect the gap between E1 and E2
        assert len(gaps) > 0


class TestDatabaseModels:
    """Tests for timeline database models."""

    def test_timeline_event_creation(self):
        """Test creating TimelineEvent model instance."""
        from backend.db.models import TimelineEvent

        event = TimelineEvent(
            doc_id=1,
            chunk_id=1,
            event_date=datetime(2023, 3, 15),
            event_date_text="March 15, 2023",
            date_precision="day",
            description="Meeting with executives",
            event_type="meeting",
            confidence=0.9,
            extraction_method="llm"
        )

        assert event.doc_id == 1
        assert event.event_date.year == 2023
        assert event.confidence == 0.9
        assert event.event_type == "meeting"

    def test_date_mention_creation(self):
        """Test creating DateMention model instance."""
        from backend.db.models import DateMention

        mention = DateMention(
            chunk_id=1,
            doc_id=1,
            date_text="March 15, 2023",
            parsed_date=datetime(2023, 3, 15),
            date_type="explicit",
            context_before="The meeting on",
            context_after="was cancelled"
        )

        assert mention.date_text == "March 15, 2023"
        assert mention.parsed_date.day == 15
        assert mention.date_type == "explicit"


class TestTimelineExtraction:
    """Integration tests for complete timeline extraction."""

    def test_extract_timeline_from_chunk(self):
        """Test full pipeline of extracting timeline from text chunk."""
        from backend.timeline_service import extract_timeline_from_chunk

        chunk_text = """
        On March 15, 2023, the board held an emergency meeting to discuss
        the merger. The deal was finalized on April 1, 2023 after extensive
        negotiations. Documents from 2022 showed early planning stages.
        """

        date_mentions, timeline_events = extract_timeline_from_chunk(
            chunk_text,
            chunk_id=1,
            doc_id=1
        )

        # Should extract date mentions
        assert len(date_mentions) > 0

        # Should extract at least some mentions with valid dates
        valid_dates = [m for m in date_mentions if m["parsed_date"] is not None]
        assert len(valid_dates) > 0

        # Events are LLM-based, so we can't guarantee exact count
        # but should be present if LLM is available
        # (This test may fail if LLM service is unavailable)

    def test_empty_text_handling(self):
        """Test that empty text doesn't crash extraction."""
        from backend.timeline_service import extract_timeline_from_chunk

        date_mentions, timeline_events = extract_timeline_from_chunk(
            "",
            chunk_id=1,
            doc_id=1
        )

        assert len(date_mentions) == 0
        assert len(timeline_events) == 0


# Pytest fixtures
@pytest.fixture
def sample_timeline_events():
    """Fixture providing sample timeline events for testing."""
    return [
        {
            "event_date": datetime(2023, 1, 15),
            "description": "Initial meeting",
            "event_type": "meeting",
            "confidence": 0.9
        },
        {
            "event_date": datetime(2023, 2, 1),
            "description": "Follow-up call",
            "event_type": "communication",
            "confidence": 0.8
        },
        {
            "event_date": datetime(2023, 4, 10),
            "description": "Contract signing",
            "event_type": "transaction",
            "confidence": 0.95
        }
    ]


if __name__ == "__main__":
    # Run tests with: python -m pytest tests/test_timeline.py -v
    pytest.main([__file__, "-v"])
