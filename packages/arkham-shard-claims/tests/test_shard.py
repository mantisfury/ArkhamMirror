"""
Claims Shard - Shard Class Tests

Tests for ClaimsShard with mocked Frame services.
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
import json

from arkham_shard_claims.shard import ClaimsShard
from arkham_shard_claims.models import (
    ClaimStatus,
    ClaimType,
    EvidenceType,
    EvidenceRelationship,
    EvidenceStrength,
    ExtractionMethod,
    ClaimFilter,
)


# === Fixtures ===


@pytest.fixture
def mock_db():
    """Create a mock database service."""
    db = AsyncMock()
    db.execute = AsyncMock()
    db.fetch_one = AsyncMock(return_value=None)
    db.fetch_all = AsyncMock(return_value=[])
    return db


@pytest.fixture
def mock_events():
    """Create a mock events service."""
    events = AsyncMock()
    events.emit = AsyncMock()
    events.subscribe = AsyncMock()
    events.unsubscribe = AsyncMock()
    return events


@pytest.fixture
def mock_llm():
    """Create a mock LLM service."""
    llm = MagicMock()
    llm.is_available = MagicMock(return_value=True)
    llm.complete = AsyncMock(return_value='[{"text": "Test claim", "type": "factual", "confidence": 0.9}]')
    return llm


@pytest.fixture
def mock_vectors():
    """Create a mock vectors service."""
    vectors = MagicMock()
    vectors.is_available = MagicMock(return_value=True)
    vectors.search = AsyncMock(return_value=[])
    return vectors


@pytest.fixture
def mock_workers():
    """Create a mock workers service."""
    workers = AsyncMock()
    workers.enqueue = AsyncMock()
    return workers


@pytest.fixture
def mock_frame(mock_db, mock_events, mock_llm, mock_vectors, mock_workers):
    """Create a mock Frame with all services."""
    frame = MagicMock()
    frame.database = mock_db
    frame.db = mock_db
    frame.events = mock_events
    frame.llm = mock_llm
    frame.vectors = mock_vectors
    frame.workers = mock_workers
    return frame


@pytest.fixture
async def initialized_shard(mock_frame):
    """Create an initialized ClaimsShard."""
    shard = ClaimsShard()
    await shard.initialize(mock_frame)
    return shard


# === Shard Metadata Tests ===


class TestShardMetadata:
    """Tests for shard metadata and properties."""

    def test_shard_name(self):
        """Verify shard name is correct."""
        shard = ClaimsShard()
        assert shard.name == "claims"

    def test_shard_version(self):
        """Verify shard version is correct."""
        shard = ClaimsShard()
        assert shard.version == "0.1.0"

    def test_shard_description(self):
        """Verify shard description exists."""
        shard = ClaimsShard()
        assert "claim" in shard.description.lower()


# === Initialization Tests ===


class TestInitialization:
    """Tests for shard initialization and shutdown."""

    @pytest.mark.asyncio
    async def test_initialize_with_frame(self, mock_frame):
        """Test shard initializes correctly with frame."""
        shard = ClaimsShard()
        await shard.initialize(mock_frame)

        assert shard.frame == mock_frame
        assert shard._db == mock_frame.database
        assert shard._events == mock_frame.events
        assert shard._initialized is True

    @pytest.mark.asyncio
    async def test_schema_creation(self, mock_frame):
        """Test database schema is created on initialization."""
        shard = ClaimsShard()
        await shard.initialize(mock_frame)

        # Verify execute was called for table creation
        assert mock_frame.database.execute.called
        calls = [str(call) for call in mock_frame.database.execute.call_args_list]
        # Check for table creation calls
        assert any("arkham_claims" in str(call) for call in calls)
        assert any("arkham_claim_evidence" in str(call) for call in calls)

    @pytest.mark.asyncio
    async def test_event_subscriptions(self, mock_frame):
        """Test event subscriptions are set up."""
        shard = ClaimsShard()
        await shard.initialize(mock_frame)

        # Verify subscribe was called
        assert mock_frame.events.subscribe.called
        subscribed_events = [
            call[0][0] for call in mock_frame.events.subscribe.call_args_list
        ]
        assert "document.processed" in subscribed_events
        assert "entity.created" in subscribed_events

    @pytest.mark.asyncio
    async def test_shutdown(self, initialized_shard, mock_frame):
        """Test shard shuts down correctly."""
        await initialized_shard.shutdown()

        # Verify unsubscribe was called
        assert mock_frame.events.unsubscribe.called
        assert initialized_shard._initialized is False

    @pytest.mark.asyncio
    async def test_get_routes(self, initialized_shard):
        """Test get_routes returns a router."""
        router = initialized_shard.get_routes()
        assert router is not None
        assert hasattr(router, "routes")


# === Claim CRUD Tests ===


class TestClaimCRUD:
    """Tests for claim create, read, update, delete operations."""

    @pytest.mark.asyncio
    async def test_create_claim_minimal(self, initialized_shard, mock_frame):
        """Test creating a claim with minimal fields."""
        claim = await initialized_shard.create_claim(
            text="The sky is blue.",
        )

        assert claim is not None
        assert claim.text == "The sky is blue."
        assert claim.status == ClaimStatus.UNVERIFIED
        assert claim.claim_type == ClaimType.FACTUAL

        # Verify event was emitted
        mock_frame.events.emit.assert_called()

    @pytest.mark.asyncio
    async def test_create_claim_full(self, initialized_shard, mock_frame):
        """Test creating a claim with all fields."""
        claim = await initialized_shard.create_claim(
            text="The meeting was at 3pm.",
            claim_type=ClaimType.QUANTITATIVE,
            source_document_id="doc-123",
            source_start_char=100,
            source_end_char=130,
            source_context="Records show the meeting was at 3pm.",
            extracted_by=ExtractionMethod.LLM,
            extraction_model="gpt-4",
            confidence=0.95,
            entity_ids=["entity-1"],
            metadata={"verified": False},
        )

        assert claim.text == "The meeting was at 3pm."
        assert claim.claim_type == ClaimType.QUANTITATIVE
        assert claim.source_document_id == "doc-123"
        assert claim.confidence == 0.95
        assert "entity-1" in claim.entity_ids

    @pytest.mark.asyncio
    async def test_get_claim_found(self, initialized_shard, mock_frame):
        """Test getting an existing claim."""
        mock_frame.database.fetch_one.return_value = {
            "id": "claim-1",
            "text": "Test claim",
            "claim_type": "factual",
            "status": "unverified",
            "confidence": 1.0,
            "source_document_id": None,
            "source_start_char": None,
            "source_end_char": None,
            "source_context": None,
            "extracted_by": "manual",
            "extraction_model": None,
            "entity_ids": "[]",
            "evidence_count": 0,
            "supporting_count": 0,
            "refuting_count": 0,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "verified_at": None,
            "metadata": "{}",
        }

        claim = await initialized_shard.get_claim("claim-1")
        assert claim is not None
        assert claim.id == "claim-1"
        assert claim.text == "Test claim"

    @pytest.mark.asyncio
    async def test_get_claim_not_found(self, initialized_shard, mock_frame):
        """Test getting a non-existent claim."""
        mock_frame.database.fetch_one.return_value = None

        claim = await initialized_shard.get_claim("nonexistent")
        assert claim is None

    @pytest.mark.asyncio
    async def test_list_claims_empty(self, initialized_shard, mock_frame):
        """Test listing claims when none exist."""
        mock_frame.database.fetch_all.return_value = []

        claims = await initialized_shard.list_claims()
        assert claims == []

    @pytest.mark.asyncio
    async def test_list_claims_with_filter(self, initialized_shard, mock_frame):
        """Test listing claims with filter."""
        filter = ClaimFilter(
            status=ClaimStatus.VERIFIED,
            min_confidence=0.8,
        )

        await initialized_shard.list_claims(filter=filter, limit=10, offset=0)

        # Verify query includes filter conditions
        mock_frame.database.fetch_all.assert_called()

    @pytest.mark.asyncio
    async def test_update_claim_status(self, initialized_shard, mock_frame):
        """Test updating claim status."""
        mock_frame.database.fetch_one.return_value = {
            "id": "claim-1",
            "text": "Test claim",
            "claim_type": "factual",
            "status": "unverified",
            "confidence": 1.0,
            "source_document_id": None,
            "source_start_char": None,
            "source_end_char": None,
            "source_context": None,
            "extracted_by": "manual",
            "extraction_model": None,
            "entity_ids": "[]",
            "evidence_count": 0,
            "supporting_count": 0,
            "refuting_count": 0,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "verified_at": None,
            "metadata": "{}",
        }

        claim = await initialized_shard.update_claim_status(
            "claim-1",
            ClaimStatus.VERIFIED,
            notes="Confirmed by analyst",
        )

        assert claim is not None
        assert claim.status == ClaimStatus.VERIFIED
        assert claim.verified_at is not None

        # Verify status change event was emitted
        mock_frame.events.emit.assert_called()

    @pytest.mark.asyncio
    async def test_update_status_not_found(self, initialized_shard, mock_frame):
        """Test updating status for non-existent claim."""
        mock_frame.database.fetch_one.return_value = None

        claim = await initialized_shard.update_claim_status(
            "nonexistent",
            ClaimStatus.VERIFIED,
        )
        assert claim is None


# === Evidence Tests ===


class TestEvidence:
    """Tests for evidence management."""

    @pytest.mark.asyncio
    async def test_add_evidence(self, initialized_shard, mock_frame):
        """Test adding evidence to a claim."""
        evidence = await initialized_shard.add_evidence(
            claim_id="claim-1",
            evidence_type=EvidenceType.DOCUMENT,
            reference_id="doc-123",
            relationship=EvidenceRelationship.SUPPORTS,
            strength=EvidenceStrength.STRONG,
            reference_title="Supporting Document",
            excerpt="This confirms the claim...",
            notes="Primary source",
        )

        assert evidence is not None
        assert evidence.claim_id == "claim-1"
        assert evidence.evidence_type == EvidenceType.DOCUMENT
        assert evidence.relationship == EvidenceRelationship.SUPPORTS
        assert evidence.strength == EvidenceStrength.STRONG

        # Verify event was emitted
        mock_frame.events.emit.assert_called()

    @pytest.mark.asyncio
    async def test_get_claim_evidence(self, initialized_shard, mock_frame):
        """Test getting evidence for a claim."""
        mock_frame.database.fetch_all.return_value = [
            {
                "id": "ev-1",
                "claim_id": "claim-1",
                "evidence_type": "document",
                "reference_id": "doc-1",
                "reference_title": "Doc 1",
                "relationship": "supports",
                "strength": "moderate",
                "excerpt": "...",
                "notes": None,
                "added_by": "system",
                "added_at": datetime.utcnow().isoformat(),
                "metadata": "{}",
            }
        ]

        evidence_list = await initialized_shard.get_claim_evidence("claim-1")
        assert len(evidence_list) == 1
        assert evidence_list[0].id == "ev-1"


# === Extraction Tests ===


class TestExtraction:
    """Tests for claim extraction."""

    @pytest.mark.asyncio
    async def test_extract_claims_from_text(self, initialized_shard, mock_frame):
        """Test extracting claims from text with LLM."""
        mock_frame.llm.complete.return_value = json.dumps([
            {"text": "Claim one", "type": "factual", "confidence": 0.9},
            {"text": "Claim two", "type": "opinion", "confidence": 0.7},
        ])

        result = await initialized_shard.extract_claims_from_text(
            text="Some text with claims.",
            document_id="doc-1",
        )

        assert result.total_extracted == 2
        assert len(result.claims) == 2
        assert result.errors == []
        assert result.processing_time_ms > 0

    @pytest.mark.asyncio
    async def test_extract_claims_llm_unavailable(self, initialized_shard, mock_frame):
        """Test extraction when LLM is unavailable."""
        mock_frame.llm.is_available.return_value = False

        result = await initialized_shard.extract_claims_from_text(
            text="Some text",
        )

        assert result.total_extracted == 0
        assert len(result.errors) > 0
        assert "LLM" in result.errors[0]


# === Similarity Tests ===


class TestSimilarity:
    """Tests for claim similarity detection."""

    @pytest.mark.asyncio
    async def test_find_similar_claims_with_vectors(self, initialized_shard, mock_frame):
        """Test finding similar claims using vector search."""
        # Setup mock claim
        mock_frame.database.fetch_one.return_value = {
            "id": "claim-1",
            "text": "The sky is blue",
            "claim_type": "factual",
            "status": "unverified",
            "confidence": 1.0,
            "source_document_id": None,
            "source_start_char": None,
            "source_end_char": None,
            "source_context": None,
            "extracted_by": "manual",
            "extraction_model": None,
            "entity_ids": "[]",
            "evidence_count": 0,
            "supporting_count": 0,
            "refuting_count": 0,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "verified_at": None,
            "metadata": "{}",
        }

        mock_frame.vectors.search.return_value = [
            {"id": "claim-2", "score": 0.95},
            {"id": "claim-3", "score": 0.85},
        ]

        matches = await initialized_shard.find_similar_claims(
            claim_id="claim-1",
            threshold=0.8,
            limit=10,
        )

        assert len(matches) == 2
        assert matches[0].matched_claim_id == "claim-2"
        assert matches[0].similarity_score == 0.95

    @pytest.mark.asyncio
    async def test_find_similar_claims_not_found(self, initialized_shard, mock_frame):
        """Test finding similar claims when source claim doesn't exist."""
        mock_frame.database.fetch_one.return_value = None

        matches = await initialized_shard.find_similar_claims("nonexistent")
        assert matches == []


