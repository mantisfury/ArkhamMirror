"""
Integration tests for shard discovery, loading, and manifest compliance.

Tests:
- Shard discovery via entry_points
- Manifest v5 schema compliance
- Shard lifecycle (initialize, shutdown)
- API route mounting

Run with:
    cd packages/arkham-frame
    pytest tests/test_shard_loading.py -v
"""

import pytest
import pytest_asyncio
import yaml
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from unittest.mock import Mock, AsyncMock, patch, MagicMock

# Import shard interface components
from arkham_frame.shard_interface import (
    ArkhamShard,
    ShardManifest,
    NavigationConfig,
    DependencyConfig,
    EventConfig,
    StateConfig,
    UIConfig,
    load_manifest_from_yaml,
)


# =============================================================================
# Test Data
# =============================================================================

# All shards that should exist
EXPECTED_SHARDS = [
    "dashboard",
    "ingest",
    "search",
    "parse",
    "embed",
    "ocr",
    "contradictions",
    "anomalies",
    "graph",
    "timeline",
    "ach",
]

# Valid navigation categories
VALID_CATEGORIES = ["System", "Data", "Search", "Analysis", "Visualize", "Export"]

# Valid state strategies
VALID_STATE_STRATEGIES = ["url", "local", "session", "none"]


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def packages_dir() -> Path:
    """Get the packages directory."""
    # Navigate from tests/ to packages/
    return Path(__file__).parent.parent.parent.parent


@pytest.fixture
def shard_yaml_paths(packages_dir: Path) -> Dict[str, Path]:
    """Get paths to all shard.yaml files."""
    paths = {}
    for shard_name in EXPECTED_SHARDS:
        shard_dir = packages_dir / f"arkham-shard-{shard_name}"
        yaml_path = shard_dir / "shard.yaml"
        if yaml_path.exists():
            paths[shard_name] = yaml_path
    return paths


@pytest.fixture
def sample_manifest_yaml() -> str:
    """Sample valid v5 manifest for testing."""
    return """
name: test-shard
version: 0.1.0
description: A test shard for unit testing
entry_point: arkham_shard_test:TestShard
api_prefix: /api/test
requires_frame: ">=0.1.0"

navigation:
  category: Analysis
  order: 50
  icon: TestIcon
  label: Test Shard
  route: /test
  badge_endpoint: /api/test/count
  badge_type: count
  sub_routes:
    - id: sub1
      label: Sub Route 1
      route: /test/sub1
      icon: SubIcon

dependencies:
  services:
    - database
    - events
  optional:
    - llm
  shards: []

capabilities:
  - test_feature_1
  - test_feature_2

events:
  publishes:
    - test.created
    - test.updated
  subscribes:
    - document.processed

state:
  strategy: url
  url_params:
    - testId
    - filter

ui:
  has_custom_ui: true
"""


# =============================================================================
# Test 1: Manifest Loading
# =============================================================================

