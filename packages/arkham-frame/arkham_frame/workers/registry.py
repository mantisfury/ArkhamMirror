"""
WorkerRegistry - Track active workers across all pools.

Provides discovery and health monitoring of workers.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import asyncio
import json
import logging

logger = logging.getLogger(__name__)


@dataclass
class WorkerInfo:
    """Information about a registered worker."""
    worker_id: str
    pool: str
    name: str
    state: str
    pid: int
    started_at: datetime
    last_heartbeat: Optional[datetime] = None
    jobs_completed: int = 0
    jobs_failed: int = 0
    current_job: Optional[str] = None

    @property
    def is_alive(self) -> bool:
        """Check if worker is considered alive (heartbeat within 30s)."""
        if not self.last_heartbeat:
            return False
        return (datetime.utcnow() - self.last_heartbeat).total_seconds() < 30

    @property
    def is_stuck(self) -> bool:
        """Check if worker might be stuck (no heartbeat for 60s)."""
        if not self.last_heartbeat:
            return True
        return (datetime.utcnow() - self.last_heartbeat).total_seconds() > 60

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "worker_id": self.worker_id,
            "pool": self.pool,
            "name": self.name,
            "state": self.state,
            "pid": self.pid,
            "started_at": self.started_at.isoformat(),
            "last_heartbeat": self.last_heartbeat.isoformat() if self.last_heartbeat else None,
            "jobs_completed": self.jobs_completed,
            "jobs_failed": self.jobs_failed,
            "current_job": self.current_job,
            "is_alive": self.is_alive,
            "is_stuck": self.is_stuck,
        }


class WorkerRegistry:
    """
    Registry for tracking active workers.

    Uses Redis to discover workers and their status.
    Workers register themselves and send heartbeats.
    """

    def __init__(self, redis_url: str = None):
        """
        Initialize registry.

        Args:
            redis_url: Redis connection URL
        """
        self.redis_url = redis_url
        self._redis = None
        self._cache: Dict[str, WorkerInfo] = {}
        self._cache_time: Optional[datetime] = None
        self._cache_ttl = 5  # Seconds

    async def connect(self, redis_client=None):
        """
        Connect to Redis.

        Args:
            redis_client: Existing Redis client to use (optional)
        """
        if redis_client:
            self._redis = redis_client
            return

        if not self.redis_url:
            import os
            self.redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379")

        try:
            import redis.asyncio as aioredis
            self._redis = aioredis.from_url(self.redis_url)
            await self._redis.ping()
        except Exception as e:
            logger.error(f"Registry Redis connection failed: {e}")
            self._redis = None

    async def disconnect(self):
        """Disconnect from Redis."""
        if self._redis:
            await self._redis.close()
            self._redis = None

    def _parse_worker_data(self, worker_id: str, data: Dict) -> WorkerInfo:
        """Parse worker data from Redis."""
        # Handle bytes keys/values
        def get_val(key, default=None):
            val = data.get(key.encode()) if isinstance(key, str) else data.get(key)
            if val is None:
                val = data.get(key, default)
            if isinstance(val, bytes):
                val = val.decode()
            return val if val is not None else default

        started_at_str = get_val("started_at")
        try:
            started_at = datetime.fromisoformat(started_at_str) if started_at_str else datetime.utcnow()
        except (ValueError, TypeError):
            started_at = datetime.utcnow()

        last_hb_str = get_val("last_heartbeat")
        try:
            last_heartbeat = datetime.fromisoformat(last_hb_str) if last_hb_str else None
        except (ValueError, TypeError):
            last_heartbeat = None

        return WorkerInfo(
            worker_id=worker_id,
            pool=get_val("pool", "unknown"),
            name=get_val("name", "Unknown"),
            state=get_val("state", "unknown"),
            pid=int(get_val("pid", 0)),
            started_at=started_at,
            last_heartbeat=last_heartbeat,
            jobs_completed=int(get_val("jobs_completed", 0)),
            jobs_failed=int(get_val("jobs_failed", 0)),
            current_job=get_val("current_job") or None,
        )

    async def get_all_workers(self, use_cache: bool = True) -> List[WorkerInfo]:
        """
        Get all registered workers.

        Args:
            use_cache: Use cached data if available

        Returns:
            List of WorkerInfo objects
        """
        if not self._redis:
            return []

        # Check cache
        if use_cache and self._cache_time:
            age = (datetime.utcnow() - self._cache_time).total_seconds()
            if age < self._cache_ttl:
                return list(self._cache.values())

        workers = []
        self._cache.clear()

        try:
            # Scan for worker keys
            cursor = 0
            while True:
                cursor, keys = await self._redis.scan(
                    cursor=cursor,
                    match="arkham:worker:*",
                    count=100,
                )

                for key in keys:
                    if isinstance(key, bytes):
                        key = key.decode()

                    worker_id = key.replace("arkham:worker:", "")
                    data = await self._redis.hgetall(key)

                    if data:
                        info = self._parse_worker_data(worker_id, data)
                        workers.append(info)
                        self._cache[worker_id] = info

                if cursor == 0:
                    break

            self._cache_time = datetime.utcnow()

        except Exception as e:
            logger.error(f"Failed to get workers: {e}")

        return workers

    async def get_worker(self, worker_id: str) -> Optional[WorkerInfo]:
        """
        Get a specific worker.

        Args:
            worker_id: Worker ID

        Returns:
            WorkerInfo or None
        """
        if not self._redis:
            return None

        try:
            key = f"arkham:worker:{worker_id}"
            data = await self._redis.hgetall(key)

            if not data:
                return None

            return self._parse_worker_data(worker_id, data)

        except Exception as e:
            logger.error(f"Failed to get worker {worker_id}: {e}")
            return None

    async def get_pool_workers(self, pool: str) -> List[WorkerInfo]:
        """
        Get workers for a specific pool.

        Args:
            pool: Pool name

        Returns:
            List of WorkerInfo objects
        """
        all_workers = await self.get_all_workers()
        return [w for w in all_workers if w.pool == pool]

    async def get_alive_workers(self, pool: str = None) -> List[WorkerInfo]:
        """
        Get workers that are alive (recent heartbeat).

        Args:
            pool: Optional pool filter

        Returns:
            List of alive WorkerInfo objects
        """
        if pool:
            workers = await self.get_pool_workers(pool)
        else:
            workers = await self.get_all_workers()

        return [w for w in workers if w.is_alive]

    async def get_stuck_workers(self, pool: str = None) -> List[WorkerInfo]:
        """
        Get workers that appear stuck.

        Args:
            pool: Optional pool filter

        Returns:
            List of stuck WorkerInfo objects
        """
        if pool:
            workers = await self.get_pool_workers(pool)
        else:
            workers = await self.get_all_workers()

        return [w for w in workers if w.is_stuck]

    async def get_pool_stats(self, pool: str) -> Dict[str, Any]:
        """
        Get statistics for a pool.

        Args:
            pool: Pool name

        Returns:
            Statistics dict
        """
        workers = await self.get_pool_workers(pool)

        return {
            "pool": pool,
            "total_workers": len(workers),
            "alive_workers": len([w for w in workers if w.is_alive]),
            "stuck_workers": len([w for w in workers if w.is_stuck]),
            "idle_workers": len([w for w in workers if w.state == "idle" and w.is_alive]),
            "processing_workers": len([w for w in workers if w.state == "processing"]),
            "total_completed": sum(w.jobs_completed for w in workers),
            "total_failed": sum(w.jobs_failed for w in workers),
        }

    async def get_all_pool_stats(self) -> List[Dict[str, Any]]:
        """
        Get statistics for all pools.

        Returns:
            List of pool statistics
        """
        from ..services.workers import WORKER_POOLS

        stats = []
        for pool_name in WORKER_POOLS.keys():
            pool_stats = await self.get_pool_stats(pool_name)
            stats.append(pool_stats)

        return stats

    async def cleanup_dead_workers(self) -> int:
        """
        Remove dead workers from registry.

        Returns:
            Number of workers cleaned up
        """
        if not self._redis:
            return 0

        count = 0
        workers = await self.get_all_workers(use_cache=False)

        for worker in workers:
            # Worker is dead if no heartbeat for 2+ minutes
            if not worker.last_heartbeat:
                continue

            age = (datetime.utcnow() - worker.last_heartbeat).total_seconds()
            if age > 120:
                try:
                    key = f"arkham:worker:{worker.worker_id}"
                    await self._redis.delete(key)

                    pool_key = f"arkham:pool:{worker.pool}:workers"
                    await self._redis.srem(pool_key, worker.worker_id)

                    count += 1
                    logger.info(f"Cleaned up dead worker {worker.worker_id}")

                except Exception as e:
                    logger.error(f"Failed to cleanup worker {worker.worker_id}: {e}")

        return count

    async def publish_event(self, event_type: str, data: Dict[str, Any]):
        """
        Publish an event to the event channel.

        Args:
            event_type: Event type
            data: Event data
        """
        if not self._redis:
            return

        try:
            await self._redis.publish("arkham:events", json.dumps({
                "event": event_type,
                **data,
            }))
        except Exception as e:
            logger.error(f"Failed to publish event: {e}")
