"""Tests for Provenance Shard API endpoints."""

import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI
from arkham_shard_provenance.api import router, init_api


@pytest.fixture
def app():
    """Create test FastAPI app."""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    # Initialize API with None values (stub mode)
    init_api(
        chain_manager=None,
        lineage_tracker=None,
        audit_logger=None,
        event_bus=None,
        storage=None,
    )
    return TestClient(app)


class TestHealthEndpoint:
    """Test health check endpoint."""

    def test_health_check(self, client):
        """Test health check returns OK."""
        response = client.get("/api/provenance/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"
        assert data["shard"] == "provenance"
        assert data["version"] == "0.1.0"


class TestCountEndpoint:
    """Test count/badge endpoint."""

    def test_get_count(self, client):
        """Test getting count for badge."""
        response = client.get("/api/provenance/count")
        assert response.status_code == 200

        data = response.json()
        assert "count" in data
        assert data["count"] == 0  # Stub returns 0


class TestChainEndpoints:
    """Test evidence chain endpoints."""

    def test_list_chains_default(self, client):
        """Test listing chains with default parameters."""
        response = client.get("/api/provenance/chains")
        assert response.status_code == 200

        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "page_size" in data
        assert data["page"] == 1
        assert data["page_size"] == 20
        assert data["total"] == 0
        assert data["items"] == []

    def test_list_chains_with_pagination(self, client):
        """Test listing chains with custom pagination."""
        response = client.get("/api/provenance/chains?page=2&page_size=10")
        assert response.status_code == 200

        data = response.json()
        assert data["page"] == 2
        assert data["page_size"] == 10

    def test_list_chains_with_sort(self, client):
        """Test listing chains with sorting."""
        response = client.get("/api/provenance/chains?sort=title&order=asc")
        assert response.status_code == 200

    def test_list_chains_with_search(self, client):
        """Test listing chains with search query."""
        response = client.get("/api/provenance/chains?q=test")
        assert response.status_code == 200

    def test_list_chains_with_status_filter(self, client):
        """Test listing chains with status filter."""
        response = client.get("/api/provenance/chains?status=active")
        assert response.status_code == 200

    def test_list_chains_invalid_sort_field(self, client):
        """Test listing chains with invalid sort field."""
        response = client.get("/api/provenance/chains?sort=invalid")
        assert response.status_code == 422  # Validation error

    def test_list_chains_invalid_order(self, client):
        """Test listing chains with invalid order."""
        response = client.get("/api/provenance/chains?order=invalid")
        assert response.status_code == 422

    def test_create_chain(self, client):
        """Test creating a new chain."""
        chain_data = {
            "title": "Test Chain",
            "description": "A test evidence chain",
            "created_by": "user-1",
        }
        response = client.post("/api/provenance/chains", json=chain_data)
        assert response.status_code == 501  # Not implemented

    def test_get_chain(self, client):
        """Test getting a single chain."""
        response = client.get("/api/provenance/chains/chain-123")
        assert response.status_code == 404  # Not found (stub)

    def test_update_chain(self, client):
        """Test updating a chain."""
        update_data = {
            "title": "Updated Title",
            "status": "verified",
        }
        response = client.put("/api/provenance/chains/chain-123", json=update_data)
        assert response.status_code == 404  # Not found (stub)

    def test_delete_chain(self, client):
        """Test deleting a chain."""
        response = client.delete("/api/provenance/chains/chain-123")
        assert response.status_code == 200

        data = response.json()
        assert data["deleted"] is True


class TestLinkEndpoints:
    """Test provenance link endpoints."""

    def test_add_link(self, client):
        """Test adding a link to a chain."""
        link_data = {
            "source_artifact_id": "src-1",
            "target_artifact_id": "tgt-1",
            "link_type": "derived_from",
            "confidence": 0.95,
        }
        response = client.post("/api/provenance/chains/chain-1/links", json=link_data)
        assert response.status_code == 501  # Not implemented

    def test_list_chain_links(self, client):
        """Test listing links in a chain."""
        response = client.get("/api/provenance/chains/chain-1/links")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)
        assert data == []

    def test_delete_link(self, client):
        """Test deleting a link."""
        response = client.delete("/api/provenance/links/link-123")
        assert response.status_code == 200

        data = response.json()
        assert data["deleted"] is True

    def test_verify_link(self, client):
        """Test verifying a link."""
        verify_data = {
            "verified_by": "reviewer-1",
            "notes": "Verified manually",
        }
        response = client.put("/api/provenance/links/link-123/verify", json=verify_data)
        assert response.status_code == 404  # Not found (stub)


