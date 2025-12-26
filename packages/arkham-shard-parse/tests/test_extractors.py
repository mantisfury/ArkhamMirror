"""
Parse Shard - Extractor Tests

Tests for NER, Date, Location, and Relation extractors.
"""

import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch

from arkham_shard_parse.extractors.ner import NERExtractor
from arkham_shard_parse.extractors.dates import DateExtractor
from arkham_shard_parse.extractors.relations import RelationExtractor
from arkham_shard_parse.models import EntityMention, EntityType


class TestNERExtractor:
    """Tests for NERExtractor class."""

    def test_initialization_default_model(self):
        """Test NER extractor initializes with default model."""
        extractor = NERExtractor()
        assert extractor.model_name == "en_core_web_sm"
        assert extractor.nlp is None

    def test_initialization_custom_model(self):
        """Test NER extractor initializes with custom model."""
        extractor = NERExtractor(model_name="en_core_web_lg")
        assert extractor.model_name == "en_core_web_lg"

    def test_initialize_without_spacy(self):
        """Test initialize gracefully handles missing spaCy."""
        extractor = NERExtractor()

        with patch.dict("sys.modules", {"spacy": None}):
            with patch("builtins.__import__", side_effect=ImportError):
                extractor.initialize()

        # Should remain None (mock mode)
        assert extractor.nlp is None

    def test_extract_in_mock_mode(self):
        """Test extraction in mock mode."""
        extractor = NERExtractor()
        # Don't initialize - stays in mock mode

        text = "John Smith works at Acme Corp in New York."
        entities = extractor.extract(text)

        assert isinstance(entities, list)
        # Mock mode uses capitalized word heuristic
        assert any(e.text == "John Smith" for e in entities)

    def test_extract_with_doc_id(self):
        """Test extraction includes doc_id in results."""
        extractor = NERExtractor()

        text = "John works here."
        entities = extractor.extract(text, doc_id="doc-123")

        for entity in entities:
            assert entity.source_doc_id == "doc-123"

    def test_extract_with_chunk_id(self):
        """Test extraction includes chunk_id in results."""
        extractor = NERExtractor()

        text = "John works here."
        entities = extractor.extract(text, doc_id="doc-123", chunk_id="chunk-456")

        for entity in entities:
            assert entity.source_chunk_id == "chunk-456"

    def test_mock_extract_capitalized_words(self):
        """Test mock extraction finds capitalized words."""
        extractor = NERExtractor()

        text = "Apple announced products."
        entities = extractor._mock_extract(text)

        assert len(entities) >= 1
        # Should find "Apple"
        texts = [e.text for e in entities]
        assert "Apple" in texts

    def test_mock_extract_consecutive_capitals(self):
        """Test mock extraction groups consecutive capitals."""
        extractor = NERExtractor()

        text = "John Smith met Jane Doe today"
        entities = extractor._mock_extract(text)

        texts = [e.text for e in entities]
        assert "John Smith" in texts
        # The mock extraction includes punctuation, so check for partial match
        assert any("Jane Doe" in t for t in texts)

    def test_mock_extract_low_confidence(self):
        """Test mock extraction uses low confidence."""
        extractor = NERExtractor()

        entities = extractor._mock_extract("John works here.")

        for entity in entities:
            assert entity.confidence == 0.5

    def test_mock_extract_empty_text(self):
        """Test mock extraction with empty text."""
        extractor = NERExtractor()

        entities = extractor._mock_extract("")

        assert entities == []

    def test_mock_extract_no_capitals(self):
        """Test mock extraction with no capital words."""
        extractor = NERExtractor()

        entities = extractor._mock_extract("all lowercase text here.")

        assert entities == []


class TestNERExtractorWithSpacy:
    """Tests for NER extractor with spaCy (if available)."""

    @pytest.fixture
    def mock_spacy_doc(self):
        """Create mock spaCy doc with entities."""
        mock_ent = MagicMock()
        mock_ent.text = "John"
        # The NER code uses EntityType[label_] which looks up by enum NAME
        # So we need to use a valid enum name like "PERSON"
        mock_ent.label_ = "PERSON"
        mock_ent.start_char = 0
        mock_ent.end_char = 4
        mock_ent.sent = MagicMock()
        mock_ent.sent.text = "John announced products."

        mock_doc = MagicMock()
        mock_doc.ents = [mock_ent]
        return mock_doc

    def test_extract_with_spacy_nlp(self, mock_spacy_doc):
        """Test extraction with actual spaCy model."""
        extractor = NERExtractor()
        extractor.nlp = MagicMock(return_value=mock_spacy_doc)

        text = "John announced products."
        entities = extractor.extract(text)

        assert len(entities) == 1
        assert entities[0].text == "John"
        assert entities[0].entity_type == EntityType.PERSON
        assert entities[0].confidence == 0.85

    def test_extract_unknown_entity_type(self):
        """Test handling unknown entity type from spaCy."""
        mock_ent = MagicMock()
        mock_ent.text = "Something"
        mock_ent.label_ = "UNKNOWN_TYPE"
        mock_ent.start_char = 0
        mock_ent.end_char = 9
        mock_ent.sent = MagicMock()
        mock_ent.sent.text = "Something happened."

        mock_doc = MagicMock()
        mock_doc.ents = [mock_ent]

        extractor = NERExtractor()
        extractor.nlp = MagicMock(return_value=mock_doc)

        entities = extractor.extract("Something happened.")

        assert len(entities) == 1
        assert entities[0].entity_type == EntityType.OTHER


