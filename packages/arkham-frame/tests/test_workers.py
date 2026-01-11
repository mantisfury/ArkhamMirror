"""
Integration tests for worker infrastructure.

Requirements:
    - PostgreSQL running (or DATABASE_URL env var)

Run with:
    cd packages/arkham-frame
    pytest tests/test_workers.py -v -s
"""

import asyncio
import json
import os
import pytest
import pytest_asyncio
import time
from datetime import datetime, timedelta

# Test configuration
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/arkham")
TEST_TIMEOUT = 30  # Max seconds for any test


@pytest_asyncio.fixture
async def db_pool():
    """Get async PostgreSQL connection pool."""
    import asyncpg

    try:
        pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
    except Exception as e:
        pytest.skip(f"PostgreSQL not available: {e}")
        return

    yield pool

    # Cleanup test jobs
    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM arkham_jobs.jobs WHERE id LIKE 'test-%'"
        )
        await conn.execute(
            "DELETE FROM arkham_jobs.workers WHERE id LIKE 'test-%'"
        )

    await pool.close()


async def wait_for_worker_registration(pool, worker_id: str, timeout: float = 2.0) -> bool:
    """Poll for worker registration with timeout."""
    elapsed = 0.0
    interval = 0.1
    while elapsed < timeout:
        await asyncio.sleep(interval)
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT 1 FROM arkham_jobs.workers WHERE id = $1",
                worker_id
            )
            if row:
                return True
        elapsed += interval
    return False


async def cleanup_test_queues(pool):
    """Clean up test jobs and workers."""
    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM arkham_jobs.jobs WHERE id LIKE 'test-%'"
        )
        await conn.execute(
            "DELETE FROM arkham_jobs.workers WHERE id LIKE 'test-%' OR id LIKE 'smoke-test-%'"
        )


# =============================================================================
# Test 1: Basic Lifecycle
# =============================================================================

class TestWorkerLifecycle:
    """Test worker start/stop/register/deregister."""

    @pytest.mark.asyncio
    async def test_worker_registers_on_start(self, db_pool):
        """Worker should register in database when started."""
        await cleanup_test_queues(db_pool)

        from arkham_frame.workers import EchoWorker

        worker = EchoWorker(database_url=DATABASE_URL, worker_id="test-lifecycle-1")
        worker.idle_timeout = 5.0  # Short timeout for test

        # Start worker in background
        task = asyncio.create_task(worker.run())

        # Wait for registration (poll instead of fixed sleep)
        registered = await wait_for_worker_registration(db_pool, worker.worker_id)
        assert registered, "Worker should be registered in database"

        # Check database registration
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT pool, state FROM arkham_jobs.workers WHERE id = $1",
                worker.worker_id
            )
            assert row["pool"] == "cpu-light"
            assert row["state"] in ["idle", "starting"]

        # Stop worker
        worker._shutdown_event.set()
        await asyncio.wait_for(task, timeout=5)

        await cleanup_test_queues(db_pool)

    @pytest.mark.asyncio
    async def test_worker_heartbeat(self, db_pool):
        """Worker should send heartbeats."""
        await cleanup_test_queues(db_pool)

        from arkham_frame.workers import EchoWorker

        worker = EchoWorker(database_url=DATABASE_URL, worker_id="test-heartbeat-1")
        worker.idle_timeout = 10.0
        worker.heartbeat_interval = 0.5  # Fast heartbeat for test

        task = asyncio.create_task(worker.run())

        # Wait for registration first
        registered = await wait_for_worker_registration(db_pool, worker.worker_id)

        # Get initial heartbeat
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT last_heartbeat FROM arkham_jobs.workers WHERE id = $1",
                worker.worker_id
            )
            hb1 = row["last_heartbeat"] if row else None

        # Wait for another heartbeat
        await asyncio.sleep(1.0)

        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT last_heartbeat FROM arkham_jobs.workers WHERE id = $1",
                worker.worker_id
            )
            hb2 = row["last_heartbeat"] if row else None

        # Heartbeat should have updated
        assert hb2 is not None
        if hb1:
            assert hb2 != hb1, "Heartbeat should update over time"

        worker._shutdown_event.set()
        await asyncio.wait_for(task, timeout=5)

        await cleanup_test_queues(db_pool)

    @pytest.mark.asyncio
    async def test_worker_deregisters_on_stop(self, db_pool):
        """Worker should deregister when stopped."""
        await cleanup_test_queues(db_pool)

        from arkham_frame.workers import EchoWorker

        worker = EchoWorker(database_url=DATABASE_URL, worker_id="test-dereg-1")
        worker.idle_timeout = 10.0

        task = asyncio.create_task(worker.run())

        # Wait for registration
        registered = await wait_for_worker_registration(db_pool, worker.worker_id)
        assert registered, "Worker should register first"

        # Verify registered
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT 1 FROM arkham_jobs.workers WHERE id = $1",
                worker.worker_id
            )
            assert row is not None

        # Stop worker
        worker._shutdown_event.set()
        await asyncio.wait_for(task, timeout=5)

        # Verify deregistered
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT 1 FROM arkham_jobs.workers WHERE id = $1",
                worker.worker_id
            )
            assert row is None, "Worker should be deregistered from database"

        await cleanup_test_queues(db_pool)


