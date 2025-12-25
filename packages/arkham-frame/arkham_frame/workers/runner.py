"""
WorkerRunner - Process manager for spawning and managing workers.

Handles worker lifecycle: spawn, monitor, scale, kill.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Type, Any
import asyncio
import logging
import multiprocessing
import os
import signal
import sys
import time

from .base import BaseWorker, run_worker
from .registry import WorkerRegistry, WorkerInfo
from ..services.workers import WORKER_POOLS

logger = logging.getLogger(__name__)


@dataclass
class WorkerProcess:
    """Tracks a worker subprocess."""
    worker_id: str
    pool: str
    process: multiprocessing.Process
    started_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def is_alive(self) -> bool:
        return self.process.is_alive()

    @property
    def pid(self) -> Optional[int]:
        return self.process.pid if self.process else None


class WorkerRunner:
    """
    Manages worker processes for ArkhamFrame.

    Responsibilities:
    - Spawn workers for specific pools
    - Monitor worker health
    - Scale workers up/down
    - Kill stuck workers
    - Graceful shutdown
    """

    def __init__(
        self,
        redis_url: str = None,
        worker_classes: Dict[str, Type[BaseWorker]] = None,
    ):
        """
        Initialize the runner.

        Args:
            redis_url: Redis connection URL
            worker_classes: Map of pool name -> worker class
        """
        self.redis_url = redis_url or os.environ.get(
            "REDIS_URL", "redis://localhost:6380"
        )
        self._worker_classes: Dict[str, Type[BaseWorker]] = worker_classes or {}
        self._processes: Dict[str, WorkerProcess] = {}
        self._registry = WorkerRegistry(self.redis_url)
        self._running = False
        self._shutdown_event = asyncio.Event()

    def register_worker_class(self, pool: str, worker_class: Type[BaseWorker]):
        """
        Register a worker class for a pool.

        Args:
            pool: Pool name
            worker_class: BaseWorker subclass
        """
        if pool not in WORKER_POOLS:
            raise ValueError(f"Unknown pool: {pool}")
        self._worker_classes[pool] = worker_class
        logger.info(f"Registered {worker_class.__name__} for pool {pool}")

    def _spawn_worker_process(self, pool: str, worker_id: str = None) -> Optional[WorkerProcess]:
        """
        Spawn a worker subprocess.

        Args:
            pool: Pool name
            worker_id: Optional worker ID

        Returns:
            WorkerProcess or None on failure
        """
        if pool not in self._worker_classes:
            logger.error(f"No worker class registered for pool {pool}")
            return None

        worker_class = self._worker_classes[pool]
        worker_id = worker_id or f"{pool}-{os.getpid()}-{len(self._processes)}"

        # Create subprocess
        process = multiprocessing.Process(
            target=run_worker,
            args=(worker_class, self.redis_url, worker_id),
            name=f"worker-{worker_id}",
            daemon=True,
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

    async def spawn_worker(self, pool: str, worker_id: str = None) -> Optional[str]:
        """
        Spawn a worker for a pool.

        Args:
            pool: Pool name
            worker_id: Optional worker ID

        Returns:
            Worker ID or None on failure
        """
        if pool not in WORKER_POOLS:
            logger.error(f"Unknown pool: {pool}")
            return None

        pool_config = WORKER_POOLS[pool]
        current_count = len([p for p in self._processes.values() if p.pool == pool and p.is_alive])

        if current_count >= pool_config["max_workers"]:
            logger.warning(f"Pool {pool} at max capacity ({pool_config['max_workers']})")
            return None

        worker_proc = self._spawn_worker_process(pool, worker_id)
        return worker_proc.worker_id if worker_proc else None

    async def spawn_workers(self, pool: str, count: int) -> List[str]:
        """
        Spawn multiple workers for a pool.

        Args:
            pool: Pool name
            count: Number of workers to spawn

        Returns:
            List of worker IDs
        """
        worker_ids = []
        for _ in range(count):
            worker_id = await self.spawn_worker(pool)
            if worker_id:
                worker_ids.append(worker_id)
            else:
                break  # Hit max capacity
        return worker_ids

    async def kill_worker(self, worker_id: str, timeout: float = 5.0) -> bool:
        """
        Kill a specific worker.

        Args:
            worker_id: Worker ID
            timeout: Seconds to wait for graceful shutdown

        Returns:
            True if killed successfully
        """
        if worker_id not in self._processes:
            logger.warning(f"Worker {worker_id} not found in runner")
            return False

        worker_proc = self._processes[worker_id]

        if not worker_proc.is_alive:
            del self._processes[worker_id]
            return True

        # Try graceful shutdown first
        try:
            os.kill(worker_proc.pid, signal.SIGTERM)
        except (ProcessLookupError, OSError):
            del self._processes[worker_id]
            return True

        # Wait for process to exit
        start = time.time()
        while worker_proc.is_alive and (time.time() - start) < timeout:
            await asyncio.sleep(0.1)

        # Force kill if still alive
        if worker_proc.is_alive:
            try:
                os.kill(worker_proc.pid, signal.SIGKILL)
            except (ProcessLookupError, OSError):
                pass

        del self._processes[worker_id]
        logger.info(f"Killed worker {worker_id}")
        return True

    async def kill_pool_workers(self, pool: str) -> int:
        """
        Kill all workers in a pool.

        Args:
            pool: Pool name

        Returns:
            Number of workers killed
        """
        workers_to_kill = [
            wid for wid, wp in self._processes.items()
            if wp.pool == pool
        ]

        count = 0
        for worker_id in workers_to_kill:
            if await self.kill_worker(worker_id):
                count += 1

        return count

    async def scale_pool(self, pool: str, target_count: int) -> Dict[str, Any]:
        """
        Scale a pool to target worker count.

        Args:
            pool: Pool name
            target_count: Desired worker count

        Returns:
            Result dict with spawned/killed counts
        """
        if pool not in WORKER_POOLS:
            return {"error": f"Unknown pool: {pool}"}

        pool_config = WORKER_POOLS[pool]
        max_workers = pool_config["max_workers"]

        if target_count > max_workers:
            logger.warning(f"Target {target_count} exceeds max {max_workers} for {pool}")
            target_count = max_workers

        if target_count < 0:
            target_count = 0

        current_workers = [
            (wid, wp) for wid, wp in self._processes.items()
            if wp.pool == pool and wp.is_alive
        ]
        current_count = len(current_workers)

        result = {"pool": pool, "target": target_count, "current": current_count}

        if target_count > current_count:
            # Scale up
            spawn_count = target_count - current_count
            spawned = await self.spawn_workers(pool, spawn_count)
            result["spawned"] = len(spawned)
            result["spawned_ids"] = spawned

        elif target_count < current_count:
            # Scale down
            kill_count = current_count - target_count
            killed = []
            for worker_id, _ in current_workers[:kill_count]:
                if await self.kill_worker(worker_id):
                    killed.append(worker_id)
            result["killed"] = len(killed)
            result["killed_ids"] = killed

        else:
            result["message"] = "Already at target count"

        return result

    def get_pool_status(self, pool: str) -> Dict[str, Any]:
        """
        Get status of workers in a pool.

        Args:
            pool: Pool name

        Returns:
            Status dict
        """
        if pool not in WORKER_POOLS:
            return {"error": f"Unknown pool: {pool}"}

        pool_config = WORKER_POOLS[pool]
        workers = [
            wp for wp in self._processes.values()
            if wp.pool == pool
        ]

        alive = [w for w in workers if w.is_alive]
        dead = [w for w in workers if not w.is_alive]

        return {
            "pool": pool,
            "type": pool_config["type"],
            "max_workers": pool_config["max_workers"],
            "running": len(alive),
            "dead": len(dead),
            "workers": [
                {
                    "worker_id": w.worker_id,
                    "pid": w.pid,
                    "alive": w.is_alive,
                    "uptime": (datetime.utcnow() - w.started_at).total_seconds(),
                }
                for w in workers
            ],
        }

    def get_all_status(self) -> List[Dict[str, Any]]:
        """Get status of all pools."""
        return [self.get_pool_status(pool) for pool in WORKER_POOLS.keys()]

    async def cleanup_dead_processes(self) -> int:
        """
        Remove dead processes from tracking.

        Returns:
            Number of processes cleaned up
        """
        dead = [
            wid for wid, wp in self._processes.items()
            if not wp.is_alive
        ]

        for worker_id in dead:
            del self._processes[worker_id]

        if dead:
            logger.info(f"Cleaned up {len(dead)} dead worker processes")

        return len(dead)

    async def monitor_loop(self, interval: float = 10.0):
        """
        Background loop to monitor workers.

        Args:
            interval: Seconds between checks
        """
        while self._running and not self._shutdown_event.is_set():
            try:
                # Cleanup dead processes
                await self.cleanup_dead_processes()

                # Check registry for stuck workers
                await self._registry.connect()
                stuck = await self._registry.get_stuck_workers()

                for worker in stuck:
                    if worker.worker_id in self._processes:
                        logger.warning(f"Worker {worker.worker_id} appears stuck, killing")
                        await self.kill_worker(worker.worker_id)

                await self._registry.cleanup_dead_workers()

            except Exception as e:
                logger.error(f"Monitor loop error: {e}")

            try:
                await asyncio.wait_for(
                    self._shutdown_event.wait(),
                    timeout=interval,
                )
                break
            except asyncio.TimeoutError:
                pass

    async def run(self, pools: List[str] = None, counts: Dict[str, int] = None):
        """
        Run the worker runner.

        Args:
            pools: List of pools to start (or all if None)
            counts: Map of pool -> worker count (uses defaults if not specified)
        """
        self._running = True
        pools = pools or []
        counts = counts or {}

        logger.info("WorkerRunner starting...")

        # Connect registry
        await self._registry.connect()

        # Spawn initial workers
        for pool in pools:
            count = counts.get(pool, 1)
            await self.spawn_workers(pool, count)

        # Start monitor loop
        monitor_task = asyncio.create_task(self.monitor_loop())

        # Wait for shutdown
        try:
            await self._shutdown_event.wait()
        except asyncio.CancelledError:
            pass
        finally:
            await self.shutdown()
            monitor_task.cancel()

    async def shutdown(self):
        """Graceful shutdown of all workers."""
        logger.info("WorkerRunner shutting down...")
        self._running = False
        self._shutdown_event.set()

        # Kill all workers
        for pool in WORKER_POOLS.keys():
            await self.kill_pool_workers(pool)

        await self._registry.disconnect()
        logger.info("WorkerRunner stopped")

    def request_shutdown(self):
        """Request shutdown (can be called from signal handler)."""
        self._shutdown_event.set()


async def run_single_worker(
    worker_class: Type[BaseWorker],
    redis_url: str = None,
    worker_id: str = None,
):
    """
    Run a single worker (async version).

    Args:
        worker_class: BaseWorker subclass
        redis_url: Redis connection URL
        worker_id: Optional worker ID
    """
    worker = worker_class(redis_url=redis_url, worker_id=worker_id)
    await worker.run()
