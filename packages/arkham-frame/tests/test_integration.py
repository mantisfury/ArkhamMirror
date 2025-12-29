"""
Integration tests for worker-shard wiring.

Tests real file processing through workers:
- ExtractWorker: PDF/DOCX text extraction
- NERWorker: Entity extraction
- EmbedWorker: Text embeddings
- LightWorker: Text normalization

Usage:
    # Quick test (no file processing)
    python tests/test_integration.py

    # Full test with real files
    python tests/test_integration.py --full

    # Test specific worker
    python tests/test_integration.py --worker extract
    python tests/test_integration.py --worker ner
    python tests/test_integration.py --worker embed
    python tests/test_integration.py --worker light
"""

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

# Test configuration
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")


async def get_redis():
    """Get async Redis client."""
    import redis.asyncio as aioredis
    client = aioredis.from_url(REDIS_URL)
    try:
        await client.ping()
        return client
    except Exception as e:
        print(f"Redis connection failed: {e}")
        print("Make sure Redis is running on port 6379")
        return None


async def cleanup_test_jobs(redis, prefix="integration-test"):
    """Clean up test jobs from Redis."""
    cursor = 0
    while True:
        cursor, keys = await redis.scan(cursor, match=f"arkham:job:{prefix}-*", count=100)
        if keys:
            await redis.delete(*keys)
        if cursor == 0:
            break

    # Clean queue entries
    for pool in ["cpu-light", "cpu-extract", "cpu-ner", "gpu-embed"]:
        queue_key = f"arkham:queue:{pool}"
        # Remove any test entries
        members = await redis.zrange(queue_key, 0, -1)
        for member in members:
            if isinstance(member, bytes):
                member = member.decode()
            if member.startswith(prefix):
                await redis.zrem(queue_key, member)


async def wait_for_job_completion(redis, job_id: str, timeout: float = 30.0) -> dict:
    """Wait for job to complete and return result."""
    job_key = f"arkham:job:{job_id}"
    elapsed = 0.0
    interval = 0.2

    while elapsed < timeout:
        status = await redis.hget(job_key, "status")
        if status:
            if isinstance(status, bytes):
                status = status.decode()
            if status in ["completed", "failed"]:
                data = await redis.hgetall(job_key)
                return {
                    k.decode() if isinstance(k, bytes) else k:
                    v.decode() if isinstance(v, bytes) else v
                    for k, v in data.items()
                }
        await asyncio.sleep(interval)
        elapsed += interval

    return {"status": "timeout"}


async def enqueue_job(redis, pool: str, job_id: str, payload: dict, priority: int = 1):
    """Enqueue a job to a worker pool."""
    queue_key = f"arkham:queue:{pool}"
    job_key = f"arkham:job:{job_id}"

    # Store job data
    await redis.hset(job_key, mapping={
        "pool": pool,
        "payload": json.dumps(payload),
        "priority": priority,
        "status": "pending",
    })

    # Add to queue
    await redis.zadd(queue_key, {job_id: priority})

    print(f"  Enqueued job {job_id} to {pool}")


# =============================================================================
# Test: LightWorker
# =============================================================================

async def test_light_worker(redis) -> bool:
    """Test LightWorker text processing."""
    print("\n--- Testing LightWorker (cpu-light) ---")

    job_id = "integration-test-light-1"

    # Test 'process' task (all-in-one) which returns normalized_text
    await enqueue_job(redis, "cpu-light", job_id, {
        "task": "process",
        "text": "  Hello   World!  This\thas\tweird   spacing.  ",
    })

    result = await wait_for_job_completion(redis, job_id, timeout=10)

    if result.get("status") == "completed":
        result_data = json.loads(result.get("result", "{}"))
        normalized = result_data.get("normalized_text", "")
        language = result_data.get("language", "unknown")
        quality = result_data.get("quality_score", 0)

        print(f"  Input:  '  Hello   World!  This\\thas\\tweird   spacing.  '")
        print(f"  Output: '{normalized}'")
        print(f"  Language: {language}, Quality: {quality}")

        if "Hello World!" in normalized and "weird spacing" in normalized:
            print("  PASS: Text normalized correctly")
            return True
        else:
            print(f"  FAIL: Unexpected normalized output")
            return False
    else:
        print(f"  FAIL: Job status = {result.get('status')}")
        if result.get("error"):
            print(f"  Error: {result.get('error')}")
        return False


# =============================================================================
# Test: NERWorker
# =============================================================================

async def test_ner_worker(redis) -> bool:
    """Test NERWorker entity extraction."""
    print("\n--- Testing NERWorker (cpu-ner) ---")

    job_id = "integration-test-ner-1"

    test_text = "John Smith met with Apple CEO Tim Cook in New York on January 15, 2024."

    await enqueue_job(redis, "cpu-ner", job_id, {
        "text": test_text,
        "doc_id": "test-doc-1",
    })

    result = await wait_for_job_completion(redis, job_id, timeout=30)

    if result.get("status") == "completed":
        result_data = json.loads(result.get("result", "{}"))
        entities = result_data.get("entities", [])
        entity_count = result_data.get("entity_count", 0)

        print(f"  Input: '{test_text}'")
        print(f"  Found {entity_count} entities:")

        for ent in entities[:5]:
            print(f"    - {ent.get('text')}: {ent.get('label')}")

        # Check for expected entities
        entity_texts = [e.get("text") for e in entities]
        expected = ["John Smith", "Apple", "Tim Cook", "New York"]
        found = sum(1 for e in expected if any(e in t for t in entity_texts))

        if found >= 2:
            print(f"  PASS: Found {found}/4 expected entities")
            return True
        else:
            print(f"  FAIL: Only found {found}/4 expected entities")
            return False
    else:
        print(f"  FAIL: Job status = {result.get('status')}")
        if result.get("error"):
            print(f"  Error: {result.get('error')}")
        return False


