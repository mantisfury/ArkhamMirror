"""
Dashboard Shard - System monitoring and controls.
"""

from typing import Dict, Any, List, Optional
from pathlib import Path
import logging
import yaml

from arkham_frame.shard_interface import (
    ArkhamShard,
    ShardManifest,
    NavigationConfig,
    SubRoute,
    DependencyConfig,
    UIConfig,
)

logger = logging.getLogger(__name__)


def load_manifest_from_yaml(yaml_path: Path) -> ShardManifest:
    """Load and parse a shard.yaml file into a ShardManifest."""
    with open(yaml_path, "r") as f:
        data = yaml.safe_load(f)

    # Parse navigation config
    nav_data = data.get("navigation", {})
    navigation = None
    if nav_data:
        sub_routes = []
        for sr in nav_data.get("sub_routes", []):
            sub_routes.append(SubRoute(
                id=sr["id"],
                label=sr["label"],
                route=sr["route"],
                icon=sr.get("icon", "Circle"),
                badge_endpoint=sr.get("badge_endpoint"),
                badge_type=sr.get("badge_type"),
            ))

        navigation = NavigationConfig(
            category=nav_data.get("category", "System"),
            order=nav_data.get("order", 99),
            icon=nav_data.get("icon", "Circle"),
            label=nav_data.get("label", data.get("name", "Unknown")),
            route=nav_data.get("route", f"/{data.get('name', 'unknown')}"),
            badge_endpoint=nav_data.get("badge_endpoint"),
            badge_type=nav_data.get("badge_type"),
            sub_routes=sub_routes,
        )

    # Parse dependencies
    deps_data = data.get("dependencies", {})
    dependencies = None
    if deps_data:
        dependencies = DependencyConfig(
            services=deps_data.get("services", []),
            optional=deps_data.get("optional", []),
            shards=deps_data.get("shards", []),
        )

    # Parse UI config
    ui_data = data.get("ui", {})
    ui = None
    if ui_data:
        ui = UIConfig(
            has_custom_ui=ui_data.get("has_custom_ui", False),
        )

    return ShardManifest(
        name=data.get("name", "unknown"),
        version=data.get("version", "0.0.0"),
        description=data.get("description", ""),
        entry_point=data.get("entry_point", ""),
        api_prefix=data.get("api_prefix", ""),
        requires_frame=data.get("requires_frame", ">=0.1.0"),
        navigation=navigation,
        dependencies=dependencies,
        ui=ui,
    )