# =============================================================================
# Test 2: Job Processing (EchoWorker)
# =============================================================================

class TestJobProcessing:
    """Test job processing with EchoWorker."""

    @pytest.mark.asyncio
    async def test_worker_processes_job(self, db_pool):
        """Worker should pick up and complete a job."""
        await cleanup_test_queues(db_pool)

        from arkham_frame.workers import EchoWorker

        # Create job
        job_id = "test-job-1"

        async with db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO arkham_jobs.jobs (id, pool, payload, priority, status)
                VALUES ($1, $2, $3, $4, 'pending')
            """, job_id, "cpu-light", json.dumps({"message": "Hello!", "delay": 0.1}), 1)

        # Start worker
        worker = EchoWorker(database_url=DATABASE_URL, worker_id="test-process-1")
        worker.idle_timeout = 3.0
        worker.poll_interval = 0.2

        task = asyncio.create_task(worker.run())

        # Wait for job to complete
        for _ in range(30):
            async with db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT status FROM arkham_jobs.jobs WHERE id = $1",
                    job_id
                )
                if row and row["status"] == "completed":
                    break
            await asyncio.sleep(0.2)

        # Verify completion
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT status, result FROM arkham_jobs.jobs WHERE id = $1",
                job_id
            )
            assert row["status"] == "completed", f"Job should be completed, got {row['status']}"

            # Check result (asyncpg returns JSONB as string)
            result = row["result"]
            if isinstance(result, str):
                result = json.loads(result)
            assert result["echoed"] is True
            assert result["message"] == "Hello!"

        worker._shutdown_event.set()
        await asyncio.wait_for(task, timeout=5)

        await cleanup_test_queues(db_pool)

    @pytest.mark.asyncio
    async def test_worker_processes_multiple_jobs(self, db_pool):
        """Worker should process multiple jobs sequentially."""
        await cleanup_test_queues(db_pool)

        from arkham_frame.workers import EchoWorker

        # Create 5 jobs
        job_ids = [f"test-multi-{i}" for i in range(5)]

        async with db_pool.acquire() as conn:
            for job_id in job_ids:
                await conn.execute("""
                    INSERT INTO arkham_jobs.jobs (id, pool, payload, priority, status)
                    VALUES ($1, $2, $3, $4, 'pending')
                """, job_id, "cpu-light", json.dumps({"message": f"Job {job_id}", "delay": 0.05}), 1)

        # Start worker
        worker = EchoWorker(database_url=DATABASE_URL, worker_id="test-multi-1")
        worker.idle_timeout = 5.0
        worker.poll_interval = 0.1

        task = asyncio.create_task(worker.run())

        # Wait for all jobs to complete
        for _ in range(50):
            completed = 0
            async with db_pool.acquire() as conn:
                for job_id in job_ids:
                    row = await conn.fetchrow(
                        "SELECT status FROM arkham_jobs.jobs WHERE id = $1",
                        job_id
                    )
                    if row and row["status"] == "completed":
                        completed += 1
            if completed == len(job_ids):
                break
            await asyncio.sleep(0.2)

        # Verify all completed
        async with db_pool.acquire() as conn:
            for job_id in job_ids:
                row = await conn.fetchrow(
                    "SELECT status FROM arkham_jobs.jobs WHERE id = $1",
                    job_id
                )
                assert row["status"] == "completed", f"Job {job_id} should be completed"

        # Check metrics
        assert worker._metrics.jobs_completed == 5

        worker._shutdown_event.set()
        await asyncio.wait_for(task, timeout=5)

        await cleanup_test_queues(db_pool)


# =============================================================================
# Test 3: Failure Handling (FailWorker)
# =============================================================================

class TestFailureHandling:
    """Test job failure and retry logic."""

    @pytest.mark.asyncio
    async def test_failed_job_retries(self, db_pool):
        """Failed job should be retried up to max_retries."""
        await cleanup_test_queues(db_pool)

        from arkham_frame.workers import FailWorker

        # Create job that will fail
        job_id = "test-fail-1"

        async with db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO arkham_jobs.jobs (id, pool, payload, priority, status, retry_count)
                VALUES ($1, $2, $3, $4, 'pending', 0)
            """, job_id, "cpu-light", json.dumps({"fail_after": 0.05}), 1)

        # Start worker (max_retries=2)
        worker = FailWorker(database_url=DATABASE_URL, worker_id="test-fail-worker-1")
        worker.idle_timeout = 5.0
        worker.poll_interval = 0.1
        worker.max_retries = 2

        task = asyncio.create_task(worker.run())

        # Wait for retries to exhaust
        for _ in range(40):
            async with db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT status FROM arkham_jobs.jobs WHERE id = $1",
                    job_id
                )
                if row and row["status"] == "failed":
                    break
            await asyncio.sleep(0.2)

        # Job should eventually fail permanently
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT status FROM arkham_jobs.jobs WHERE id = $1",
                job_id
            )
            assert row["status"] == "failed", "Job should be marked as failed after retries"

        # Worker should still be alive
        assert worker._metrics.jobs_failed >= 1

        worker._shutdown_event.set()
        await asyncio.wait_for(task, timeout=5)

        await cleanup_test_queues(db_pool)

    @pytest.mark.asyncio
    async def test_worker_survives_job_failure(self, db_pool):
        """Worker should continue processing after a job fails."""
        await cleanup_test_queues(db_pool)

        from arkham_frame.workers.base import BaseWorker

        # Create a worker that fails on first job, succeeds on second
        class FailOnceWorker(BaseWorker):
            pool = "cpu-light"
            name = "FailOnceWorker"

            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.call_count = 0  # Instance variable

            async def process_job(self, job_id, payload):
                self.call_count += 1
                if self.call_count == 1:
                    raise ValueError("First job fails")
                return {"success": True, "call": self.call_count}

        # Create two jobs
        async with db_pool.acquire() as conn:
            for i, job_id in enumerate(["test-failonce-1", "test-failonce-2"]):
                await conn.execute("""
                    INSERT INTO arkham_jobs.jobs (id, pool, payload, priority, status)
                    VALUES ($1, $2, $3, $4, 'pending')
                """, job_id, "cpu-light", json.dumps({"num": i}), i + 1)

        worker = FailOnceWorker(database_url=DATABASE_URL, worker_id="test-failonce-worker")
        worker.idle_timeout = 10.0
        worker.poll_interval = 0.1
        worker.max_retries = 0  # Don't retry for this test

        task = asyncio.create_task(worker.run())

        # Wait for worker to register first
        await wait_for_worker_registration(db_pool, worker.worker_id)

        # Poll for second job to complete
        for _ in range(50):  # 5 seconds max
            async with db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT status FROM arkham_jobs.jobs WHERE id = $1",
                    "test-failonce-2"
                )
                if row and row["status"] == "completed":
                    break
            await asyncio.sleep(0.1)

        # Second job should have completed
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT status FROM arkham_jobs.jobs WHERE id = $1",
                "test-failonce-2"
            )
            assert row["status"] == "completed", f"Second job should complete even after first fails, got {row['status']}"

        assert worker._metrics.jobs_failed == 1
        assert worker._metrics.jobs_completed == 1

        worker._shutdown_event.set()
        await asyncio.wait_for(task, timeout=5)

        await cleanup_test_queues(db_pool)


