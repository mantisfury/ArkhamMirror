"""Tests for settings shard API endpoints."""

import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI
from unittest.mock import MagicMock

from arkham_shard_settings.api import router, init_api


@pytest.fixture
def mock_services():
    """Create mock services for API testing."""
    return {
        "db": MagicMock(),
        "event_bus": MagicMock(),
        "storage": MagicMock(),
    }


@pytest.fixture
def app(mock_services):
    """Create a test FastAPI app with the router."""
    init_api(
        db=mock_services["db"],
        event_bus=mock_services["event_bus"],
        storage=mock_services["storage"],
    )

    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    """Create a test client."""
    return TestClient(app)


class TestHealthEndpoint:
    """Test health check endpoint."""

    def test_health_with_storage(self, client):
        """Test health endpoint with storage available."""
        response = client.get("/api/settings/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["shard"] == "settings"
        assert data["version"] == "0.1.0"
        assert data["storage_available"] is True

    def test_health_without_storage(self):
        """Test health endpoint without storage."""
        init_api(
            db=MagicMock(),
            event_bus=MagicMock(),
            storage=None,
        )

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        response = client.get("/api/settings/health")

        assert response.status_code == 200
        data = response.json()
        assert data["storage_available"] is False


class TestCountEndpoint:
    """Test count endpoint."""

    def test_get_modified_count(self, client):
        """Test get modified settings count."""
        response = client.get("/api/settings/count")

        assert response.status_code == 200
        data = response.json()
        assert "count" in data
        assert data["count"] == 0


class TestListSettingsEndpoint:
    """Test list settings endpoint."""

    def test_list_settings_default(self, client):
        """Test list settings with default params."""
        response = client.get("/api/settings/")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert data == []

    def test_list_settings_with_category(self, client):
        """Test list settings with category filter."""
        response = client.get("/api/settings/?category=appearance")
        assert response.status_code == 200

    def test_list_settings_with_search(self, client):
        """Test list settings with search."""
        response = client.get("/api/settings/?search=theme")
        assert response.status_code == 200

    def test_list_settings_modified_only(self, client):
        """Test list settings with modified_only filter."""
        response = client.get("/api/settings/?modified_only=true")
        assert response.status_code == 200


class TestGetSettingEndpoint:
    """Test get setting endpoint."""

    def test_get_setting_not_found(self, client):
        """Test get setting returns 404."""
        response = client.get("/api/settings/appearance.theme")

        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()

    def test_get_nested_setting_key(self, client):
        """Test get setting with nested key."""
        response = client.get("/api/settings/category/subcategory/setting")
        assert response.status_code == 404


class TestUpdateSettingEndpoint:
    """Test update setting endpoint."""

    def test_update_setting_not_found(self, client):
        """Test update setting returns 404."""
        response = client.put(
            "/api/settings/appearance.theme",
            json={"value": "dark"},
        )

        assert response.status_code == 404


class TestResetSettingEndpoint:
    """Test reset setting endpoint."""

    def test_reset_setting_not_found(self, client):
        """Test reset setting returns 404."""
        response = client.delete("/api/settings/appearance.theme")
        assert response.status_code == 404


class TestCategoryEndpoints:
    """Test category endpoints."""

    def test_get_category_settings(self, client):
        """Test get category settings."""
        response = client.get("/api/settings/category/appearance")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_update_category_settings(self, client):
        """Test bulk update category settings."""
        response = client.put(
            "/api/settings/category/appearance",
            json={"settings": {"theme": "dark", "font_size": 14}},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["category"] == "appearance"
        assert data["updated_count"] == 2


class TestProfileEndpoints:
    """Test profile endpoints."""

    def test_list_profiles_empty(self, client):
        """Test list profiles returns empty."""
        response = client.get("/api/settings/profiles")

        assert response.status_code == 200
        data = response.json()
        assert data == []

    def test_create_profile(self, client):
        """Test create profile."""
        response = client.post(
            "/api/settings/profiles",
            json={
                "name": "Test Profile",
                "description": "A test profile",
                "settings": {"theme": "dark"},
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test Profile"
        assert data["description"] == "A test profile"
        assert "id" in data

    def test_create_profile_minimal(self, client):
        """Test create profile with minimal data."""
        response = client.post(
            "/api/settings/profiles",
            json={"name": "Minimal"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Minimal"

    def test_create_profile_missing_name(self, client):
        """Test create profile fails without name."""
        response = client.post(
            "/api/settings/profiles",
            json={"description": "No name"},
        )

        assert response.status_code == 422

    def test_get_profile_not_found(self, client):
        """Test get profile returns 404."""
        response = client.get("/api/settings/profiles/nonexistent")
        assert response.status_code == 404

    def test_update_profile_not_found(self, client):
        """Test update profile returns 404."""
        response = client.put(
            "/api/settings/profiles/nonexistent",
            json={"name": "Updated"},
        )
        assert response.status_code == 404

    def test_delete_profile(self, client):
        """Test delete profile."""
        response = client.delete("/api/settings/profiles/profile-1")

        assert response.status_code == 200
        data = response.json()
        assert data["deleted"] is True
        assert data["profile_id"] == "profile-1"

    def test_apply_profile(self, client):
        """Test apply profile."""
        response = client.post("/api/settings/profiles/profile-1/apply")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["profile_id"] == "profile-1"


class TestShardSettingsEndpoints:
    """Test shard settings endpoints."""

    def test_list_shard_settings(self, client):
        """Test list shard settings."""
        response = client.get("/api/settings/shards")

        assert response.status_code == 200
        data = response.json()
        assert data == []

    def test_get_shard_settings_not_found(self, client):
        """Test get shard settings returns 404."""
        response = client.get("/api/settings/shards/nonexistent")
        assert response.status_code == 404

    def test_update_shard_settings_not_found(self, client):
        """Test update shard settings returns 404."""
        response = client.put(
            "/api/settings/shards/search",
            json={"settings": {"max_results": 100}},
        )
        assert response.status_code == 404

    def test_reset_shard_settings(self, client):
        """Test reset shard settings."""
        response = client.delete("/api/settings/shards/search")

        assert response.status_code == 200
        data = response.json()
        assert data["reset"] is True
        assert data["shard_name"] == "search"


class TestBackupEndpoints:
    """Test backup endpoints."""

    def test_list_backups_empty(self, client):
        """Test list backups returns empty."""
        response = client.get("/api/settings/backups")

        assert response.status_code == 200
        data = response.json()
        assert data == []

    def test_create_backup_with_storage(self, client):
        """Test create backup."""
        response = client.post(
            "/api/settings/backup",
            json={
                "name": "Test Backup",
                "description": "A test backup",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert "Test Backup" in data["name"]
        assert "id" in data

    def test_create_backup_without_storage(self):
        """Test create backup fails without storage."""
        init_api(
            db=MagicMock(),
            event_bus=MagicMock(),
            storage=None,
        )

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        response = client.post(
            "/api/settings/backup",
            json={"name": "Test"},
        )

        assert response.status_code == 503
        assert "Storage service not available" in response.json()["detail"]

    def test_get_backup_not_found(self, client):
        """Test get backup returns 404."""
        response = client.get("/api/settings/backups/nonexistent")
        assert response.status_code == 404

    def test_restore_backup(self, client):
        """Test restore backup."""
        response = client.post("/api/settings/restore/backup-1")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["backup_id"] == "backup-1"

    def test_delete_backup(self, client):
        """Test delete backup."""
        response = client.delete("/api/settings/backups/backup-1")

        assert response.status_code == 200
        data = response.json()
        assert data["deleted"] is True


class TestExportImportEndpoints:
    """Test export/import endpoints."""

    def test_export_settings(self, client):
        """Test export settings."""
        response = client.get("/api/settings/export")

        assert response.status_code == 200
        data = response.json()
        assert data["version"] == "1.0"
        assert "exported_at" in data
        assert "settings" in data

    def test_export_settings_with_profiles(self, client):
        """Test export settings including profiles."""
        response = client.get("/api/settings/export?include_profiles=true")

        assert response.status_code == 200
        data = response.json()
        assert "profiles" in data

    def test_export_settings_without_profiles(self, client):
        """Test export settings excluding profiles."""
        response = client.get("/api/settings/export?include_profiles=false")

        assert response.status_code == 200
        data = response.json()
        assert data["profiles"] is None

    def test_import_settings(self, client):
        """Test import settings."""
        response = client.post(
            "/api/settings/import",
            json={
                "version": "1.0",
                "settings": {"theme": "dark"},
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_import_settings_merge(self, client):
        """Test import settings with merge."""
        response = client.post(
            "/api/settings/import?merge=true",
            json={"settings": {}},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["merge"] is True


class TestValidationEndpoint:
    """Test validation endpoint."""

    def test_validate_setting(self, client):
        """Test validate setting."""
        response = client.post(
            "/api/settings/validate?key=theme",
            json="dark",
        )

        assert response.status_code == 200
        data = response.json()
        assert data["is_valid"] is True
        assert data["errors"] == []


class TestRequestValidation:
    """Test request validation."""

    def test_create_profile_empty_name(self, client):
        """Test create profile with empty name."""
        response = client.post(
            "/api/settings/profiles",
            json={"name": ""},
        )
        assert response.status_code == 422

    def test_update_category_missing_settings(self, client):
        """Test update category with invalid data."""
        response = client.put(
            "/api/settings/category/appearance",
            json={},
        )
        assert response.status_code == 422


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
