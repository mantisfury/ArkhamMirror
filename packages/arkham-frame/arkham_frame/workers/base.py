"""
BaseWorker - Abstract base class for all ArkhamFrame workers.

Workers poll a Redis queue, process jobs, and report results.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, Any, Optional
import asyncio
import json
import logging
import os
import signal
import time
import uuid

logger = logging.getLogger(__name__)


class WorkerState(Enum):
    """Worker lifecycle states."""
    STARTING = "starting"
    IDLE = "idle"
    PROCESSING = "processing"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class WorkerMetrics:
    """Worker performance metrics."""
    jobs_completed: int = 0
    jobs_failed: int = 0
    total_processing_time: float = 0.0
    last_job_time: Optional[datetime] = None
    last_heartbeat: Optional[datetime] = None
    errors: list = field(default_factory=list)

    @property
    def avg_job_time(self) -> float:
        """Average job processing time in seconds."""
        if self.jobs_completed == 0:
            return 0.0
        return self.total_processing_time / self.jobs_completed

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "jobs_completed": self.jobs_completed,
            "jobs_failed": self.jobs_failed,
            "avg_job_time": round(self.avg_job_time, 3),
            "total_processing_time": round(self.total_processing_time, 3),
            "last_job_time": self.last_job_time.isoformat() if self.last_job_time else None,
            "last_heartbeat": self.last_heartbeat.isoformat() if self.last_heartbeat else None,
            "recent_errors": self.errors[-5:],  # Last 5 errors
        }


class BaseWorker(ABC):
    """
    Abstract base class for all workers.

    Subclasses must implement:
    - pool: The worker pool this worker belongs to
    - process_job(): The actual job processing logic

    Lifecycle:
    1. Worker starts and connects to Redis
    2. Enters main loop: poll queue -> process -> report
    3. Sends heartbeats every 10 seconds
    4. On shutdown signal: finish current job, cleanup, exit
    """

    # Subclasses must override
    pool: str = "unknown"
    name: str = "BaseWorker"

    # Configuration
    poll_interval: float = 1.0  # Seconds between queue polls
    heartbeat_interval: float = 10.0  # Seconds between heartbeats
    idle_timeout: float = 60.0  # Seconds of idle before shutdown
    job_timeout: float = 300.0  # Max seconds per job
    max_retries: int = 3

    def __init__(self, redis_url: str = None, worker_id: str = None):
        """
        Initialize worker.

        Args:
            redis_url: Redis connection URL (defaults to env var)
            worker_id: Unique worker ID (auto-generated if not provided)
        """
        self.worker_id = worker_id or f"{self.pool}-{uuid.uuid4().hex[:8]}"
        self.redis_url = redis_url or os.environ.get(
            "REDIS_URL", "redis://localhost:6379"
        )

        self._redis = None
        self._state = WorkerState.STOPPED
        self._metrics = WorkerMetrics()
        self._current_job = None
        self._current_job_start = None
        self._last_job_time = None
        self._shutdown_event = asyncio.Event()
        self._running = False

        # Setup signal handlers
        self._setup_signals()

    def _setup_signals(self):
        """Setup signal handlers for graceful shutdown."""
        try:
            signal.signal(signal.SIGTERM, self._signal_handler)
            signal.signal(signal.SIGINT, self._signal_handler)
        except (ValueError, OSError):
            # Signals not available (Windows or not main thread)
            pass

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        logger.info(f"Worker {self.worker_id} received signal {signum}")
        self._shutdown_event.set()

    async def connect(self) -> bool:
        """Connect to Redis."""
        try:
            import redis.asyncio as aioredis

            self._redis = aioredis.from_url(self.redis_url)
            await self._redis.ping()
            logger.info(f"Worker {self.worker_id} connected to Redis")
            return True
        except Exception as e:
            logger.error(f"Worker {self.worker_id} Redis connection failed: {e}")
            return False

    async def disconnect(self):
        """Disconnect from Redis."""
        if self._redis:
            await self._redis.close()
            self._redis = None

    async def register(self):
        """Register worker in Redis registry."""
        if not self._redis:
            return

        worker_key = f"arkham:worker:{self.worker_id}"
        await self._redis.hset(worker_key, mapping={
            "pool": self.pool,
            "name": self.name,
            "state": self._state.value,
            "started_at": datetime.utcnow().isoformat(),
            "pid": os.getpid(),
        })
        # Set expiry so dead workers disappear
        await self._redis.expire(worker_key, 120)

        # Add to pool set
        pool_key = f"arkham:pool:{self.pool}:workers"
        await self._redis.sadd(pool_key, self.worker_id)

    async def deregister(self):
        """Remove worker from Redis registry."""
        if not self._redis:
            return

        worker_key = f"arkham:worker:{self.worker_id}"
        await self._redis.delete(worker_key)

        pool_key = f"arkham:pool:{self.pool}:workers"
        await self._redis.srem(pool_key, self.worker_id)

    async def heartbeat(self):
        """Send heartbeat to Redis."""
        if not self._redis:
            return

        self._metrics.last_heartbeat = datetime.utcnow()

        worker_key = f"arkham:worker:{self.worker_id}"
        await self._redis.hset(worker_key, mapping={
            "state": self._state.value,
            "last_heartbeat": self._metrics.last_heartbeat.isoformat(),
            "jobs_completed": self._metrics.jobs_completed,
            "jobs_failed": self._metrics.jobs_failed,
            "current_job": self._current_job or "",
        })
        # Refresh expiry
        await self._redis.expire(worker_key, 120)

    async def dequeue_job(self) -> Optional[Dict[str, Any]]:
        """
        Dequeue a job from the pool's queue.

        Returns:
            Job data dict or None if queue is empty.
        """
        if not self._redis:
            return None

        queue_key = f"arkham:queue:{self.pool}"

        # Pop highest priority job (lowest score)
        result = await self._redis.zpopmin(queue_key, count=1)
        if not result:
            return None

        job_id = result[0][0]
        if isinstance(job_id, bytes):
            job_id = job_id.decode()

        # Get job data
        job_key = f"arkham:job:{job_id}"
        job_data = await self._redis.hgetall(job_key)

        if not job_data:
            logger.warning(f"Job {job_id} not found in Redis")
            return None

        # Parse job data
        payload_raw = job_data.get(b"payload") or job_data.get("payload", "{}")
        if isinstance(payload_raw, bytes):
            payload_raw = payload_raw.decode()
        payload = json.loads(payload_raw)

        # Mark as active
        await self._redis.hset(job_key, mapping={
            "status": "active",
            "worker_id": self.worker_id,
            "started_at": datetime.utcnow().isoformat(),
        })

        return {
            "id": job_id,
            "pool": self.pool,
            "payload": payload,
            "job_key": job_key,
        }

    async def complete_job(self, job_id: str, result: Dict[str, Any] = None):
        """Mark job as completed."""
        if not self._redis:
            return

        job_key = f"arkham:job:{job_id}"
        await self._redis.hset(job_key, mapping={
            "status": "completed",
            "completed_at": datetime.utcnow().isoformat(),
            "result": json.dumps(result or {}),
        })

        # Publish completion event
        await self._redis.publish("arkham:events", json.dumps({
            "event": "worker.job.completed",
            "job_id": job_id,
            "worker_id": self.worker_id,
            "pool": self.pool,
            "result": result,
        }))

    async def fail_job(self, job_id: str, error: str, requeue: bool = False):
        """Mark job as failed."""
        if not self._redis:
            return

        job_key = f"arkham:job:{job_id}"

        if requeue:
            # Get current retry count
            retry_count = await self._redis.hget(job_key, "retry_count") or 0
            if isinstance(retry_count, bytes):
                retry_count = int(retry_count.decode())
            else:
                retry_count = int(retry_count)

            if retry_count < self.max_retries:
                # Requeue with lower priority
                await self._redis.hset(job_key, mapping={
                    "status": "pending",
                    "retry_count": retry_count + 1,
                    "last_error": error,
                })
                queue_key = f"arkham:queue:{self.pool}"
                # Higher priority number = lower priority
                await self._redis.zadd(queue_key, {job_id: 10 + retry_count})
                logger.info(f"Requeued job {job_id} (retry {retry_count + 1})")
                return

        # Mark as failed (no more retries)
        await self._redis.hset(job_key, mapping={
            "status": "failed",
            "completed_at": datetime.utcnow().isoformat(),
            "error": error,
        })

        # Add to dead letter queue
        dlq_key = f"arkham:dlq:{self.pool}"
        await self._redis.lpush(dlq_key, job_id)

        # Publish failure event
        await self._redis.publish("arkham:events", json.dumps({
            "event": "worker.job.failed",
            "job_id": job_id,
            "worker_id": self.worker_id,
            "pool": self.pool,
            "error": error,
        }))

    @abstractmethod
    async def process_job(self, job_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a job. Subclasses must implement this.

        Args:
            job_id: The job ID
            payload: Job data from the queue

        Returns:
            Result dict to store with the completed job.

        Raises:
            Exception: On failure, job will be marked as failed.
        """
        pass

    async def _process_with_timeout(self, job: Dict[str, Any]) -> Dict[str, Any]:
        """Process job with timeout."""
        job_id = job["id"]
        payload = job["payload"]

        try:
            result = await asyncio.wait_for(
                self.process_job(job_id, payload),
                timeout=self.job_timeout,
            )
            return result
        except asyncio.TimeoutError:
            raise TimeoutError(f"Job {job_id} timed out after {self.job_timeout}s")

    async def run(self):
        """
        Main worker loop.

        Polls queue, processes jobs, sends heartbeats.
        Exits on shutdown signal or idle timeout.
        """
        self._running = True
        self._state = WorkerState.STARTING

        # Connect to Redis
        if not await self.connect():
            self._state = WorkerState.ERROR
            return

        # Register worker
        await self.register()
        self._state = WorkerState.IDLE

        logger.info(f"Worker {self.worker_id} started for pool {self.pool}")

        last_heartbeat = time.time()
        idle_start = time.time()

        try:
            while self._running and not self._shutdown_event.is_set():
                # Send heartbeat if needed
                if time.time() - last_heartbeat >= self.heartbeat_interval:
                    await self.heartbeat()
                    last_heartbeat = time.time()

                # Try to get a job
                job = await self.dequeue_job()

                if job:
                    idle_start = time.time()  # Reset idle timer
                    self._state = WorkerState.PROCESSING
                    self._current_job = job["id"]
                    self._current_job_start = datetime.utcnow()

                    logger.info(f"Worker {self.worker_id} processing job {job['id']}")

                    try:
                        start_time = time.time()
                        result = await self._process_with_timeout(job)
                        elapsed = time.time() - start_time

                        await self.complete_job(job["id"], result)

                        self._metrics.jobs_completed += 1
                        self._metrics.total_processing_time += elapsed
                        self._metrics.last_job_time = datetime.utcnow()

                        logger.info(
                            f"Worker {self.worker_id} completed job {job['id']} "
                            f"in {elapsed:.2f}s"
                        )

                    except Exception as e:
                        error_msg = str(e)
                        logger.error(
                            f"Worker {self.worker_id} job {job['id']} failed: {error_msg}"
                        )

                        await self.fail_job(job["id"], error_msg, requeue=True)

                        self._metrics.jobs_failed += 1
                        self._metrics.errors.append({
                            "job_id": job["id"],
                            "error": error_msg,
                            "time": datetime.utcnow().isoformat(),
                        })

                    finally:
                        self._current_job = None
                        self._current_job_start = None
                        self._state = WorkerState.IDLE

                else:
                    # No job available, check idle timeout
                    idle_time = time.time() - idle_start
                    if idle_time >= self.idle_timeout:
                        logger.info(
                            f"Worker {self.worker_id} idle for {idle_time:.0f}s, "
                            "shutting down"
                        )
                        break

                    # Wait before next poll
                    try:
                        await asyncio.wait_for(
                            self._shutdown_event.wait(),
                            timeout=self.poll_interval,
                        )
                        break  # Shutdown requested
                    except asyncio.TimeoutError:
                        pass  # Normal timeout, continue polling

        except Exception as e:
            logger.error(f"Worker {self.worker_id} error: {e}")
            self._state = WorkerState.ERROR
        finally:
            await self.shutdown()

    async def shutdown(self):
        """Graceful shutdown."""
        self._state = WorkerState.STOPPING
        self._running = False

        logger.info(f"Worker {self.worker_id} shutting down...")

        # If we have a current job, try to requeue it
        if self._current_job:
            logger.warning(
                f"Worker {self.worker_id} has incomplete job {self._current_job}, "
                "requeuing"
            )
            await self.fail_job(
                self._current_job,
                "Worker shutdown while processing",
                requeue=True,
            )

        # Deregister
        await self.deregister()

        # Disconnect
        await self.disconnect()

        self._state = WorkerState.STOPPED
        logger.info(f"Worker {self.worker_id} stopped")

    def get_status(self) -> Dict[str, Any]:
        """Get worker status."""
        return {
            "worker_id": self.worker_id,
            "pool": self.pool,
            "name": self.name,
            "state": self._state.value,
            "current_job": self._current_job,
            "current_job_duration": (
                (datetime.utcnow() - self._current_job_start).total_seconds()
                if self._current_job_start else None
            ),
            "metrics": self._metrics.to_dict(),
            "pid": os.getpid(),
        }


def run_worker(worker_class: type, redis_url: str = None, worker_id: str = None):
    """
    Convenience function to run a worker.

    Args:
        worker_class: BaseWorker subclass
        redis_url: Redis connection URL
        worker_id: Optional worker ID
    """
    worker = worker_class(redis_url=redis_url, worker_id=worker_id)
    asyncio.run(worker.run())
