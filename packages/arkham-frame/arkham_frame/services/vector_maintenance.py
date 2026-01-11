"""
VectorMaintenanceService - Scheduled maintenance for pgvector IVFFlat indexes.

Provides:
- Weekly scheduled reindexing (Sunday 3 AM by default)
- Nightly health checks (every night at 2 AM)
- Manual reindex trigger from Settings UI
- Collection statistics and health reporting
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class MaintenanceStatus(str, Enum):
    """Status of a maintenance operation."""
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ReindexResult:
    """Result of a reindex operation."""
    collection: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    status: MaintenanceStatus = MaintenanceStatus.RUNNING
    old_lists: int = 0
    new_lists: int = 0
    vector_count: int = 0
    duration_seconds: float = 0
    error: Optional[str] = None


@dataclass
class HealthCheckResult:
    """Result of a health check."""
    timestamp: datetime
    collections: List[Dict[str, Any]] = field(default_factory=list)
    total_vectors: int = 0
    total_collections: int = 0
    warnings: List[str] = field(default_factory=list)
    status: str = "healthy"


class VectorMaintenanceService:
    """
    Manages scheduled maintenance for pgvector IVFFlat indexes.

    IVFFlat indexes need periodic rebuilding as data distribution changes.
    This service handles:
    - Weekly scheduled reindex (configurable day/time)
    - Nightly health checks
    - On-demand manual reindex
    - Health and statistics reporting
    """

    def __init__(
        self,
        vectors_service=None,
        scheduler_service=None,
        db_pool=None,
        event_bus=None,
    ):
        """
        Initialize the vector maintenance service.

        Args:
            vectors_service: VectorService instance for reindex operations
            scheduler_service: SchedulerService for scheduled tasks
            db_pool: Database connection pool
            event_bus: EventBus for notifications
        """
        self._vectors = vectors_service
        self._scheduler = scheduler_service
        self._db_pool = db_pool
        self._event_bus = event_bus

        # Current operation state
        self._current_operation: Optional[str] = None
        self._reindex_in_progress = False
        self._last_reindex: Optional[datetime] = None
        self._last_health_check: Optional[datetime] = None

        # Results history
        self._reindex_history: List[ReindexResult] = []
        self._health_history: List[HealthCheckResult] = []

        # Configuration (can be updated via settings)
        self._config = {
            "reindex_day_of_week": 0,  # Sunday
            "reindex_hour": 3,  # 3 AM
            "health_check_hour": 2,  # 2 AM
            "max_history": 50,
        }

        self._initialized = False

    def set_vectors_service(self, vectors_service) -> None:
        """Set the vectors service."""
        self._vectors = vectors_service

    def set_scheduler_service(self, scheduler_service) -> None:
        """Set the scheduler service."""
        self._scheduler = scheduler_service

    def set_db_pool(self, db_pool) -> None:
        """Set the database pool."""
        self._db_pool = db_pool

    def set_event_bus(self, event_bus) -> None:
        """Set the event bus."""
        self._event_bus = event_bus

    async def initialize(self) -> None:
        """Initialize the service and schedule maintenance tasks."""
        if self._initialized:
            return

        # Load config from database if available
        await self._load_config()

        # Register maintenance functions with scheduler
        if self._scheduler:
            self._scheduler.register_job(
                "vector_weekly_reindex",
                self._scheduled_reindex
            )
            self._scheduler.register_job(
                "vector_nightly_check",
                self._scheduled_health_check
            )

            # Schedule weekly reindex
            self._scheduler.schedule_cron(
                name="Vector Weekly Reindex",
                func_name="vector_weekly_reindex",
                day_of_week=str(self._config["reindex_day_of_week"]),
                hour=str(self._config["reindex_hour"]),
                minute="0",
            )

            # Schedule nightly health check
            self._scheduler.schedule_cron(
                name="Vector Nightly Health Check",
                func_name="vector_nightly_check",
                hour=str(self._config["health_check_hour"]),
                minute="0",
            )

            logger.info(
                f"Scheduled weekly reindex (day={self._config['reindex_day_of_week']}, "
                f"hour={self._config['reindex_hour']}) and nightly health check "
                f"(hour={self._config['health_check_hour']})"
            )

        self._initialized = True
        logger.info("VectorMaintenanceService initialized")

    async def shutdown(self) -> None:
        """Shutdown the service."""
        self._initialized = False
        logger.info("VectorMaintenanceService shutdown")

    async def _load_config(self) -> None:
        """Load configuration from database."""
        if not self._db_pool:
            return

        try:
            async with self._db_pool.acquire() as conn:
                row = await conn.fetchrow("""
                    SELECT value FROM arkham_frame.maintenance_settings
                    WHERE key = 'vector_reindex'
                """)
                if row and row['value']:
                    import json
                    config = row['value'] if isinstance(row['value'], dict) else json.loads(row['value'])
                    if 'day_of_week' in config:
                        self._config['reindex_day_of_week'] = config['day_of_week']
                    if 'hour' in config:
                        self._config['reindex_hour'] = config['hour']
                    if config.get('last_run'):
                        self._last_reindex = datetime.fromisoformat(config['last_run'])
        except Exception as e:
            logger.warning(f"Failed to load maintenance config: {e}")

    async def _save_last_run(self, operation: str) -> None:
        """Save the last run timestamp to database."""
        if not self._db_pool:
            return

        try:
            async with self._db_pool.acquire() as conn:
                await conn.execute("""
                    UPDATE arkham_frame.maintenance_settings
                    SET value = jsonb_set(value, '{last_run}', to_jsonb(NOW()::text)),
                        updated_at = NOW()
                    WHERE key = $1
                """, operation)
        except Exception as e:
            logger.warning(f"Failed to save last run time: {e}")

    # =========================================
    # Scheduled Tasks
    # =========================================

    async def _scheduled_reindex(self) -> Dict[str, Any]:
        """Scheduled weekly reindex task."""
        logger.info("Starting scheduled weekly reindex")

        if self._event_bus:
            await self._event_bus.emit(
                "vector.maintenance.reindex.started",
                {"scheduled": True, "timestamp": datetime.utcnow().isoformat()},
                source="vector-maintenance"
            )

        result = await self.reindex_all()

        if self._event_bus:
            await self._event_bus.emit(
                "vector.maintenance.reindex.completed",
                {
                    "scheduled": True,
                    "success": result.get("success", False),
                    "collections": result.get("collections_reindexed", 0),
                },
                source="vector-maintenance"
            )

        await self._save_last_run("vector_reindex")
        return result

    async def _scheduled_health_check(self) -> Dict[str, Any]:
        """Scheduled nightly health check task."""
        logger.info("Starting scheduled nightly health check")

        result = await self.health_check()
        self._last_health_check = datetime.utcnow()

        if result.warnings and self._event_bus:
            await self._event_bus.emit(
                "vector.maintenance.health.warning",
                {
                    "warnings": result.warnings,
                    "timestamp": result.timestamp.isoformat(),
                },
                source="vector-maintenance"
            )

        return {
            "status": result.status,
            "total_vectors": result.total_vectors,
            "warnings": result.warnings,
        }

    # =========================================
    # Manual Operations
    # =========================================

    async def reindex_all(self) -> Dict[str, Any]:
        """
        Reindex all vector collections.

        Returns:
            Dict with success status and details
        """
        if self._reindex_in_progress:
            return {
                "success": False,
                "error": "Reindex already in progress",
            }

        if not self._vectors:
            return {
                "success": False,
                "error": "VectorService not available",
            }

        self._reindex_in_progress = True
        self._current_operation = "reindex_all"

        results = []
        errors = []

        try:
            # Get all collections
            collections = await self._vectors.list_collections()

            for coll in collections:
                coll_name = coll.name if hasattr(coll, 'name') else coll.get('name', str(coll))

                result = ReindexResult(
                    collection=coll_name,
                    started_at=datetime.utcnow(),
                )

                try:
                    # Get current state
                    info = await self._vectors.get_collection_info(coll_name)
                    result.old_lists = info.lists if hasattr(info, 'lists') else 0
                    result.vector_count = info.vector_count if hasattr(info, 'vector_count') else 0

                    # Perform reindex
                    reindex_result = await self._vectors.reindex_collection(coll_name)

                    result.completed_at = datetime.utcnow()
                    result.duration_seconds = (result.completed_at - result.started_at).total_seconds()
                    result.new_lists = reindex_result.get('new_lists', result.old_lists)
                    result.status = MaintenanceStatus.COMPLETED

                    logger.info(
                        f"Reindexed {coll_name}: "
                        f"lists {result.old_lists} -> {result.new_lists}, "
                        f"vectors={result.vector_count}, "
                        f"duration={result.duration_seconds:.1f}s"
                    )

                except Exception as e:
                    result.completed_at = datetime.utcnow()
                    result.duration_seconds = (result.completed_at - result.started_at).total_seconds()
                    result.status = MaintenanceStatus.FAILED
                    result.error = str(e)
                    errors.append(f"{coll_name}: {e}")
                    logger.error(f"Failed to reindex {coll_name}: {e}")

                results.append(result)

            # Update history
            self._reindex_history.extend(results)
            if len(self._reindex_history) > self._config["max_history"]:
                self._reindex_history = self._reindex_history[-self._config["max_history"]:]

            self._last_reindex = datetime.utcnow()

            return {
                "success": len(errors) == 0,
                "collections_reindexed": len([r for r in results if r.status == MaintenanceStatus.COMPLETED]),
                "collections_failed": len(errors),
                "errors": errors,
                "total_duration_seconds": sum(r.duration_seconds for r in results),
            }

        finally:
            self._reindex_in_progress = False
            self._current_operation = None

    async def reindex_collection(self, collection: str) -> Dict[str, Any]:
        """
        Reindex a specific collection.

        Args:
            collection: Collection name to reindex

        Returns:
            Dict with success status and details
        """
        if self._reindex_in_progress:
            return {
                "success": False,
                "error": "Reindex already in progress",
            }

        if not self._vectors:
            return {
                "success": False,
                "error": "VectorService not available",
            }

        self._reindex_in_progress = True
        self._current_operation = f"reindex_{collection}"

        result = ReindexResult(
            collection=collection,
            started_at=datetime.utcnow(),
        )

        try:
            # Get current state
            info = await self._vectors.get_collection_info(collection)
            result.old_lists = info.lists if hasattr(info, 'lists') else 0
            result.vector_count = info.vector_count if hasattr(info, 'vector_count') else 0

            # Perform reindex
            reindex_result = await self._vectors.reindex_collection(collection)

            result.completed_at = datetime.utcnow()
            result.duration_seconds = (result.completed_at - result.started_at).total_seconds()
            result.new_lists = reindex_result.get('new_lists', result.old_lists)
            result.status = MaintenanceStatus.COMPLETED

            # Add to history
            self._reindex_history.append(result)
            if len(self._reindex_history) > self._config["max_history"]:
                self._reindex_history.pop(0)

            logger.info(
                f"Reindexed {collection}: "
                f"lists {result.old_lists} -> {result.new_lists}, "
                f"vectors={result.vector_count}, "
                f"duration={result.duration_seconds:.1f}s"
            )

            return {
                "success": True,
                "collection": collection,
                "old_lists": result.old_lists,
                "new_lists": result.new_lists,
                "vector_count": result.vector_count,
                "duration_seconds": result.duration_seconds,
            }

        except Exception as e:
            result.completed_at = datetime.utcnow()
            result.duration_seconds = (result.completed_at - result.started_at).total_seconds()
            result.status = MaintenanceStatus.FAILED
            result.error = str(e)

            self._reindex_history.append(result)
            logger.error(f"Failed to reindex {collection}: {e}")

            return {
                "success": False,
                "collection": collection,
                "error": str(e),
            }

        finally:
            self._reindex_in_progress = False
            self._current_operation = None

    async def health_check(self) -> HealthCheckResult:
        """
        Perform a health check on all vector collections.

        Returns:
            HealthCheckResult with collection status and warnings
        """
        result = HealthCheckResult(timestamp=datetime.utcnow())

        if not self._vectors:
            result.status = "unavailable"
            result.warnings.append("VectorService not available")
            return result

        try:
            collections = await self._vectors.list_collections()
            result.total_collections = len(collections)

            for coll in collections:
                coll_name = coll.name if hasattr(coll, 'name') else coll.get('name', str(coll))

                try:
                    info = await self._vectors.get_collection_info(coll_name)

                    coll_data = {
                        "name": coll_name,
                        "vector_count": info.vector_count if hasattr(info, 'vector_count') else 0,
                        "vector_size": info.vector_size if hasattr(info, 'vector_size') else 0,
                        "index_type": info.index_type if hasattr(info, 'index_type') else "unknown",
                        "lists": info.lists if hasattr(info, 'lists') else 0,
                        "probes": info.probes if hasattr(info, 'probes') else 0,
                        "last_reindex": info.last_reindex.isoformat() if hasattr(info, 'last_reindex') and info.last_reindex else None,
                    }

                    result.collections.append(coll_data)
                    result.total_vectors += coll_data["vector_count"]

                    # Check for issues
                    if coll_data["vector_count"] > 0:
                        # Check if lists parameter is appropriate
                        optimal_lists = self._calculate_optimal_lists(coll_data["vector_count"])
                        current_lists = coll_data["lists"]

                        if current_lists > 0 and abs(current_lists - optimal_lists) / optimal_lists > 0.5:
                            result.warnings.append(
                                f"{coll_name}: lists={current_lists} may be suboptimal "
                                f"(suggested ~{optimal_lists} for {coll_data['vector_count']} vectors)"
                            )

                        # Check if reindex is overdue (no reindex in 14+ days)
                        if coll_data["last_reindex"]:
                            last_reindex = datetime.fromisoformat(coll_data["last_reindex"])
                            days_since = (datetime.utcnow() - last_reindex).days
                            if days_since > 14:
                                result.warnings.append(
                                    f"{coll_name}: last reindex was {days_since} days ago"
                                )

                except Exception as e:
                    result.warnings.append(f"{coll_name}: failed to get info - {e}")

            # Determine overall status
            if result.warnings:
                result.status = "warning"
            else:
                result.status = "healthy"

            # Add to history
            self._health_history.append(result)
            if len(self._health_history) > self._config["max_history"]:
                self._health_history.pop(0)

        except Exception as e:
            result.status = "error"
            result.warnings.append(f"Health check failed: {e}")
            logger.error(f"Vector health check failed: {e}")

        return result

    def _calculate_optimal_lists(self, vector_count: int) -> int:
        """Calculate optimal IVFFlat lists parameter for a given vector count."""
        if vector_count < 1000:
            return 10
        elif vector_count < 1000000:
            return max(10, vector_count // 1000)
        else:
            import math
            return max(100, int(math.sqrt(vector_count)))

    # =========================================
    # Status and History
    # =========================================

    def get_status(self) -> Dict[str, Any]:
        """Get current maintenance status."""
        return {
            "reindex_in_progress": self._reindex_in_progress,
            "current_operation": self._current_operation,
            "last_reindex": self._last_reindex.isoformat() if self._last_reindex else None,
            "last_health_check": self._last_health_check.isoformat() if self._last_health_check else None,
            "config": self._config,
            "initialized": self._initialized,
        }

    def get_reindex_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get reindex operation history."""
        return [
            {
                "collection": r.collection,
                "started_at": r.started_at.isoformat(),
                "completed_at": r.completed_at.isoformat() if r.completed_at else None,
                "status": r.status.value,
                "old_lists": r.old_lists,
                "new_lists": r.new_lists,
                "vector_count": r.vector_count,
                "duration_seconds": r.duration_seconds,
                "error": r.error,
            }
            for r in self._reindex_history[-limit:]
        ]

    def get_health_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get health check history."""
        return [
            {
                "timestamp": h.timestamp.isoformat(),
                "status": h.status,
                "total_vectors": h.total_vectors,
                "total_collections": h.total_collections,
                "warnings": h.warnings,
            }
            for h in self._health_history[-limit:]
        ]

    async def update_config(
        self,
        reindex_day_of_week: Optional[int] = None,
        reindex_hour: Optional[int] = None,
        health_check_hour: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Update maintenance configuration.

        Args:
            reindex_day_of_week: Day of week for reindex (0=Sunday, 6=Saturday)
            reindex_hour: Hour of day for reindex (0-23)
            health_check_hour: Hour of day for health check (0-23)

        Returns:
            Updated configuration
        """
        if reindex_day_of_week is not None:
            if not 0 <= reindex_day_of_week <= 6:
                return {"success": False, "error": "day_of_week must be 0-6"}
            self._config["reindex_day_of_week"] = reindex_day_of_week

        if reindex_hour is not None:
            if not 0 <= reindex_hour <= 23:
                return {"success": False, "error": "reindex_hour must be 0-23"}
            self._config["reindex_hour"] = reindex_hour

        if health_check_hour is not None:
            if not 0 <= health_check_hour <= 23:
                return {"success": False, "error": "health_check_hour must be 0-23"}
            self._config["health_check_hour"] = health_check_hour

        # Save to database
        if self._db_pool:
            try:
                import json
                async with self._db_pool.acquire() as conn:
                    await conn.execute("""
                        UPDATE arkham_frame.maintenance_settings
                        SET value = $2, updated_at = NOW()
                        WHERE key = 'vector_reindex'
                    """, 'vector_reindex', json.dumps({
                        "schedule": "weekly",
                        "day_of_week": self._config["reindex_day_of_week"],
                        "hour": self._config["reindex_hour"],
                        "last_run": self._last_reindex.isoformat() if self._last_reindex else None,
                    }))
            except Exception as e:
                logger.warning(f"Failed to save config to database: {e}")

        # Note: Schedule updates would require scheduler reconfiguration
        # For simplicity, changes take effect after restart

        return {
            "success": True,
            "config": self._config,
            "note": "Schedule changes take effect after restart",
        }
