"""
Parse Shard - API Tests

Tests for all FastAPI endpoints.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI

from arkham_shard_parse.api import router, init_api
from arkham_shard_parse.models import EntityMention, EntityType, DateMention, EntityLinkingResult


@pytest.fixture
def mock_ner_extractor():
    """Create mock NER extractor."""
    mock = MagicMock()
    mock.extract.return_value = [
        EntityMention(
            text="John Smith",
            entity_type=EntityType.PERSON,
            start_char=0,
            end_char=10,
            confidence=0.9,
        ),
        EntityMention(
            text="Acme Corp",
            entity_type=EntityType.ORGANIZATION,
            start_char=20,
            end_char=29,
            confidence=0.85,
        ),
    ]
    return mock


@pytest.fixture
def mock_date_extractor():
    """Create mock date extractor."""
    mock = MagicMock()
    mock.extract.return_value = [
        DateMention(
            text="2024-01-15",
            normalized_date=None,
            date_type="absolute",
            confidence=0.9,
        ),
    ]
    return mock


@pytest.fixture
def mock_location_extractor():
    """Create mock location extractor."""
    return MagicMock()


@pytest.fixture
def mock_relation_extractor():
    """Create mock relation extractor."""
    mock = MagicMock()
    mock.extract.return_value = []
    return mock


@pytest.fixture
def mock_entity_linker():
    """Create mock entity linker."""
    mock = MagicMock()
    mock.link_mentions = AsyncMock(return_value=[])
    return mock


@pytest.fixture
def mock_coref_resolver():
    """Create mock coreference resolver."""
    return MagicMock()


@pytest.fixture
def mock_chunker():
    """Create mock text chunker."""
    mock = MagicMock()
    return mock


@pytest.fixture
def mock_worker_service():
    """Create mock worker service."""
    mock = MagicMock()
    mock.enqueue = AsyncMock(return_value={"job_id": "test-job-123"})
    return mock


@pytest.fixture
def mock_event_bus():
    """Create mock event bus."""
    mock = MagicMock()
    mock.emit = AsyncMock()
    return mock


@pytest.fixture
def client(
    mock_ner_extractor,
    mock_date_extractor,
    mock_location_extractor,
    mock_relation_extractor,
    mock_entity_linker,
    mock_coref_resolver,
    mock_chunker,
    mock_worker_service,
    mock_event_bus,
):
    """Create test client with mocked dependencies."""
    init_api(
        ner_extractor=mock_ner_extractor,
        date_extractor=mock_date_extractor,
        location_extractor=mock_location_extractor,
        relation_extractor=mock_relation_extractor,
        entity_linker=mock_entity_linker,
        coref_resolver=mock_coref_resolver,
        chunker=mock_chunker,
        worker_service=mock_worker_service,
        event_bus=mock_event_bus,
    )

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


class TestParseTextEndpoint:
    """Tests for POST /api/parse/text endpoint."""

    def test_parse_text_basic(self, client, mock_ner_extractor, mock_date_extractor):
        """Test parsing text with basic options."""
        response = client.post(
            "/api/parse/text",
            json={
                "text": "John Smith works at Acme Corp since 2024-01-15.",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "entities" in data
        assert "dates" in data
        assert "locations" in data
        assert "relationships" in data
        assert data["total_entities"] == 2
        assert data["total_dates"] == 1
        assert data["processing_time_ms"] > 0

    def test_parse_text_with_doc_id(self, client, mock_ner_extractor):
        """Test parsing text with document ID."""
        response = client.post(
            "/api/parse/text",
            json={
                "text": "Sample text",
                "doc_id": "doc-123",
            },
        )

        assert response.status_code == 200
        mock_ner_extractor.extract.assert_called_once()
        call_args = mock_ner_extractor.extract.call_args
        assert call_args[1]["doc_id"] == "doc-123"

    def test_parse_text_entities_only(self, client, mock_ner_extractor, mock_date_extractor):
        """Test parsing text with only entity extraction."""
        response = client.post(
            "/api/parse/text",
            json={
                "text": "John Smith works at Acme Corp.",
                "extract_entities": True,
                "extract_dates": False,
                "extract_locations": False,
                "extract_relationships": False,
            },
        )

        assert response.status_code == 200
        mock_ner_extractor.extract.assert_called_once()
        mock_date_extractor.extract.assert_not_called()

    def test_parse_text_dates_only(self, client, mock_ner_extractor, mock_date_extractor):
        """Test parsing text with only date extraction."""
        response = client.post(
            "/api/parse/text",
            json={
                "text": "Meeting on 2024-01-15.",
                "extract_entities": False,
                "extract_dates": True,
                "extract_locations": False,
                "extract_relationships": False,
            },
        )

        assert response.status_code == 200
        mock_ner_extractor.extract.assert_not_called()
        mock_date_extractor.extract.assert_called_once()

    def test_parse_text_all_disabled(self, client):
        """Test parsing text with all extraction disabled."""
        response = client.post(
            "/api/parse/text",
            json={
                "text": "Some text.",
                "extract_entities": False,
                "extract_dates": False,
                "extract_locations": False,
                "extract_relationships": False,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_entities"] == 0
        assert data["total_dates"] == 0

    def test_parse_text_empty_text(self, client, mock_ner_extractor):
        """Test parsing empty text."""
        mock_ner_extractor.extract.return_value = []

        response = client.post(
            "/api/parse/text",
            json={"text": ""},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_entities"] == 0


class TestParseTextNotInitialized:
    """Tests for parse text when service not initialized."""

    def test_parse_text_not_initialized(self):
        """Test parsing when NER extractor not initialized."""
        # Reset API state
        init_api(
            ner_extractor=None,
            date_extractor=None,
            location_extractor=None,
            relation_extractor=None,
            entity_linker=None,
            coref_resolver=None,
            chunker=None,
            worker_service=None,
            event_bus=None,
        )

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        response = client.post(
            "/api/parse/text",
            json={"text": "Test text"},
        )

        assert response.status_code == 503
        assert "not initialized" in response.json()["detail"]


class TestParseDocumentEndpoint:
    """Tests for POST /api/parse/document/{doc_id} endpoint."""

    def test_parse_document_dispatches_job(self, client, mock_worker_service, mock_event_bus):
        """Test that parsing a document dispatches a worker job."""
        response = client.post("/api/parse/document/doc-123")

        assert response.status_code == 200
        data = response.json()
        assert data["document_id"] == "doc-123"
        assert data["status"] == "processing"

        mock_worker_service.enqueue.assert_called_once()
        call_args = mock_worker_service.enqueue.call_args
        assert call_args[1]["pool"] == "cpu-ner"
        assert call_args[1]["payload"]["document_id"] == "doc-123"
        assert call_args[1]["payload"]["job_type"] == "parse_document"

    def test_parse_document_emits_event(self, client, mock_event_bus):
        """Test that parsing a document emits an event."""
        response = client.post("/api/parse/document/doc-456")

        assert response.status_code == 200
        mock_event_bus.emit.assert_called_once()
        call_args = mock_event_bus.emit.call_args
        assert call_args[0][0] == "parse.document.started"
        assert call_args[0][1]["document_id"] == "doc-456"


class TestParseDocumentNotInitialized:
    """Tests for parse document when service not initialized."""

    def test_parse_document_not_initialized(self):
        """Test parsing document when worker service not available."""
        init_api(
            ner_extractor=MagicMock(),
            date_extractor=MagicMock(),
            location_extractor=MagicMock(),
            relation_extractor=MagicMock(),
            entity_linker=MagicMock(),
            coref_resolver=MagicMock(),
            chunker=MagicMock(),
            worker_service=None,
            event_bus=None,
        )

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        response = client.post("/api/parse/document/doc-123")

        assert response.status_code == 503
        assert "not available" in response.json()["detail"]


class TestGetEntitiesEndpoint:
    """Tests for GET /api/parse/entities/{doc_id} endpoint."""

    def test_get_entities(self, client):
        """Test getting entities for a document."""
        response = client.get("/api/parse/entities/doc-123")

        assert response.status_code == 200
        data = response.json()
        assert data["document_id"] == "doc-123"
        assert "entities" in data
        assert "total" in data

    def test_get_entities_not_found(self, client):
        """Test getting entities for nonexistent document."""
        response = client.get("/api/parse/entities/nonexistent")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0


class TestGetChunksEndpoint:
    """Tests for GET /api/parse/chunks/{doc_id} endpoint."""

    def test_get_chunks(self, client):
        """Test getting chunks for a document."""
        response = client.get("/api/parse/chunks/doc-123")

        assert response.status_code == 200
        data = response.json()
        assert data["document_id"] == "doc-123"
        assert "chunks" in data
        assert "total" in data

    def test_get_chunks_not_found(self, client):
        """Test getting chunks for nonexistent document."""
        response = client.get("/api/parse/chunks/nonexistent")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0


class TestChunkTextEndpoint:
    """Tests for POST /api/parse/chunk endpoint."""

    def test_chunk_text_default_params(self, client):
        """Test chunking text with default parameters."""
        response = client.post(
            "/api/parse/chunk",
            json={"text": "Sample text for chunking."},
        )

        assert response.status_code == 200
        data = response.json()
        assert "chunks" in data
        assert "total_chunks" in data
        assert "total_chars" in data
        # Default params: chunk_size=500, overlap=50, method="sentence"
        assert data["total_chunks"] >= 1

    def test_chunk_text_custom_params(self, client):
        """Test chunking text with custom parameters."""
        response = client.post(
            "/api/parse/chunk",
            json={
                "text": "Sample text " * 100,  # Longer text to ensure chunking
                "chunk_size": 100,
                "overlap": 10,
                "method": "fixed",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_chunks"] >= 1


class TestChunkTextNotInitialized:
    """Tests for chunk text when service not initialized."""

    def test_chunk_text_not_initialized(self):
        """Test chunking when chunker not initialized."""
        init_api(
            ner_extractor=MagicMock(),
            date_extractor=MagicMock(),
            location_extractor=MagicMock(),
            relation_extractor=MagicMock(),
            entity_linker=MagicMock(),
            coref_resolver=MagicMock(),
            chunker=None,
            worker_service=MagicMock(),
            event_bus=MagicMock(),
        )

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        response = client.post(
            "/api/parse/chunk",
            json={"text": "Test text"},
        )

        assert response.status_code == 503
        assert "not initialized" in response.json()["detail"]


class TestLinkEntitiesEndpoint:
    """Tests for POST /api/parse/link endpoint."""

    def test_link_entities_basic(self, client, mock_entity_linker):
        """Test linking entities."""
        mock_mention = EntityMention(
            text="Apple",
            entity_type=EntityType.ORGANIZATION,
            start_char=0,
            end_char=5,
            confidence=0.9,
        )
        mock_entity_linker.link_mentions.return_value = [
            EntityLinkingResult(
                mention=mock_mention,
                canonical_entity_id="ent-apple-123",
                confidence=1.0,
                reason="exact_match",
            ),
        ]

        response = client.post(
            "/api/parse/link",
            json={
                "entities": [
                    {
                        "text": "Apple",
                        "entity_type": "ORGANIZATION",
                        "start_char": 0,
                        "end_char": 5,
                        "confidence": 0.9,
                    },
                ],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "linked_entities" in data
        assert "new_canonical_entities" in data

    def test_link_entities_with_new_entities(self, client, mock_entity_linker):
        """Test linking entities that create new canonical entities."""
        mock_mention = EntityMention(
            text="Unknown Corp",
            entity_type=EntityType.ORGANIZATION,
            start_char=0,
            end_char=12,
            confidence=0.7,
        )
        mock_entity_linker.link_mentions.return_value = [
            EntityLinkingResult(
                mention=mock_mention,
                canonical_entity_id=None,
                confidence=0.0,
                reason="no_match",
            ),
        ]

        response = client.post(
            "/api/parse/link",
            json={
                "entities": [
                    {
                        "text": "Unknown Corp",
                        "entity_type": "ORGANIZATION",
                    },
                ],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["new_canonical_entities"] == 1

    def test_link_entities_empty_list(self, client, mock_entity_linker):
        """Test linking empty entity list."""
        mock_entity_linker.link_mentions.return_value = []

        response = client.post(
            "/api/parse/link",
            json={"entities": []},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["linked_entities"] == []
        assert data["new_canonical_entities"] == 0


class TestLinkEntitiesNotInitialized:
    """Tests for link entities when service not initialized."""

    def test_link_entities_not_initialized(self):
        """Test linking when entity linker not initialized."""
        init_api(
            ner_extractor=MagicMock(),
            date_extractor=MagicMock(),
            location_extractor=MagicMock(),
            relation_extractor=MagicMock(),
            entity_linker=None,
            coref_resolver=MagicMock(),
            chunker=MagicMock(),
            worker_service=MagicMock(),
            event_bus=MagicMock(),
        )

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        response = client.post(
            "/api/parse/link",
            json={"entities": []},
        )

        assert response.status_code == 503
        assert "not initialized" in response.json()["detail"]


class TestGetStatsEndpoint:
    """Tests for GET /api/parse/stats endpoint."""

    def test_get_stats(self, client):
        """Test getting parse statistics."""
        response = client.get("/api/parse/stats")

        assert response.status_code == 200
        data = response.json()
        assert "total_entities" in data
        assert "total_chunks" in data
        assert "total_documents_parsed" in data
        assert "entity_types" in data
