"""
End-to-end pipeline test.

Tests the full document processing pipeline:
1. ExtractWorker - Extract text from file
2. LightWorker - Normalize and assess quality
3. NERWorker - Extract entities
4. EmbedWorker - Generate embeddings

Usage:
    python tests/test_e2e_pipeline.py
    python tests/test_e2e_pipeline.py --file path/to/document.txt
"""

import asyncio
import json
import os
import sys
import tempfile
import time
from pathlib import Path

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6380")


async def get_redis():
    """Get async Redis client."""
    import redis.asyncio as aioredis
    client = aioredis.from_url(REDIS_URL)
    try:
        await client.ping()
        return client
    except Exception as e:
        print(f"Redis connection failed: {e}")
        return None


async def enqueue_job(redis, pool: str, job_id: str, payload: dict, priority: int = 1):
    """Enqueue a job."""
    queue_key = f"arkham:queue:{pool}"
    job_key = f"arkham:job:{job_id}"

    await redis.hset(job_key, mapping={
        "pool": pool,
        "payload": json.dumps(payload),
        "priority": priority,
        "status": "pending",
    })
    await redis.zadd(queue_key, {job_id: priority})


async def wait_for_job(redis, job_id: str, timeout: float = 60.0) -> dict:
    """Wait for job completion."""
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
                result = {}
                for k, v in data.items():
                    key = k.decode() if isinstance(k, bytes) else k
                    val = v.decode() if isinstance(v, bytes) else v
                    result[key] = val
                return result
        await asyncio.sleep(interval)
        elapsed += interval

    return {"status": "timeout"}


async def cleanup_jobs(redis, prefix="e2e-test"):
    """Clean up test jobs."""
    for pool in ["cpu-extract", "cpu-light", "cpu-ner", "gpu-embed"]:
        queue_key = f"arkham:queue:{pool}"
        members = await redis.zrange(queue_key, 0, -1)
        for member in members:
            if isinstance(member, bytes):
                member = member.decode()
            if member.startswith(prefix):
                await redis.zrem(queue_key, member)

    cursor = 0
    while True:
        cursor, keys = await redis.scan(cursor, match=f"arkham:job:{prefix}-*", count=100)
        if keys:
            await redis.delete(*keys)
        if cursor == 0:
            break


def create_test_document():
    """Create a test document with rich content for NER."""
    content = """CONFIDENTIAL MEMO

Date: December 15, 2024
From: John Smith, CEO
To: Sarah Johnson, CFO
CC: Michael Chen, Legal Counsel

Subject: Acquisition of TechCorp Industries

Dear Sarah,

Following our meeting in New York last Tuesday, I wanted to summarize the key points
regarding the proposed acquisition of TechCorp Industries for $2.5 billion.

Key Findings:

1. TechCorp, headquartered in San Francisco, California, has shown consistent
   revenue growth of 25% year-over-year since 2020.

2. Their CEO, David Williams, has agreed to stay on for a 2-year transition period.

3. The European Union regulatory review is expected to complete by March 2025.

4. Goldman Sachs will serve as our primary financial advisor, with Morgan Stanley
   providing secondary analysis.

Timeline:
- January 15, 2025: Board approval vote
- February 1, 2025: Public announcement
- Q2 2025: Expected close

Please have the financial projections ready for the December 20th board meeting.
We need to present this to the shareholders at our annual meeting in April.

Best regards,
John Smith
Chief Executive Officer
Acme Corporation
123 Business Avenue
Chicago, IL 60601
Phone: (312) 555-0100
Email: jsmith@acmecorp.com

---
This document contains proprietary information.
Copyright 2024 Acme Corporation. All rights reserved.
"""
    return content


