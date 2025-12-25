"""
WorkerService - Redis queue and worker management.

Implements the worker pool architecture from WORKER_ARCHITECTURE.md.
"""

from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
import json
import logging
import uuid

logger = logging.getLogger(__name__)


class WorkerError(Exception):
    """Base worker error."""
    pass


class WorkerNotFoundError(WorkerError):
    """Worker not found."""
    pass


class QueueUnavailableError(WorkerError):
    """Queue not available."""
    pass


@dataclass
class Job:
    """A job in the queue."""
    id: str
    pool: str
    payload: Dict[str, Any]
    priority: int = 1
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: str = "pending"  # pending, active, completed, failed
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


# Worker pool definitions from WORKER_ARCHITECTURE.md
WORKER_POOLS = {
    # IO pools
    "io-file": {"type": "io", "max_workers": 20},
    "io-db": {"type": "io", "max_workers": 10},

    # CPU pools
    "cpu-light": {"type": "cpu", "max_workers": 50},
    "cpu-heavy": {"type": "cpu", "max_workers": 6},
    "cpu-ner": {"type": "cpu", "max_workers": 8},
    "cpu-extract": {"type": "cpu", "max_workers": 4},
    "cpu-image": {"type": "cpu", "max_workers": 4},
    "cpu-archive": {"type": "cpu", "max_workers": 2},

    # GPU pools
    "gpu-paddle": {"type": "gpu", "max_workers": 1, "vram_mb": 2000},
    "gpu-qwen": {"type": "gpu", "max_workers": 1, "vram_mb": 8000},
    "gpu-whisper": {"type": "gpu", "max_workers": 1, "vram_mb": 4000},
    "gpu-embed": {"type": "gpu", "max_workers": 1, "vram_mb": 2000},

    # LLM pools (optional)
    "llm-enrich": {"type": "llm", "max_workers": 4},
    "llm-analysis": {"type": "llm", "max_workers": 2},
}