class TestManifestLoading:
    """Tests for loading and parsing shard.yaml files."""

    def test_load_manifest_from_yaml_string(self, tmp_path, sample_manifest_yaml):
        """Test loading a manifest from a YAML file."""
        # Write sample manifest to temp file
        yaml_path = tmp_path / "shard.yaml"
        yaml_path.write_text(sample_manifest_yaml)

        # Load manifest
        manifest = load_manifest_from_yaml(yaml_path)

        # Verify basic fields
        assert manifest.name == "test-shard"
        assert manifest.version == "0.1.0"
        assert manifest.description == "A test shard for unit testing"
        assert manifest.entry_point == "arkham_shard_test:TestShard"
        assert manifest.api_prefix == "/api/test"
        assert manifest.requires_frame == ">=0.1.0"

    def test_load_manifest_navigation(self, tmp_path, sample_manifest_yaml):
        """Test navigation config parsing."""
        yaml_path = tmp_path / "shard.yaml"
        yaml_path.write_text(sample_manifest_yaml)
        manifest = load_manifest_from_yaml(yaml_path)

        assert manifest.navigation is not None
        assert manifest.navigation.category == "Analysis"
        assert manifest.navigation.order == 50
        assert manifest.navigation.icon == "TestIcon"
        assert manifest.navigation.label == "Test Shard"
        assert manifest.navigation.route == "/test"
        assert manifest.navigation.badge_endpoint == "/api/test/count"
        assert manifest.navigation.badge_type == "count"

        # Sub-routes
        assert len(manifest.navigation.sub_routes) == 1
        sub = manifest.navigation.sub_routes[0]
        assert sub.id == "sub1"
        assert sub.label == "Sub Route 1"
        assert sub.route == "/test/sub1"

    def test_load_manifest_dependencies(self, tmp_path, sample_manifest_yaml):
        """Test dependencies config parsing."""
        yaml_path = tmp_path / "shard.yaml"
        yaml_path.write_text(sample_manifest_yaml)
        manifest = load_manifest_from_yaml(yaml_path)

        assert manifest.dependencies is not None
        assert "database" in manifest.dependencies.services
        assert "events" in manifest.dependencies.services
        assert "llm" in manifest.dependencies.optional
        assert manifest.dependencies.shards == []

    def test_load_manifest_events(self, tmp_path, sample_manifest_yaml):
        """Test events config parsing."""
        yaml_path = tmp_path / "shard.yaml"
        yaml_path.write_text(sample_manifest_yaml)
        manifest = load_manifest_from_yaml(yaml_path)

        assert manifest.events is not None
        assert "test.created" in manifest.events.publishes
        assert "test.updated" in manifest.events.publishes
        assert "document.processed" in manifest.events.subscribes

    def test_load_manifest_state(self, tmp_path, sample_manifest_yaml):
        """Test state config parsing."""
        yaml_path = tmp_path / "shard.yaml"
        yaml_path.write_text(sample_manifest_yaml)
        manifest = load_manifest_from_yaml(yaml_path)

        assert manifest.state is not None
        assert manifest.state.strategy == "url"
        assert "testId" in manifest.state.url_params
        assert "filter" in manifest.state.url_params

    def test_load_manifest_ui(self, tmp_path, sample_manifest_yaml):
        """Test UI config parsing."""
        yaml_path = tmp_path / "shard.yaml"
        yaml_path.write_text(sample_manifest_yaml)
        manifest = load_manifest_from_yaml(yaml_path)

        assert manifest.ui is not None
        assert manifest.ui.has_custom_ui is True

    def test_load_manifest_capabilities(self, tmp_path, sample_manifest_yaml):
        """Test capabilities list parsing."""
        yaml_path = tmp_path / "shard.yaml"
        yaml_path.write_text(sample_manifest_yaml)
        manifest = load_manifest_from_yaml(yaml_path)

        assert len(manifest.capabilities) == 2
        assert "test_feature_1" in manifest.capabilities
        assert "test_feature_2" in manifest.capabilities

    def test_manifest_to_dict(self, tmp_path, sample_manifest_yaml):
        """Test manifest serialization to dictionary."""
        yaml_path = tmp_path / "shard.yaml"
        yaml_path.write_text(sample_manifest_yaml)
        manifest = load_manifest_from_yaml(yaml_path)

        data = manifest.to_dict()

        assert data["name"] == "test-shard"
        assert data["version"] == "0.1.0"
        assert "navigation" in data
        assert data["navigation"]["category"] == "Analysis"
        assert "dependencies" in data
        assert "events" in data
        assert "state" in data
        assert "ui" in data


# =============================================================================
# Test 2: V5 Manifest Compliance
# =============================================================================

