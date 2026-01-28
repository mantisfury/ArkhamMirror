"""
BaseWorker - Abstract base class for all ArkhamFrame workers.

Workers poll a PostgreSQL job queue using SKIP LOCKED, process jobs, and report results.
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
import socket
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
    1. Worker starts and connects to PostgreSQL
    2. Enters main loop: poll queue -> process -> report
    3. Sends heartbeats every 30 seconds
    4. On shutdown signal: finish current job, cleanup, exit
    """

    # Subclasses must override
    pool: str = "unknown"
    name: str = "BaseWorker"

    # Configuration
    poll_interval: float = 1.0  # Seconds between queue polls
    heartbeat_interval: float = 30.0  # Seconds between heartbeats
    idle_timeout: float = 60.0  # Seconds of idle before shutdown
    job_timeout: float = 300.0  # Max seconds per job
    max_retries: int = 3

    def __init__(self, database_url: str = None, worker_id: str = None):
        """
        Initialize worker.

        Args:
            database_url: PostgreSQL connection URL (defaults to env var)
            worker_id: Unique worker ID (auto-generated if not provided)
        """
        self.worker_id = worker_id or f"{self.pool}-{uuid.uuid4().hex[:8]}"
        self.database_url = database_url or os.environ.get(
            "DATABASE_URL", "postgresql://arkham:arkhampass@localhost:5432/arkhamdb"
        )

        self._db_pool = None
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
        """Connect to PostgreSQL."""
        try:
            import asyncpg

            # JSON codec setup for asyncpg (JSONB is returned as string by default)
            async def init_connection(conn):
                """Initialize connection with JSON codecs."""
                await conn.set_type_codec(
                    'jsonb',
                    encoder=json.dumps,
                    decoder=json.loads,
                    schema='pg_catalog'
                )
                await conn.set_type_codec(
                    'json',
                    encoder=json.dumps,
                    decoder=json.loads,
                    schema='pg_catalog'
                )

            self._db_pool = await asyncpg.create_pool(
                self.database_url,
                min_size=1,
                max_size=3,
                init=init_connection,  # Set up JSON codecs
            )
            logger.info(f"Worker {self.worker_id} connected to PostgreSQL")
            return True
        except Exception as e:
            logger.error(f"Worker {self.worker_id} PostgreSQL connection failed: {e}")
            return False

    async def disconnect(self):
        """Disconnect from PostgreSQL."""
        if self._db_pool:
            await self._db_pool.close()
            self._db_pool = None

    async def register(self):
        """Register worker in database registry."""
        if not self._db_pool:
            return

        async with self._db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO arkham_jobs.workers
                (id, pool, name, hostname, pid, state, started_at, last_heartbeat)
                VALUES ($1, $2, $3, $4, $5, $6, NOW(), NOW())
                ON CONFLICT (id) DO UPDATE SET
                    state = EXCLUDED.state,
                    started_at = NOW(),
                    last_heartbeat = NOW()
            """, self.worker_id, self.pool, self.name, socket.gethostname(),
                os.getpid(), self._state.value)

    async def deregister(self):
        """Remove worker from database registry."""
        if not self._db_pool:
            return

        async with self._db_pool.acquire() as conn:
            await conn.execute("""
                DELETE FROM arkham_jobs.workers
                WHERE id = $1
            """, self.worker_id)

    async def heartbeat(self):
        """Send heartbeat to database."""
        if not self._db_pool:
            return

        self._metrics.last_heartbeat = datetime.utcnow()

        async with self._db_pool.acquire() as conn:
            await conn.execute("""
                UPDATE arkham_jobs.workers
                SET state = $2,
                    last_heartbeat = NOW(),
                    jobs_completed = $3,
                    jobs_failed = $4,
                    current_job = $5
                WHERE id = $1
            """, self.worker_id, self._state.value, self._metrics.jobs_completed,
                self._metrics.jobs_failed, self._current_job)

    async def dequeue_job(self) -> Optional[Dict[str, Any]]:
        """
        Dequeue a job from the pool's queue using SKIP LOCKED.

        This is the key PostgreSQL pattern for concurrent job processing.
        SKIP LOCKED ensures multiple workers don't get the same job.

        Returns:
            Job data dict or None if queue is empty.
        """
        if not self._db_pool:
            return None

        async with self._db_pool.acquire() as conn:
            # First, promote any scheduled jobs that are ready
            await conn.execute("""
                UPDATE arkham_jobs.jobs
                SET status = 'pending'
                WHERE status = 'scheduled'
                  AND scheduled_at <= NOW()
            """)

            # SKIP LOCKED is the magic - it skips rows locked by other workers
            row = await conn.fetchrow("""
                UPDATE arkham_jobs.jobs
                SET status = 'processing',
                    started_at = NOW(),
                    worker_id = $2
                WHERE id = (
                    SELECT id FROM arkham_jobs.jobs
                    WHERE pool = $1
                      AND status = 'pending'
                    ORDER BY priority ASC, created_at ASC
                    FOR UPDATE SKIP LOCKED
                    LIMIT 1
                )
                RETURNING id, pool, job_type, payload, priority, created_at,
                          retry_count, max_retries
            """, self.pool, self.worker_id)

            if not row:
                return None

            payload = row['payload']
            if isinstance(payload, str):
                payload = json.loads(payload)

            return {
                "id": row['id'],
                "pool": row['pool'],
                "job_type": row['job_type'],
                "payload": payload,
                "priority": row['priority'],
                "retry_count": row['retry_count'],
                "max_retries": row['max_retries'],
            }

    async def complete_job(self, job_id: str, result: Dict[str, Any] = None):
        """Mark job as completed."""
        if not self._db_pool:
            return

        async with self._db_pool.acquire() as conn:
            # Pass dict directly - asyncpg JSON codec handles serialization
            await conn.execute("""
                UPDATE arkham_jobs.jobs
                SET status = 'completed',
                    completed_at = NOW(),
                    result = $2
                WHERE id = $1
            """, job_id, result or {})

            # Update worker stats
            await conn.execute("""
                UPDATE arkham_jobs.workers
                SET jobs_completed = jobs_completed + 1,
                    current_job = NULL
                WHERE id = $1
            """, self.worker_id)

    async def fail_job(
        self,
        job_id: str,
        error: str,
        requeue: bool = False,
        worker_failure: bool = False,
    ):
        """
        Mark job as failed.

        When worker_failure=True, the job is requeued due to worker crash/shutdown,
        not due to the job raising. Uses worker_requeue_count / max_worker_requeues
        to limit requeues; exceeding marks the job dead with a user warning
        (possible toxic job). Does not increment the worker's jobs_failed.
        """
        if not self._db_pool:
            return

        async with self._db_pool.acquire() as conn:
            # Get current job state
            row = await conn.fetchrow("""
                SELECT retry_count, max_retries, pool, job_type, payload, created_at,
                       COALESCE(worker_requeue_count, 0) AS worker_requeue_count,
                       COALESCE(max_worker_requeues, 3) AS max_worker_requeues
                FROM arkham_jobs.jobs WHERE id = $1
            """, job_id)

            if not row:
                return

            if worker_failure and requeue:
                # Requeue limit for worker-failure: safety cap before user warning
                wr_count = row['worker_requeue_count']
                max_wr = row['max_worker_requeues']
                if wr_count < max_wr:
                    await conn.execute("""
                        UPDATE arkham_jobs.jobs
                        SET status = 'pending',
                            started_at = NULL,
                            worker_id = NULL,
                            worker_requeue_count = COALESCE(worker_requeue_count, 0) + 1,
                            last_error = $2
                        WHERE id = $1
                    """, job_id, error)
                    logger.info(
                        f"Requeued job {job_id} after worker failure "
                        f"(worker_requeue {wr_count + 1}/{max_wr})"
                    )
                else:
                    msg = (
                        "Job requeued too many times due to worker failure; "
                        "possible toxic job. Last: " + error
                    )
                    await conn.execute("""
                        INSERT INTO arkham_jobs.dead_letters
                        (job_id, pool, job_type, payload, error, retry_count, original_created_at)
                        VALUES ($1, $2, $3, $4, $5, $6, $7)
                    """, job_id, row['pool'], row['job_type'], row['payload'],
                        msg, row['retry_count'], row['created_at'])
                    await conn.execute("""
                        UPDATE arkham_jobs.jobs
                        SET status = 'dead',
                            completed_at = NOW(),
                            last_error = $2,
                            worker_id = NULL,
                            started_at = NULL
                        WHERE id = $1
                    """, job_id, msg)
                    logger.warning(
                        f"Job {job_id} moved to dead letter queue (worker requeue limit exceeded): {msg}"
                    )
                # Clear current_job for this worker; do not increment jobs_failed
                await conn.execute("""
                    UPDATE arkham_jobs.workers
                    SET current_job = NULL
                    WHERE id = $1
                """, self.worker_id)
                return

            # Job-failure path: use retry_count / max_retries
            retry_count = row['retry_count']
            max_retries = row['max_retries']

            if requeue and retry_count < max_retries:
                # Requeue with incremented retry count
                await conn.execute("""
                    UPDATE arkham_jobs.jobs
                    SET status = 'pending',
                        started_at = NULL,
                        worker_id = NULL,
                        retry_count = retry_count + 1,
                        last_error = $2
                    WHERE id = $1
                """, job_id, error)
                logger.info(f"Requeued job {job_id} (retry {retry_count + 1}/{max_retries})")
            else:
                # Move to dead letter queue
                await conn.execute("""
                    INSERT INTO arkham_jobs.dead_letters
                    (job_id, pool, job_type, payload, error, retry_count, original_created_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                """, job_id, row['pool'], row['job_type'], row['payload'],
                    error, row['retry_count'], row['created_at'])

                # Mark as dead
                await conn.execute("""
                    UPDATE arkham_jobs.jobs
                    SET status = 'dead',
                        completed_at = NOW(),
                        last_error = $2
                    WHERE id = $1
                """, job_id, error)
                logger.warning(f"Job {job_id} moved to dead letter queue: {error}")

            # Update worker stats
            await conn.execute("""
                UPDATE arkham_jobs.workers
                SET jobs_failed = jobs_failed + 1,
                    current_job = NULL
                WHERE id = $1
            """, self.worker_id)

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

        # Connect to PostgreSQL
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

        # If we have a current job, requeue it (worker failed, not the job)
        if self._current_job:
            logger.warning(
                f"Worker {self.worker_id} has incomplete job {self._current_job}, "
                "requeuing (worker failure)"
            )
            await self.fail_job(
                self._current_job,
                "Worker shutdown while processing",
                requeue=True,
                worker_failure=True,
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


def run_worker(worker_class: type, database_url: str = None, worker_id: str = None):
    """
    Convenience function to run a worker.

    Args:
        worker_class: BaseWorker subclass
        database_url: PostgreSQL connection URL
        worker_id: Optional worker ID
    """
    worker = worker_class(database_url=database_url, worker_id=worker_id)
    asyncio.run(worker.run())
