"""Tests for Summary Shard API endpoints."""

import pytest
from unittest.mock import AsyncMock, Mock, patch
from fastapi.testclient import TestClient

from arkham_shard_summary import SummaryShard
from arkham_shard_summary.api import router, init_api
from arkham_shard_summary.models import (
    Summary,
    SummaryType,
    SummaryStatus,
    SourceType,
    SummaryLength,
    SummaryResult,
)


class MockFrame:
    """Mock ArkhamFrame for API testing."""

    def __init__(self):
        self.services = {}

    def get_service(self, name: str):
        """Get a mock service."""
        if name == "database" or name == "db":
            return None

        if name == "events":
            mock_events = Mock()
            mock_events.subscribe = Mock()
            mock_events.unsubscribe = Mock()
            mock_events.emit = AsyncMock()
            return mock_events

        if name == "llm":
            mock_llm = Mock()
            mock_llm.generate = AsyncMock(return_value="Mock LLM summary.")
            mock_llm.model_name = "mock-llm"
            return mock_llm

        if name == "workers":
            return Mock()

        return None


@pytest.fixture
async def shard():
    """Create and initialize a shard for testing."""
    shard = SummaryShard()
    frame = MockFrame()
    await shard.initialize(frame)
    init_api(shard)
    return shard


@pytest.fixture
def client(shard):
    """Create test client."""
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(router)

    return TestClient(app)