class WorkerService:
    """
    Redis queue and worker management service.

    Manages job queues across multiple worker pools with priority
    handling and event emission.
    """

    def __init__(self, config):
        self.config = config
        self._redis = None
        self._available = False
        self._jobs: Dict[str, Job] = {}  # In-memory job tracking
        self._handlers: Dict[str, Callable] = {}  # Pool -> handler function
        self._event_bus = None

    def set_event_bus(self, event_bus) -> None:
        """Set event bus for job notifications."""
        self._event_bus = event_bus

    async def initialize(self) -> None:
        """Initialize Redis connection."""
        try:
            import redis

            self._redis = redis.from_url(self.config.redis_url)
            self._redis.ping()
            self._available = True
            logger.info(f"Redis connected: {self.config.redis_url}")
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}")
            self._available = False

    async def shutdown(self) -> None:
        """Close Redis connection."""
        if self._redis:
            self._redis.close()
        self._available = False
        logger.info("Redis connection closed")

    def is_available(self) -> bool:
        """Check if Redis is available."""
        return self._available

    # --- Job Queuing ---

    async def enqueue(
        self,
        pool: str,
        job_id: str,
        payload: Dict[str, Any],
        priority: int = 1,
    ) -> Job:
        """
        Enqueue a job to a worker pool.

        Args:
            pool: Worker pool name (e.g., "cpu-light", "gpu-paddle")
            job_id: Unique job identifier
            payload: Job data
            priority: Priority level (1=highest)

        Returns:
            Created Job object
        """
        if pool not in WORKER_POOLS:
            raise WorkerError(f"Unknown worker pool: {pool}")

        job = Job(
            id=job_id,
            pool=pool,
            payload=payload,
            priority=priority,
        )

        self._jobs[job_id] = job

        if self._available and self._redis:
            # Add to Redis sorted set (priority queue)
            queue_key = f"arkham:queue:{pool}"
            self._redis.zadd(queue_key, {job_id: priority})

            # Store job data
            job_key = f"arkham:job:{job_id}"
            self._redis.hset(job_key, mapping={
                "pool": pool,
                "payload": json.dumps(payload),
                "priority": priority,
                "status": "pending",
                "created_at": job.created_at.isoformat(),
            })

            logger.debug(f"Enqueued job {job_id} to {pool} (priority={priority})")
        else:
            logger.warning(f"Redis unavailable, job {job_id} tracked in memory only")

        return job

    async def dequeue(self, pool: str) -> Optional[Job]:
        """
        Dequeue the highest priority job from a pool.

        Args:
            pool: Worker pool name

        Returns:
            Job if available, None otherwise
        """
        if not self._available or not self._redis:
            return None

        queue_key = f"arkham:queue:{pool}"

        # Get highest priority job (lowest score)
        result = self._redis.zpopmin(queue_key, count=1)
        if not result:
            return None

        job_id = result[0][0]
        if isinstance(job_id, bytes):
            job_id = job_id.decode()

        # Get job data
        job_key = f"arkham:job:{job_id}"
        job_data = self._redis.hgetall(job_key)

        if not job_data:
            return None

        # Parse job data
        payload = json.loads(job_data.get(b"payload", b"{}"))

        job = Job(
            id=job_id,
            pool=pool,
            payload=payload,
            priority=int(job_data.get(b"priority", 1)),
            status="active",
        )
        job.started_at = datetime.utcnow()

        # Update status in Redis
        self._redis.hset(job_key, "status", "active")
        self._redis.hset(job_key, "started_at", job.started_at.isoformat())

        self._jobs[job_id] = job
        return job

    async def complete_job(
        self,
        job_id: str,
        result: Dict[str, Any] = None,
    ) -> None:
        """Mark a job as completed."""
        job = self._jobs.get(job_id)
        if job:
            job.status = "completed"
            job.completed_at = datetime.utcnow()
            job.result = result

        if self._available and self._redis:
            job_key = f"arkham:job:{job_id}"
            self._redis.hset(job_key, mapping={
                "status": "completed",
                "completed_at": datetime.utcnow().isoformat(),
                "result": json.dumps(result or {}),
            })

        # Emit event
        if self._event_bus:
            await self._event_bus.publish(
                "worker.job.completed",
                {"job_id": job_id, "result": result},
                source="worker-service",
            )

    async def fail_job(
        self,
        job_id: str,
        error: str,
    ) -> None:
        """Mark a job as failed."""
        job = self._jobs.get(job_id)
        if job:
            job.status = "failed"
            job.completed_at = datetime.utcnow()
            job.error = error

        if self._available and self._redis:
            job_key = f"arkham:job:{job_id}"
            self._redis.hset(job_key, mapping={
                "status": "failed",
                "completed_at": datetime.utcnow().isoformat(),
                "error": error,
            })

        # Emit event
        if self._event_bus:
            await self._event_bus.publish(
                "worker.job.failed",
                {"job_id": job_id, "error": error},
                source="worker-service",
            )

    def get_job(self, job_id: str) -> Optional[Job]:
        """Get a job by ID."""
        return self._jobs.get(job_id)

    # --- Queue Stats ---

    async def get_queue_stats(self) -> List[Dict[str, Any]]:
        """Get queue statistics for all pools."""
        stats = []

        for pool_name, pool_config in WORKER_POOLS.items():
            pool_stats = {
                "name": pool_name,
                "type": pool_config["type"],
                "max_workers": pool_config["max_workers"],
                "pending": 0,
                "active": 0,
                "completed": 0,
                "failed": 0,
            }

            if self._available and self._redis:
                queue_key = f"arkham:queue:{pool_name}"
                pool_stats["pending"] = self._redis.zcard(queue_key)

            # Count from in-memory jobs
            for job in self._jobs.values():
                if job.pool == pool_name:
                    if job.status == "active":
                        pool_stats["active"] += 1
                    elif job.status == "completed":
                        pool_stats["completed"] += 1
                    elif job.status == "failed":
                        pool_stats["failed"] += 1

            stats.append(pool_stats)

        return stats

    async def get_pool_stats(self, pool: str) -> Dict[str, Any]:
        """Get statistics for a specific pool."""
        if pool not in WORKER_POOLS:
            raise WorkerError(f"Unknown pool: {pool}")

        pool_config = WORKER_POOLS[pool]
        stats = {
            "name": pool,
            "type": pool_config["type"],
            "max_workers": pool_config["max_workers"],
            "pending": 0,
            "active": 0,
            "completed": 0,
            "failed": 0,
        }

        if self._available and self._redis:
            queue_key = f"arkham:queue:{pool}"
            stats["pending"] = self._redis.zcard(queue_key)

        for job in self._jobs.values():
            if job.pool == pool:
                if job.status == "active":
                    stats["active"] += 1
                elif job.status == "completed":
                    stats["completed"] += 1
                elif job.status == "failed":
                    stats["failed"] += 1

        return stats

    # --- Worker Management ---

    async def get_workers(self) -> List[Dict[str, Any]]:
        """Get active workers."""
        # TODO: Implement actual worker tracking
        return []

    async def scale(self, pool: str, count: int) -> bool:
        """Scale workers for a pool."""
        if pool not in WORKER_POOLS:
            raise WorkerError(f"Unknown pool: {pool}")

        max_workers = WORKER_POOLS[pool]["max_workers"]
        if count > max_workers:
            logger.warning(f"Requested {count} workers for {pool}, max is {max_workers}")
            count = max_workers

        logger.info(f"Scaling {pool} to {count} workers")
        return True

    async def start_worker(self, pool: str) -> Dict[str, Any]:
        """Start a worker for a pool."""
        if pool not in WORKER_POOLS:
            raise WorkerError(f"Unknown pool: {pool}")

        logger.info(f"Starting worker for {pool}")
        return {"success": True, "pool": pool}

    async def stop_worker(self, worker_id: str) -> Dict[str, Any]:
        """Stop a worker."""
        logger.info(f"Stopping worker {worker_id}")
        return {"success": True}

    def register_handler(self, pool: str, handler: Callable) -> None:
        """Register a job handler for a pool."""
        self._handlers[pool] = handler
        logger.info(f"Registered handler for pool {pool}")
