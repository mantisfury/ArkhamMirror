"""
Example worker implementations for testing.

These workers demonstrate the BaseWorker pattern and can be used
to verify the worker infrastructure is functioning correctly.
"""

import asyncio
import logging
from typing import Dict, Any

from .base import BaseWorker

logger = logging.getLogger(__name__)


class EchoWorker(BaseWorker):
    """
    Simple echo worker for testing.

    Processes jobs by echoing back the payload with a delay.
    Uses cpu-light pool for testing.
    """

    pool = "cpu-light"
    name = "EchoWorker"

    # Fast polling for testing
    poll_interval = 0.5
    idle_timeout = 30.0

    async def process_job(self, job_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Echo the payload back.

        Payload:
            delay: Optional sleep time in seconds (default 0.5)
            message: Optional message to echo

        Returns:
            Echoed payload with processing info
        """
        delay = payload.get("delay", 0.5)
        message = payload.get("message", "Hello from EchoWorker!")

        logger.info(f"EchoWorker processing: {message} (delay={delay}s)")

        # Simulate work
        await asyncio.sleep(delay)

        return {
            "echoed": True,
            "message": message,
            "delay": delay,
            "worker_id": self.worker_id,
        }


class FailWorker(BaseWorker):
    """
    Worker that always fails (for testing error handling).

    Uses cpu-light pool for testing.
    """

    pool = "cpu-light"
    name = "FailWorker"

    poll_interval = 0.5
    idle_timeout = 30.0
    max_retries = 2

    async def process_job(self, job_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Always fails."""
        fail_after = payload.get("fail_after", 0.1)

        await asyncio.sleep(fail_after)

        raise ValueError(f"FailWorker intentionally failed (job {job_id})")


class SlowWorker(BaseWorker):
    """
    Worker that takes a long time (for testing timeouts).

    Uses cpu-heavy pool for testing.
    """

    pool = "cpu-heavy"
    name = "SlowWorker"

    poll_interval = 1.0
    idle_timeout = 60.0
    job_timeout = 10.0  # Short timeout for testing

    async def process_job(self, job_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Sleep for a configurable time."""
        sleep_time = payload.get("sleep", 5.0)

        logger.info(f"SlowWorker sleeping for {sleep_time}s")
        await asyncio.sleep(sleep_time)

        return {"slept": sleep_time}


# Map pools to example workers for testing
EXAMPLE_WORKERS = {
    "cpu-light": EchoWorker,
    "cpu-heavy": SlowWorker,
}


async def test_worker_infrastructure():
    """
    Quick test of worker infrastructure.

    Run this to verify workers can connect and process jobs.
    """
    import os
    import redis.asyncio as aioredis
    import json
    import uuid

    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6380")

    print("Testing Worker Infrastructure")
    print("=" * 50)

    # 1. Test Redis connection
    print("\n1. Testing Redis connection...")
    try:
        r = aioredis.from_url(redis_url)
        await r.ping()
        print(f"   OK - Connected to {redis_url}")
    except Exception as e:
        print(f"   FAILED - {e}")
        print("   Make sure Redis is running!")
        return False

    # 2. Enqueue a test job
    print("\n2. Enqueueing test job...")
    job_id = f"test-{uuid.uuid4().hex[:8]}"
    queue_key = "arkham:queue:cpu-light"
    job_key = f"arkham:job:{job_id}"

    await r.zadd(queue_key, {job_id: 1})
    await r.hset(job_key, mapping={
        "pool": "cpu-light",
        "payload": json.dumps({"message": "Test message", "delay": 0.1}),
        "priority": 1,
        "status": "pending",
    })
    print(f"   OK - Created job {job_id}")

    # 3. Start a worker
    print("\n3. Starting EchoWorker...")
    worker = EchoWorker(redis_url=redis_url, worker_id="test-worker")

    # Run worker for a short time
    async def run_briefly():
        await worker.connect()
        await worker.register()

        # Process one job
        job = await worker.dequeue_job()
        if job:
            print(f"   Got job: {job['id']}")
            result = await worker.process_job(job["id"], job["payload"])
            await worker.complete_job(job["id"], result)
            print(f"   Result: {result}")
        else:
            print("   No job found in queue")

        await worker.deregister()
        await worker.disconnect()

    await run_briefly()

    # 4. Check job status
    print("\n4. Checking job status...")
    status = await r.hget(job_key, "status")
    if status:
        status = status.decode() if isinstance(status, bytes) else status
    print(f"   Job status: {status}")

    # Cleanup
    await r.delete(job_key)
    await r.close()

    if status == "completed":
        print("\n" + "=" * 50)
        print("SUCCESS - Worker infrastructure is functional!")
        return True
    else:
        print("\n" + "=" * 50)
        print(f"FAILED - Job status is '{status}', expected 'completed'")
        return False


if __name__ == "__main__":
    asyncio.run(test_worker_infrastructure())
