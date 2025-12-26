"""Tests for OCR shard implementation."""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from arkham_shard_ocr.shard import OCRShard


@pytest_asyncio.fixture
async def mock_frame():
    """Create a mock Frame instance."""
    frame = MagicMock()
    frame.config = MagicMock()
    frame.config.get = MagicMock(return_value="paddle")

    # Mock services
    worker_service = MagicMock()
    worker_service.register_worker = MagicMock()
    worker_service.unregister_worker = MagicMock()
    worker_service.enqueue = AsyncMock(return_value="job-123")
    worker_service.wait_for_result = AsyncMock(return_value={"text": "result"})

    event_bus = MagicMock()
    event_bus.subscribe = AsyncMock()
    event_bus.unsubscribe = AsyncMock()
    event_bus.emit = AsyncMock()

    doc_service = MagicMock()

    def get_service(name):
        if name == "workers":
            return worker_service
        elif name == "events":
            return event_bus
        elif name == "documents":
            return doc_service
        return None

    frame.get_service = MagicMock(side_effect=get_service)

    return frame


class TestOCRShardMetadata:
    """Test OCR shard metadata."""

    def test_shard_name(self):
        """Test shard has correct name."""
        shard = OCRShard()
        assert shard.name == "ocr"

    def test_shard_version(self):
        """Test shard has version."""
        shard = OCRShard()
        assert shard.version == "0.1.0"

    def test_shard_description(self):
        """Test shard has description."""
        shard = OCRShard()
        assert "optical character recognition" in shard.description.lower()

    def test_shard_has_manifest(self):
        """Test shard loads manifest from shard.yaml."""
        shard = OCRShard()
        assert hasattr(shard, "manifest")
        # Manifest should be loaded by parent class


class TestOCRShardInitialization:
    """Test OCR shard initialization."""

    def test_shard_creation(self):
        """Test creating a shard instance."""
        shard = OCRShard()
        assert shard.name == "ocr"
        assert shard._frame is None
        assert shard._config is None
        assert shard._default_engine == "paddle"

    @pytest.mark.asyncio
    async def test_initialize_with_frame(self, mock_frame):
        """Test initializing shard with frame."""
        shard = OCRShard()
        await shard.initialize(mock_frame)

        assert shard._frame == mock_frame
        assert shard._config is not None

    @pytest.mark.asyncio
    async def test_initialize_sets_default_engine(self, mock_frame):
        """Test initialization sets default engine from config."""
        mock_frame.config.get = MagicMock(return_value="qwen")

        shard = OCRShard()
        await shard.initialize(mock_frame)

        assert shard._default_engine == "qwen"
        mock_frame.config.get.assert_called_with("ocr.default_engine", "paddle")

    @pytest.mark.asyncio
    async def test_initialize_registers_workers(self, mock_frame):
        """Test initialization registers workers."""
        shard = OCRShard()
        await shard.initialize(mock_frame)

        worker_service = mock_frame.get_service("workers")
        assert worker_service.register_worker.call_count == 2

        # Check both workers were registered
        from arkham_shard_ocr.workers import PaddleWorker, QwenWorker
        calls = worker_service.register_worker.call_args_list
        registered_workers = [call[0][0] for call in calls]
        assert PaddleWorker in registered_workers
        assert QwenWorker in registered_workers

    @pytest.mark.asyncio
    async def test_initialize_subscribes_to_events(self, mock_frame):
        """Test initialization subscribes to events."""
        shard = OCRShard()
        await shard.initialize(mock_frame)

        event_bus = mock_frame.get_service("events")
        event_bus.subscribe.assert_called_once()

        # Verify subscribed to correct event
        call_args = event_bus.subscribe.call_args
        assert call_args[0][0] == "ingest.job.completed"

    @pytest.mark.asyncio
    async def test_initialize_without_worker_service(self, mock_frame):
        """Test initialization when worker service unavailable."""
        mock_frame.get_service = MagicMock(return_value=None)

        shard = OCRShard()
        # Should not raise an error
        await shard.initialize(mock_frame)

    @pytest.mark.asyncio
    async def test_initialize_without_event_bus(self, mock_frame):
        """Test initialization when event bus unavailable."""
        def get_service(name):
            if name == "workers":
                return MagicMock()
            return None

        mock_frame.get_service = MagicMock(side_effect=get_service)

        shard = OCRShard()
        # Should not raise an error
        await shard.initialize(mock_frame)

    @pytest.mark.asyncio
    async def test_initialize_initializes_api(self, mock_frame):
        """Test initialization sets up API."""
        shard = OCRShard()
        await shard.initialize(mock_frame)

        # Verify API was initialized with shard reference
        from arkham_shard_ocr import api
        assert api._shard == shard