# === Merge Tests ===


class TestMerge:
    """Tests for claim merging."""

    @pytest.mark.asyncio
    async def test_merge_claims(self, initialized_shard, mock_frame):
        """Test merging duplicate claims."""
        # Mock primary claim
        mock_frame.database.fetch_one.return_value = {
            "id": "primary",
            "text": "Primary claim",
            "claim_type": "factual",
            "status": "verified",
            "confidence": 1.0,
            "source_document_id": None,
            "source_start_char": None,
            "source_end_char": None,
            "source_context": None,
            "extracted_by": "manual",
            "extraction_model": None,
            "entity_ids": '["e1"]',
            "evidence_count": 1,
            "supporting_count": 1,
            "refuting_count": 0,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "verified_at": None,
            "metadata": "{}",
        }

        # Mock evidence for merged claims
        mock_frame.database.fetch_all.return_value = [
            {
                "id": "ev-1",
                "claim_id": "dup-1",
                "evidence_type": "document",
                "reference_id": "doc-1",
                "reference_title": "Doc",
                "relationship": "supports",
                "strength": "moderate",
                "excerpt": None,
                "notes": None,
                "added_by": "system",
                "added_at": datetime.utcnow().isoformat(),
                "metadata": "{}",
            }
        ]

        result = await initialized_shard.merge_claims(
            primary_claim_id="primary",
            claim_ids_to_merge=["dup-1", "dup-2"],
        )

        assert result.primary_claim_id == "primary"
        assert "dup-1" in result.merged_claim_ids
        assert "dup-2" in result.merged_claim_ids

        # Verify merge event was emitted
        mock_frame.events.emit.assert_called()