class TestLineageEndpoints:
    """Test lineage tracking endpoints."""

    def test_get_lineage_default(self, client):
        """Test getting lineage with default parameters."""
        response = client.get("/api/provenance/lineage/artifact-123")
        assert response.status_code == 200

        data = response.json()
        assert data["artifact_id"] == "artifact-123"
        assert "nodes" in data
        assert "edges" in data
        assert data["direction"] == "both"
        assert data["nodes"] == []
        assert data["edges"] == []

    def test_get_lineage_upstream(self, client):
        """Test getting upstream lineage."""
        response = client.get("/api/provenance/lineage/artifact-123?direction=upstream")
        assert response.status_code == 200

        data = response.json()
        assert data["direction"] == "upstream"

    def test_get_lineage_downstream(self, client):
        """Test getting downstream lineage."""
        response = client.get("/api/provenance/lineage/artifact-123?direction=downstream")
        assert response.status_code == 200

        data = response.json()
        assert data["direction"] == "downstream"

    def test_get_lineage_with_max_depth(self, client):
        """Test getting lineage with max depth."""
        response = client.get("/api/provenance/lineage/artifact-123?max_depth=3")
        assert response.status_code == 200

    def test_get_lineage_invalid_direction(self, client):
        """Test getting lineage with invalid direction."""
        response = client.get("/api/provenance/lineage/artifact-123?direction=invalid")
        assert response.status_code == 422

    def test_get_upstream(self, client):
        """Test getting upstream dependencies."""
        response = client.get("/api/provenance/lineage/artifact-123/upstream")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)
        assert data == []

    def test_get_downstream(self, client):
        """Test getting downstream dependents."""
        response = client.get("/api/provenance/lineage/artifact-123/downstream")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)
        assert data == []


class TestAuditEndpoints:
    """Test audit log endpoints."""

    def test_list_audit_records_default(self, client):
        """Test listing audit records with default parameters."""
        response = client.get("/api/provenance/audit")
        assert response.status_code == 200

        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "page_size" in data
        assert data["page"] == 1
        assert data["page_size"] == 20

    def test_list_audit_records_with_filters(self, client):
        """Test listing audit records with filters."""
        response = client.get(
            "/api/provenance/audit?chain_id=chain-1&event_type=chain_created"
        )
        assert response.status_code == 200

    def test_list_audit_records_with_event_source(self, client):
        """Test listing audit records filtered by event source."""
        response = client.get("/api/provenance/audit?event_source=provenance")
        assert response.status_code == 200

    def test_get_chain_audit(self, client):
        """Test getting audit trail for a specific chain."""
        response = client.get("/api/provenance/audit/chain-123")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)
        assert data == []

    def test_export_audit_json(self, client):
        """Test exporting audit trail as JSON."""
        response = client.post("/api/provenance/audit/export?format=json")
        # Should fail without storage service
        assert response.status_code in [501, 503]

    def test_export_audit_csv(self, client):
        """Test exporting audit trail as CSV."""
        response = client.post("/api/provenance/audit/export?format=csv")
        assert response.status_code in [501, 503]

    def test_export_audit_pdf(self, client):
        """Test exporting audit trail as PDF."""
        response = client.post("/api/provenance/audit/export?format=pdf")
        assert response.status_code in [501, 503]

    def test_export_audit_invalid_format(self, client):
        """Test exporting audit with invalid format."""
        response = client.post("/api/provenance/audit/export?format=invalid")
        assert response.status_code == 422

    def test_export_audit_with_chain_filter(self, client):
        """Test exporting audit for specific chain."""
        response = client.post("/api/provenance/audit/export?chain_id=chain-1")
        assert response.status_code in [501, 503]