# =============================================================================
# Test 4: Stuck Detection (SlowWorker)
# =============================================================================

class TestStuckDetection:
    """Test stuck worker detection and handling."""

    @pytest.mark.asyncio
    async def test_job_timeout(self, db_pool):
        """Job exceeding timeout should fail and be requeued."""
        await cleanup_test_queues(db_pool)

        from arkham_frame.workers import SlowWorker

        # Create job that takes longer than timeout
        job_id = "test-slow-1"

        async with db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO arkham_jobs.jobs (id, pool, payload, priority, status)
                VALUES ($1, $2, $3, $4, 'pending')
            """, job_id, "cpu-heavy", json.dumps({"sleep": 30}), 1)

        # Worker with short timeout
        worker = SlowWorker(database_url=DATABASE_URL, worker_id="test-slow-worker-1")
        worker.job_timeout = 0.5  # 0.5 second timeout
        worker.idle_timeout = 10.0
        worker.poll_interval = 0.1
        worker.max_retries = 1

        task = asyncio.create_task(worker.run())

        # Wait for worker to register first
        await wait_for_worker_registration(db_pool, worker.worker_id)

        # Poll for job status to change from "active" (after timeout it should be requeued or failed)
        for _ in range(50):  # 5 seconds max
            async with db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT status FROM arkham_jobs.jobs WHERE id = $1",
                    job_id
                )
                if row and row["status"] in ["pending", "failed"]:
                    break
            await asyncio.sleep(0.1)

        # Job should be requeued or failed
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT status FROM arkham_jobs.jobs WHERE id = $1",
                job_id
            )
            assert row["status"] in ["pending", "failed"], f"Job should be requeued or failed, got {row['status']}"

        # Worker should have recorded the failure
        assert worker._metrics.jobs_failed >= 1

        worker._shutdown_event.set()
        await asyncio.wait_for(task, timeout=5)

        await cleanup_test_queues(db_pool)


# =============================================================================
# Test 5: Worker Registry
# =============================================================================

class TestWorkerRegistry:
    """Test WorkerRegistry functionality."""

    @pytest.mark.asyncio
    async def test_registry_discovers_workers(self, db_pool):
        """Registry should discover running workers."""
        await cleanup_test_queues(db_pool)

        from arkham_frame.workers import EchoWorker, WorkerRegistry

        # Start multiple workers
        workers = []
        tasks = []
        for i in range(3):
            worker = EchoWorker(database_url=DATABASE_URL, worker_id=f"test-reg-{i}")
            worker.idle_timeout = 10.0
            workers.append(worker)
            tasks.append(asyncio.create_task(worker.run()))

        # Wait for all workers to register
        for worker in workers:
            registered = await wait_for_worker_registration(db_pool, worker.worker_id)
            assert registered, f"Worker {worker.worker_id} should register"

        # Query registry
        registry = WorkerRegistry(database_url=DATABASE_URL)
        await registry.connect(db_pool)

        all_workers = await registry.get_all_workers()
        test_workers = [w for w in all_workers if w.worker_id.startswith("test-reg-")]

        assert len(test_workers) == 3, f"Should find 3 workers, found {len(test_workers)}"

        # Check pool filter
        pool_workers = await registry.get_pool_workers("cpu-light")
        test_pool_workers = [w for w in pool_workers if w.worker_id.startswith("test-reg-")]
        assert len(test_pool_workers) == 3

        # Stop all workers
        for worker in workers:
            worker._shutdown_event.set()
        await asyncio.gather(*tasks, return_exceptions=True)

        await cleanup_test_queues(db_pool)

    @pytest.mark.asyncio
    async def test_registry_detects_dead_workers(self, db_pool):
        """Registry should detect workers that stopped heartbeating."""
        await cleanup_test_queues(db_pool)

        from arkham_frame.workers import WorkerRegistry

        # Manually create a "dead" worker entry (old heartbeat)
        worker_id = "test-dead-worker"
        old_time = datetime.utcnow() - timedelta(hours=1)

        async with db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO arkham_jobs.workers (id, pool, name, state, pid, started_at, last_heartbeat)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
            """, worker_id, "cpu-light", "DeadWorker", "processing", 99999, old_time, old_time)

        registry = WorkerRegistry(database_url=DATABASE_URL)
        await registry.connect(db_pool)

        # Check stuck detection
        stuck = await registry.get_stuck_workers()
        stuck_ids = [w.worker_id for w in stuck]
        assert worker_id in stuck_ids, "Should detect stuck worker"

        # Cleanup
        cleaned = await registry.cleanup_dead_workers()
        assert cleaned >= 1, "Should cleanup dead workers"

        # Worker should be gone
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT 1 FROM arkham_jobs.workers WHERE id = $1",
                worker_id
            )
            assert row is None, "Dead worker should be removed"

        await cleanup_test_queues(db_pool)