# === Statistics Tests ===


class TestStatistics:
    """Tests for statistics retrieval."""

    @pytest.mark.asyncio
    async def test_get_statistics(self, initialized_shard, mock_frame):
        """Test getting claim statistics."""
        # Mock various stat queries
        mock_frame.database.fetch_one.side_effect = [
            {"count": 100},  # total
            {"count": 75},   # evidence total
            {"count": 60},   # supporting
            {"count": 15},   # refuting
            {"count": 80},   # with evidence
            {"avg": 0.87},   # avg confidence
            {"avg": 2.5},    # avg evidence
        ]
        mock_frame.database.fetch_all.side_effect = [
            [{"status": "verified", "count": 50}, {"status": "unverified", "count": 50}],
            [{"claim_type": "factual", "count": 80}],
            [{"extracted_by": "llm", "count": 70}],
        ]

        stats = await initialized_shard.get_statistics()

        assert stats.total_claims == 100

    @pytest.mark.asyncio
    async def test_get_count(self, initialized_shard, mock_frame):
        """Test getting claim count."""
        mock_frame.database.fetch_one.return_value = {"count": 42}

        count = await initialized_shard.get_count()
        assert count == 42

    @pytest.mark.asyncio
    async def test_get_count_by_status(self, initialized_shard, mock_frame):
        """Test getting claim count filtered by status."""
        mock_frame.database.fetch_one.return_value = {"count": 25}

        count = await initialized_shard.get_count(status="verified")
        assert count == 25