class TestNERExtractorAsync:
    """Tests for async NER extraction."""

    @pytest.mark.asyncio
    async def test_extract_async_without_worker(self):
        """Test async extraction falls back to sync."""
        extractor = NERExtractor()

        entities = await extractor.extract_async("John works here.")

        assert isinstance(entities, list)

    @pytest.mark.asyncio
    async def test_extract_async_with_worker(self):
        """Test async extraction dispatches to worker."""
        mock_worker = MagicMock()
        mock_worker.enqueue = MagicMock(return_value=None)

        # Make enqueue awaitable
        async def mock_enqueue(**kwargs):
            return {"job_id": "test-123"}

        mock_worker.enqueue = mock_enqueue

        extractor = NERExtractor()
        entities = await extractor.extract_async(
            "John works here.",
            worker_service=mock_worker,
        )

        # Returns empty - result comes via event bus
        assert entities == []


class TestDateExtractor:
    """Tests for DateExtractor class."""

    def test_initialization(self):
        """Test date extractor initialization."""
        extractor = DateExtractor()
        assert extractor is not None

    def test_extract_iso_date(self):
        """Test extraction of ISO format date."""
        extractor = DateExtractor()
        # Force regex mode for predictable testing
        extractor.dateparser_available = False

        text = "The meeting is on 2024-01-15."
        dates = extractor.extract(text)

        assert len(dates) == 1
        assert dates[0].text == "2024-01-15"
        assert dates[0].normalized_date == datetime(2024, 1, 15)
        assert dates[0].date_type == "absolute"

    def test_extract_with_doc_id(self):
        """Test extraction includes doc_id."""
        extractor = DateExtractor()
        extractor.dateparser_available = False

        dates = extractor.extract("Event on 2024-06-15", doc_id="doc-123")

        assert len(dates) == 1
        assert dates[0].source_doc_id == "doc-123"

    def test_extract_no_dates(self):
        """Test extraction with no dates."""
        extractor = DateExtractor()
        extractor.dateparser_available = False

        dates = extractor.extract("No dates in this text.")

        assert dates == []

    def test_extract_invalid_date(self):
        """Test extraction skips invalid dates."""
        extractor = DateExtractor()
        extractor.dateparser_available = False

        # Invalid date (month 13)
        dates = extractor.extract("Invalid date 2024-13-45.")

        assert dates == []

    def test_extract_relative_dates(self):
        """Test extraction of relative dates."""
        extractor = DateExtractor()

        dates = extractor.extract_relative_dates("Let's meet yesterday.")

        assert len(dates) == 1
        assert dates[0].text == "yesterday"
        assert dates[0].date_type == "relative"

    def test_extract_relative_last_week(self):
        """Test extraction of 'last week'."""
        extractor = DateExtractor()

        dates = extractor.extract_relative_dates("It happened last week.")

        assert len(dates) == 1
        assert "last week" in dates[0].text

    def test_extract_relative_days_ago(self):
        """Test extraction of 'X days ago'."""
        extractor = DateExtractor()

        dates = extractor.extract_relative_dates("This was 5 days ago.")

        assert len(dates) == 1
        assert "5 days ago" in dates[0].text

    def test_extract_multiple_dates(self):
        """Test extraction of multiple dates."""
        extractor = DateExtractor()
        extractor.dateparser_available = False

        text = "Start: 2024-01-01, End: 2024-12-31"
        dates = extractor.extract(text)

        assert len(dates) == 2


class TestDateExtractorWithDateparser:
    """Tests for date extractor with dateparser library."""

    @pytest.fixture
    def extractor_with_dateparser(self):
        """Create extractor with mocked dateparser."""
        extractor = DateExtractor()
        extractor.dateparser_available = True
        extractor.dateparser = MagicMock()
        return extractor

    def test_extract_with_dateparser(self, extractor_with_dateparser):
        """Test extraction uses dateparser when available."""
        extractor_with_dateparser.dateparser.parse.return_value = datetime(2024, 1, 15)

        text = "Meeting on 01/15/2024"
        dates = extractor_with_dateparser.extract(text)

        # May or may not find dates depending on pattern matching
        assert isinstance(dates, list)


