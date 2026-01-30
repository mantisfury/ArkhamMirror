"""
WorkerService - PostgreSQL job queue and worker management.

Implements the worker pool architecture using PostgreSQL with SKIP LOCKED
for concurrent job dequeuing and LISTEN/NOTIFY for real-time events.

Key features:
- Priority queue using PostgreSQL ORDER BY priority, created_at
- Concurrent dequeue using SELECT ... FOR UPDATE SKIP LOCKED
- Real-time notifications via LISTEN/NOTIFY
- Worker heartbeat and stale worker recovery
- Dead letter queue for failed jobs
"""

from typing import List, Dict, Any, Optional, Callable, Type
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import json
import logging
import multiprocessing
import os
from pathlib import Path
import time
import uuid
import asyncio

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
    job_type: str = "default"
    priority: int = 5  # 1-10, lower = higher priority
    created_at: datetime = field(default_factory=datetime.utcnow)
    scheduled_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: str = "pending"  # pending, scheduled, processing, completed, failed, dead
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    worker_id: Optional[str] = None
    worker_requeue_count: int = 0  # Requeues due to worker failure (stale/crash)
    max_worker_requeues: int = 3  # Cap before marking dead with "possible toxic job" warning


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


@dataclass
class WorkerInfo:
    """Information about a running worker."""
    id: str
    pool: str
    name: str = ""
    hostname: Optional[str] = None
    pid: Optional[int] = None
    status: str = "idle"  # starting, idle, processing, stopping, stopped, error
    started_at: datetime = field(default_factory=datetime.utcnow)
    last_heartbeat: datetime = field(default_factory=datetime.utcnow)
    current_job_id: Optional[str] = None
    jobs_completed: int = 0
    jobs_failed: int = 0


@dataclass
class WorkerProcess:
    """Tracks a worker subprocess."""
    worker_id: str
    pool: str
    process: multiprocessing.Process
    started_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def is_alive(self) -> bool:
        return self.process.is_alive() if self.process else False

    @property
    def pid(self) -> Optional[int]:
        return self.process.pid if self.process else None