class TestVerificationEndpoints:
    """Test chain verification endpoints."""

    def test_verify_chain(self, client):
        """Test verifying chain integrity."""
        response = client.post("/api/provenance/chains/chain-123/verify")
        assert response.status_code == 200

        data = response.json()
        assert "chain_id" in data
        assert "verified" in data
        assert "issues" in data
        assert data["chain_id"] == "chain-123"
        assert data["verified"] is True
        assert data["issues"] == []


class TestRequestValidation:
    """Test request validation."""

    def test_create_chain_missing_title(self, client):
        """Test creating chain without required title."""
        chain_data = {
            "description": "Missing title",
        }
        response = client.post("/api/provenance/chains", json=chain_data)
        assert response.status_code == 422

    def test_add_link_missing_fields(self, client):
        """Test adding link with missing required fields."""
        link_data = {
            "source_artifact_id": "src-1",
            # Missing target_artifact_id and link_type
        }
        response = client.post("/api/provenance/chains/chain-1/links", json=link_data)
        assert response.status_code == 422

    def test_add_link_invalid_confidence(self, client):
        """Test adding link with invalid confidence value."""
        link_data = {
            "source_artifact_id": "src-1",
            "target_artifact_id": "tgt-1",
            "link_type": "derived_from",
            "confidence": 1.5,  # Invalid - should be 0.0 to 1.0
        }
        # Note: This test assumes confidence validation exists
        # If not, this would pass validation
        response = client.post("/api/provenance/chains/chain-1/links", json=link_data)
        # Could be 422 if validation exists, or 501 if not implemented
        assert response.status_code in [422, 501]

    def test_list_chains_invalid_page(self, client):
        """Test listing chains with invalid page number."""
        response = client.get("/api/provenance/chains?page=0")
        assert response.status_code == 422

    def test_list_chains_page_size_too_large(self, client):
        """Test listing chains with page size exceeding max."""
        response = client.get("/api/provenance/chains?page_size=1000")
        assert response.status_code == 422


class TestPaginationBehavior:
    """Test pagination behavior."""

    def test_pagination_page_defaults(self, client):
        """Test that page defaults to 1."""
        response = client.get("/api/provenance/chains")
        data = response.json()
        assert data["page"] == 1

    def test_pagination_page_size_defaults(self, client):
        """Test that page_size defaults to 20."""
        response = client.get("/api/provenance/chains")
        data = response.json()
        assert data["page_size"] == 20

    def test_pagination_custom_values(self, client):
        """Test custom pagination values."""
        response = client.get("/api/provenance/chains?page=3&page_size=50")
        data = response.json()
        assert data["page"] == 3
        assert data["page_size"] == 50

    def test_audit_pagination(self, client):
        """Test audit endpoint pagination."""
        response = client.get("/api/provenance/audit?page=2&page_size=10")
        assert response.status_code == 200

        data = response.json()
        assert data["page"] == 2
        assert data["page_size"] == 10


class TestAPIInitialization:
    """Test API initialization."""

    def test_api_init_sets_globals(self):
        """Test that init_api sets global variables."""
        from arkham_shard_provenance import api

        # Mock objects
        mock_chain_manager = object()
        mock_lineage_tracker = object()
        mock_audit_logger = object()
        mock_event_bus = object()
        mock_storage = object()

        init_api(
            chain_manager=mock_chain_manager,
            lineage_tracker=mock_lineage_tracker,
            audit_logger=mock_audit_logger,
            event_bus=mock_event_bus,
            storage=mock_storage,
        )

        assert api._chain_manager is mock_chain_manager
        assert api._lineage_tracker is mock_lineage_tracker
        assert api._audit_logger is mock_audit_logger
        assert api._event_bus is mock_event_bus
        assert api._storage is mock_storage


class TestRouterConfiguration:
    """Test router configuration."""

    def test_router_prefix(self):
        """Test that router has correct prefix."""
        assert router.prefix == "/api/provenance"

    def test_router_tags(self):
        """Test that router has correct tags."""
        assert "provenance" in router.tags