class TestHealthEndpoint:
    """Test health check endpoint."""

    def test_health(self, client, shard):
        """Test health endpoint."""
        response = client.get("/api/summary/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["shard"] == "summary"
        assert "llm_available" in data


class TestCapabilitiesEndpoint:
    """Test capabilities endpoint."""

    def test_capabilities(self, client, shard):
        """Test capabilities endpoint."""
        response = client.get("/api/summary/capabilities")

        assert response.status_code == 200
        data = response.json()
        assert "llm_available" in data
        assert "workers_available" in data
        assert "summary_types" in data
        assert "source_types" in data
        assert "target_lengths" in data


class TestTypesEndpoint:
    """Test types endpoint."""

    def test_get_types(self, client, shard):
        """Test getting summary types."""
        response = client.get("/api/summary/types")

        assert response.status_code == 200
        data = response.json()
        assert "types" in data
        assert len(data["types"]) > 0

        # Check structure
        first_type = data["types"][0]
        assert "value" in first_type
        assert "label" in first_type
        assert "description" in first_type


class TestCountEndpoint:
    """Test count endpoint."""

    @pytest.mark.asyncio
    async def test_get_count_empty(self, client, shard):
        """Test getting count when no summaries exist."""
        response = client.get("/api/summary/count")

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0

    @pytest.mark.asyncio
    async def test_get_count_with_summaries(self, client, shard):
        """Test getting count with summaries."""
        # Create a summary first
        from arkham_shard_summary.models import SummaryRequest

        request = SummaryRequest(
            source_type=SourceType.DOCUMENT,
            source_ids=["doc-123"],
        )
        await shard.generate_summary(request)

        response = client.get("/api/summary/count")

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1


class TestListEndpoint:
    """Test list summaries endpoint."""

    def test_list_empty(self, client, shard):
        """Test listing when no summaries exist."""
        response = client.get("/api/summary/")

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0
        assert data["page"] == 1
        assert data["page_size"] == 20

    @pytest.mark.asyncio
    async def test_list_with_summaries(self, client, shard):
        """Test listing summaries."""
        from arkham_shard_summary.models import SummaryRequest

        # Create a few summaries
        for i in range(3):
            request = SummaryRequest(
                source_type=SourceType.DOCUMENT,
                source_ids=[f"doc-{i}"],
            )
            await shard.generate_summary(request)

        response = client.get("/api/summary/")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 3
        assert data["total"] == 3

    def test_list_with_pagination(self, client, shard):
        """Test listing with pagination."""
        response = client.get("/api/summary/?page=1&page_size=10")

        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 1
        assert data["page_size"] == 10

    def test_list_with_filters(self, client, shard):
        """Test listing with filters."""
        response = client.get("/api/summary/?summary_type=detailed&source_type=document")

        assert response.status_code == 200

    def test_list_with_invalid_filter(self, client, shard):
        """Test listing with invalid filter."""
        response = client.get("/api/summary/?summary_type=invalid")

        assert response.status_code == 400


class TestCreateEndpoint:
    """Test create summary endpoint."""

    def test_create_summary(self, client, shard):
        """Test creating a summary."""
        request_data = {
            "source_type": "document",
            "source_ids": ["doc-123"],
            "summary_type": "detailed",
            "target_length": "medium",
            "include_key_points": True,
            "include_title": True,
        }

        response = client.post("/api/summary/", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert "summary_id" in data
        assert data["status"] == "completed"
        assert "content" in data

    def test_create_summary_with_focus(self, client, shard):
        """Test creating summary with focus areas."""
        request_data = {
            "source_type": "document",
            "source_ids": ["doc-123"],
            "summary_type": "executive",
            "focus_areas": ["key findings"],
            "exclude_topics": ["acknowledgments"],
        }

        response = client.post("/api/summary/", json=request_data)

        assert response.status_code == 200

    def test_create_summary_invalid_type(self, client, shard):
        """Test creating summary with invalid type."""
        request_data = {
            "source_type": "invalid_type",
            "source_ids": ["doc-123"],
        }

        response = client.post("/api/summary/", json=request_data)

        assert response.status_code == 422  # Validation error

    def test_create_summary_no_sources(self, client, shard):
        """Test creating summary with no source IDs."""
        request_data = {
            "source_type": "document",
            "source_ids": [],
        }

        response = client.post("/api/summary/", json=request_data)

        assert response.status_code == 422  # Validation error


class TestGetEndpoint:
    """Test get summary endpoint."""

    @pytest.mark.asyncio
    async def test_get_summary(self, client, shard):
        """Test getting a summary by ID."""
        from arkham_shard_summary.models import SummaryRequest

        # Create a summary first
        request = SummaryRequest(
            source_type=SourceType.DOCUMENT,
            source_ids=["doc-123"],
        )
        result = await shard.generate_summary(request)
        summary_id = result.summary_id

        # Get it
        response = client.get(f"/api/summary/{summary_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == summary_id
        assert "content" in data

    def test_get_nonexistent_summary(self, client, shard):
        """Test getting a summary that doesn't exist."""
        response = client.get("/api/summary/nonexistent-id")

        assert response.status_code == 404


class TestDeleteEndpoint:
    """Test delete summary endpoint."""

    @pytest.mark.asyncio
    async def test_delete_summary(self, client, shard):
        """Test deleting a summary."""
        from arkham_shard_summary.models import SummaryRequest

        # Create a summary first
        request = SummaryRequest(
            source_type=SourceType.DOCUMENT,
            source_ids=["doc-123"],
        )
        result = await shard.generate_summary(request)
        summary_id = result.summary_id

        # Delete it
        response = client.delete(f"/api/summary/{summary_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["deleted"] is True
        assert data["summary_id"] == summary_id

    def test_delete_nonexistent_summary(self, client, shard):
        """Test deleting a summary that doesn't exist."""
        response = client.delete("/api/summary/nonexistent-id")

        assert response.status_code == 404


class TestBatchEndpoint:
    """Test batch summary endpoint."""

    def test_batch_summaries(self, client, shard):
        """Test batch summary creation."""
        request_data = {
            "requests": [
                {
                    "source_type": "document",
                    "source_ids": ["doc-1"],
                    "summary_type": "brief",
                },
                {
                    "source_type": "document",
                    "source_ids": ["doc-2"],
                    "summary_type": "detailed",
                },
            ],
            "parallel": False,
            "stop_on_error": False,
        }

        response = client.post("/api/summary/batch", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert data["successful"] == 2
        assert data["failed"] == 0
        assert len(data["summaries"]) == 2


class TestDocumentEndpoint:
    """Test document summary endpoint."""

    @pytest.mark.asyncio
    async def test_get_document_summary_new(self, client, shard):
        """Test getting summary for document (creates new)."""
        response = client.get("/api/summary/document/doc-123")

        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "content" in data

    @pytest.mark.asyncio
    async def test_get_document_summary_existing(self, client, shard):
        """Test getting summary for document (returns existing)."""
        from arkham_shard_summary.models import SummaryRequest

        # Create a summary first
        request = SummaryRequest(
            source_type=SourceType.DOCUMENT,
            source_ids=["doc-456"],
        )
        result = await shard.generate_summary(request)
        summary_id = result.summary_id

        # Get it via document endpoint
        response = client.get("/api/summary/document/doc-456")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == summary_id

    def test_get_document_summary_regenerate(self, client, shard):
        """Test forcing regeneration of document summary."""
        response = client.get("/api/summary/document/doc-789?regenerate=true")

        assert response.status_code == 200

    def test_get_document_summary_invalid_type(self, client, shard):
        """Test getting document summary with invalid type."""
        response = client.get("/api/summary/document/doc-123?summary_type=invalid")

        assert response.status_code == 400


class TestStatsEndpoint:
    """Test statistics endpoint."""

    @pytest.mark.asyncio
    async def test_get_stats(self, client, shard):
        """Test getting statistics."""
        from arkham_shard_summary.models import SummaryRequest

        # Create a few summaries
        await shard.generate_summary(
            SummaryRequest(
                source_type=SourceType.DOCUMENT,
                source_ids=["doc-1"],
                summary_type=SummaryType.BRIEF,
            )
        )
        await shard.generate_summary(
            SummaryRequest(
                source_type=SourceType.DOCUMENT,
                source_ids=["doc-2"],
                summary_type=SummaryType.DETAILED,
            )
        )

        response = client.get("/api/summary/stats")

        assert response.status_code == 200
        data = response.json()
        assert data["total_summaries"] == 2
        assert "by_type" in data
        assert "by_source_type" in data
        assert "avg_confidence" in data
