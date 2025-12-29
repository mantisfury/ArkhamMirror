"""
Integration tests for worker infrastructure.

Requirements:
    - Redis running at localhost:6379 (or REDIS_URL env var)

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
from datetime import datetime

# Test configuration
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")
TEST_TIMEOUT = 30  # Max seconds for any test


@pytest_asyncio.fixture
async def redis_client():
    """Get async Redis client."""
    import redis.asyncio as aioredis

    client = aioredis.from_url(REDIS_URL)
    try:
        await client.ping()
    except Exception as e:
        pytest.skip(f"Redis not available: {e}")

    yield client

    # Cleanup test keys
    cursor = 0
    while True:
        cursor, keys = await client.scan(cursor, match="arkham:test:*", count=100)
        if keys:
            await client.delete(*keys)
        if cursor == 0:
            break

    await client.aclose()


async def wait_for_worker_registration(redis_client, worker_id: str, timeout: float = 2.0) -> bool:
    """Poll for worker registration with timeout."""
    worker_key = f"arkham:worker:{worker_id}"
    elapsed = 0.0
    interval = 0.1
    while elapsed < timeout:
        await asyncio.sleep(interval)
        if await redis_client.exists(worker_key):
            return True
        elapsed += interval
    return False


async def cleanup_test_queues(redis_client):
    """Clean up test queues."""
    # Clean worker registrations
    cursor = 0
    while True:
        cursor, keys = await redis_client.scan(cursor, match="arkham:worker:test-*", count=100)
        if keys:
            await redis_client.delete(*keys)
        if cursor == 0:
            break

    # Clean smoke test worker
    await redis_client.delete("arkham:worker:smoke-test-worker")

    # Clean test jobs
    cursor = 0
    while True:
        cursor, keys = await redis_client.scan(cursor, match="arkham:job:test-*", count=100)
        if keys:
            await redis_client.delete(*keys)
        if cursor == 0:
            break

    # Clean queues used by test workers
    await redis_client.delete("arkham:queue:cpu-light")
    await redis_client.delete("arkham:queue:cpu-heavy")
    await redis_client.delete("arkham:dlq:cpu-light")


# =============================================================================
# Test 1: Basic Lifecycle
# =============================================================================

class TestWorkerLifecycle:
    """Test worker start/stop/register/deregister."""

    @pytest.mark.asyncio
    async def test_worker_registers_on_start(self, redis_client):
        """Worker should register in Redis when started."""
        await cleanup_test_queues(redis_client)

        from arkham_frame.workers import EchoWorker

        worker = EchoWorker(redis_url=REDIS_URL, worker_id="test-lifecycle-1")
        worker.idle_timeout = 5.0  # Short timeout for test

        # Start worker in background
        task = asyncio.create_task(worker.run())

        # Wait for registration (poll instead of fixed sleep)
        registered = await wait_for_worker_registration(redis_client, worker.worker_id)
        assert registered, "Worker should be registered in Redis"

        # Check Redis registration
        worker_key = f"arkham:worker:{worker.worker_id}"

        data = await redis_client.hgetall(worker_key)
        assert data[b"pool"] == b"cpu-light"
        assert data[b"state"] in [b"idle", b"starting"]

        # Stop worker
        worker._shutdown_event.set()
        await asyncio.wait_for(task, timeout=5)

        await cleanup_test_queues(redis_client)

    @pytest.mark.asyncio
    async def test_worker_heartbeat(self, redis_client):
        """Worker should send heartbeats."""
        await cleanup_test_queues(redis_client)

        from arkham_frame.workers import EchoWorker

        worker = EchoWorker(redis_url=REDIS_URL, worker_id="test-heartbeat-1")
        worker.idle_timeout = 10.0
        worker.heartbeat_interval = 0.5  # Fast heartbeat for test

        task = asyncio.create_task(worker.run())

        # Wait for registration first
        registered = await wait_for_worker_registration(redis_client, worker.worker_id)

        # Get initial heartbeat
        worker_key = f"arkham:worker:{worker.worker_id}"
        hb1 = await redis_client.hget(worker_key, "last_heartbeat")

        # Wait for another heartbeat
        await asyncio.sleep(1.0)
        hb2 = await redis_client.hget(worker_key, "last_heartbeat")

        # Heartbeat should have updated
        assert hb2 is not None
        if hb1:
            assert hb2 != hb1, "Heartbeat should update over time"

        worker._shutdown_event.set()
        await asyncio.wait_for(task, timeout=5)

        await cleanup_test_queues(redis_client)

    @pytest.mark.asyncio
    async def test_worker_deregisters_on_stop(self, redis_client):
        """Worker should deregister when stopped."""
        await cleanup_test_queues(redis_client)

        from arkham_frame.workers import EchoWorker

        worker = EchoWorker(redis_url=REDIS_URL, worker_id="test-dereg-1")
        worker.idle_timeout = 10.0

        task = asyncio.create_task(worker.run())

        # Wait for registration
        registered = await wait_for_worker_registration(redis_client, worker.worker_id)
        assert registered, "Worker should register first"

        # Verify registered
        worker_key = f"arkham:worker:{worker.worker_id}"
        assert await redis_client.exists(worker_key)

        # Stop worker
        worker._shutdown_event.set()
        await asyncio.wait_for(task, timeout=5)

        # Verify deregistered
        exists = await redis_client.exists(worker_key)
        assert not exists, "Worker should be deregistered from Redis"

        await cleanup_test_queues(redis_client)


# =============================================================================
# Test 2: Job Processing (EchoWorker)
# =============================================================================

class TestJobProcessing:
    """Test job processing with EchoWorker."""

    @pytest.mark.asyncio
    async def test_worker_processes_job(self, redis_client):
        """Worker should pick up and complete a job."""
        await cleanup_test_queues(redis_client)

        from arkham_frame.workers import EchoWorker

        # Create job
        job_id = "test-job-1"
        queue_key = "arkham:queue:cpu-light"
        job_key = f"arkham:job:{job_id}"

        await redis_client.zadd(queue_key, {job_id: 1})
        await redis_client.hset(job_key, mapping={
            "pool": "cpu-light",
            "payload": json.dumps({"message": "Hello!", "delay": 0.1}),
            "priority": 1,
            "status": "pending",
        })

        # Start worker
        worker = EchoWorker(redis_url=REDIS_URL, worker_id="test-process-1")
        worker.idle_timeout = 3.0
        worker.poll_interval = 0.2

        task = asyncio.create_task(worker.run())

        # Wait for job to complete
        for _ in range(30):
            status = await redis_client.hget(job_key, "status")
            if status == b"completed":
                break
            await asyncio.sleep(0.2)

        # Verify completion
        status = await redis_client.hget(job_key, "status")
        assert status == b"completed", f"Job should be completed, got {status}"

        # Check result
        result_raw = await redis_client.hget(job_key, "result")
        result = json.loads(result_raw)
        assert result["echoed"] is True
        assert result["message"] == "Hello!"

        worker._shutdown_event.set()
        await asyncio.wait_for(task, timeout=5)

        await cleanup_test_queues(redis_client)

    @pytest.mark.asyncio
    async def test_worker_processes_multiple_jobs(self, redis_client):
        """Worker should process multiple jobs sequentially."""
        await cleanup_test_queues(redis_client)

        from arkham_frame.workers import EchoWorker

        # Create 5 jobs
        queue_key = "arkham:queue:cpu-light"
        job_ids = [f"test-multi-{i}" for i in range(5)]

        for job_id in job_ids:
            job_key = f"arkham:job:{job_id}"
            await redis_client.zadd(queue_key, {job_id: 1})
            await redis_client.hset(job_key, mapping={
                "pool": "cpu-light",
                "payload": json.dumps({"message": f"Job {job_id}", "delay": 0.05}),
                "priority": 1,
                "status": "pending",
            })

        # Start worker
        worker = EchoWorker(redis_url=REDIS_URL, worker_id="test-multi-1")
        worker.idle_timeout = 5.0
        worker.poll_interval = 0.1

        task = asyncio.create_task(worker.run())

        # Wait for all jobs to complete
        for _ in range(50):
            completed = 0
            for job_id in job_ids:
                status = await redis_client.hget(f"arkham:job:{job_id}", "status")
                if status == b"completed":
                    completed += 1
            if completed == len(job_ids):
                break
            await asyncio.sleep(0.2)

        # Verify all completed
        for job_id in job_ids:
            status = await redis_client.hget(f"arkham:job:{job_id}", "status")
            assert status == b"completed", f"Job {job_id} should be completed"

        # Check metrics
        assert worker._metrics.jobs_completed == 5

        worker._shutdown_event.set()
        await asyncio.wait_for(task, timeout=5)

        await cleanup_test_queues(redis_client)


# =============================================================================
# Test 3: Failure Handling (FailWorker)
# =============================================================================

class TestFailureHandling:
    """Test job failure and retry logic."""

    @pytest.mark.asyncio
    async def test_failed_job_retries(self, redis_client):
        """Failed job should be retried up to max_retries."""
        await cleanup_test_queues(redis_client)

        from arkham_frame.workers import FailWorker

        # Create job that will fail
        job_id = "test-fail-1"
        queue_key = "arkham:queue:cpu-light"
        job_key = f"arkham:job:{job_id}"

        await redis_client.zadd(queue_key, {job_id: 1})
        await redis_client.hset(job_key, mapping={
            "pool": "cpu-light",
            "payload": json.dumps({"fail_after": 0.05}),
            "priority": 1,
            "status": "pending",
            "retry_count": 0,
        })

        # Start worker (max_retries=2)
        worker = FailWorker(redis_url=REDIS_URL, worker_id="test-fail-worker-1")
        worker.idle_timeout = 5.0
        worker.poll_interval = 0.1
        worker.max_retries = 2

        task = asyncio.create_task(worker.run())

        # Wait for retries to exhaust
        for _ in range(40):
            status = await redis_client.hget(job_key, "status")
            if status == b"failed":
                break
            await asyncio.sleep(0.2)

        # Job should eventually fail permanently
        status = await redis_client.hget(job_key, "status")
        assert status == b"failed", "Job should be marked as failed after retries"

        # Check dead letter queue
        dlq_key = "arkham:dlq:cpu-light"
        dlq_len = await redis_client.llen(dlq_key)
        assert dlq_len > 0, "Failed job should be in dead letter queue"

        # Worker should still be alive
        assert worker._metrics.jobs_failed >= 1

        worker._shutdown_event.set()
        await asyncio.wait_for(task, timeout=5)

        await cleanup_test_queues(redis_client)

    @pytest.mark.asyncio
    async def test_worker_survives_job_failure(self, redis_client):
        """Worker should continue processing after a job fails."""
        await cleanup_test_queues(redis_client)

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
        queue_key = "arkham:queue:cpu-light"

        for i, job_id in enumerate(["test-failonce-1", "test-failonce-2"]):
            job_key = f"arkham:job:{job_id}"
            await redis_client.zadd(queue_key, {job_id: i + 1})
            await redis_client.hset(job_key, mapping={
                "pool": "cpu-light",
                "payload": json.dumps({"num": i}),
                "priority": i + 1,
                "status": "pending",
            })

        worker = FailOnceWorker(redis_url=REDIS_URL, worker_id="test-failonce-worker")
        worker.idle_timeout = 10.0
        worker.poll_interval = 0.1
        worker.max_retries = 0  # Don't retry for this test

        task = asyncio.create_task(worker.run())

        # Wait for worker to register first
        await wait_for_worker_registration(redis_client, worker.worker_id)

        # Poll for second job to complete
        for _ in range(50):  # 5 seconds max
            status = await redis_client.hget("arkham:job:test-failonce-2", "status")
            if status == b"completed":
                break
            await asyncio.sleep(0.1)

        # Second job should have completed
        status = await redis_client.hget("arkham:job:test-failonce-2", "status")
        assert status == b"completed", f"Second job should complete even after first fails, got {status}"

        assert worker._metrics.jobs_failed == 1
        assert worker._metrics.jobs_completed == 1

        worker._shutdown_event.set()
        await asyncio.wait_for(task, timeout=5)

        await cleanup_test_queues(redis_client)


# =============================================================================
# Test 4: Stuck Detection (SlowWorker)
# =============================================================================

class TestStuckDetection:
    """Test stuck worker detection and handling."""

    @pytest.mark.asyncio
    async def test_job_timeout(self, redis_client):
        """Job exceeding timeout should fail and be requeued."""
        await cleanup_test_queues(redis_client)

        from arkham_frame.workers import SlowWorker

        # Create job that takes longer than timeout
        job_id = "test-slow-1"
        queue_key = "arkham:queue:cpu-heavy"
        job_key = f"arkham:job:{job_id}"

        await redis_client.zadd(queue_key, {job_id: 1})
        await redis_client.hset(job_key, mapping={
            "pool": "cpu-heavy",
            "payload": json.dumps({"sleep": 30}),  # 30 seconds
            "priority": 1,
            "status": "pending",
        })

        # Worker with short timeout
        worker = SlowWorker(redis_url=REDIS_URL, worker_id="test-slow-worker-1")
        worker.job_timeout = 0.5  # 0.5 second timeout
        worker.idle_timeout = 10.0
        worker.poll_interval = 0.1
        worker.max_retries = 1

        task = asyncio.create_task(worker.run())

        # Wait for worker to register first
        await wait_for_worker_registration(redis_client, worker.worker_id)

        # Poll for job status to change from "active" (after timeout it should be requeued or failed)
        for _ in range(50):  # 5 seconds max
            status = await redis_client.hget(job_key, "status")
            if status in [b"pending", b"failed"]:
                break
            await asyncio.sleep(0.1)

        # Job should be requeued or failed
        status = await redis_client.hget(job_key, "status")
        assert status in [b"pending", b"failed"], f"Job should be requeued or failed, got {status}"

        # Worker should have recorded the failure
        assert worker._metrics.jobs_failed >= 1

        worker._shutdown_event.set()
        await asyncio.wait_for(task, timeout=5)

        await cleanup_test_queues(redis_client)


# =============================================================================
# Test 5: Worker Registry
# =============================================================================

class TestWorkerRegistry:
    """Test WorkerRegistry functionality."""

    @pytest.mark.asyncio
    async def test_registry_discovers_workers(self, redis_client):
        """Registry should discover running workers."""
        await cleanup_test_queues(redis_client)

        from arkham_frame.workers import EchoWorker, WorkerRegistry

        # Start multiple workers
        workers = []
        tasks = []
        for i in range(3):
            worker = EchoWorker(redis_url=REDIS_URL, worker_id=f"test-reg-{i}")
            worker.idle_timeout = 10.0
            workers.append(worker)
            tasks.append(asyncio.create_task(worker.run()))

        # Wait for all workers to register
        for worker in workers:
            registered = await wait_for_worker_registration(redis_client, worker.worker_id)
            assert registered, f"Worker {worker.worker_id} should register"

        # Query registry
        registry = WorkerRegistry(redis_url=REDIS_URL)
        await registry.connect(redis_client)

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

        await cleanup_test_queues(redis_client)

    @pytest.mark.asyncio
    async def test_registry_detects_dead_workers(self, redis_client):
        """Registry should detect workers that stopped heartbeating."""
        await cleanup_test_queues(redis_client)

        from arkham_frame.workers import WorkerRegistry

        # Manually create a "dead" worker entry (old heartbeat)
        worker_id = "test-dead-worker"
        worker_key = f"arkham:worker:{worker_id}"

        old_time = datetime(2020, 1, 1, 0, 0, 0).isoformat()
        await redis_client.hset(worker_key, mapping={
            "pool": "cpu-light",
            "name": "DeadWorker",
            "state": "processing",
            "pid": 99999,
            "started_at": old_time,
            "last_heartbeat": old_time,
        })

        registry = WorkerRegistry(redis_url=REDIS_URL)
        await registry.connect(redis_client)

        # Check stuck detection
        stuck = await registry.get_stuck_workers()
        stuck_ids = [w.worker_id for w in stuck]
        assert worker_id in stuck_ids, "Should detect stuck worker"

        # Cleanup
        cleaned = await registry.cleanup_dead_workers()
        assert cleaned >= 1, "Should cleanup dead workers"

        # Worker should be gone
        exists = await redis_client.exists(worker_key)
        assert not exists, "Dead worker should be removed"

        await cleanup_test_queues(redis_client)


# =============================================================================
# Test 6: WorkerRunner
# =============================================================================

class TestWorkerRunner:
    """Test WorkerRunner process management."""

    @pytest.mark.asyncio
    async def test_runner_spawns_workers(self, redis_client):
        """Runner should spawn worker processes."""
        await cleanup_test_queues(redis_client)

        from arkham_frame.workers import WorkerRunner, EchoWorker

        runner = WorkerRunner(redis_url=REDIS_URL)
        runner.register_worker_class("cpu-light", EchoWorker)

        # Spawn workers
        worker_ids = await runner.spawn_workers("cpu-light", 2)

        assert len(worker_ids) == 2, f"Should spawn 2 workers, got {len(worker_ids)}"

        # Give processes time to start
        await asyncio.sleep(1)

        # Check status
        status = runner.get_pool_status("cpu-light")
        assert status["running"] == 2, f"Should have 2 running, got {status}"

        # Cleanup
        await runner.kill_pool_workers("cpu-light")
        await asyncio.sleep(0.5)

        status = runner.get_pool_status("cpu-light")
        assert status["running"] == 0

        await cleanup_test_queues(redis_client)

    @pytest.mark.asyncio
    async def test_runner_scales_pool(self, redis_client):
        """Runner should scale pool up and down."""
        await cleanup_test_queues(redis_client)

        from arkham_frame.workers import WorkerRunner, EchoWorker

        runner = WorkerRunner(redis_url=REDIS_URL)
        runner.register_worker_class("cpu-light", EchoWorker)

        # Scale up
        result = await runner.scale_pool("cpu-light", 3)
        assert result.get("spawned") == 3

        await asyncio.sleep(1)
        status = runner.get_pool_status("cpu-light")
        assert status["running"] == 3

        # Scale down
        result = await runner.scale_pool("cpu-light", 1)
        assert result.get("killed") == 2

        await asyncio.sleep(1)
        status = runner.get_pool_status("cpu-light")
        assert status["running"] == 1

        # Cleanup
        await runner.scale_pool("cpu-light", 0)
        await asyncio.sleep(0.5)

        await cleanup_test_queues(redis_client)


# =============================================================================
# Quick Smoke Test (run without pytest)
# =============================================================================

async def smoke_test():
    """Quick smoke test - can run directly."""
    import redis.asyncio as aioredis

    print("=" * 60)
    print("Worker Infrastructure Smoke Test")
    print("=" * 60)

    # Test Redis connection
    print("\n1. Testing Redis connection...")
    try:
        r = aioredis.from_url(REDIS_URL)
        await r.ping()
        print(f"   OK - Connected to {REDIS_URL}")
    except Exception as e:
        print(f"   FAILED - {e}")
        print("   Make sure Redis is running!")
        return False

    # Test worker lifecycle
    print("\n2. Testing worker lifecycle...")
    from arkham_frame.workers import EchoWorker

    worker = EchoWorker(redis_url=REDIS_URL, worker_id="smoke-test-worker")
    worker.idle_timeout = 5.0

    task = asyncio.create_task(worker.run())

    # Poll for registration (async operations need time to complete)
    registered = False
    for _ in range(20):
        await asyncio.sleep(0.1)
        exists = await r.exists(f"arkham:worker:{worker.worker_id}")
        if exists:
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
        await r.aclose()
        return False

    # Create and process job
    print("\n3. Testing job processing...")
    job_id = "smoke-test-job"
    await r.zadd("arkham:queue:cpu-light", {job_id: 1})
    await r.hset(f"arkham:job:{job_id}", mapping={
        "pool": "cpu-light",
        "payload": json.dumps({"message": "Smoke test!", "delay": 0.1}),
        "priority": 1,
        "status": "pending",
    })

    # Wait for completion
    for _ in range(20):
        status = await r.hget(f"arkham:job:{job_id}", "status")
        if status == b"completed":
            break
        await asyncio.sleep(0.2)

    if status == b"completed":
        result = json.loads(await r.hget(f"arkham:job:{job_id}", "result"))
        print(f"   OK - Job completed: {result.get('message')}")
    else:
        print(f"   FAILED - Job status: {status}")
        return False

    # Stop worker
    print("\n4. Testing graceful shutdown...")
    worker._shutdown_event.set()
    await asyncio.wait_for(task, timeout=5)

    # Check deregistered
    exists = await r.exists(f"arkham:worker:{worker.worker_id}")
    if not exists:
        print("   OK - Worker deregistered")
    else:
        print("   FAILED - Worker still registered")
        return False

    # Cleanup
    await r.delete(f"arkham:job:{job_id}")
    await r.aclose()

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED!")
    print("=" * 60)
    return True


if __name__ == "__main__":
    result = asyncio.run(smoke_test())
    exit(0 if result else 1)
