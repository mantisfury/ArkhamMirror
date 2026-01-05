"""
Dashboard Shard - System monitoring and controls.
"""

from typing import Dict, Any, List, Optional
import logging

from arkham_frame.shard_interface import ArkhamShard

logger = logging.getLogger(__name__)


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
        super().__init__()  # Auto-loads manifest from shard.yaml

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

    def get_routes(self):
        """Return the FastAPI router for this shard."""
        from .api import router
        return router

    # === Service Health ===

    async def get_service_health(self) -> Dict[str, Any]:
        """Get health status of all services."""
        health = {
            "is_docker": self.frame.config.is_docker,
            "database": {"available": False, "info": None},
            "vectors": {"available": False, "info": None},
            "llm": {"available": False, "info": None},
            "workers": {"available": False, "info": None},
            "events": {"available": True, "info": None},
        }

        # Database
        if self.frame.db:
            health["database"]["available"] = True
            # Only expose host/database, never credentials
            db_url = self.frame.config.database_url
            safe_url = db_url.split("@")[-1] if "@" in db_url else "configured"
            health["database"]["info"] = {
                "url": safe_url,
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
        config = {
            "endpoint": self.frame.config.llm_endpoint,
            "model": self.frame.config.get("llm.model", "local-model"),
            "available": self.frame.llm.is_available() if self.frame.llm else False,
            "api_key_configured": False,
            "api_key_source": None,
            "is_docker": self.frame.config.is_docker,
            "default_lm_studio_endpoint": self.frame.config.get_local_llm_default(),
            "default_ollama_endpoint": self.frame.config.get_local_ollama_default(),
        }

        # Add API key status (never expose the actual key)
        if self.frame.llm:
            config["api_key_configured"] = self.frame.llm.has_api_key()
            config["api_key_source"] = self.frame.llm.get_api_key_source()
            # OpenRouter fallback routing info
            config["is_openrouter"] = self.frame.llm.is_openrouter()
            config["fallback_routing_enabled"] = self.frame.llm.is_fallback_routing_enabled()
            config["fallback_models"] = self.frame.llm.get_fallback_models()

        return config

    async def update_llm_config(
        self,
        endpoint: Optional[str] = None,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update LLM configuration and persist to Settings shard."""
        if endpoint:
            self.frame.config.set("llm_endpoint", endpoint)
        if model:
            self.frame.config.set("llm.model", model)

        # Persist to Settings shard for survival across restarts
        await self._persist_llm_settings(endpoint, model)

        # Reinitialize LLM service
        if self.frame.llm:
            await self.frame.llm.shutdown()
            await self.frame.llm.initialize()

        return await self.get_llm_config()

    async def _persist_llm_settings(
        self,
        endpoint: Optional[str] = None,
        model: Optional[str] = None,
    ) -> None:
        """Persist LLM settings to the Settings shard database."""
        try:
            # Get Settings shard from app state
            settings_shard = getattr(self.frame.app.state, "settings_shard", None)
            if not settings_shard:
                logger.warning("Settings shard not available - LLM config will not persist")
                return

            # Update settings in database
            if endpoint is not None:
                await settings_shard.update_setting("llm.endpoint", endpoint, validate=False)
                logger.info(f"Persisted llm.endpoint to Settings: {endpoint}")

            if model is not None:
                await settings_shard.update_setting("llm.model", model, validate=False)
                logger.info(f"Persisted llm.model to Settings: {model}")

            # Emit event for other services to react
            if self.frame.events:
                await self.frame.events.emit(
                    "settings.llm.updated",
                    {"endpoint": endpoint, "model": model},
                    source="dashboard"
                )

        except Exception as e:
            logger.error(f"Failed to persist LLM settings: {e}")

    async def reset_llm_config(self) -> Dict[str, Any]:
        """Reset LLM configuration to defaults."""
        # Use environment-aware default endpoint
        default_endpoint = self.frame.config.get_local_llm_default()
        default_model = "local-model"

        self.frame.config.set("llm_endpoint", default_endpoint)
        self.frame.config.set("llm.model", default_model)

        # Persist reset values (empty string = use env var defaults)
        await self._persist_llm_settings("", "")

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

    async def set_fallback_models(
        self,
        models: list[str],
        enabled: bool = True,
    ) -> Dict[str, Any]:
        """
        Configure OpenRouter fallback models.
        
        Args:
            models: List of model IDs in priority order
            enabled: Enable or disable fallback routing
        """
        if not self.frame.llm:
            return {"success": False, "error": "LLM service not initialized"}
        
        if not self.frame.llm.is_openrouter():
            return {
                "success": False, 
                "error": "Fallback routing is only available with OpenRouter"
            }
        
        # Set fallback models
        self.frame.llm.set_fallback_models(models)
        self.frame.llm.enable_fallback_routing(enabled)
        
        return {
            "success": True,
            "fallback_models": self.frame.llm.get_fallback_models(),
            "fallback_routing_enabled": self.frame.llm.is_fallback_routing_enabled(),
        }

    async def get_fallback_models(self) -> Dict[str, Any]:
        """Get current fallback model configuration."""
        if not self.frame.llm:
            return {
                "is_openrouter": False,
                "fallback_models": [],
                "fallback_routing_enabled": False,
            }
        
        return {
            "is_openrouter": self.frame.llm.is_openrouter(),
            "fallback_models": self.frame.llm.get_fallback_models(),
            "fallback_routing_enabled": self.frame.llm.is_fallback_routing_enabled(),
        }

    # === Database Controls ===

    async def get_database_info(self) -> Dict[str, Any]:
        """Get database information."""
        if not self.frame.db:
            return {"available": False}

        connected = await self.frame.db.is_connected()
        schemas = await self.frame.db.list_schemas() if connected else []

        return {
            "available": connected,
            "url": self.frame.config.database_url.split("@")[-1] if connected else None,
            "schemas": schemas,
        }

    async def get_database_stats(self) -> Dict[str, Any]:
        """Get detailed database statistics."""
        if not self.frame.db:
            return {"connected": False}
        return await self.frame.db.get_stats()

    async def get_table_info(self, schema: str) -> List[Dict[str, Any]]:
        """Get table information for a schema."""
        if not self.frame.db:
            return []
        return await self.frame.db.get_table_info(schema)

    async def run_migrations(self) -> Dict[str, Any]:
        """Run database migrations."""
        # TODO: Integrate with Alembic when available
        return {"success": True, "message": "Migrations are managed by individual shards on startup"}

    async def reset_database(self, confirm: bool = False) -> Dict[str, Any]:
        """Reset database (dangerous!)."""
        if not confirm:
            return {"success": False, "error": "Confirmation required"}

        if not self.frame.db:
            return {"success": False, "error": "Database not available"}

        return await self.frame.db.reset_database()

    async def vacuum_database(self) -> Dict[str, Any]:
        """Run VACUUM ANALYZE on database."""
        if not self.frame.db:
            return {"success": False, "error": "Database not available"}

        return await self.frame.db.vacuum_analyze()

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

        return await self.frame.workers.scale(queue, count)

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

    async def stop_all_workers(self, pool: Optional[str] = None) -> Dict[str, Any]:
        """Stop all workers, optionally filtered by pool."""
        if not self.frame.workers:
            return {"success": False, "error": "Worker service not available"}
        return await self.frame.workers.stop_all_workers(pool)

    async def get_pool_info(self) -> List[Dict[str, Any]]:
        """Get information about all worker pools."""
        if not self.frame.workers:
            return []
        return self.frame.workers.get_pool_info()

    async def get_jobs(
        self,
        pool: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get jobs with optional filtering."""
        if not self.frame.workers:
            return []
        return await self.frame.workers.get_jobs(pool=pool, status=status, limit=limit)

    async def clear_queue(self, pool: str, status: Optional[str] = None) -> Dict[str, Any]:
        """Clear jobs from a queue."""
        if not self.frame.workers:
            return {"success": False, "error": "Worker service not available"}
        return await self.frame.workers.clear_queue(pool, status)

    async def retry_failed_jobs(
        self,
        pool: str,
        job_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Retry failed jobs."""
        if not self.frame.workers:
            return {"success": False, "error": "Worker service not available"}
        return await self.frame.workers.retry_failed_jobs(pool, job_ids)

    async def cancel_job(self, job_id: str) -> Dict[str, Any]:
        """Cancel a job."""
        if not self.frame.workers:
            return {"success": False, "error": "Worker service not available"}
        return await self.frame.workers.cancel_job(job_id)

    # === Events ===

    async def get_events(
        self,
        limit: int = 50,
        offset: int = 0,
        source: Optional[str] = None,
        event_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get recent events with optional filtering."""
        if not self.frame.events:
            return []

        events = self.frame.events.get_events(
            limit=limit,
            offset=offset,
            source=source,
            event_type=event_type,
        )
        return [
            {
                "event_type": e.event_type,
                "payload": e.payload,
                "source": e.source,
                "timestamp": e.timestamp.isoformat(),
                "sequence": e.sequence,
            }
            for e in events
        ]

    async def get_event_count(
        self,
        source: Optional[str] = None,
        event_type: Optional[str] = None,
    ) -> int:
        """Get count of events matching filters."""
        if not self.frame.events:
            return 0
        return self.frame.events.get_event_count(source=source, event_type=event_type)

    async def get_event_types(self) -> List[str]:
        """Get list of unique event types."""
        if not self.frame.events:
            return []
        return self.frame.events.get_event_types()

    async def get_event_sources(self) -> List[str]:
        """Get list of unique event sources."""
        if not self.frame.events:
            return []
        return self.frame.events.get_event_sources()

    async def clear_events(self) -> Dict[str, Any]:
        """Clear event history."""
        if not self.frame.events:
            return {"success": False, "error": "Event service not available"}
        count = self.frame.events.clear_history()
        return {"success": True, "cleared": count}

    async def get_errors(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent error events."""
        if not self.frame.events:
            return []

        # Use wildcard pattern to match error events
        events = self.frame.events.get_events(limit=limit * 2)
        errors = [
            {
                "event_type": e.event_type,
                "payload": e.payload,
                "source": e.source,
                "timestamp": e.timestamp.isoformat(),
                "sequence": e.sequence,
            }
            for e in events
            if "error" in e.event_type.lower() or "fail" in e.event_type.lower()
        ]
        return errors[:limit]
