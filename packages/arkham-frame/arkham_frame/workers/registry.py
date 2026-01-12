"""
WorkerRegistry - Track active workers across all pools.

Provides discovery and health monitoring of workers using PostgreSQL.
Workers register themselves in arkham_jobs.workers table.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import asyncio
import logging
import os

import asyncpg

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

    Uses PostgreSQL arkham_jobs.workers table to discover workers and their status.
    Workers register themselves and send heartbeats directly to the database.
    """

    def __init__(self, database_url: str = None):
        """
        Initialize registry.

        Args:
            database_url: PostgreSQL connection URL
        """
        self.database_url = database_url
        self._pool: Optional[asyncpg.Pool] = None
        self._cache: Dict[str, WorkerInfo] = {}
        self._cache_time: Optional[datetime] = None
        self._cache_ttl = 5  # Seconds

    async def connect(self, pool: asyncpg.Pool = None):
        """
        Connect to PostgreSQL.

        Args:
            pool: Existing connection pool to use (optional)
        """
        if pool:
            self._pool = pool
            return

        if not self.database_url:
            self.database_url = os.environ.get(
                "DATABASE_URL",
                "postgresql://arkham:arkhampass@localhost:5432/arkhamdb"
            )

        try:
            self._pool = await asyncpg.create_pool(self.database_url, min_size=1, max_size=5)
        except Exception as e:
            logger.error(f"Registry PostgreSQL connection failed: {e}")
            self._pool = None

    async def disconnect(self):
        """Disconnect from PostgreSQL."""
        if self._pool:
            await self._pool.close()
            self._pool = None

    def _parse_worker_row(self, row: asyncpg.Record) -> WorkerInfo:
        """Parse worker data from database row."""
        return WorkerInfo(
            worker_id=row['id'],
            pool=row['pool'],
            name=row['name'],
            state=row['state'],
            pid=row['pid'] or 0,
            started_at=row['started_at'] or datetime.utcnow(),
            last_heartbeat=row['last_heartbeat'],
            jobs_completed=row['jobs_completed'] or 0,
            jobs_failed=row['jobs_failed'] or 0,
            current_job=row['current_job'],
        )

    async def get_all_workers(self, use_cache: bool = True) -> List[WorkerInfo]:
        """
        Get all registered workers.

        Args:
            use_cache: Use cached data if available

        Returns:
            List of WorkerInfo objects
        """
        if not self._pool:
            return []

        # Check cache
        if use_cache and self._cache_time:
            age = (datetime.utcnow() - self._cache_time).total_seconds()
            if age < self._cache_ttl:
                return list(self._cache.values())

        workers = []
        self._cache.clear()

        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT id, pool, name, state, pid, hostname,
                           started_at, last_heartbeat,
                           jobs_completed, jobs_failed, current_job
                    FROM arkham_jobs.workers
                    ORDER BY pool, started_at
                """)

                for row in rows:
                    info = self._parse_worker_row(row)
                    workers.append(info)
                    self._cache[info.worker_id] = info

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
        if not self._pool:
            return None

        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow("""
                    SELECT id, pool, name, state, pid, hostname,
                           started_at, last_heartbeat,
                           jobs_completed, jobs_failed, current_job
                    FROM arkham_jobs.workers
                    WHERE id = $1
                """, worker_id)

                if not row:
                    return None

                return self._parse_worker_row(row)

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
        if not self._pool:
            return 0

        try:
            async with self._pool.acquire() as conn:
                # Delete workers with no heartbeat for 2+ minutes
                result = await conn.execute("""
                    DELETE FROM arkham_jobs.workers
                    WHERE last_heartbeat < NOW() - INTERVAL '2 minutes'
                """)

                # Parse "DELETE X" to get count
                count = int(result.split()[-1]) if result else 0

                if count > 0:
                    logger.info(f"Cleaned up {count} dead workers")

                return count

        except Exception as e:
            logger.error(f"Failed to cleanup dead workers: {e}")
            return 0