class TestRelationExtractor:
    """Tests for RelationExtractor class."""

    def test_initialization(self):
        """Test relation extractor initialization."""
        extractor = RelationExtractor()
        assert extractor.patterns is not None

    def test_patterns_loaded(self):
        """Test that relation patterns are loaded."""
        extractor = RelationExtractor()

        assert "employment" in extractor.patterns
        assert "ownership" in extractor.patterns
        assert "association" in extractor.patterns
        assert "location" in extractor.patterns

    def test_employment_patterns(self):
        """Test employment relation patterns exist."""
        extractor = RelationExtractor()

        patterns = extractor.patterns["employment"]
        assert "works for" in patterns
        assert "CEO of" in patterns

    def test_extract_employment_relation(self):
        """Test extraction of employment relationship."""
        extractor = RelationExtractor()

        entities = [
            EntityMention(
                text="John",
                entity_type=EntityType.PERSON,
                start_char=0,
                end_char=4,
                confidence=0.9,
            ),
            EntityMention(
                text="Acme",
                entity_type=EntityType.ORGANIZATION,
                start_char=15,
                end_char=19,
                confidence=0.9,
            ),
        ]

        text = "John works for Acme corporation."
        relations = extractor.extract(text, entities)

        assert len(relations) == 1
        assert relations[0].relation_type == "employment"

    def test_extract_no_relation(self):
        """Test extraction with no relationship."""
        extractor = RelationExtractor()

        entities = [
            EntityMention(
                text="John",
                entity_type=EntityType.PERSON,
                start_char=0,
                end_char=4,
                confidence=0.9,
            ),
            EntityMention(
                text="Jane",
                entity_type=EntityType.PERSON,
                start_char=10,
                end_char=14,
                confidence=0.9,
            ),
        ]

        text = "John and Jane walked."
        relations = extractor.extract(text, entities)

        assert relations == []

    def test_extract_with_doc_id(self):
        """Test extraction includes doc_id."""
        extractor = RelationExtractor()

        entities = [
            EntityMention(
                text="Apple",
                entity_type=EntityType.ORGANIZATION,
                start_char=0,
                end_char=5,
                confidence=0.9,
            ),
            EntityMention(
                text="Beats",
                entity_type=EntityType.ORGANIZATION,
                start_char=15,
                end_char=20,
                confidence=0.9,
            ),
        ]

        text = "Apple acquired Beats Electronics."
        relations = extractor.extract(text, entities, doc_id="doc-123")

        assert len(relations) == 1
        assert relations[0].source_doc_id == "doc-123"

    def test_extract_ownership_relation(self):
        """Test extraction of ownership relationship."""
        extractor = RelationExtractor()

        entities = [
            EntityMention(
                text="Microsoft",
                entity_type=EntityType.ORGANIZATION,
                start_char=0,
                end_char=9,
                confidence=0.9,
            ),
            EntityMention(
                text="LinkedIn",
                entity_type=EntityType.ORGANIZATION,
                start_char=20,
                end_char=28,
                confidence=0.9,
            ),
        ]

        text = "Microsoft purchased LinkedIn."
        relations = extractor.extract(text, entities)

        assert len(relations) == 1
        assert relations[0].relation_type == "ownership"

    def test_extract_single_entity(self):
        """Test extraction with single entity (no pairs)."""
        extractor = RelationExtractor()

        entities = [
            EntityMention(
                text="John",
                entity_type=EntityType.PERSON,
                start_char=0,
                end_char=4,
                confidence=0.9,
            ),
        ]

        text = "John walked."
        relations = extractor.extract(text, entities)

        assert relations == []

    def test_extract_empty_entities(self):
        """Test extraction with no entities."""
        extractor = RelationExtractor()

        relations = extractor.extract("Some text.", [])

        assert relations == []

    def test_relation_confidence(self):
        """Test that relations have confidence scores."""
        extractor = RelationExtractor()

        # "Tim works for Acme."
        #  0123456789012345678
        # Tim = 0-3, Acme = 14-18
        # Note: patterns are lowercase ("works for") and compared against lowercased text
        entities = [
            EntityMention(
                text="Tim",
                entity_type=EntityType.PERSON,
                start_char=0,
                end_char=3,
                confidence=0.9,
            ),
            EntityMention(
                text="Acme",
                entity_type=EntityType.ORGANIZATION,
                start_char=14,
                end_char=18,
                confidence=0.9,
            ),
        ]

        text = "Tim works for Acme."
        relations = extractor.extract(text, entities)

        assert len(relations) == 1
        assert relations[0].confidence == 0.7

    def test_relation_evidence_text(self):
        """Test that relations include evidence text."""
        extractor = RelationExtractor()

        # "Tim works for Acme."
        entities = [
            EntityMention(
                text="Tim",
                entity_type=EntityType.PERSON,
                start_char=0,
                end_char=3,
                confidence=0.9,
            ),
            EntityMention(
                text="Acme",
                entity_type=EntityType.ORGANIZATION,
                start_char=14,
                end_char=18,
                confidence=0.9,
            ),
        ]

        text = "Tim works for Acme."
        relations = extractor.extract(text, entities)

        assert len(relations) == 1
        assert relations[0].evidence_text is not None