# =============================================================================
# Test: EmbedWorker
# =============================================================================

async def test_embed_worker(redis) -> bool:
    """Test EmbedWorker embedding generation."""
    print("\n--- Testing EmbedWorker (gpu-embed) ---")

    job_id = "integration-test-embed-1"

    await enqueue_job(redis, "gpu-embed", job_id, {
        "text": "This is a test sentence for embedding generation.",
    })

    result = await wait_for_job_completion(redis, job_id, timeout=60)

    if result.get("status") == "completed":
        result_data = json.loads(result.get("result", "{}"))
        embedding = result_data.get("embedding", [])
        dimensions = result_data.get("dimensions", 0)
        model = result_data.get("model", "unknown")

        print(f"  Model: {model}")
        print(f"  Dimensions: {dimensions}")
        print(f"  Embedding preview: [{embedding[0]:.4f}, {embedding[1]:.4f}, ...]")

        if dimensions > 0 and len(embedding) == dimensions:
            print(f"  PASS: Generated {dimensions}-dim embedding")
            return True
        else:
            print(f"  FAIL: Invalid embedding dimensions")
            return False
    else:
        print(f"  FAIL: Job status = {result.get('status')}")
        if result.get("error"):
            print(f"  Error: {result.get('error')}")
        return False


# =============================================================================
# Test: ExtractWorker
# =============================================================================

async def test_extract_worker(redis) -> bool:
    """Test ExtractWorker text extraction."""
    print("\n--- Testing ExtractWorker (cpu-extract) ---")

    # Create a simple test text file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write("This is a test document.\n")
        f.write("It has multiple lines.\n")
        f.write("The ExtractWorker should read this text.")
        test_file = f.name

    try:
        job_id = "integration-test-extract-1"

        await enqueue_job(redis, "cpu-extract", job_id, {
            "file_path": test_file,
        })

        result = await wait_for_job_completion(redis, job_id, timeout=30)

        if result.get("status") == "completed":
            result_data = json.loads(result.get("result", "{}"))
            text = result_data.get("text", "")
            success = result_data.get("success", False)

            print(f"  File: {test_file}")
            print(f"  Extracted {len(text)} characters")
            print(f"  Preview: '{text[:50]}...'")

            if success and "test document" in text:
                print("  PASS: Text extracted correctly")
                return True
            else:
                print("  FAIL: Extraction failed or text mismatch")
                return False
        else:
            print(f"  FAIL: Job status = {result.get('status')}")
            if result.get("error"):
                print(f"  Error: {result.get('error')}")
            return False
    finally:
        # Cleanup
        os.unlink(test_file)


# =============================================================================
# Main
# =============================================================================

async def run_tests(workers: list[str] = None, with_workers: bool = False):
    """Run integration tests."""
    print("=" * 60)
    print("SHATTERED Worker Integration Tests")
    print("=" * 60)

    # Connect to Redis
    redis = await get_redis()
    if not redis:
        return False

    # Cleanup old test data
    print("\nCleaning up old test data...")
    await cleanup_test_jobs(redis)

    # If running with workers, spawn them
    worker_tasks = []
    if with_workers:
        print("\nSpawning workers...")
        from arkham_frame.workers import (
            LightWorker, NERWorker, EmbedWorker, ExtractWorker
        )

        worker_classes = {
            "light": LightWorker,
            "ner": NERWorker,
            "embed": EmbedWorker,
            "extract": ExtractWorker,
        }

        for name, cls in worker_classes.items():
            if workers and name not in workers:
                continue
            worker = cls(redis_url=REDIS_URL, worker_id=f"test-{name}-worker")
            worker.idle_timeout = 60.0
            task = asyncio.create_task(worker.run())
            worker_tasks.append((worker, task))
            print(f"  Started {name} worker")

        # Give workers time to register
        await asyncio.sleep(1.0)

    # Run tests
    results = {}

    test_map = {
        "light": test_light_worker,
        "ner": test_ner_worker,
        "embed": test_embed_worker,
        "extract": test_extract_worker,
    }

    for name, test_fn in test_map.items():
        if workers and name not in workers:
            continue

        try:
            results[name] = await test_fn(redis)
        except Exception as e:
            print(f"\n--- Testing {name}Worker ---")
            print(f"  ERROR: {e}")
            results[name] = False

    # Shutdown workers
    if worker_tasks:
        print("\nShutting down workers...")
        for worker, task in worker_tasks:
            worker._shutdown_event.set()
        await asyncio.gather(*[t for _, t in worker_tasks], return_exceptions=True)

    # Cleanup
    await cleanup_test_jobs(redis)
    await redis.aclose()

    # Summary
    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for name, result in results.items():
        status = "PASS" if result else "FAIL"
        print(f"  {name:10} {status}")

    print(f"\n  {passed}/{total} tests passed")
    print("=" * 60)

    return passed == total


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Worker integration tests")
    parser.add_argument(
        "--worker",
        choices=["light", "ner", "embed", "extract"],
        help="Test specific worker only",
    )
    parser.add_argument(
        "--with-workers",
        action="store_true",
        help="Spawn workers automatically (for CI)",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Run full test suite with all workers",
    )

    args = parser.parse_args()

    workers = [args.worker] if args.worker else None
    with_workers = args.with_workers or args.full

    success = asyncio.run(run_tests(workers=workers, with_workers=with_workers))
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