class TestOCRShardShutdown:
    """Test OCR shard shutdown."""

    @pytest.mark.asyncio
    async def test_shutdown(self, mock_frame):
        """Test shutting down the shard."""
        shard = OCRShard()
        await shard.initialize(mock_frame)
        await shard.shutdown()

        # Verify workers were unregistered
        worker_service = mock_frame.get_service("workers")
        assert worker_service.unregister_worker.call_count == 2

    @pytest.mark.asyncio
    async def test_shutdown_unsubscribes_from_events(self, mock_frame):
        """Test shutdown unsubscribes from events."""
        shard = OCRShard()
        await shard.initialize(mock_frame)
        await shard.shutdown()

        event_bus = mock_frame.get_service("events")
        event_bus.unsubscribe.assert_called_once()

        # Verify unsubscribed from correct event
        call_args = event_bus.unsubscribe.call_args
        assert call_args[0][0] == "ingest.job.completed"

    @pytest.mark.asyncio
    async def test_shutdown_without_frame(self):
        """Test shutdown before initialization."""
        shard = OCRShard()
        # Should not raise an error
        await shard.shutdown()

    @pytest.mark.asyncio
    async def test_shutdown_without_services(self, mock_frame):
        """Test shutdown when services unavailable."""
        mock_frame.get_service = MagicMock(return_value=None)

        shard = OCRShard()
        await shard.initialize(mock_frame)
        # Should not raise an error
        await shard.shutdown()


class TestOCRShardRoutes:
    """Test OCR shard routes."""

    def test_get_routes(self):
        """Test getting routes returns router."""
        shard = OCRShard()
        routes = shard.get_routes()

        from arkham_shard_ocr.api import router
        assert routes == router

    def test_routes_has_endpoints(self):
        """Test router has expected endpoints."""
        shard = OCRShard()
        router = shard.get_routes()

        # Get route paths
        paths = [route.path for route in router.routes]

        assert "/health" in paths
        assert "/page" in paths
        assert "/document" in paths
        assert "/upload" in paths