class DashboardShard(ArkhamShard):
    """
    Dashboard shard for system monitoring and configuration.

    Provides:
    - Service health monitoring
    - LLM configuration and testing
    - Database controls (info, migrate, reset, vacuum)
    - Worker management (scale, start, stop)
    - Event log viewing
    """

    name = "dashboard"
    version = "0.1.0"
    description = "System monitoring and controls"

    def __init__(self):
        self.frame = None
        self._manifest = None

    @property
    def manifest(self) -> ShardManifest:
        """Load shard manifest from shard.yaml."""
        if self._manifest is None:
            manifest_path = Path(__file__).parent.parent / "shard.yaml"
            if manifest_path.exists():
                try:
                    self._manifest = load_manifest_from_yaml(manifest_path)
                except Exception as e:
                    logger.warning(f"Failed to load shard.yaml: {e}")
                    self._manifest = self._fallback_manifest()
            else:
                self._manifest = self._fallback_manifest()
        return self._manifest

    def _fallback_manifest(self) -> ShardManifest:
        """Create a fallback manifest if shard.yaml is unavailable."""
        return ShardManifest(
            name="dashboard",
            version="0.1.0",
            description="Dashboard shard",
            entry_point="arkham_shard_dashboard.shard:DashboardShard",
            navigation=NavigationConfig(
                category="System",
                order=10,
                icon="LayoutDashboard",
                label="Dashboard",
                route="/dashboard",
            ),
        )

    async def initialize(self, frame) -> None:
        """Initialize the dashboard shard."""
        logger.info("Dashboard shard initializing...")

        self.frame = frame

        # Register API routes
        from .api import router
        # Routes will be registered by the Frame

        logger.info("Dashboard shard initialized")

    async def shutdown(self) -> None:
        """Shutdown the dashboard shard."""
        logger.info("Dashboard shard shutting down...")

    def get_api_router(self):
        """Return the FastAPI router for this shard."""
        from .api import router
        return router

    # === Service Health ===

    async def get_service_health(self) -> Dict[str, Any]:
        """Get health status of all services."""
        health = {
            "database": {"available": False, "info": None},
            "vectors": {"available": False, "info": None},
            "llm": {"available": False, "info": None},
            "workers": {"available": False, "info": None},
            "events": {"available": True, "info": None},
        }

        # Database
        if self.frame.db:
            health["database"]["available"] = True
            health["database"]["info"] = {
                "url": self.frame.config.database_url[:30] + "...",
            }

        # Vectors
        if self.frame.vectors:
            health["vectors"]["available"] = self.frame.vectors.is_available()

        # LLM
        if self.frame.llm:
            health["llm"]["available"] = self.frame.llm.is_available()
            if self.frame.llm.is_available():
                health["llm"]["info"] = {
                    "endpoint": self.frame.llm.get_endpoint(),
                }

        # Workers
        if self.frame.workers:
            health["workers"]["available"] = self.frame.workers.is_available()
            if self.frame.workers.is_available():
                health["workers"]["info"] = await self.frame.workers.get_queue_stats()

        return health

    # === LLM Configuration ===

    async def get_llm_config(self) -> Dict[str, Any]:
        """Get current LLM configuration."""
        return {
            "endpoint": self.frame.config.llm_endpoint,
            "model": self.frame.config.get("llm.model", "local-model"),
            "available": self.frame.llm.is_available() if self.frame.llm else False,
        }

    async def update_llm_config(
        self,
        endpoint: Optional[str] = None,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update LLM configuration."""
        if endpoint:
            self.frame.config.set("llm_endpoint", endpoint)
        if model:
            self.frame.config.set("llm.model", model)

        # Reinitialize LLM service
        if self.frame.llm:
            await self.frame.llm.shutdown()
            await self.frame.llm.initialize()

        return await self.get_llm_config()

    async def test_llm_connection(self) -> Dict[str, Any]:
        """Test LLM connection."""
        if not self.frame.llm:
            return {"success": False, "error": "LLM service not initialized"}

        try:
            response = await self.frame.llm.chat(
                messages=[{"role": "user", "content": "Say 'OK' if you can hear me."}],
                max_tokens=10,
            )
            return {"success": True, "response": response}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # === Database Controls ===

    async def get_database_info(self) -> Dict[str, Any]:
        """Get database information."""
        if not self.frame.db:
            return {"available": False}

        return {
            "available": True,
            "url": self.frame.config.database_url[:30] + "...",
            "schemas": [],  # Would query for schemas
        }

    async def run_migrations(self) -> Dict[str, Any]:
        """Run database migrations."""
        # In a real implementation, this would run Alembic migrations
        return {"success": True, "message": "Migrations would run here"}

    async def reset_database(self, confirm: bool = False) -> Dict[str, Any]:
        """Reset database (dangerous!)."""
        if not confirm:
            return {"success": False, "error": "Confirmation required"}

        # In a real implementation, this would drop and recreate tables
        return {"success": True, "message": "Database reset would happen here"}

    async def vacuum_database(self) -> Dict[str, Any]:
        """Run VACUUM ANALYZE on database."""
        # In a real implementation, this would run VACUUM
        return {"success": True, "message": "VACUUM would run here"}

    # === Worker Controls ===

    async def get_workers(self) -> List[Dict[str, Any]]:
        """Get list of active workers."""
        if not self.frame.workers:
            return []
        return await self.frame.workers.get_workers()

    async def get_queue_stats(self) -> List[Dict[str, Any]]:
        """Get queue statistics."""
        if not self.frame.workers:
            return []
        return await self.frame.workers.get_queue_stats()

    async def scale_workers(self, queue: str, count: int) -> Dict[str, Any]:
        """Scale workers for a queue."""
        if not self.frame.workers:
            return {"success": False, "error": "Worker service not available"}

        success = await self.frame.workers.scale(queue, count)
        return {"success": success, "queue": queue, "target_count": count}

    async def start_worker(self, queue: str) -> Dict[str, Any]:
        """Start a worker for a queue."""
        if not self.frame.workers:
            return {"success": False, "error": "Worker service not available"}
        return await self.frame.workers.start_worker(queue)

    async def stop_worker(self, worker_id: str) -> Dict[str, Any]:
        """Stop a worker."""
        if not self.frame.workers:
            return {"success": False, "error": "Worker service not available"}
        return await self.frame.workers.stop_worker(worker_id)

    # === Events ===

    async def get_events(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent events."""
        if not self.frame.events:
            return []

        events = self.frame.events.get_events(limit=limit)
        return [
            {
                "event_type": e.event_type,
                "payload": e.payload,
                "source": e.source,
                "timestamp": e.timestamp.isoformat(),
            }
            for e in events
        ]

    async def get_errors(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent error events."""
        if not self.frame.events:
            return []

        events = self.frame.events.get_events(limit=limit * 2)
        errors = [
            {
                "event_type": e.event_type,
                "payload": e.payload,
                "source": e.source,
                "timestamp": e.timestamp.isoformat(),
            }
            for e in events
            if "error" in e.event_type.lower() or "fail" in e.event_type.lower()
        ]
        return errors[:limit]