# =============================================================================
# Quick Smoke Test (run without pytest)
# =============================================================================

async def smoke_test():
    """Quick smoke test - can run directly."""
    import asyncpg

    print("=" * 60)
    print("Worker Infrastructure Smoke Test")
    print("=" * 60)

    # Test PostgreSQL connection
    print("\n1. Testing PostgreSQL connection...")
    try:
        pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=3)
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        print(f"   OK - Connected to PostgreSQL")
    except Exception as e:
        print(f"   FAILED - {e}")
        print("   Make sure PostgreSQL is running!")
        return False

    # Test worker lifecycle
    print("\n2. Testing worker lifecycle...")
    from arkham_frame.workers import EchoWorker

    worker = EchoWorker(database_url=DATABASE_URL, worker_id="smoke-test-worker")
    worker.idle_timeout = 5.0

    task = asyncio.create_task(worker.run())

    # Poll for registration
    registered = False
    for _ in range(20):
        await asyncio.sleep(0.1)
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT 1 FROM arkham_jobs.workers WHERE id = $1",
                worker.worker_id
            )
            if row:
                registered = True
                break

    if registered:
        print("   OK - Worker registered")
    else:
        print("   FAILED - Worker not registered")
        worker._shutdown_event.set()
        try:
            await asyncio.wait_for(task, timeout=2)
        except asyncio.TimeoutError:
            pass
        await pool.close()
        return False

    # Create and process job
    print("\n3. Testing job processing...")
    job_id = "smoke-test-job"
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO arkham_jobs.jobs (id, pool, payload, priority, status)
            VALUES ($1, $2, $3, $4, 'pending')
            ON CONFLICT (id) DO UPDATE SET status = 'pending', payload = EXCLUDED.payload
        """, job_id, "cpu-light", json.dumps({"message": "Smoke test!", "delay": 0.1}), 1)

    # Wait for completion
    status = None
    for _ in range(20):
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT status, result FROM arkham_jobs.jobs WHERE id = $1",
                job_id
            )
            if row and row["status"] == "completed":
                status = "completed"
                result = row["result"]
                break
        await asyncio.sleep(0.2)

    if status == "completed":
        if isinstance(result, str):
            result = json.loads(result)
        print(f"   OK - Job completed: {result.get('message')}")
    else:
        print(f"   FAILED - Job status: {status}")
        return False

    # Stop worker
    print("\n4. Testing graceful shutdown...")
    worker._shutdown_event.set()
    await asyncio.wait_for(task, timeout=5)

    # Check deregistered
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT 1 FROM arkham_jobs.workers WHERE id = $1",
            worker.worker_id
        )
        if row is None:
            print("   OK - Worker deregistered")
        else:
            print("   FAILED - Worker still registered")
            return False

    # Cleanup
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM arkham_jobs.jobs WHERE id = $1", job_id)
    await pool.close()

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED!")
    print("=" * 60)
    return True


if __name__ == "__main__":
    result = asyncio.run(smoke_test())
    exit(0 if result else 1)