# === Helper Method Tests ===


class TestHelperMethods:
    """Tests for private helper methods."""

    def test_simple_similarity(self):
        """Test simple text similarity calculation."""
        shard = ClaimsShard()

        # Identical texts
        score = shard._simple_similarity(
            "the sky is blue",
            "the sky is blue",
        )
        assert score == 1.0

        # Similar texts
        score = shard._simple_similarity(
            "the sky is blue",
            "the sky is very blue",
        )
        assert 0.5 < score < 1.0

        # Different texts
        score = shard._simple_similarity(
            "the sky is blue",
            "apples and oranges",
        )
        assert score < 0.5

        # Empty text
        score = shard._simple_similarity("", "something")
        assert score == 0.0

    def test_parse_extraction_response_valid(self):
        """Test parsing valid LLM extraction response."""
        shard = ClaimsShard()

        response = '[{"text": "Claim 1", "type": "factual"}]'
        result = shard._parse_extraction_response(response)

        assert len(result) == 1
        assert result[0]["text"] == "Claim 1"

    def test_parse_extraction_response_with_prefix(self):
        """Test parsing LLM response with text prefix."""
        shard = ClaimsShard()

        response = 'Here are the claims: [{"text": "Claim 1"}]'
        result = shard._parse_extraction_response(response)

        assert len(result) == 1

    def test_parse_extraction_response_invalid(self):
        """Test parsing invalid LLM response."""
        shard = ClaimsShard()

        response = "This is not JSON"
        result = shard._parse_extraction_response(response)

        assert result == []


# === Event Handler Tests ===


class TestEventHandlers:
    """Tests for event handlers."""

    @pytest.mark.asyncio
    async def test_on_document_processed(self, initialized_shard, mock_frame):
        """Test handling document.processed event."""
        event = {
            "payload": {
                "document_id": "doc-123",
            }
        }

        await initialized_shard._on_document_processed(event)

        # Should enqueue extraction job
        mock_frame.workers.enqueue.assert_called()

    @pytest.mark.asyncio
    async def test_on_entity_created(self, initialized_shard, mock_frame):
        """Test handling entity.created event."""
        mock_frame.database.fetch_all.return_value = []

        event = {
            "payload": {
                "entity_id": "entity-1",
                "name": "John Doe",
            }
        }

        await initialized_shard._on_entity_created(event)

        # Should search for claims mentioning entity
        mock_frame.database.fetch_all.assert_called()