class TestOCRPageMethod:
    """Test the ocr_page method."""

    @pytest.mark.asyncio
    async def test_ocr_page_success(self, mock_frame):
        """Test OCR page with default engine."""
        shard = OCRShard()
        await shard.initialize(mock_frame)

        result = await shard.ocr_page(image_path="/path/to/image.png")

        # Verify worker was enqueued
        worker_service = mock_frame.get_service("workers")
        worker_service.enqueue.assert_called_once()

        call_args = worker_service.enqueue.call_args
        assert call_args.kwargs["pool"] == "gpu-paddle"
        assert call_args.kwargs["payload"]["image_path"] == "/path/to/image.png"
        assert call_args.kwargs["payload"]["lang"] == "en"

        # Verify result was awaited
        worker_service.wait_for_result.assert_called_once_with("job-123")
        assert result == {"text": "result"}

    @pytest.mark.asyncio
    async def test_ocr_page_with_qwen_engine(self, mock_frame):
        """Test OCR page with Qwen engine."""
        shard = OCRShard()
        await shard.initialize(mock_frame)

        await shard.ocr_page(
            image_path="/path/to/image.png",
            engine="qwen",
        )

        worker_service = mock_frame.get_service("workers")
        call_args = worker_service.enqueue.call_args
        assert call_args.kwargs["pool"] == "gpu-qwen"

    @pytest.mark.asyncio
    async def test_ocr_page_with_custom_language(self, mock_frame):
        """Test OCR page with custom language."""
        shard = OCRShard()
        await shard.initialize(mock_frame)

        await shard.ocr_page(
            image_path="/path/to/image.png",
            language="zh",
        )

        worker_service = mock_frame.get_service("workers")
        call_args = worker_service.enqueue.call_args
        assert call_args.kwargs["payload"]["lang"] == "zh"

    @pytest.mark.asyncio
    async def test_ocr_page_without_worker_service(self, mock_frame):
        """Test OCR page when worker service unavailable."""
        mock_frame.get_service = MagicMock(return_value=None)

        shard = OCRShard()
        await shard.initialize(mock_frame)

        with pytest.raises(RuntimeError, match="Worker service not available"):
            await shard.ocr_page(image_path="/path/to/image.png")

    @pytest.mark.asyncio
    async def test_ocr_page_uses_default_engine(self, mock_frame):
        """Test OCR page uses configured default engine."""
        mock_frame.config.get = MagicMock(return_value="qwen")

        shard = OCRShard()
        await shard.initialize(mock_frame)

        await shard.ocr_page(image_path="/path/to/image.png")

        # Should use qwen pool since default is qwen
        worker_service = mock_frame.get_service("workers")
        call_args = worker_service.enqueue.call_args
        assert call_args.kwargs["pool"] == "gpu-qwen"


class TestOCRDocumentMethod:
    """Test the ocr_document method."""

    @pytest.mark.asyncio
    async def test_ocr_document_success(self, mock_frame):
        """Test OCR document processing."""
        shard = OCRShard()
        await shard.initialize(mock_frame)

        result = await shard.ocr_document(document_id="doc123")

        assert result["document_id"] == "doc123"
        assert result["engine"] == "paddle"
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_ocr_document_with_engine(self, mock_frame):
        """Test OCR document with specific engine."""
        shard = OCRShard()
        await shard.initialize(mock_frame)

        result = await shard.ocr_document(
            document_id="doc123",
            engine="qwen",
        )

        assert result["engine"] == "qwen"

    @pytest.mark.asyncio
    async def test_ocr_document_emits_start_event(self, mock_frame):
        """Test OCR document emits start event."""
        shard = OCRShard()
        await shard.initialize(mock_frame)

        await shard.ocr_document(document_id="doc123")

        event_bus = mock_frame.get_service("events")
        # Should emit start and completion events
        assert event_bus.emit.call_count == 2

        # Check start event
        first_call = event_bus.emit.call_args_list[0]
        assert first_call[0][0] == "ocr.document.started"
        assert first_call[0][1]["document_id"] == "doc123"
        assert first_call.kwargs["source"] == "ocr-shard"

    @pytest.mark.asyncio
    async def test_ocr_document_emits_completion_event(self, mock_frame):
        """Test OCR document emits completion event."""
        shard = OCRShard()
        await shard.initialize(mock_frame)

        result = await shard.ocr_document(document_id="doc123")

        event_bus = mock_frame.get_service("events")
        # Check completion event
        second_call = event_bus.emit.call_args_list[1]
        assert second_call[0][0] == "ocr.document.completed"
        assert second_call[0][1] == result
        assert second_call.kwargs["source"] == "ocr-shard"

    @pytest.mark.asyncio
    async def test_ocr_document_without_event_bus(self, mock_frame):
        """Test OCR document when event bus unavailable."""
        def get_service(name):
            if name == "events":
                return None
            return MagicMock()

        mock_frame.get_service = MagicMock(side_effect=get_service)

        shard = OCRShard()
        await shard.initialize(mock_frame)

        # Should not raise error
        result = await shard.ocr_document(document_id="doc123")
        assert result["document_id"] == "doc123"

    @pytest.mark.asyncio
    async def test_ocr_document_without_doc_service(self, mock_frame):
        """Test OCR document when document service unavailable."""
        def get_service(name):
            if name == "documents":
                return None
            if name == "events":
                event_bus = MagicMock()
                event_bus.emit = AsyncMock()
                event_bus.subscribe = AsyncMock()
                return event_bus
            if name == "workers":
                worker_service = MagicMock()
                worker_service.register_worker = MagicMock()
                return worker_service
            return MagicMock()

        mock_frame.get_service = MagicMock(side_effect=get_service)

        shard = OCRShard()
        await shard.initialize(mock_frame)

        # Should raise error when doc service unavailable
        with pytest.raises(RuntimeError, match="Document service not available"):
            await shard.ocr_document(document_id="doc123")


