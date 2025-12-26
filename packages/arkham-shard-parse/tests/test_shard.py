"""
Parse Shard - Shard Tests

Tests for the ParseShard class including initialization,
lifecycle, and public API.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime

from arkham_shard_parse.shard import ParseShard
from arkham_shard_parse.models import EntityMention, EntityType


class TestShardMetadata:
    """Tests for shard metadata and manifest."""

    def test_shard_name(self):
        """Test shard name."""
        shard = ParseShard()
        assert shard.name == "parse"

    def test_shard_version(self):
        """Test shard version."""
        shard = ParseShard()
        assert shard.version == "0.1.0"

    def test_shard_description(self):
        """Test shard description."""
        shard = ParseShard()
        assert "Entity extraction" in shard.description
        assert "NER" in shard.description


class TestShardInitialization:
    """Tests for shard initialization."""

    @pytest.fixture
    def mock_frame(self):
        """Create mock Frame."""
        frame = MagicMock()
        frame.config = MagicMock()
        frame.config.get = MagicMock(side_effect=lambda key, default=None: default)
        frame.get_service = MagicMock()
        return frame

    @pytest.fixture
    def mock_db_service(self):
        """Create mock database service."""
        return MagicMock()

    @pytest.fixture
    def mock_worker_service(self):
        """Create mock worker service."""
        mock = MagicMock()
        mock.register_worker = MagicMock()
        return mock

    @pytest.fixture
    def mock_event_bus(self):
        """Create mock event bus."""
        mock = MagicMock()
        mock.subscribe = MagicMock()
        mock.unsubscribe = MagicMock()
        return mock

    @pytest.mark.asyncio
    async def test_initialize_creates_extractors(self, mock_frame, mock_db_service, mock_worker_service, mock_event_bus):
        """Test that initialization creates all extractors."""
        mock_frame.get_service.side_effect = lambda name: {
            "database": mock_db_service,
            "workers": mock_worker_service,
            "events": mock_event_bus,
        }.get(name)

        shard = ParseShard()

        with patch.object(shard, "_frame", None):
            await shard.initialize(mock_frame)

        assert shard.ner_extractor is not None
        assert shard.date_extractor is not None
        assert shard.location_extractor is not None
        assert shard.relation_extractor is not None
        assert shard.entity_linker is not None
        assert shard.coref_resolver is not None
        assert shard.chunker is not None

    @pytest.mark.asyncio
    async def test_initialize_uses_config(self, mock_frame, mock_db_service, mock_worker_service, mock_event_bus):
        """Test that initialization uses config values."""
        mock_frame.config.get.side_effect = lambda key, default=None: {
            "parse.spacy_model": "en_core_web_lg",
            "parse.chunk_size": 1000,
            "parse.chunk_overlap": 100,
            "parse.chunk_method": "fixed",
        }.get(key, default)
        mock_frame.get_service.side_effect = lambda name: {
            "database": mock_db_service,
            "workers": mock_worker_service,
            "events": mock_event_bus,
        }.get(name)

        shard = ParseShard()
        await shard.initialize(mock_frame)

        assert shard.ner_extractor.model_name == "en_core_web_lg"
        assert shard.chunker.chunk_size == 1000
        assert shard.chunker.overlap == 100
        assert shard.chunker.method == "fixed"

    @pytest.mark.asyncio
    async def test_initialize_registers_workers(self, mock_frame, mock_db_service, mock_worker_service, mock_event_bus):
        """Test that initialization registers workers."""
        mock_frame.get_service.side_effect = lambda name: {
            "database": mock_db_service,
            "workers": mock_worker_service,
            "events": mock_event_bus,
        }.get(name)

        shard = ParseShard()
        await shard.initialize(mock_frame)

        mock_worker_service.register_worker.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_subscribes_to_events(self, mock_frame, mock_db_service, mock_worker_service, mock_event_bus):
        """Test that initialization subscribes to events."""
        mock_frame.get_service.side_effect = lambda name: {
            "database": mock_db_service,
            "workers": mock_worker_service,
            "events": mock_event_bus,
        }.get(name)

        shard = ParseShard()
        await shard.initialize(mock_frame)

        assert mock_event_bus.subscribe.call_count == 2
        event_names = [call[0][0] for call in mock_event_bus.subscribe.call_args_list]
        assert "ingest.job.completed" in event_names
        assert "worker.job.completed" in event_names

    @pytest.mark.asyncio
    async def test_initialize_without_services(self, mock_frame):
        """Test initialization when services are unavailable."""
        mock_frame.get_service.return_value = None

        shard = ParseShard()
        await shard.initialize(mock_frame)

        # Should complete without errors
        assert shard.ner_extractor is not None


class TestShardShutdown:
    """Tests for shard shutdown."""

    @pytest.fixture
    def mock_frame(self):
        """Create mock Frame."""
        frame = MagicMock()
        frame.config = MagicMock()
        frame.config.get = MagicMock(return_value=None)
        frame.get_service = MagicMock()
        return frame

    @pytest.mark.asyncio
    async def test_shutdown_unregisters_workers(self, mock_frame):
        """Test that shutdown unregisters workers."""
        mock_worker_service = MagicMock()
        mock_worker_service.register_worker = MagicMock()
        mock_worker_service.unregister_worker = MagicMock()
        mock_event_bus = MagicMock()
        mock_event_bus.subscribe = MagicMock()
        mock_event_bus.unsubscribe = MagicMock()

        mock_frame.get_service.side_effect = lambda name: {
            "workers": mock_worker_service,
            "events": mock_event_bus,
            "database": MagicMock(),
        }.get(name)

        shard = ParseShard()
        await shard.initialize(mock_frame)
        await shard.shutdown()

        mock_worker_service.unregister_worker.assert_called_once()

    @pytest.mark.asyncio
    async def test_shutdown_unsubscribes_events(self, mock_frame):
        """Test that shutdown unsubscribes from events."""
        mock_worker_service = MagicMock()
        mock_event_bus = MagicMock()

        mock_frame.get_service.side_effect = lambda name: {
            "workers": mock_worker_service,
            "events": mock_event_bus,
            "database": MagicMock(),
        }.get(name)

        shard = ParseShard()
        await shard.initialize(mock_frame)
        await shard.shutdown()

        assert mock_event_bus.unsubscribe.call_count == 2

    @pytest.mark.asyncio
    async def test_shutdown_clears_components(self, mock_frame):
        """Test that shutdown clears all components."""
        mock_frame.get_service.return_value = None

        shard = ParseShard()
        await shard.initialize(mock_frame)
        await shard.shutdown()

        assert shard.ner_extractor is None
        assert shard.date_extractor is None
        assert shard.location_extractor is None
        assert shard.relation_extractor is None
        assert shard.entity_linker is None
        assert shard.coref_resolver is None
        assert shard.chunker is None


class TestShardRoutes:
    """Tests for shard route configuration."""

    def test_get_routes_returns_router(self):
        """Test that get_routes returns the FastAPI router."""
        shard = ParseShard()
        routes = shard.get_routes()
        assert routes is not None


class TestEventHandlers:
    """Tests for shard event handlers."""

    @pytest.fixture
    def initialized_shard(self):
        """Create an initialized shard with mocks."""
        shard = ParseShard()
        shard._frame = MagicMock()
        shard.ner_extractor = MagicMock()
        shard.date_extractor = MagicMock()
        shard.chunker = MagicMock()
        return shard

    @pytest.mark.asyncio
    async def test_on_document_ingested_dispatches_job(self, initialized_shard):
        """Test that document ingestion triggers parse job."""
        mock_worker_service = MagicMock()
        mock_worker_service.enqueue = AsyncMock()
        initialized_shard._frame.get_service.return_value = mock_worker_service

        event = {
            "job_id": "ingest-job-123",
            "result": {
                "document_id": "doc-456",
            },
        }

        await initialized_shard._on_document_ingested(event)

        mock_worker_service.enqueue.assert_called_once()
        call_args = mock_worker_service.enqueue.call_args
        assert call_args[1]["pool"] == "cpu-ner"
        assert call_args[1]["payload"]["document_id"] == "doc-456"
        assert call_args[1]["payload"]["job_type"] == "parse_document"

    @pytest.mark.asyncio
    async def test_on_document_ingested_no_doc_id(self, initialized_shard):
        """Test handling ingestion event with no document ID."""
        mock_worker_service = MagicMock()
        mock_worker_service.enqueue = AsyncMock()
        initialized_shard._frame.get_service.return_value = mock_worker_service

        event = {
            "job_id": "ingest-job-123",
            "result": {},
        }

        await initialized_shard._on_document_ingested(event)

        mock_worker_service.enqueue.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_worker_completed_emits_event(self, initialized_shard):
        """Test that worker completion emits parse.document.completed."""
        mock_event_bus = MagicMock()
        mock_event_bus.emit = AsyncMock()
        initialized_shard._frame.get_service.return_value = mock_event_bus

        event = {
            "job_type": "parse_document",
            "result": {
                "document_id": "doc-123",
                "total_entities": 10,
                "total_chunks": 5,
            },
        }

        await initialized_shard._on_worker_completed(event)

        mock_event_bus.emit.assert_called_once()
        call_args = mock_event_bus.emit.call_args
        assert call_args[0][0] == "parse.document.completed"
        assert call_args[0][1]["document_id"] == "doc-123"
        assert call_args[0][1]["entities"] == 10
        assert call_args[0][1]["chunks"] == 5

    @pytest.mark.asyncio
    async def test_on_worker_completed_ignores_other_jobs(self, initialized_shard):
        """Test that non-parse job completions are ignored."""
        mock_event_bus = MagicMock()
        mock_event_bus.emit = AsyncMock()
        initialized_shard._frame.get_service.return_value = mock_event_bus

        event = {
            "job_type": "other_job",
            "result": {
                "document_id": "doc-123",
            },
        }

        await initialized_shard._on_worker_completed(event)

        mock_event_bus.emit.assert_not_called()


class TestPublicAPI:
    """Tests for shard public API methods."""

    @pytest.fixture
    def initialized_shard(self):
        """Create an initialized shard with mocks."""
        shard = ParseShard()
        shard._frame = MagicMock()

        # Mock extractors
        shard.ner_extractor = MagicMock()
        shard.ner_extractor.extract.return_value = [
            EntityMention(
                text="John",
                entity_type=EntityType.PERSON,
                start_char=0,
                end_char=4,
                confidence=0.9,
            ),
        ]

        shard.date_extractor = MagicMock()
        shard.date_extractor.extract.return_value = []

        shard.relation_extractor = MagicMock()
        shard.relation_extractor.extract.return_value = []

        shard.chunker = MagicMock()
        shard.chunker.chunk_text.return_value = []

        return shard

    @pytest.mark.asyncio
    async def test_parse_text_returns_result(self, initialized_shard):
        """Test parse_text returns expected structure."""
        result = await initialized_shard.parse_text("John Smith works here.")

        assert "entities" in result
        assert "dates" in result
        assert "locations" in result
        assert "relationships" in result
        assert "chunks" in result
        assert "total_entities" in result
        assert "total_chunks" in result
        assert "processing_time_ms" in result

    @pytest.mark.asyncio
    async def test_parse_text_with_doc_id(self, initialized_shard):
        """Test parse_text with document ID."""
        result = await initialized_shard.parse_text(
            "John Smith works here.",
            doc_id="doc-123",
        )

        initialized_shard.ner_extractor.extract.assert_called_once()
        initialized_shard.chunker.chunk_text.assert_called_once()
        assert result["total_entities"] == 1

    @pytest.mark.asyncio
    async def test_parse_text_without_doc_id(self, initialized_shard):
        """Test parse_text without document ID skips chunking."""
        result = await initialized_shard.parse_text("Test text")

        initialized_shard.chunker.chunk_text.assert_not_called()
        assert result["chunks"] == []

    @pytest.mark.asyncio
    async def test_parse_document_requires_doc_service(self, initialized_shard):
        """Test parse_document requires document service."""
        initialized_shard._frame.get_service.return_value = None

        with pytest.raises(RuntimeError, match="Document service not available"):
            await initialized_shard.parse_document("doc-123")

    @pytest.mark.asyncio
    async def test_parse_document_with_doc_service(self, initialized_shard):
        """Test parse_document with document service available."""
        mock_doc_service = MagicMock()
        initialized_shard._frame.get_service.return_value = mock_doc_service

        result = await initialized_shard.parse_document("doc-123")

        # Currently returns mock result
        assert "entities" in result


class TestExtractorIntegration:
    """Integration tests for extractors."""

    @pytest.fixture
    def mock_frame(self):
        """Create mock Frame."""
        frame = MagicMock()
        frame.config = MagicMock()
        frame.config.get = MagicMock(return_value=None)
        frame.get_service = MagicMock(return_value=None)
        return frame

    @pytest.mark.asyncio
    async def test_ner_extractor_initialized_with_config(self, mock_frame):
        """Test NER extractor uses configured model."""
        mock_frame.config.get.side_effect = lambda key, default=None: {
            "parse.spacy_model": "en_core_web_md",
        }.get(key, default)

        shard = ParseShard()
        await shard.initialize(mock_frame)

        assert shard.ner_extractor.model_name == "en_core_web_md"

    @pytest.mark.asyncio
    async def test_chunker_initialized_with_config(self, mock_frame):
        """Test chunker uses configured settings."""
        mock_frame.config.get.side_effect = lambda key, default=None: {
            "parse.chunk_size": 800,
            "parse.chunk_overlap": 80,
            "parse.chunk_method": "semantic",
        }.get(key, default)

        shard = ParseShard()
        await shard.initialize(mock_frame)

        assert shard.chunker.chunk_size == 800
        assert shard.chunker.overlap == 80
        assert shard.chunker.method == "semantic"


class TestEntityLinkerIntegration:
    """Integration tests for entity linker."""

    @pytest.fixture
    def mock_frame(self):
        """Create mock Frame with database."""
        frame = MagicMock()
        frame.config = MagicMock()
        frame.config.get = MagicMock(return_value=None)
        frame.get_service = MagicMock()
        return frame

    @pytest.mark.asyncio
    async def test_entity_linker_receives_database(self, mock_frame):
        """Test entity linker is initialized with database service."""
        mock_db = MagicMock()
        mock_frame.get_service.side_effect = lambda name: {
            "database": mock_db,
        }.get(name)

        shard = ParseShard()
        await shard.initialize(mock_frame)

        assert shard.entity_linker.db == mock_db
