"""
WorkerService - Redis queue and worker management.

Implements the worker pool architecture from WORKER_ARCHITECTURE.md.
Includes integrated process spawning for workers.
"""

from typing import List, Dict, Any, Optional, Callable, Type
from dataclasses import dataclass, field
from datetime import datetime
import json
import logging
import multiprocessing
import os
from pathlib import Path
import time
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


@dataclass
class WorkerInfo:
    """Information about a running worker."""
    id: str
    pool: str
    status: str = "idle"  # idle, processing, stopping
    started_at: datetime = field(default_factory=datetime.utcnow)
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
        self._workers: Dict[str, WorkerInfo] = {}  # Active workers (metadata)
        self._processes: Dict[str, WorkerProcess] = {}  # Actual worker processes
        self._target_counts: Dict[str, int] = {}  # Target worker counts per pool
        self._registered_workers: Dict[str, Type] = {}  # Pool -> worker class
        self._pubsub_task = None  # Background task for Redis pubsub
        self._pubsub_running = False

    def set_event_bus(self, event_bus) -> None:
        """Set event bus for job notifications."""
        self._event_bus = event_bus

    async def initialize(self) -> None:
        """Initialize Redis connection and start pubsub listener."""
        try:
            import redis

            self._redis = redis.from_url(self.config.redis_url)
            self._redis.ping()
            self._available = True
            logger.info(f"Redis connected: {self.config.redis_url}")

            # Start pubsub listener to receive worker events
            await self._start_pubsub_listener()
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}")
            self._available = False

    async def _start_pubsub_listener(self) -> None:
        """Start background task to listen for Redis pubsub events from workers."""
        import asyncio

        self._pubsub_running = True
        self._pubsub_task = asyncio.create_task(self._pubsub_loop())
        logger.info("Started Redis pubsub listener for worker events")

    async def _pubsub_loop(self) -> None:
        """Background loop that listens for worker events on Redis pubsub."""
        import asyncio
        import redis.asyncio as aioredis

        try:
            # Create async Redis connection for pubsub
            async_redis = aioredis.from_url(self.config.redis_url)
            pubsub = async_redis.pubsub()
            await pubsub.subscribe("arkham:events")

            while self._pubsub_running:
                try:
                    message = await asyncio.wait_for(
                        pubsub.get_message(ignore_subscribe_messages=True),
                        timeout=1.0
                    )
                    if message and message["type"] == "message":
                        await self._handle_pubsub_message(message["data"])
                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    logger.warning(f"Pubsub message error: {e}")
                    await asyncio.sleep(1.0)

        except Exception as e:
            logger.error(f"Pubsub loop error: {e}")
        finally:
            try:
                await pubsub.unsubscribe("arkham:events")
                await async_redis.close()
            except:
                pass

    async def _handle_pubsub_message(self, data: bytes) -> None:
        """Handle a message from Redis pubsub."""
        try:
            if isinstance(data, bytes):
                data = data.decode()
            event_data = json.loads(data)

            event_type = event_data.pop("event", None)
            if not event_type:
                return

            # Update internal job tracking
            job_id = event_data.get("job_id")
            if job_id and job_id in self._jobs:
                job = self._jobs[job_id]
                if event_type == "worker.job.completed":
                    job.status = "completed"
                    job.completed_at = datetime.utcnow()
                    job.result = event_data.get("result")
                elif event_type == "worker.job.failed":
                    job.status = "failed"
                    job.completed_at = datetime.utcnow()
                    job.error = event_data.get("error")

            # Bridge to Frame's EventBus
            if self._event_bus:
                await self._event_bus.emit(event_type, event_data, source="worker-service")
                logger.debug(f"Bridged event {event_type} to EventBus")

        except Exception as e:
            logger.warning(f"Failed to handle pubsub message: {e}")

    async def shutdown(self) -> None:
        """Gracefully shutdown all workers and close Redis connection."""
        # Stop pubsub listener
        self._pubsub_running = False
        if self._pubsub_task:
            self._pubsub_task.cancel()
            try:
                await self._pubsub_task
            except:
                pass
            self._pubsub_task = None

        # Stop all running workers gracefully
        if self._processes:
            logger.info(f"Shutting down {len(self._processes)} worker(s)...")
            await self._shutdown_all_workers(timeout=30.0)

        if self._redis:
            self._redis.close()
        self._available = False
        logger.info("WorkerService shutdown complete")

    async def _shutdown_all_workers(self, timeout: float = 30.0) -> None:
        """Gracefully shutdown all workers, waiting for current jobs to complete."""
        if not self._processes:
            return

        # Send terminate signal to all workers (they will finish current job)
        for worker_id, worker_proc in list(self._processes.items()):
            if worker_proc.is_alive:
                try:
                    worker_proc.process.terminate()
                    logger.info(f"Sent shutdown signal to worker {worker_id}")
                except (ProcessLookupError, OSError):
                    pass

        # Wait for all workers to finish (with timeout)
        start = time.time()
        while self._processes and (time.time() - start) < timeout:
            # Check which workers are still alive
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

            # Wait a bit before checking again
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

        # Auto-scale: ensure at least one worker is running for this pool
        await self._ensure_worker_for_pool(pool)

        return job

    async def _ensure_worker_for_pool(self, pool: str) -> None:
        """Ensure at least one worker is running for the given pool."""
        # Count running workers for this pool
        running = sum(
            1 for wp in self._processes.values()
            if wp.pool == pool and wp.is_alive
        )

        if running == 0:
            # No workers running, spawn one
            logger.info(f"Auto-scaling: spawning worker for pool {pool}")
            try:
                await self.scale(pool, 1)
            except Exception as e:
                logger.warning(f"Failed to auto-scale pool {pool}: {e}")

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
            await self._event_bus.emit(
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
            await self._event_bus.emit(
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
        """Get active workers with process info."""
        self._cleanup_dead_processes()
        workers = []

        for worker_id in set(self._workers.keys()) | set(self._processes.keys()):
            worker_info = self._workers.get(worker_id)
            worker_proc = self._processes.get(worker_id)

            if worker_proc and worker_proc.is_alive:
                workers.append({
                    "id": worker_id,
                    "pool": worker_proc.pool,
                    "status": worker_info.status if worker_info else "running",
                    "started_at": worker_proc.started_at.isoformat(),
                    "current_job_id": worker_info.current_job_id if worker_info else None,
                    "jobs_completed": worker_info.jobs_completed if worker_info else 0,
                    "jobs_failed": worker_info.jobs_failed if worker_info else 0,
                    "uptime_seconds": (datetime.utcnow() - worker_proc.started_at).total_seconds(),
                    "pid": worker_proc.pid,
                })
            elif worker_info:
                # Metadata exists but no process (shouldn't happen normally)
                workers.append({
                    "id": worker_id,
                    "pool": worker_info.pool,
                    "status": worker_info.status,
                    "started_at": worker_info.started_at.isoformat(),
                    "current_job_id": worker_info.current_job_id,
                    "jobs_completed": worker_info.jobs_completed,
                    "jobs_failed": worker_info.jobs_failed,
                    "uptime_seconds": (datetime.utcnow() - worker_info.started_at).total_seconds(),
                    "pid": None,
                })

        return workers

    async def get_workers_by_pool(self, pool: str) -> List[Dict[str, Any]]:
        """Get workers for a specific pool."""
        return [
            {
                "id": w.id,
                "pool": w.pool,
                "status": w.status,
                "started_at": w.started_at.isoformat(),
                "current_job_id": w.current_job_id,
                "jobs_completed": w.jobs_completed,
                "jobs_failed": w.jobs_failed,
            }
            for w in self._workers.values()
            if w.pool == pool
        ]

    def get_worker_count(self, pool: str) -> int:
        """Get number of active workers for a pool."""
        # Count actual running processes
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
        """Get the worker class for a pool, checking both registered and built-in workers."""
        # First check shard-registered workers
        if pool in self._registered_workers:
            return self._registered_workers[pool]

        # Fall back to built-in workers from cli.py
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

        # Get Redis URL from config (defaults handled by ConfigService)
        redis_url = self.config.redis_url or 'redis://localhost:6379'

        # Set DATA_SILO_PATH for workers to resolve relative file paths
        # This enables portability across Docker/host environments
        data_silo_path = self.config.get("data_silo_path", "./DataSilo")
        os.environ["DATA_SILO_PATH"] = str(Path(data_silo_path).resolve())

        # Import the run_worker function
        from arkham_frame.workers.base import run_worker

        # Create subprocess (non-daemon so workers can finish their current job on shutdown)
        # Environment variables are inherited by the child process
        process = multiprocessing.Process(
            target=run_worker,
            args=(worker_class, redis_url, worker_id),
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

        # Try graceful shutdown - use terminate() for cross-platform compatibility
        try:
            worker_proc.process.terminate()
        except (ProcessLookupError, OSError):
            del self._processes[worker_id]
            return True

        # Wait for process to exit
        start = time.time()
        while worker_proc.is_alive and (time.time() - start) < timeout:
            time.sleep(0.1)

        # Force kill if still alive
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

        # Start or stop workers to match target
        current_count = self.get_worker_count(pool)

        if count > current_count:
            # Start more workers
            for _ in range(count - current_count):
                await self.start_worker(pool)
        elif count < current_count:
            # Stop excess workers
            pool_workers = [w for w in self._workers.values() if w.pool == pool]
            for worker in pool_workers[count:]:
                await self.stop_worker(worker.id)

        logger.info(f"Scaled {pool} from {old_count} to {count} workers")

        # Emit event
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

        # Check if worker class is available
        worker_class = self._get_worker_class(pool)
        if not worker_class:
            return {
                "success": False,
                "error": f"No worker implementation for pool {pool}. Worker class not registered.",
            }

        # Check max workers
        current_count = self.get_worker_count(pool)
        max_workers = WORKER_POOLS[pool]["max_workers"]
        if current_count >= max_workers:
            return {
                "success": False,
                "error": f"Pool {pool} already at max workers ({max_workers})",
            }

        # Generate worker ID and spawn process
        worker_id = f"{pool}-{uuid.uuid4().hex[:8]}"
        worker_proc = self._spawn_worker_process(pool, worker_id)

        if not worker_proc:
            return {
                "success": False,
                "error": f"Failed to spawn worker for pool {pool}",
            }

        # Create metadata entry
        worker = WorkerInfo(id=worker_id, pool=pool)
        self._workers[worker_id] = worker

        logger.info(f"Started worker {worker_id} (PID {worker_proc.pid}) for pool {pool}")

        # Emit event
        if self._event_bus:
            await self._event_bus.emit(
                "worker.started",
                {"worker_id": worker_id, "pool": pool, "pid": worker_proc.pid},
                source="worker-service",
            )

        return {"success": True, "worker_id": worker_id, "pool": pool, "pid": worker_proc.pid}

    async def stop_worker(self, worker_id: str) -> Dict[str, Any]:
        """Stop a worker by killing its process."""
        # Check both workers and processes
        if worker_id not in self._workers and worker_id not in self._processes:
            return {"success": False, "error": f"Worker {worker_id} not found"}

        pool = None
        if worker_id in self._workers:
            worker = self._workers[worker_id]
            pool = worker.pool
            worker.status = "stopping"

        # Kill the actual process if it exists
        if worker_id in self._processes:
            if not pool:
                pool = self._processes[worker_id].pool
            self._kill_worker_process(worker_id)

        # Remove metadata
        if worker_id in self._workers:
            del self._workers[worker_id]

        logger.info(f"Stopped worker {worker_id}")

        # Emit event
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

        # Get all worker IDs from both workers and processes
        worker_ids = set(self._workers.keys()) | set(self._processes.keys())

        for worker_id in worker_ids:
            # Check if we should filter by pool
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
        """
        Register a worker class from a shard.

        The worker class must have a `pool` attribute defining which pool it serves.

        Args:
            worker_class: BaseWorker subclass with pool attribute
        """
        pool = getattr(worker_class, "pool", None)
        if not pool:
            raise WorkerError(f"Worker class {worker_class.__name__} has no pool attribute")

        if pool not in WORKER_POOLS:
            logger.warning(f"Worker pool {pool} not in predefined pools, adding dynamically")
            WORKER_POOLS[pool] = {"type": "custom", "max_workers": 4}

        self._registered_workers[pool] = worker_class
        logger.info(f"Registered worker {worker_class.__name__} for pool {pool}")

    def unregister_worker(self, worker_class: type) -> None:
        """
        Unregister a worker class.

        Args:
            worker_class: BaseWorker subclass to unregister
        """
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

    # --- Job Result Waiting (for dispatchers) ---

    async def wait_for_result(
        self,
        job_id: str,
        timeout: float = 300.0,
        poll_interval: float = 0.5,
    ) -> Dict[str, Any]:
        """
        Wait for a job to complete and return its result.

        Args:
            job_id: Job ID to wait for
            timeout: Maximum time to wait in seconds
            poll_interval: Time between status checks

        Returns:
            Job result dict

        Raises:
            WorkerError: If job fails or times out
        """
        import asyncio

        start_time = asyncio.get_event_loop().time()

        while True:
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed > timeout:
                raise WorkerError(f"Job {job_id} timed out after {timeout}s")

            job = self._jobs.get(job_id)
            if job:
                if job.status == "completed":
                    return job.result or {}
                elif job.status == "failed":
                    raise WorkerError(f"Job {job_id} failed: {job.error}")

            # Check Redis if available
            if self._available and self._redis:
                job_key = f"arkham:job:{job_id}"
                job_data = self._redis.hgetall(job_key)
                if job_data:
                    status = job_data.get(b"status") or job_data.get("status")
                    if isinstance(status, bytes):
                        status = status.decode()

                    if status == "completed":
                        result_raw = job_data.get(b"result") or job_data.get("result", "{}")
                        if isinstance(result_raw, bytes):
                            result_raw = result_raw.decode()
                        return json.loads(result_raw)
                    elif status == "failed":
                        error = job_data.get(b"error") or job_data.get("error", "Unknown error")
                        if isinstance(error, bytes):
                            error = error.decode()
                        raise WorkerError(f"Job {job_id} failed: {error}")

            await asyncio.sleep(poll_interval)

    async def enqueue_and_wait(
        self,
        pool: str,
        payload: Dict[str, Any],
        priority: int = 1,
        timeout: float = 300.0,
    ) -> Dict[str, Any]:
        """
        Enqueue a job and wait for its result.

        Convenience method that combines enqueue() and wait_for_result().

        Args:
            pool: Worker pool name
            payload: Job data
            priority: Priority level (1=highest)
            timeout: Maximum time to wait

        Returns:
            Job result dict
        """
        job_id = str(uuid.uuid4())
        await self.enqueue(pool, job_id, payload, priority)
        return await self.wait_for_result(job_id, timeout)

    # --- Queue Management ---

    async def get_jobs(
        self,
        pool: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Get jobs with optional filtering.

        Args:
            pool: Filter by pool name
            status: Filter by status (pending, active, completed, failed)
            limit: Maximum number of jobs to return

        Returns:
            List of job dicts
        """
        jobs = []

        for job in self._jobs.values():
            if pool and job.pool != pool:
                continue
            if status and job.status != status:
                continue

            jobs.append({
                "id": job.id,
                "pool": job.pool,
                "status": job.status,
                "priority": job.priority,
                "created_at": job.created_at.isoformat(),
                "started_at": job.started_at.isoformat() if job.started_at else None,
                "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                "error": job.error,
                "payload": job.payload,
                "result": job.result,
            })

            if len(jobs) >= limit:
                break

        return jobs

    async def clear_queue(
        self,
        pool: str,
        status: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Clear jobs from a queue.

        Args:
            pool: Pool name to clear
            status: Only clear jobs with this status (None = clear pending only)

        Returns:
            Result with count of cleared jobs
        """
        if pool not in WORKER_POOLS:
            raise WorkerError(f"Unknown pool: {pool}")

        # Default to clearing pending jobs only
        if status is None:
            status = "pending"

        cleared = 0

        # Clear from Redis
        if self._available and self._redis and status == "pending":
            queue_key = f"arkham:queue:{pool}"
            cleared = self._redis.zcard(queue_key)
            self._redis.delete(queue_key)

        # Clear from in-memory tracking
        jobs_to_remove = [
            job_id for job_id, job in self._jobs.items()
            if job.pool == pool and job.status == status
        ]

        for job_id in jobs_to_remove:
            del self._jobs[job_id]
            if self._available and self._redis:
                self._redis.delete(f"arkham:job:{job_id}")

        cleared = max(cleared, len(jobs_to_remove))

        logger.info(f"Cleared {cleared} {status} jobs from {pool}")

        # Emit event
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
        """
        Retry failed jobs by re-enqueueing them.

        Args:
            pool: Pool name
            job_ids: Specific job IDs to retry (None = retry all failed)

        Returns:
            Result with count of retried jobs
        """
        if pool not in WORKER_POOLS:
            raise WorkerError(f"Unknown pool: {pool}")

        retried = []

        # Find failed jobs
        failed_jobs = [
            job for job in self._jobs.values()
            if job.pool == pool and job.status == "failed"
        ]

        if job_ids:
            failed_jobs = [j for j in failed_jobs if j.id in job_ids]

        for job in failed_jobs:
            # Create new job with same payload
            new_job_id = f"{job.id}-retry-{uuid.uuid4().hex[:4]}"
            await self.enqueue(pool, new_job_id, job.payload, job.priority)
            retried.append({"original_id": job.id, "new_id": new_job_id})

            # Remove old failed job from tracking
            del self._jobs[job.id]

        logger.info(f"Retried {len(retried)} failed jobs in {pool}")

        # Emit event
        if self._event_bus:
            await self._event_bus.emit(
                "worker.jobs.retried",
                {"pool": pool, "count": len(retried), "jobs": retried},
                source="worker-service",
            )

        return {"success": True, "pool": pool, "retried": retried, "count": len(retried)}

    async def cancel_job(self, job_id: str) -> Dict[str, Any]:
        """
        Cancel a pending or active job.

        Args:
            job_id: Job ID to cancel

        Returns:
            Result indicating success/failure
        """
        job = self._jobs.get(job_id)

        if not job:
            return {"success": False, "error": f"Job {job_id} not found"}

        if job.status not in ("pending", "active"):
            return {"success": False, "error": f"Job {job_id} is {job.status}, cannot cancel"}

        old_status = job.status
        job.status = "cancelled"
        job.completed_at = datetime.utcnow()

        # Remove from Redis queue if pending
        if self._available and self._redis and old_status == "pending":
            queue_key = f"arkham:queue:{job.pool}"
            self._redis.zrem(queue_key, job_id)

        # Update Redis job status
        if self._available and self._redis:
            job_key = f"arkham:job:{job_id}"
            self._redis.hset(job_key, mapping={
                "status": "cancelled",
                "completed_at": job.completed_at.isoformat(),
            })

        logger.info(f"Cancelled job {job_id}")

        # Emit event
        if self._event_bus:
            await self._event_bus.emit(
                "worker.job.cancelled",
                {"job_id": job_id, "pool": job.pool},
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