class WorkerService:
    """
    PostgreSQL job queue and worker management service.

    Uses SKIP LOCKED for concurrent job dequeuing and LISTEN/NOTIFY
    for real-time event distribution.
    """

    def __init__(self, config):
        self.config = config
        self._db_pool = None
        self._available = False
        self._jobs: Dict[str, Job] = {}  # In-memory job tracking (cache)
        self._handlers: Dict[str, Callable] = {}  # Pool -> handler function
        self._event_bus = None
        self._workers: Dict[str, WorkerInfo] = {}  # Active workers (metadata)
        self._processes: Dict[str, WorkerProcess] = {}  # Actual worker processes
        self._target_counts: Dict[str, int] = {}  # Target worker counts per pool
        self._registered_workers: Dict[str, Type] = {}  # Pool -> worker class
        self._listener_task = None  # Background task for LISTEN/NOTIFY
        self._listener_running = False
        self._heartbeat_task = None  # Background task for worker heartbeat
        self._heartbeat_running = False

    def set_event_bus(self, event_bus) -> None:
        """Set event bus for job notifications."""
        self._event_bus = event_bus

    def set_db_pool(self, db_pool) -> None:
        """Set the database connection pool."""
        self._db_pool = db_pool
        self._available = db_pool is not None

    async def initialize(self) -> None:
        """Initialize PostgreSQL connection and start listener."""
        try:
            # Create database pool if not already set
            if self._db_pool is None:
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

                database_url = self.config.database_url if self.config else None
                if not database_url:
                    import os
                    database_url = os.environ.get("DATABASE_URL", "postgresql://arkham:arkhampass@localhost:5432/arkhamdb")

                if database_url:
                    try:
                        self._db_pool = await asyncpg.create_pool(
                            database_url,
                            min_size=2,
                            max_size=10,
                            command_timeout=60,
                            init=init_connection,  # Set up JSON codecs
                        )
                        logger.info(f"WorkerService connected to PostgreSQL")
                    except Exception as e:
                        logger.warning(f"WorkerService failed to connect to PostgreSQL: {e}")
                        self._available = False
                        return
                else:
                    logger.warning("No DATABASE_URL configured for WorkerService")
                    self._available = False
                    return

            # Verify the arkham_jobs schema exists
            async with self._db_pool.acquire() as conn:
                result = await conn.fetchval("""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.schemata
                        WHERE schema_name = 'arkham_jobs'
                    )
                """)
                if not result:
                    logger.warning("arkham_jobs schema not found, job queue unavailable")
                    self._available = False
                    return

            self._available = True
            logger.info("WorkerService initialized with PostgreSQL SKIP LOCKED")

            # Start LISTEN/NOTIFY listener
            await self._start_notify_listener()

            # Start heartbeat task
            await self._start_heartbeat_task()

        except Exception as e:
            logger.warning(f"WorkerService initialization failed: {e}")
            self._available = False

    async def _start_notify_listener(self) -> None:
        """Start background task to listen for PostgreSQL NOTIFY events."""
        self._listener_running = True
        self._listener_task = asyncio.create_task(self._notify_loop())
        logger.info("Started PostgreSQL LISTEN/NOTIFY listener")

    async def _notify_loop(self) -> None:
        """Background loop that listens for NOTIFY events."""
        try:
            # Get a dedicated connection for listening
            conn = await self._db_pool.acquire()
            try:
                # Subscribe to channels
                await conn.add_listener('arkham_job_available', self._handle_job_available)
                await conn.add_listener('arkham_job_completed', self._handle_job_completed)
                await conn.add_listener('arkham_job_failed', self._handle_job_failed)
                await conn.add_listener('arkham_worker_event', self._handle_worker_event)

                logger.info("Subscribed to PostgreSQL NOTIFY channels")

                # Keep connection alive
                while self._listener_running:
                    await asyncio.sleep(1.0)

            finally:
                # Unsubscribe and release
                try:
                    await conn.remove_listener('arkham_job_available', self._handle_job_available)
                    await conn.remove_listener('arkham_job_completed', self._handle_job_completed)
                    await conn.remove_listener('arkham_job_failed', self._handle_job_failed)
                    await conn.remove_listener('arkham_worker_event', self._handle_worker_event)
                except:
                    pass
                await self._db_pool.release(conn)

        except Exception as e:
            logger.error(f"NOTIFY listener error: {e}")

    def _handle_job_available(self, conn, pid, channel, payload):
        """Handle job available notification."""
        try:
            data = json.loads(payload)
            logger.debug(f"Job available: {data.get('pool')} - {data.get('job_id')}")
            # Bridge to EventBus if available
            if self._event_bus:
                asyncio.create_task(self._event_bus.emit(
                    "worker.job.available",
                    data,
                    source="worker-service"
                ))
        except Exception as e:
            logger.warning(f"Failed to handle job available: {e}")

    def _handle_job_completed(self, conn, pid, channel, payload):
        """Handle job completed notification."""
        try:
            data = json.loads(payload)
            job_id = data.get('job_id')
            logger.debug(f"Job completed: {job_id}")

            # Update in-memory cache
            if job_id in self._jobs:
                job = self._jobs[job_id]
                job.status = "completed"
                job.completed_at = datetime.utcnow()

            # Bridge to EventBus
            if self._event_bus:
                asyncio.create_task(self._event_bus.emit(
                    "worker.job.completed",
                    data,
                    source="worker-service"
                ))
        except Exception as e:
            logger.warning(f"Failed to handle job completed: {e}")

    def _handle_job_failed(self, conn, pid, channel, payload):
        """Handle job failed notification."""
        try:
            data = json.loads(payload)
            job_id = data.get('job_id')
            error = data.get('error')
            logger.debug(f"Job failed: {job_id} - {error}")

            # Update in-memory cache
            if job_id in self._jobs:
                job = self._jobs[job_id]
                job.status = "failed"
                job.completed_at = datetime.utcnow()
                job.error = error

            # Bridge to EventBus
            if self._event_bus:
                asyncio.create_task(self._event_bus.emit(
                    "worker.job.failed",
                    data,
                    source="worker-service"
                ))
        except Exception as e:
            logger.warning(f"Failed to handle job failed: {e}")

    def _handle_worker_event(self, conn, pid, channel, payload):
        """Handle worker state change notification."""
        try:
            data = json.loads(payload)
            worker_id = data.get('worker_id')
            event = data.get('event')
            logger.debug(f"Worker event: {worker_id} - {event}")

            # Update in-memory cache
            if worker_id in self._workers:
                self._workers[worker_id].status = event

            # Bridge to EventBus
            if self._event_bus:
                asyncio.create_task(self._event_bus.emit(
                    f"worker.{event}",
                    data,
                    source="worker-service"
                ))
        except Exception as e:
            logger.warning(f"Failed to handle worker event: {e}")

    async def _start_heartbeat_task(self) -> None:
        """Start background task for worker heartbeat and stale worker cleanup."""
        self._heartbeat_running = True
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        logger.info("Started worker heartbeat task")

    async def _heartbeat_loop(self) -> None:
        """Background loop that sends heartbeats and cleans up stale workers."""
        while self._heartbeat_running:
            try:
                # Update heartbeat for all our workers
                if self._available and self._db_pool:
                    async with self._db_pool.acquire() as conn:
                        for worker_id in self._workers:
                            await conn.execute("""
                                UPDATE arkham_jobs.workers
                                SET last_heartbeat = NOW()
                                WHERE id = $1
                            """, worker_id)

                        # Clean up stale workers (2 minute timeout)
                        cleaned = await conn.fetchval("""
                            SELECT arkham_jobs.cleanup_stale_workers(120)
                        """)
                        if cleaned > 0:
                            logger.info(f"Cleaned up {cleaned} stale workers")

                await asyncio.sleep(30)  # Heartbeat every 30 seconds

            except Exception as e:
                logger.warning(f"Heartbeat error: {e}")
                await asyncio.sleep(5)

    async def shutdown(self) -> None:
        """Gracefully shutdown all workers and close connections."""
        # Stop listener
        self._listener_running = False
        if self._listener_task:
            self._listener_task.cancel()
            try:
                await self._listener_task
            except:
                pass
            self._listener_task = None

        # Stop heartbeat
        self._heartbeat_running = False
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except:
                pass
            self._heartbeat_task = None

        # Stop all running workers gracefully
        if self._processes:
            logger.info(f"Shutting down {len(self._processes)} worker(s)...")
            await self._shutdown_all_workers(timeout=30.0)

        # Mark our workers as stopped in database
        if self._available and self._db_pool:
            try:
                async with self._db_pool.acquire() as conn:
                    for worker_id in self._workers:
                        await conn.execute("""
                            UPDATE arkham_jobs.workers
                            SET state = 'stopped'
                            WHERE id = $1
                        """, worker_id)
            except:
                pass

        self._available = False
        logger.info("WorkerService shutdown complete")

    async def _shutdown_all_workers(self, timeout: float = 30.0) -> None:
        """Gracefully shutdown all workers, waiting for current jobs to complete."""
        if not self._processes:
            return

        # Send terminate signal to all workers
        for worker_id, worker_proc in list(self._processes.items()):
            if worker_proc.is_alive:
                try:
                    worker_proc.process.terminate()
                    logger.info(f"Sent shutdown signal to worker {worker_id}")
                except (ProcessLookupError, OSError):
                    pass

        # Wait for all workers to finish
        start = time.time()
        while self._processes and (time.time() - start) < timeout:
            still_alive = []
            for worker_id, worker_proc in list(self._processes.items()):
                if worker_proc.is_alive:
                    still_alive.append(worker_id)
                else:
                    del self._processes[worker_id]
                    if worker_id in self._workers:
                        del self._workers[worker_id]
                    logger.info(f"Worker {worker_id} stopped gracefully")

            if not still_alive:
                break

            time.sleep(0.5)

        # Force kill any remaining workers
        for worker_id, worker_proc in list(self._processes.items()):
            if worker_proc.is_alive:
                logger.warning(f"Force killing worker {worker_id} (timeout exceeded)")
                try:
                    worker_proc.process.kill()
                except (ProcessLookupError, OSError):
                    pass
            del self._processes[worker_id]
            if worker_id in self._workers:
                del self._workers[worker_id]

    def is_available(self) -> bool:
        """Check if job queue is available."""
        return self._available

    # --- Job Queuing ---

    async def enqueue(
        self,
        pool: str,
        job_id: str,
        payload: Dict[str, Any],
        priority: int = 5,
        job_type: str = "default",
        max_retries: int = 3,
        scheduled_at: Optional[datetime] = None,
    ) -> Job:
        """
        Enqueue a job to a worker pool.

        Args:
            pool: Worker pool name (e.g., "cpu-light", "gpu-paddle")
            job_id: Unique job identifier
            payload: Job data
            priority: Priority level (1-10, lower = higher priority)
            job_type: Job type identifier
            max_retries: Maximum retry attempts
            scheduled_at: Optional scheduled time (None = immediate)

        Returns:
            Created Job object
        """
        if pool not in WORKER_POOLS:
            raise WorkerError(f"Unknown worker pool: {pool}")

        # arkham_jobs.jobs.id is VARCHAR(36); avoid StringDataRightTruncationError from any caller
        if len(job_id) > 36:
            logger.warning(
                "job_id longer than VARCHAR(36), using generated UUID (original_len=%s, prefix=%r)",
                len(job_id),
                job_id[:40],
            )
            job_id = str(uuid.uuid4())

        # Clamp priority to valid range
        priority = max(1, min(10, priority))

        status = "scheduled" if scheduled_at else "pending"

        job = Job(
            id=job_id,
            pool=pool,
            payload=payload,
            job_type=job_type,
            priority=priority,
            status=status,
            max_retries=max_retries,
            scheduled_at=scheduled_at,
        )

        self._jobs[job_id] = job

        if self._available and self._db_pool:
            async with self._db_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO arkham_jobs.jobs
                    (id, pool, job_type, payload, priority, status, scheduled_at, max_retries)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    ON CONFLICT (id) DO UPDATE SET
                        pool = EXCLUDED.pool,
                        payload = EXCLUDED.payload,
                        priority = EXCLUDED.priority,
                        status = EXCLUDED.status
                """, job_id, pool, job_type, json.dumps(payload), priority,
                    status, scheduled_at, max_retries)

            logger.debug(f"Enqueued job {job_id} to {pool} (priority={priority})")
        else:
            logger.warning(f"Database unavailable, job {job_id} tracked in memory only")

        # Auto-scale: ensure at least one worker is running for this pool
        await self._ensure_worker_for_pool(pool)

        return job

    async def _ensure_worker_for_pool(self, pool: str) -> None:
        """Ensure at least one worker is running for the given pool."""
        running = sum(
            1 for wp in self._processes.values()
            if wp.pool == pool and wp.is_alive
        )

        if running == 0:
            logger.info(f"Auto-scaling: spawning worker for pool {pool}")
            try:
                await self.scale(pool, 1)
            except Exception as e:
                logger.warning(f"Failed to auto-scale pool {pool}: {e}")

    async def dequeue(self, pool: str, worker_id: str) -> Optional[Job]:
        """
        Dequeue the highest priority job from a pool using SKIP LOCKED.

        This is the key PostgreSQL pattern for concurrent job processing.
        SKIP LOCKED ensures multiple workers don't get the same job.

        Args:
            pool: Worker pool name
            worker_id: ID of the worker claiming the job

        Returns:
            Job if available, None otherwise
        """
        if not self._available or not self._db_pool:
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
                          retry_count, max_retries,
                          COALESCE(worker_requeue_count, 0) AS worker_requeue_count,
                          COALESCE(max_worker_requeues, 3) AS max_worker_requeues
            """, pool, worker_id)

            if not row:
                return None

            job = Job(
                id=row['id'],
                pool=row['pool'],
                job_type=row['job_type'],
                payload=json.loads(row['payload']) if isinstance(row['payload'], str) else row['payload'],
                priority=row['priority'],
                created_at=row['created_at'],
                status="processing",
                started_at=datetime.utcnow(),
                retry_count=row['retry_count'],
                max_retries=row['max_retries'],
                worker_requeue_count=row['worker_requeue_count'],
                max_worker_requeues=row['max_worker_requeues'],
                worker_id=worker_id,
            )

            self._jobs[job.id] = job
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

        if self._available and self._db_pool:
            async with self._db_pool.acquire() as conn:
                await conn.execute("""
                    UPDATE arkham_jobs.jobs
                    SET status = 'completed',
                        completed_at = NOW(),
                        result = $2
                    WHERE id = $1
                """, job_id, json.dumps(result or {}))

        # Emit event
        if self._event_bus:
            await self._event_bus.emit(
                "worker.job.completed",
                {"job_id": job_id, "result": result},
                source="worker-service",
            )

    async def fail_job(
        self,
        job_id: str,
        error: str,
        should_retry: bool = True,
    ) -> None:
        """
        Mark a job as failed.

        If retry is enabled and retries remain, re-queue the job.
        Otherwise, move to dead letter queue.
        """
        job = self._jobs.get(job_id)

        if self._available and self._db_pool:
            async with self._db_pool.acquire() as conn:
                # Get current job state
                row = await conn.fetchrow("""
                    SELECT pool, job_type, payload, retry_count, max_retries
                    FROM arkham_jobs.jobs WHERE id = $1
                """, job_id)

                if not row:
                    return

                retry_count = row['retry_count']
                max_retries = row['max_retries']

                if should_retry and retry_count < max_retries:
                    # Re-queue with incremented retry count
                    await conn.execute("""
                        UPDATE arkham_jobs.jobs
                        SET status = 'pending',
                            started_at = NULL,
                            worker_id = NULL,
                            retry_count = retry_count + 1,
                            last_error = $2
                        WHERE id = $1
                    """, job_id, error)
                    logger.info(f"Job {job_id} retrying ({retry_count + 1}/{max_retries})")
                else:
                    # Move to dead letter queue
                    await conn.execute("""
                        INSERT INTO arkham_jobs.dead_letters
                        (job_id, pool, job_type, payload, error, retry_count, original_created_at)
                        SELECT id, pool, job_type, payload, $2, retry_count, created_at
                        FROM arkham_jobs.jobs WHERE id = $1
                    """, job_id, error)

                    await conn.execute("""
                        UPDATE arkham_jobs.jobs
                        SET status = 'dead',
                            completed_at = NOW(),
                            last_error = $2
                        WHERE id = $1
                    """, job_id, error)
                    logger.warning(f"Job {job_id} moved to dead letter queue: {error}")

        if job:
            job.status = "failed"
            job.completed_at = datetime.utcnow()
            job.error = error

        # Emit event
        if self._event_bus:
            await self._event_bus.emit(
                "worker.job.failed",
                {"job_id": job_id, "error": error},
                source="worker-service",
            )

    def get_job(self, job_id: str) -> Optional[Job]:
        """Get a job by ID from cache."""
        return self._jobs.get(job_id)

    async def get_job_from_db(self, job_id: str) -> Optional[Job]:
        """Get a job by ID from database."""
        if not self._available or not self._db_pool:
            return self._jobs.get(job_id)

        async with self._db_pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT id, pool, job_type, payload, priority, status,
                       created_at, scheduled_at, started_at, completed_at,
                       worker_id, retry_count, max_retries, last_error, result,
                       COALESCE(worker_requeue_count, 0) AS worker_requeue_count,
                       COALESCE(max_worker_requeues, 3) AS max_worker_requeues
                FROM arkham_jobs.jobs WHERE id = $1
            """, job_id)

            if not row:
                return None

            return Job(
                id=row['id'],
                pool=row['pool'],
                job_type=row['job_type'],
                payload=json.loads(row['payload']) if isinstance(row['payload'], str) else row['payload'],
                priority=row['priority'],
                status=row['status'],
                created_at=row['created_at'],
                scheduled_at=row['scheduled_at'],
                started_at=row['started_at'],
                completed_at=row['completed_at'],
                worker_id=row['worker_id'],
                retry_count=row['retry_count'],
                max_retries=row['max_retries'],
                worker_requeue_count=row['worker_requeue_count'],
                max_worker_requeues=row['max_worker_requeues'],
                error=row['last_error'],
                result=json.loads(row['result']) if isinstance(row['result'], str) else row['result'],
            )

    async def get_job_result(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Get just the result field for a job.

        This is more efficient than get_job_from_db when you only need the result.

        Args:
            job_id: Job ID to fetch result for

        Returns:
            Result dict, or None if job not found or has no result
        """
        if not self._available or not self._db_pool:
            # Check cache
            job = self._jobs.get(job_id)
            return job.result if job else None

        async with self._db_pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT result FROM arkham_jobs.jobs WHERE id = $1
            """, job_id)

            if not row or not row['result']:
                return None

            result = row['result']
            if isinstance(result, str):
                return json.loads(result)
            return result

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
                "scheduled": 0,
                "processing": 0,
                "completed": 0,
                "failed": 0,
                "dead": 0,
            }

            if self._available and self._db_pool:
                async with self._db_pool.acquire() as conn:
                    rows = await conn.fetch("""
                        SELECT status, COUNT(*) as count
                        FROM arkham_jobs.jobs
                        WHERE pool = $1
                        GROUP BY status
                    """, pool_name)

                    for row in rows:
                        if row['status'] in pool_stats:
                            pool_stats[row['status']] = row['count']

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
            "scheduled": 0,
            "processing": 0,
            "completed": 0,
            "failed": 0,
            "dead": 0,
            "workers_active": self.get_worker_count(pool),
            "workers_target": self.get_target_count(pool),
        }

        if self._available and self._db_pool:
            async with self._db_pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT status, COUNT(*) as count
                    FROM arkham_jobs.jobs
                    WHERE pool = $1
                    GROUP BY status
                """, pool)

                for row in rows:
                    if row['status'] in stats:
                        stats[row['status']] = row['count']

        return stats

    # --- Worker Management ---

    async def get_workers(self) -> List[Dict[str, Any]]:
        """Get active workers with process info."""
        self._cleanup_dead_processes()
        workers = []

        # Get workers from database
        if self._available and self._db_pool:
            async with self._db_pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT id, pool, name, hostname, pid, state,
                           jobs_completed, jobs_failed, current_job,
                           started_at, last_heartbeat
                    FROM arkham_jobs.workers
                    WHERE state NOT IN ('stopped', 'error')
                    ORDER BY started_at DESC
                """)

                for row in rows:
                    workers.append({
                        "id": row['id'],
                        "pool": row['pool'],
                        "name": row['name'],
                        "hostname": row['hostname'],
                        "pid": row['pid'],
                        "status": row['state'],
                        "jobs_completed": row['jobs_completed'],
                        "jobs_failed": row['jobs_failed'],
                        "current_job_id": row['current_job'],
                        "started_at": row['started_at'].isoformat() if row['started_at'] else None,
                        "last_heartbeat": row['last_heartbeat'].isoformat() if row['last_heartbeat'] else None,
                        "uptime_seconds": (datetime.utcnow() - row['started_at']).total_seconds() if row['started_at'] else 0,
                    })

        return workers

    async def get_workers_by_pool(self, pool: str) -> List[Dict[str, Any]]:
        """Get workers for a specific pool."""
        all_workers = await self.get_workers()
        return [w for w in all_workers if w.get('pool') == pool]

    def get_worker_count(self, pool: str) -> int:
        """Get number of active workers for a pool."""
        self._cleanup_dead_processes()
        return sum(1 for p in self._processes.values() if p.pool == pool and p.is_alive)

    def get_target_count(self, pool: str) -> int:
        """Get target worker count for a pool."""
        return self._target_counts.get(pool, 0)

    def _cleanup_dead_processes(self) -> int:
        """Remove dead processes from tracking."""
        dead = [
            wid for wid, wp in self._processes.items()
            if not wp.is_alive
        ]
        for worker_id in dead:
            del self._processes[worker_id]
            if worker_id in self._workers:
                del self._workers[worker_id]
        return len(dead)

    def _get_worker_class(self, pool: str) -> Optional[Type]:
        """Get the worker class for a pool."""
        if pool in self._registered_workers:
            return self._registered_workers[pool]

        try:
            from arkham_frame.workers.cli import get_worker_class
            return get_worker_class(pool)
        except ImportError:
            return None

    def _spawn_worker_process(self, pool: str, worker_id: str) -> Optional[WorkerProcess]:
        """Spawn a worker subprocess."""
        worker_class = self._get_worker_class(pool)
        if not worker_class:
            logger.error(f"No worker class registered for pool {pool}")
            return None

        # Get database URL from config
        database_url = getattr(self.config, 'database_url', None) or 'postgresql://arkham:arkhampass@localhost:5432/arkhamdb'

        # Set DATA_SILO_PATH for workers
        data_silo_path = getattr(self.config, 'data_silo_path', None) or "./data_silo"
        os.environ["DATA_SILO_PATH"] = str(Path(data_silo_path).resolve())

        from arkham_frame.workers.base import run_worker

        process = multiprocessing.Process(
            target=run_worker,
            args=(worker_class, database_url, worker_id),
            name=f"worker-{worker_id}",
            daemon=False,
        )

        process.start()

        worker_proc = WorkerProcess(
            worker_id=worker_id,
            pool=pool,
            process=process,
        )

        self._processes[worker_id] = worker_proc
        logger.info(f"Spawned worker {worker_id} (PID {process.pid}) for pool {pool}")

        return worker_proc

    def _kill_worker_process(self, worker_id: str, timeout: float = 5.0) -> bool:
        """Kill a worker process."""
        if worker_id not in self._processes:
            return False

        worker_proc = self._processes[worker_id]

        if not worker_proc.is_alive:
            del self._processes[worker_id]
            return True

        try:
            worker_proc.process.terminate()
        except (ProcessLookupError, OSError):
            del self._processes[worker_id]
            return True

        start = time.time()
        while worker_proc.is_alive and (time.time() - start) < timeout:
            time.sleep(0.1)

        if worker_proc.is_alive:
            try:
                worker_proc.process.kill()
            except (ProcessLookupError, OSError):
                pass

        del self._processes[worker_id]
        return True

    async def scale(self, pool: str, count: int) -> Dict[str, Any]:
        """Scale workers for a pool."""
        if pool not in WORKER_POOLS:
            raise WorkerError(f"Unknown pool: {pool}")

        max_workers = WORKER_POOLS[pool]["max_workers"]
        if count > max_workers:
            logger.warning(f"Requested {count} workers for {pool}, max is {max_workers}")
            count = max_workers
        if count < 0:
            count = 0

        old_count = self._target_counts.get(pool, 0)
        self._target_counts[pool] = count

        current_count = self.get_worker_count(pool)

        if count > current_count:
            for _ in range(count - current_count):
                await self.start_worker(pool)
        elif count < current_count:
            pool_workers = [w for w in self._workers.values() if w.pool == pool]
            for worker in pool_workers[count:]:
                await self.stop_worker(worker.id)

        logger.info(f"Scaled {pool} from {old_count} to {count} workers")

        if self._event_bus:
            await self._event_bus.emit(
                "worker.pool.scaled",
                {"pool": pool, "old_count": old_count, "new_count": count},
                source="worker-service",
            )

        return {
            "success": True,
            "pool": pool,
            "previous_count": old_count,
            "target_count": count,
            "current_count": self.get_worker_count(pool),
        }

    async def start_worker(self, pool: str) -> Dict[str, Any]:
        """Start a worker for a pool by spawning a subprocess."""
        if pool not in WORKER_POOLS:
            return {"success": False, "error": f"Unknown pool: {pool}"}

        worker_class = self._get_worker_class(pool)
        if not worker_class:
            return {
                "success": False,
                "error": f"No worker implementation for pool {pool}",
            }

        current_count = self.get_worker_count(pool)
        max_workers = WORKER_POOLS[pool]["max_workers"]
        if current_count >= max_workers:
            return {
                "success": False,
                "error": f"Pool {pool} already at max workers ({max_workers})",
            }

        worker_id = f"{pool}-{uuid.uuid4().hex[:8]}"
        worker_proc = self._spawn_worker_process(pool, worker_id)

        if not worker_proc:
            return {
                "success": False,
                "error": f"Failed to spawn worker for pool {pool}",
            }

        # Register worker in database
        if self._available and self._db_pool:
            try:
                import socket
                hostname = socket.gethostname()
                async with self._db_pool.acquire() as conn:
                    await conn.execute("""
                        INSERT INTO arkham_jobs.workers
                        (id, pool, name, hostname, pid, state)
                        VALUES ($1, $2, $3, $4, $5, 'starting')
                    """, worker_id, pool, f"worker-{worker_id}", hostname, worker_proc.pid)
            except Exception as e:
                logger.warning(f"Failed to register worker in database: {e}")

        worker = WorkerInfo(id=worker_id, pool=pool, pid=worker_proc.pid)
        self._workers[worker_id] = worker

        logger.info(f"Started worker {worker_id} (PID {worker_proc.pid}) for pool {pool}")

        if self._event_bus:
            await self._event_bus.emit(
                "worker.started",
                {"worker_id": worker_id, "pool": pool, "pid": worker_proc.pid},
                source="worker-service",
            )

        return {"success": True, "worker_id": worker_id, "pool": pool, "pid": worker_proc.pid}

    async def stop_worker(self, worker_id: str) -> Dict[str, Any]:
        """Stop a worker by killing its process."""
        if worker_id not in self._workers and worker_id not in self._processes:
            return {"success": False, "error": f"Worker {worker_id} not found"}

        pool = None
        if worker_id in self._workers:
            worker = self._workers[worker_id]
            pool = worker.pool
            worker.status = "stopping"

        if worker_id in self._processes:
            if not pool:
                pool = self._processes[worker_id].pool
            self._kill_worker_process(worker_id)

        # Update database
        if self._available and self._db_pool:
            try:
                async with self._db_pool.acquire() as conn:
                    await conn.execute("""
                        UPDATE arkham_jobs.workers
                        SET state = 'stopped'
                        WHERE id = $1
                    """, worker_id)
            except:
                pass

        if worker_id in self._workers:
            del self._workers[worker_id]

        logger.info(f"Stopped worker {worker_id}")

        if self._event_bus and pool:
            await self._event_bus.emit(
                "worker.stopped",
                {"worker_id": worker_id, "pool": pool},
                source="worker-service",
            )

        return {"success": True, "worker_id": worker_id}

    async def stop_all_workers(self, pool: Optional[str] = None) -> Dict[str, Any]:
        """Stop all workers, optionally filtered by pool."""
        stopped = []

        worker_ids = set(self._workers.keys()) | set(self._processes.keys())

        for worker_id in worker_ids:
            worker_pool = None
            if worker_id in self._workers:
                worker_pool = self._workers[worker_id].pool
            elif worker_id in self._processes:
                worker_pool = self._processes[worker_id].pool

            if pool and worker_pool != pool:
                continue

            result = await self.stop_worker(worker_id)
            if result["success"]:
                stopped.append(worker_id)

        return {"success": True, "stopped": stopped, "count": len(stopped)}

    def register_handler(self, pool: str, handler: Callable) -> None:
        """Register a job handler for a pool."""
        self._handlers[pool] = handler
        logger.info(f"Registered handler for pool {pool}")

    # --- Worker Registration (for shards) ---

    def register_worker(self, worker_class: type) -> None:
        """Register a worker class from a shard."""
        pool = getattr(worker_class, "pool", None)
        if not pool:
            raise WorkerError(f"Worker class {worker_class.__name__} has no pool attribute")

        if pool not in WORKER_POOLS:
            logger.warning(f"Worker pool {pool} not in predefined pools, adding dynamically")
            WORKER_POOLS[pool] = {"type": "custom", "max_workers": 4}

        self._registered_workers[pool] = worker_class
        logger.info(f"Registered worker {worker_class.__name__} for pool {pool}")

    def unregister_worker(self, worker_class: type) -> None:
        """Unregister a worker class."""
        pool = getattr(worker_class, "pool", None)
        if pool and pool in self._registered_workers:
            del self._registered_workers[pool]
            logger.info(f"Unregistered worker for pool {pool}")

    def get_registered_workers(self) -> Dict[str, type]:
        """Get all registered worker classes."""
        return self._registered_workers.copy()

    def get_worker_class(self, pool: str) -> Optional[type]:
        """Get the worker class for a pool."""
        return self._registered_workers.get(pool)

    # --- Job Result Waiting ---

    async def wait_for_result(
        self,
        job_id: str,
        timeout: float = 300.0,
        poll_interval: float = 0.5,
    ) -> Dict[str, Any]:
        """Wait for a job to complete and return its result."""
        start_time = asyncio.get_event_loop().time()

        while True:
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed > timeout:
                raise WorkerError(f"Job {job_id} timed out after {timeout}s")

            # Check in-memory cache for status (not result - result comes from DB)
            job = self._jobs.get(job_id)
            if job:
                if job.status in ("failed", "dead"):
                    raise WorkerError(f"Job {job_id} failed: {job.error}")

            # Check database for status and result
            # Always fetch result from DB since NOTIFY doesn't include it
            if self._available and self._db_pool:
                async with self._db_pool.acquire() as conn:
                    row = await conn.fetchrow("""
                        SELECT status, result, last_error
                        FROM arkham_jobs.jobs WHERE id = $1
                    """, job_id)

                    if row:
                        if row['status'] == 'completed':
                            result = row['result']
                            if isinstance(result, str):
                                result = json.loads(result)
                            return result or {}
                        elif row['status'] in ('failed', 'dead'):
                            raise WorkerError(f"Job {job_id} failed: {row['last_error']}")

            await asyncio.sleep(poll_interval)

    async def enqueue_and_wait(
        self,
        pool: str,
        payload: Dict[str, Any],
        priority: int = 5,
        timeout: float = 300.0,
        job_type: str = "default",
    ) -> Dict[str, Any]:
        """Enqueue a job and wait for its result."""
        job_id = str(uuid.uuid4())
        await self.enqueue(pool, job_id, payload, priority, job_type)
        return await self.wait_for_result(job_id, timeout)

    # --- Queue Management ---

    async def get_jobs(
        self,
        pool: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Get jobs with optional filtering."""
        jobs = []

        if self._available and self._db_pool:
            async with self._db_pool.acquire() as conn:
                query = """
                    SELECT id, pool, job_type, status, priority,
                           payload, result, last_error,
                           created_at, scheduled_at, started_at, completed_at,
                           worker_id, retry_count, max_retries,
                           COALESCE(worker_requeue_count, 0) AS worker_requeue_count,
                           COALESCE(max_worker_requeues, 3) AS max_worker_requeues
                    FROM arkham_jobs.jobs
                    WHERE 1=1
                """
                params = []
                param_count = 0

                if pool:
                    param_count += 1
                    query += f" AND pool = ${param_count}"
                    params.append(pool)

                if status:
                    param_count += 1
                    query += f" AND status = ${param_count}"
                    params.append(status)

                query += " ORDER BY created_at DESC"
                param_count += 1
                query += f" LIMIT ${param_count}"
                params.append(limit)
                param_count += 1
                query += f" OFFSET ${param_count}"
                params.append(offset)

                rows = await conn.fetch(query, *params)

                for row in rows:
                    jobs.append({
                        "id": row['id'],
                        "pool": row['pool'],
                        "job_type": row['job_type'],
                        "status": row['status'],
                        "priority": row['priority'],
                        "payload": row['payload'] if isinstance(row['payload'], dict) else json.loads(row['payload']) if row['payload'] else {},
                        "result": row['result'] if isinstance(row['result'], dict) else json.loads(row['result']) if row['result'] else None,
                        "error": row['last_error'],
                        "created_at": row['created_at'].isoformat() if row['created_at'] else None,
                        "scheduled_at": row['scheduled_at'].isoformat() if row['scheduled_at'] else None,
                        "started_at": row['started_at'].isoformat() if row['started_at'] else None,
                        "completed_at": row['completed_at'].isoformat() if row['completed_at'] else None,
                        "worker_id": row['worker_id'],
                        "retry_count": row['retry_count'],
                        "max_retries": row['max_retries'],
                        "worker_requeue_count": row['worker_requeue_count'],
                        "max_worker_requeues": row['max_worker_requeues'],
                    })

        return jobs

    async def clear_queue(
        self,
        pool: str,
        status: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Clear jobs from a queue."""
        if pool not in WORKER_POOLS:
            raise WorkerError(f"Unknown pool: {pool}")

        if status is None:
            status = "pending"

        cleared = 0

        if self._available and self._db_pool:
            async with self._db_pool.acquire() as conn:
                result = await conn.execute("""
                    DELETE FROM arkham_jobs.jobs
                    WHERE pool = $1 AND status = $2
                """, pool, status)
                # Parse "DELETE N" result
                cleared = int(result.split()[-1])

        # Clear from in-memory cache
        jobs_to_remove = [
            job_id for job_id, job in self._jobs.items()
            if job.pool == pool and job.status == status
        ]
        for job_id in jobs_to_remove:
            del self._jobs[job_id]

        cleared = max(cleared, len(jobs_to_remove))

        logger.info(f"Cleared {cleared} {status} jobs from {pool}")

        if self._event_bus:
            await self._event_bus.emit(
                "worker.queue.cleared",
                {"pool": pool, "status": status, "count": cleared},
                source="worker-service",
            )

        return {"success": True, "pool": pool, "status": status, "cleared": cleared}

    async def retry_failed_jobs(
        self,
        pool: str,
        job_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Retry failed jobs by re-enqueueing them."""
        if pool not in WORKER_POOLS:
            raise WorkerError(f"Unknown pool: {pool}")

        retried = []

        if self._available and self._db_pool:
            async with self._db_pool.acquire() as conn:
                # Get failed jobs
                if job_ids:
                    rows = await conn.fetch("""
                        SELECT id, payload, priority, job_type
                        FROM arkham_jobs.jobs
                        WHERE pool = $1 AND status IN ('failed', 'dead') AND id = ANY($2)
                    """, pool, job_ids)
                else:
                    rows = await conn.fetch("""
                        SELECT id, payload, priority, job_type
                        FROM arkham_jobs.jobs
                        WHERE pool = $1 AND status IN ('failed', 'dead')
                    """, pool)

                for row in rows:
                    # job id must fit VARCHAR(36); use fresh UUID instead of prefixing original
                    new_job_id = str(uuid.uuid4())
                    payload = row['payload'] if isinstance(row['payload'], dict) else json.loads(row['payload'])

                    await conn.execute("""
                        INSERT INTO arkham_jobs.jobs
                        (id, pool, job_type, payload, priority, status)
                        VALUES ($1, $2, $3, $4, $5, 'pending')
                    """, new_job_id, pool, row['job_type'], json.dumps(payload), row['priority'])

                    # Remove old failed job
                    await conn.execute("""
                        DELETE FROM arkham_jobs.jobs WHERE id = $1
                    """, row['id'])

                    retried.append({"original_id": row['id'], "new_id": new_job_id})

        logger.info(f"Retried {len(retried)} failed jobs in {pool}")

        if self._event_bus:
            await self._event_bus.emit(
                "worker.jobs.retried",
                {"pool": pool, "count": len(retried), "jobs": retried},
                source="worker-service",
            )

        return {"success": True, "pool": pool, "retried": retried, "count": len(retried)}

    async def cancel_job(self, job_id: str) -> Dict[str, Any]:
        """Cancel a pending job."""
        if self._available and self._db_pool:
            async with self._db_pool.acquire() as conn:
                result = await conn.execute("""
                    UPDATE arkham_jobs.jobs
                    SET status = 'failed',
                        completed_at = NOW(),
                        last_error = 'Cancelled by user'
                    WHERE id = $1 AND status IN ('pending', 'scheduled')
                """, job_id)

                if "UPDATE 0" in result:
                    return {"success": False, "error": f"Job {job_id} not found or not cancellable"}

        job = self._jobs.get(job_id)
        if job and job.status in ("pending", "scheduled"):
            job.status = "failed"
            job.completed_at = datetime.utcnow()
            job.error = "Cancelled by user"

        logger.info(f"Cancelled job {job_id}")

        if self._event_bus:
            await self._event_bus.emit(
                "worker.job.cancelled",
                {"job_id": job_id},
                source="worker-service",
            )

        return {"success": True, "job_id": job_id}

    def get_pool_info(self) -> List[Dict[str, Any]]:
        """Get information about all worker pools."""
        return [
            {
                "name": name,
                "type": config["type"],
                "max_workers": config["max_workers"],
                "vram_mb": config.get("vram_mb"),
                "current_workers": self.get_worker_count(name),
                "target_workers": self.get_target_count(name),
            }
            for name, config in WORKER_POOLS.items()
        ]

    # --- Dead Letter Queue Management ---

    async def get_dead_letters(
        self,
        pool: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get jobs from the dead letter queue."""
        if not self._available or not self._db_pool:
            return []

        async with self._db_pool.acquire() as conn:
            if pool:
                rows = await conn.fetch("""
                    SELECT id, job_id, pool, job_type, payload, error,
                           retry_count, original_created_at, failed_at,
                           reprocessed_at, reprocessed_job_id
                    FROM arkham_jobs.dead_letters
                    WHERE pool = $1 AND reprocessed_at IS NULL
                    ORDER BY failed_at DESC
                    LIMIT $2
                """, pool, limit)
            else:
                rows = await conn.fetch("""
                    SELECT id, job_id, pool, job_type, payload, error,
                           retry_count, original_created_at, failed_at,
                           reprocessed_at, reprocessed_job_id
                    FROM arkham_jobs.dead_letters
                    WHERE reprocessed_at IS NULL
                    ORDER BY failed_at DESC
                    LIMIT $1
                """, limit)

            return [
                {
                    "id": row['id'],
                    "job_id": row['job_id'],
                    "pool": row['pool'],
                    "job_type": row['job_type'],
                    "payload": row['payload'] if isinstance(row['payload'], dict) else json.loads(row['payload']) if row['payload'] else {},
                    "error": row['error'],
                    "retry_count": row['retry_count'],
                    "original_created_at": row['original_created_at'].isoformat() if row['original_created_at'] else None,
                    "failed_at": row['failed_at'].isoformat() if row['failed_at'] else None,
                }
                for row in rows
            ]

    async def reprocess_dead_letter(self, dlq_id: int) -> Dict[str, Any]:
        """Reprocess a job from the dead letter queue."""
        if not self._available or not self._db_pool:
            return {"success": False, "error": "Database unavailable"}

        async with self._db_pool.acquire() as conn:
            # Get the dead letter
            row = await conn.fetchrow("""
                SELECT job_id, pool, job_type, payload
                FROM arkham_jobs.dead_letters
                WHERE id = $1 AND reprocessed_at IS NULL
            """, dlq_id)

            if not row:
                return {"success": False, "error": f"Dead letter {dlq_id} not found"}

            # Create new job (id must fit VARCHAR(36); use fresh UUID)
            new_job_id = str(uuid.uuid4())
            payload = row['payload'] if isinstance(row['payload'], dict) else json.loads(row['payload'])

            await conn.execute("""
                INSERT INTO arkham_jobs.jobs
                (id, pool, job_type, payload, status)
                VALUES ($1, $2, $3, $4, 'pending')
            """, new_job_id, row['pool'], row['job_type'], json.dumps(payload))

            # Mark dead letter as reprocessed
            await conn.execute("""
                UPDATE arkham_jobs.dead_letters
                SET reprocessed_at = NOW(), reprocessed_job_id = $2
                WHERE id = $1
            """, dlq_id, new_job_id)

            logger.info(f"Reprocessed dead letter {dlq_id} as job {new_job_id}")

            return {"success": True, "dlq_id": dlq_id, "new_job_id": new_job_id}