class TestManifestCompliance:
    """Tests that all shard.yaml files comply with v5 schema."""

    def test_all_expected_shards_have_manifests(self, shard_yaml_paths):
        """Every expected shard should have a shard.yaml file."""
        for shard_name in EXPECTED_SHARDS:
            assert shard_name in shard_yaml_paths, f"Missing shard.yaml for {shard_name}"

    @pytest.mark.parametrize("shard_name", EXPECTED_SHARDS)
    def test_manifest_has_required_fields(self, shard_yaml_paths, shard_name):
        """Each manifest must have required fields."""
        if shard_name not in shard_yaml_paths:
            pytest.skip(f"Shard {shard_name} manifest not found")

        manifest = load_manifest_from_yaml(shard_yaml_paths[shard_name])

        assert manifest.name, f"{shard_name}: name is required"
        assert manifest.version, f"{shard_name}: version is required"
        assert manifest.entry_point, f"{shard_name}: entry_point is required"
        assert manifest.api_prefix, f"{shard_name}: api_prefix is required"

    @pytest.mark.parametrize("shard_name", EXPECTED_SHARDS)
    def test_manifest_has_navigation(self, shard_yaml_paths, shard_name):
        """Each v5 manifest should have navigation config."""
        if shard_name not in shard_yaml_paths:
            pytest.skip(f"Shard {shard_name} manifest not found")

        manifest = load_manifest_from_yaml(shard_yaml_paths[shard_name])

        assert manifest.navigation is not None, f"{shard_name}: navigation is required for v5"
        assert manifest.navigation.category in VALID_CATEGORIES, \
            f"{shard_name}: invalid category '{manifest.navigation.category}'"
        assert isinstance(manifest.navigation.order, int), \
            f"{shard_name}: order must be integer"
        assert manifest.navigation.icon, f"{shard_name}: icon is required"
        assert manifest.navigation.label, f"{shard_name}: label is required"
        assert manifest.navigation.route, f"{shard_name}: route is required"

    @pytest.mark.parametrize("shard_name", EXPECTED_SHARDS)
    def test_manifest_has_dependencies(self, shard_yaml_paths, shard_name):
        """Each manifest should have dependencies config."""
        if shard_name not in shard_yaml_paths:
            pytest.skip(f"Shard {shard_name} manifest not found")

        manifest = load_manifest_from_yaml(shard_yaml_paths[shard_name])

        # Dependencies are optional but if present should have correct structure
        if manifest.dependencies:
            assert isinstance(manifest.dependencies.services, list), \
                f"{shard_name}: services must be a list"
            assert isinstance(manifest.dependencies.optional, list), \
                f"{shard_name}: optional must be a list"
            # Shards should NOT depend on other shards
            assert manifest.dependencies.shards == [], \
                f"{shard_name}: shards dependency list must be empty (no shard dependencies allowed)"

    @pytest.mark.parametrize("shard_name", EXPECTED_SHARDS)
    def test_manifest_state_strategy_valid(self, shard_yaml_paths, shard_name):
        """State strategy must be valid if present."""
        if shard_name not in shard_yaml_paths:
            pytest.skip(f"Shard {shard_name} manifest not found")

        manifest = load_manifest_from_yaml(shard_yaml_paths[shard_name])

        if manifest.state:
            assert manifest.state.strategy in VALID_STATE_STRATEGIES, \
                f"{shard_name}: invalid state strategy '{manifest.state.strategy}'"

    @pytest.mark.parametrize("shard_name", EXPECTED_SHARDS)
    def test_manifest_api_prefix_format(self, shard_yaml_paths, shard_name):
        """API prefix should follow /api/{name} pattern."""
        if shard_name not in shard_yaml_paths:
            pytest.skip(f"Shard {shard_name} manifest not found")

        manifest = load_manifest_from_yaml(shard_yaml_paths[shard_name])

        assert manifest.api_prefix.startswith("/api/"), \
            f"{shard_name}: api_prefix should start with /api/"

    @pytest.mark.parametrize("shard_name", EXPECTED_SHARDS)
    def test_manifest_entry_point_format(self, shard_yaml_paths, shard_name):
        """Entry point should follow module:Class pattern."""
        if shard_name not in shard_yaml_paths:
            pytest.skip(f"Shard {shard_name} manifest not found")

        manifest = load_manifest_from_yaml(shard_yaml_paths[shard_name])

        assert ":" in manifest.entry_point, \
            f"{shard_name}: entry_point should be 'module:ClassName' format"