class TestEventHandlers:
    """Test event handler methods."""

    @pytest.mark.asyncio
    async def test_on_document_ingested_image(self, mock_frame):
        """Test document ingested handler for image type."""
        shard = OCRShard()
        await shard.initialize(mock_frame)

        # Mock ocr_document method
        shard.ocr_document = AsyncMock()

        event = {
            "document_id": "doc123",
            "document_type": "image",
        }

        await shard._on_document_ingested(event)

        # Should trigger OCR
        shard.ocr_document.assert_called_once_with("doc123")

    @pytest.mark.asyncio
    async def test_on_document_ingested_scanned_pdf(self, mock_frame):
        """Test document ingested handler for scanned PDF."""
        shard = OCRShard()
        await shard.initialize(mock_frame)

        shard.ocr_document = AsyncMock()

        event = {
            "document_id": "doc456",
            "document_type": "scanned_pdf",
        }

        await shard._on_document_ingested(event)

        # Should trigger OCR
        shard.ocr_document.assert_called_once_with("doc456")

    @pytest.mark.asyncio
    async def test_on_document_ingested_text_document(self, mock_frame):
        """Test document ingested handler for text document."""
        shard = OCRShard()
        await shard.initialize(mock_frame)

        shard.ocr_document = AsyncMock()

        event = {
            "document_id": "doc789",
            "document_type": "text",
        }

        await shard._on_document_ingested(event)

        # Should NOT trigger OCR for text documents
        shard.ocr_document.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_document_ingested_missing_type(self, mock_frame):
        """Test document ingested handler with missing type."""
        shard = OCRShard()
        await shard.initialize(mock_frame)

        shard.ocr_document = AsyncMock()

        event = {
            "document_id": "doc999",
        }

        await shard._on_document_ingested(event)

        # Should NOT trigger OCR when type missing
        shard.ocr_document.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_document_ingested_pdf_type(self, mock_frame):
        """Test document ingested handler for regular PDF."""
        shard = OCRShard()
        await shard.initialize(mock_frame)

        shard.ocr_document = AsyncMock()

        event = {
            "document_id": "doc111",
            "document_type": "pdf",
        }

        await shard._on_document_ingested(event)

        # Should NOT trigger OCR for regular PDFs (only scanned_pdf)
        shard.ocr_document.assert_not_called()


class TestShardIntegration:
    """Test shard integration scenarios."""

    @pytest.mark.asyncio
    async def test_full_lifecycle(self, mock_frame):
        """Test complete shard lifecycle."""
        shard = OCRShard()

        # Initialize
        await shard.initialize(mock_frame)
        assert shard._frame is not None

        # Process page
        result = await shard.ocr_page(image_path="/test.png")
        assert "text" in result

        # Process document
        doc_result = await shard.ocr_document(document_id="doc123")
        assert doc_result["document_id"] == "doc123"

        # Shutdown
        await shard.shutdown()

    @pytest.mark.asyncio
    async def test_multiple_page_ocr_calls(self, mock_frame):
        """Test processing multiple pages."""
        shard = OCRShard()
        await shard.initialize(mock_frame)

        # Process multiple pages
        result1 = await shard.ocr_page(image_path="/page1.png")
        result2 = await shard.ocr_page(image_path="/page2.png")
        result3 = await shard.ocr_page(image_path="/page3.png")

        worker_service = mock_frame.get_service("workers")
        assert worker_service.enqueue.call_count == 3
        assert worker_service.wait_for_result.call_count == 3