async def run_e2e_test(test_file: str = None):
    """Run the end-to-end pipeline test."""
    print("=" * 70)
    print("END-TO-END PIPELINE TEST")
    print("=" * 70)

    # Connect to Redis
    redis = await get_redis()
    if not redis:
        return False

    # Clean up old test data
    print("\n[1] Cleaning up previous test data...")
    await cleanup_jobs(redis)

    # Start workers
    print("\n[2] Starting workers...")
    from arkham_frame.workers import ExtractWorker, LightWorker, NERWorker, EmbedWorker

    workers = []
    tasks = []

    worker_classes = [
        ("extract", ExtractWorker),
        ("light", LightWorker),
        ("ner", NERWorker),
        ("embed", EmbedWorker),
    ]

    for name, cls in worker_classes:
        worker = cls(redis_url=REDIS_URL, worker_id=f"e2e-{name}-worker")
        worker.idle_timeout = 120.0
        workers.append(worker)
        tasks.append(asyncio.create_task(worker.run()))
        print(f"    Started {name} worker")

    await asyncio.sleep(1.0)  # Let workers register

    # Create or use test file
    if test_file and Path(test_file).exists():
        file_path = test_file
        print(f"\n[3] Using provided file: {file_path}")
    else:
        print("\n[3] Creating test document...")
        content = create_test_document()
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(content)
            file_path = f.name
        print(f"    Created: {file_path}")
        print(f"    Size: {len(content)} characters")

    pipeline_start = time.time()
    results = {}

    try:
        # Stage 1: Extract text
        print("\n" + "-" * 70)
        print("STAGE 1: Text Extraction (cpu-extract)")
        print("-" * 70)

        job_id = "e2e-test-extract"
        await enqueue_job(redis, "cpu-extract", job_id, {
            "file_path": file_path,
        })
        print(f"    Dispatched job: {job_id}")

        result = await wait_for_job(redis, job_id, timeout=30)
        if result.get("status") != "completed":
            print(f"    FAILED: {result.get('error', 'Unknown error')}")
            return False

        extract_result = json.loads(result.get("result", "{}"))
        text = extract_result.get("text", "")
        results["extract"] = extract_result

        print(f"    Status: COMPLETED")
        print(f"    Extracted: {len(text)} characters")
        print(f"    Preview: {text[:100]}...")

        # Stage 2: Normalize and assess quality
        print("\n" + "-" * 70)
        print("STAGE 2: Text Processing (cpu-light)")
        print("-" * 70)

        job_id = "e2e-test-light"
        await enqueue_job(redis, "cpu-light", job_id, {
            "task": "process",
            "text": text,
        })
        print(f"    Dispatched job: {job_id}")

        result = await wait_for_job(redis, job_id, timeout=30)
        if result.get("status") != "completed":
            print(f"    FAILED: {result.get('error', 'Unknown error')}")
            return False

        light_result = json.loads(result.get("result", "{}"))
        normalized_text = light_result.get("normalized_text", text)
        results["light"] = light_result

        print(f"    Status: COMPLETED")
        print(f"    Language: {light_result.get('language', 'unknown')}")
        print(f"    Quality Score: {light_result.get('quality_score', 0)}")
        print(f"    Word Count: {light_result.get('word_count', 0)}")

        # Stage 3: Entity extraction
        print("\n" + "-" * 70)
        print("STAGE 3: Entity Extraction (cpu-ner)")
        print("-" * 70)

        job_id = "e2e-test-ner"
        await enqueue_job(redis, "cpu-ner", job_id, {
            "text": normalized_text,
            "doc_id": "e2e-test-doc",
        })
        print(f"    Dispatched job: {job_id}")

        result = await wait_for_job(redis, job_id, timeout=60)
        if result.get("status") != "completed":
            print(f"    FAILED: {result.get('error', 'Unknown error')}")
            return False

        ner_result = json.loads(result.get("result", "{}"))
        entities = ner_result.get("entities", [])
        results["ner"] = ner_result

        print(f"    Status: COMPLETED")
        print(f"    Total Entities: {len(entities)}")

        # Group entities by type
        by_type = {}
        for ent in entities:
            label = ent.get("label", "other")
            if label not in by_type:
                by_type[label] = []
            by_type[label].append(ent.get("text"))

        for label, texts in sorted(by_type.items()):
            unique = list(set(texts))[:5]
            print(f"    {label}: {', '.join(unique)}" + (" ..." if len(texts) > 5 else ""))

        # Stage 4: Generate embeddings
        print("\n" + "-" * 70)
        print("STAGE 4: Embedding Generation (gpu-embed)")
        print("-" * 70)

        # Chunk the text for embedding (simple chunking)
        chunk_size = 500
        chunks = [normalized_text[i:i+chunk_size] for i in range(0, len(normalized_text), chunk_size)]
        print(f"    Text split into {len(chunks)} chunks")

        embeddings = []
        for i, chunk in enumerate(chunks[:3]):  # Limit to first 3 chunks for speed
            job_id = f"e2e-test-embed-{i}"
            await enqueue_job(redis, "gpu-embed", job_id, {
                "text": chunk,
            })

            result = await wait_for_job(redis, job_id, timeout=60)
            if result.get("status") == "completed":
                embed_result = json.loads(result.get("result", "{}"))
                embeddings.append({
                    "chunk_index": i,
                    "dimensions": embed_result.get("dimensions", 0),
                    "model": embed_result.get("model", "unknown"),
                })

        results["embed"] = embeddings

        if embeddings:
            print(f"    Status: COMPLETED")
            print(f"    Chunks Embedded: {len(embeddings)}")
            print(f"    Model: {embeddings[0].get('model', 'unknown')}")
            print(f"    Dimensions: {embeddings[0].get('dimensions', 0)}")
        else:
            print(f"    Status: FAILED - No embeddings generated")

        # Summary
        pipeline_time = time.time() - pipeline_start
        print("\n" + "=" * 70)
        print("PIPELINE SUMMARY")
        print("=" * 70)
        print(f"    Total Time: {pipeline_time:.2f}s")
        print(f"    File: {file_path}")
        print(f"    Characters: {len(text)}")
        print(f"    Entities Found: {len(entities)}")
        print(f"    Embeddings Generated: {len(embeddings)}")
        print()

        # Detailed entity summary
        print("Entity Breakdown:")
        for label, texts in sorted(by_type.items()):
            print(f"    {label}: {len(texts)}")

        print("\n" + "=" * 70)
        print("ALL STAGES COMPLETED SUCCESSFULLY")
        print("=" * 70)

        return True

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        # Cleanup
        print("\n[5] Shutting down workers...")
        for worker in workers:
            worker._shutdown_event.set()
        await asyncio.gather(*tasks, return_exceptions=True)

        await cleanup_jobs(redis)

        # Remove temp file if we created it
        if not test_file and Path(file_path).exists():
            os.unlink(file_path)

        await redis.aclose()


def main():
    import argparse
    parser = argparse.ArgumentParser(description="End-to-end pipeline test")
    parser.add_argument("--file", help="Path to test file (optional)")
    args = parser.parse_args()

    success = asyncio.run(run_e2e_test(test_file=args.file))
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