# =============================================================================
# Test 3: Shard Base Class
# =============================================================================

class TestShardBaseClass:
    """Tests for the ArkhamShard abstract base class."""

    def test_shard_requires_initialize(self):
        """Shard subclasses must implement initialize."""
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            class IncompleteShardNoInit(ArkhamShard):
                async def shutdown(self):
                    pass

            IncompleteShardNoInit()

    def test_shard_requires_shutdown(self):
        """Shard subclasses must implement shutdown."""
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            class IncompleteShardNoShutdown(ArkhamShard):
                async def initialize(self, frame):
                    pass

            IncompleteShardNoShutdown()

    def test_complete_shard_instantiates(self):
        """A properly implemented shard can be instantiated."""
        class CompleteShard(ArkhamShard):
            name = "complete"
            version = "1.0.0"
            description = "A complete shard"

            async def initialize(self, frame):
                self.frame = frame

            async def shutdown(self):
                pass

        shard = CompleteShard()
        assert shard.name == "complete"
        assert shard.version == "1.0.0"
        assert shard.frame is None  # Not initialized yet

    def test_shard_has_fallback_manifest(self):
        """Shard creates minimal manifest from class attributes if no yaml."""
        class MinimalShard(ArkhamShard):
            name = "minimal"
            version = "0.5.0"
            description = "Minimal test shard"

            async def initialize(self, frame):
                pass

            async def shutdown(self):
                pass

        shard = MinimalShard()
        assert shard.manifest is not None
        assert shard.manifest.name == "minimal"
        assert shard.manifest.version == "0.5.0"

    def test_get_routes_returns_none_by_default(self):
        """Default get_routes() returns None."""
        class NoRoutesShard(ArkhamShard):
            name = "no-routes"
            version = "1.0.0"

            async def initialize(self, frame):
                pass

            async def shutdown(self):
                pass

        shard = NoRoutesShard()
        assert shard.get_routes() is None
        # Backwards compatibility alias
        assert shard.get_api_router() is None


# =============================================================================
# Test 4: Shard Lifecycle
# =============================================================================

class TestShardLifecycle:
    """Tests for shard initialization and shutdown."""

    @pytest.mark.asyncio
    async def test_shard_initialize_receives_frame(self):
        """Shard.initialize() receives frame reference."""
        class TrackingInitShard(ArkhamShard):
            name = "tracking"
            version = "1.0.0"
            init_called = False
            received_frame = None

            async def initialize(self, frame):
                self.init_called = True
                self.received_frame = frame
                self.frame = frame

            async def shutdown(self):
                pass

        mock_frame = Mock()
        mock_frame.get_service = Mock(return_value=None)

        shard = TrackingInitShard()
        await shard.initialize(mock_frame)

        assert shard.init_called is True
        assert shard.received_frame is mock_frame
        assert shard.frame is mock_frame

    @pytest.mark.asyncio
    async def test_shard_shutdown_called(self):
        """Shard.shutdown() is properly called."""
        class TrackingShutdownShard(ArkhamShard):
            name = "tracking-shutdown"
            version = "1.0.0"
            shutdown_called = False

            async def initialize(self, frame):
                self.frame = frame

            async def shutdown(self):
                self.shutdown_called = True

        mock_frame = Mock()
        shard = TrackingShutdownShard()
        await shard.initialize(mock_frame)
        await shard.shutdown()

        assert shard.shutdown_called is True

    @pytest.mark.asyncio
    async def test_shard_can_register_workers(self):
        """Shard can register workers during initialize."""
        class WorkerRegisteringShard(ArkhamShard):
            name = "worker-registering"
            version = "1.0.0"
            registered_worker = None

            async def initialize(self, frame):
                self.frame = frame
                worker_service = frame.get_service("workers")
                if worker_service:
                    # Simulate worker registration
                    self.registered_worker = "test-worker"

            async def shutdown(self):
                pass

        mock_worker_service = Mock()
        mock_worker_service.register_worker = Mock()

        mock_frame = Mock()
        mock_frame.get_service = Mock(return_value=mock_worker_service)

        shard = WorkerRegisteringShard()
        await shard.initialize(mock_frame)

        mock_frame.get_service.assert_called_with("workers")
        assert shard.registered_worker == "test-worker"

    @pytest.mark.asyncio
    async def test_shard_can_subscribe_to_events(self):
        """Shard can subscribe to events during initialize."""
        class EventSubscribingShard(ArkhamShard):
            name = "event-subscribing"
            version = "1.0.0"
            subscribed_events = []

            async def initialize(self, frame):
                self.frame = frame
                events = frame.get_service("events")
                if events:
                    await events.subscribe("document.processed", self.handle_document)
                    self.subscribed_events.append("document.processed")

            async def handle_document(self, payload):
                pass

            async def shutdown(self):
                pass

        mock_events = AsyncMock()
        mock_frame = Mock()
        mock_frame.get_service = Mock(return_value=mock_events)

        shard = EventSubscribingShard()
        await shard.initialize(mock_frame)

        mock_events.subscribe.assert_called_once()
        assert "document.processed" in shard.subscribed_events


