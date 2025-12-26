"""Tests for entities shard API endpoints."""

import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI
from unittest.mock import MagicMock, AsyncMock

from arkham_shard_entities.api import router, init_api


@pytest.fixture
def mock_services():
    """Create mock services for API testing."""
    return {
        "db": MagicMock(),
        "event_bus": MagicMock(),
        "vectors_service": MagicMock(),
        "entity_service": MagicMock(),
    }


@pytest.fixture
def app(mock_services):
    """Create a test FastAPI app with the router."""
    # Initialize API with mock services
    init_api(
        db=mock_services["db"],
        event_bus=mock_services["event_bus"],
        vectors_service=mock_services["vectors_service"],
        entity_service=mock_services["entity_service"],
    )

    # Create app and include router
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    """Create a test client."""
    return TestClient(app)


class TestHealthEndpoint:
    """Test health check endpoint."""

    def test_health_with_all_services(self, client):
        """Test health endpoint with all services available."""
        response = client.get("/api/entities/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["shard"] == "entities"
        assert data["vectors_available"] is True
        assert data["entity_service_available"] is True

    def test_health_without_optional_services(self):
        """Test health endpoint without optional services."""
        # Initialize with None for optional services
        init_api(
            db=MagicMock(),
            event_bus=MagicMock(),
            vectors_service=None,
            entity_service=None,
        )

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        response = client.get("/api/entities/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["vectors_available"] is False
        assert data["entity_service_available"] is False


class TestListEntitiesEndpoint:
    """Test list entities endpoint."""

    def test_list_entities_default_params(self, client):
        """Test list entities with default parameters."""
        response = client.get("/api/entities/items")

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "page_size" in data
        assert data["items"] == []
        assert data["total"] == 0
        assert data["page"] == 1
        assert data["page_size"] == 20

    def test_list_entities_with_pagination(self, client):
        """Test list entities with pagination params."""
        response = client.get("/api/entities/items?page=2&page_size=50")

        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 2
        assert data["page_size"] == 50

    def test_list_entities_pagination_limits(self, client):
        """Test pagination limits are enforced."""
        # Page too low
        response = client.get("/api/entities/items?page=0")
        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 1  # Should be clamped to 1

        # Page size too high
        response = client.get("/api/entities/items?page_size=500")
        assert response.status_code == 200
        data = response.json()
        assert data["page_size"] == 100  # Should be clamped to max 100

    def test_list_entities_with_filter(self, client):
        """Test list entities with entity type filter."""
        response = client.get("/api/entities/items?filter=PERSON")

        assert response.status_code == 200
        # Stub returns empty list regardless of filter

    def test_list_entities_with_search(self, client):
        """Test list entities with search query."""
        response = client.get("/api/entities/items?q=John")

        assert response.status_code == 200
        # Stub returns empty list regardless of search

    def test_list_entities_with_sort(self, client):
        """Test list entities with sorting."""
        response = client.get("/api/entities/items?sort=name&order=desc")

        assert response.status_code == 200

    def test_list_entities_show_merged(self, client):
        """Test list entities including merged entities."""
        response = client.get("/api/entities/items?show_merged=true")

        assert response.status_code == 200


class TestGetEntityEndpoint:
    """Test get entity endpoint."""

    def test_get_entity_not_found(self, client):
        """Test get entity returns 404 for non-existent entity."""
        response = client.get("/api/entities/items/nonexistent-id")

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert data["detail"] == "Entity not found"


class TestUpdateEntityEndpoint:
    """Test update entity endpoint."""

    def test_update_entity_not_found(self, client):
        """Test update entity returns 404 for non-existent entity."""
        update_data = {
            "name": "Updated Name",
        }
        response = client.put("/api/entities/items/nonexistent-id", json=update_data)

        assert response.status_code == 404

    def test_update_entity_partial_update(self, client):
        """Test partial update with only some fields."""
        update_data = {
            "name": "New Name",
        }
        response = client.put("/api/entities/items/test-id", json=update_data)

        # Stub returns 404, but validates request format
        assert response.status_code == 404

    def test_update_entity_all_fields(self, client):
        """Test update with all fields."""
        update_data = {
            "name": "New Name",
            "entity_type": "ORGANIZATION",
            "aliases": ["Alias1", "Alias2"],
            "metadata": {"key": "value"},
        }
        response = client.put("/api/entities/items/test-id", json=update_data)

        # Stub returns 404
        assert response.status_code == 404


class TestDeleteEntityEndpoint:
    """Test delete entity endpoint."""

    def test_delete_entity(self, client):
        """Test delete entity endpoint."""
        response = client.delete("/api/entities/items/test-id")

        assert response.status_code == 200
        data = response.json()
        assert data["deleted"] is True
        assert data["entity_id"] == "test-id"


class TestCountEndpoint:
    """Test count endpoint."""

    def test_count_default(self, client):
        """Test count with no filter."""
        response = client.get("/api/entities/count")

        assert response.status_code == 200
        data = response.json()
        assert "count" in data
        assert data["count"] == 0

    def test_count_with_filter(self, client):
        """Test count with entity type filter."""
        response = client.get("/api/entities/count?filter=PERSON")

        assert response.status_code == 200


class TestDuplicatesEndpoint:
    """Test duplicates endpoint."""

    def test_get_duplicates_default(self, client):
        """Test get duplicates with default params."""
        response = client.get("/api/entities/duplicates")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert data == []

    def test_get_duplicates_with_filter(self, client):
        """Test get duplicates with entity type filter."""
        response = client.get("/api/entities/duplicates?entity_type=PERSON")

        assert response.status_code == 200

    def test_get_duplicates_with_threshold(self, client):
        """Test get duplicates with custom threshold."""
        response = client.get("/api/entities/duplicates?threshold=0.9")

        assert response.status_code == 200


class TestMergeSuggestionsEndpoint:
    """Test merge suggestions endpoint."""

    def test_merge_suggestions_without_vectors(self):
        """Test merge suggestions fails without vector service."""
        # Initialize without vector service
        init_api(
            db=MagicMock(),
            event_bus=MagicMock(),
            vectors_service=None,
            entity_service=MagicMock(),
        )

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        response = client.get("/api/entities/merge-suggestions")

        assert response.status_code == 503
        data = response.json()
        assert "Vector service not available" in data["detail"]

    def test_merge_suggestions_with_vectors(self, client):
        """Test merge suggestions with vector service."""
        response = client.get("/api/entities/merge-suggestions")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_merge_suggestions_for_entity(self, client):
        """Test merge suggestions for specific entity."""
        response = client.get("/api/entities/merge-suggestions?entity_id=test-id")

        assert response.status_code == 200

    def test_merge_suggestions_with_limit(self, client):
        """Test merge suggestions with custom limit."""
        response = client.get("/api/entities/merge-suggestions?limit=5")

        assert response.status_code == 200


class TestMergeEntitiesEndpoint:
    """Test merge entities endpoint."""

    def test_merge_entities(self, client):
        """Test merge entities endpoint."""
        merge_data = {
            "entity_ids": ["id1", "id2", "id3"],
            "canonical_id": "id1",
            "canonical_name": "John Doe",
        }
        response = client.post("/api/entities/merge", json=merge_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["canonical_id"] == "id1"
        assert data["merged_count"] == 3

    def test_merge_entities_without_canonical_name(self, client):
        """Test merge entities without providing canonical name."""
        merge_data = {
            "entity_ids": ["id1", "id2"],
            "canonical_id": "id1",
        }
        response = client.post("/api/entities/merge", json=merge_data)

        assert response.status_code == 200


class TestListRelationshipsEndpoint:
    """Test list relationships endpoint."""

    def test_list_relationships_default(self, client):
        """Test list relationships with default params."""
        response = client.get("/api/entities/relationships")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert data == []

    def test_list_relationships_with_filter(self, client):
        """Test list relationships filtered by entity."""
        response = client.get("/api/entities/relationships?entity_id=test-id")

        assert response.status_code == 200

    def test_list_relationships_by_type(self, client):
        """Test list relationships filtered by type."""
        response = client.get("/api/entities/relationships?relationship_type=WORKS_FOR")

        assert response.status_code == 200

    def test_list_relationships_pagination(self, client):
        """Test list relationships with pagination."""
        response = client.get("/api/entities/relationships?page=2&page_size=10")

        assert response.status_code == 200


class TestCreateRelationshipEndpoint:
    """Test create relationship endpoint."""

    def test_create_relationship_not_found(self, client):
        """Test create relationship returns 404 if entity not found."""
        rel_data = {
            "source_id": "person-id",
            "target_id": "org-id",
            "relationship_type": "WORKS_FOR",
        }
        response = client.post("/api/entities/relationships", json=rel_data)

        assert response.status_code == 404

    def test_create_relationship_with_metadata(self, client):
        """Test create relationship with metadata."""
        rel_data = {
            "source_id": "person-id",
            "target_id": "org-id",
            "relationship_type": "WORKS_FOR",
            "confidence": 0.95,
            "metadata": {"position": "Engineer", "start_date": "2020-01-01"},
        }
        response = client.post("/api/entities/relationships", json=rel_data)

        # Stub returns 404
        assert response.status_code == 404


class TestDeleteRelationshipEndpoint:
    """Test delete relationship endpoint."""

    def test_delete_relationship(self, client):
        """Test delete relationship endpoint."""
        response = client.delete("/api/entities/relationships/rel-id")

        assert response.status_code == 200
        data = response.json()
        assert data["deleted"] is True
        assert data["relationship_id"] == "rel-id"


class TestGetEntityRelationshipsEndpoint:
    """Test get entity relationships endpoint."""

    def test_get_entity_relationships(self, client):
        """Test get all relationships for an entity."""
        response = client.get("/api/entities/test-id/relationships")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert data == []


class TestGetEntityMentionsEndpoint:
    """Test get entity mentions endpoint."""

    def test_get_entity_mentions_default(self, client):
        """Test get entity mentions with default params."""
        response = client.get("/api/entities/test-id/mentions")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert data == []

    def test_get_entity_mentions_pagination(self, client):
        """Test get entity mentions with pagination."""
        response = client.get("/api/entities/test-id/mentions?page=2&page_size=100")

        assert response.status_code == 200


class TestBatchMergeEndpoint:
    """Test batch merge endpoint."""

    def test_batch_merge_empty(self, client):
        """Test batch merge with empty list."""
        response = client.post("/api/entities/batch/merge", json=[])

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["processed"] == 0
        assert data["failed"] == 0

    def test_batch_merge_multiple(self, client):
        """Test batch merge with multiple operations."""
        batch_data = [
            {
                "entity_ids": ["id1", "id2"],
                "canonical_id": "id1",
            },
            {
                "entity_ids": ["id3", "id4"],
                "canonical_id": "id3",
            },
        ]
        response = client.post("/api/entities/batch/merge", json=batch_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["processed"] == 2
        assert data["failed"] == 0
        assert isinstance(data["errors"], list)


class TestRequestValidation:
    """Test request validation."""

    def test_update_entity_invalid_json(self, client):
        """Test update entity with invalid JSON."""
        response = client.put(
            "/api/entities/items/test-id",
            data="not valid json",
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 422

    def test_merge_missing_required_fields(self, client):
        """Test merge entities with missing required fields."""
        # Missing canonical_id
        merge_data = {
            "entity_ids": ["id1", "id2"],
        }
        response = client.post("/api/entities/merge", json=merge_data)

        assert response.status_code == 422

    def test_relationship_missing_required_fields(self, client):
        """Test create relationship with missing required fields."""
        # Missing target_id
        rel_data = {
            "source_id": "person-id",
            "relationship_type": "WORKS_FOR",
        }
        response = client.post("/api/entities/relationships", json=rel_data)

        assert response.status_code == 422


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