# =============================================================================
# Test 5: API Route Integration
# =============================================================================

class TestAPIRouteIntegration:
    """Tests for shard API route mounting."""

    def test_shard_with_custom_routes(self):
        """Shard can provide custom FastAPI router."""
        from fastapi import APIRouter

        class RoutedShard(ArkhamShard):
            name = "routed"
            version = "1.0.0"

            async def initialize(self, frame):
                self.frame = frame

            async def shutdown(self):
                pass

            def get_routes(self):
                router = APIRouter()

                @router.get("/test")
                async def test_endpoint():
                    return {"status": "ok"}

                return router

        shard = RoutedShard()
        router = shard.get_routes()

        assert router is not None
        # Check that router has our route
        routes = [route.path for route in router.routes]
        assert "/test" in routes


# =============================================================================
# Test 6: Shard Discovery (Mocked Entry Points)
# =============================================================================

class TestShardDiscovery:
    """Tests for shard discovery via entry_points."""

    def test_entry_point_format_validation(self):
        """Entry points should follow arkham.shards group pattern."""
        # This tests the expected format, not actual discovery
        expected_format = {
            "dashboard": "arkham_shard_dashboard:DashboardShard",
            "ingest": "arkham_shard_ingest:IngestShard",
            "search": "arkham_shard_search:SearchShard",
            "parse": "arkham_shard_parse:ParseShard",
            "embed": "arkham_shard_embed:EmbedShard",
            "ocr": "arkham_shard_ocr:OCRShard",
            "contradictions": "arkham_shard_contradictions:ContradictionsShard",
            "anomalies": "arkham_shard_anomalies:AnomaliesShard",
            "graph": "arkham_shard_graph:GraphShard",
            "timeline": "arkham_shard_timeline:TimelineShard",
            "ach": "arkham_shard_ach:ACHShard",
        }

        for shard_name, entry_point in expected_format.items():
            module, classname = entry_point.split(":")
            assert module.startswith("arkham_shard_"), \
                f"{shard_name}: module should start with arkham_shard_"
            assert classname.endswith("Shard"), \
                f"{shard_name}: class should end with Shard"

    @patch("importlib.metadata.entry_points")
    def test_discover_shards_via_entry_points(self, mock_entry_points):
        """Test shard discovery mechanism (mocked)."""
        # Create mock entry points
        mock_ep1 = Mock()
        mock_ep1.name = "dashboard"
        mock_ep1.value = "arkham_shard_dashboard:DashboardShard"

        mock_ep2 = Mock()
        mock_ep2.name = "search"
        mock_ep2.value = "arkham_shard_search:SearchShard"

        # Mock the entry_points call
        mock_entry_points.return_value = {"arkham.shards": [mock_ep1, mock_ep2]}

        from importlib.metadata import entry_points
        eps = entry_points()

        if "arkham.shards" in eps:
            shard_eps = eps["arkham.shards"]
            names = [ep.name for ep in shard_eps]
            assert "dashboard" in names
            assert "search" in names


# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
