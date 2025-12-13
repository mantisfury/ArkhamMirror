"""
Contradiction Detection Worker

RQ worker for background contradiction detection with:
- Per-entity processing with progress tracking
- GPU thermal protection (cooldowns)
- Pause/stop control via Redis
- Priority queue by entity connection count
"""

import os
import sys
import time
import uuid
import logging
from pathlib import Path
from typing import List, Dict, Optional
from dotenv import load_dotenv

load_dotenv()

# Add project root to path for central config
project_root = Path(__file__).resolve()
while project_root.name != "ArkhamMirror" and project_root.parent != project_root:
    project_root = project_root.parent
sys.path.insert(0, str(project_root))

from config import REDIS_URL
from redis import Redis

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Redis connection - use central config
redis_conn = Redis.from_url(REDIS_URL)

# Default cooldown settings - cooldown happens between batches (50 entities)
DEFAULT_COOLDOWN_ENTITIES = 50  # Pause after each batch
DEFAULT_COOLDOWN_SECONDS = 30  # How long to pause between batches
DEFAULT_MAX_RUNTIME_MINUTES = 60  # Force break after this


# ==================== Phase 2: Caching Helpers ====================


def compute_entity_content_hash(
    session, entity_id: int, doc_ids: Optional[List[int]] = None
) -> tuple[str, int]:
    """
    Compute a hash of all chunk content related to an entity.

    Returns (hash, chunk_count) tuple.
    """
    import hashlib
    from arkham.services.db.models import Entity, Chunk

    # Get chunks for entity via its mentions
    entity_records = (
        session.query(Entity)
        .filter(Entity.canonical_entity_id == entity_id)
        .limit(20)
        .all()
    )
    doc_ids_for_entity = list(set(e.doc_id for e in entity_records if e.doc_id))

    if not doc_ids_for_entity:
        return "", 0

    # Filter by doc_ids if provided
    if doc_ids:
        doc_ids_for_entity = [d for d in doc_ids_for_entity if d in doc_ids]

    if not doc_ids_for_entity:
        return "", 0

    # Get chunks from these docs
    chunks = (
        session.query(Chunk)
        .filter(Chunk.doc_id.in_(doc_ids_for_entity))
        .order_by(Chunk.id)
        .limit(10)  # Same limit as analysis
        .all()
    )

    if not chunks:
        return "", 0

    # Create hash from chunk texts
    hasher = hashlib.md5()
    for chunk in chunks:
        hasher.update(chunk.text.encode("utf-8"))

    return hasher.hexdigest(), len(chunks)


def get_entity_cache(session, entity_id: int):
    """Get cached analysis data for an entity."""
    from arkham.services.db.models import EntityAnalysisCache

    return (
        session.query(EntityAnalysisCache)
        .filter(EntityAnalysisCache.entity_id == entity_id)
        .first()
    )


def update_entity_cache(
    session,
    entity_id: int,
    content_hash: str,
    chunk_count: int,
    contradiction_count: int,
):
    """Update or insert cache entry for an entity."""
    from arkham.services.db.models import EntityAnalysisCache
    from datetime import datetime

    cache = get_entity_cache(session, entity_id)

    if cache:
        cache.content_hash = content_hash
        cache.last_analyzed_at = datetime.utcnow()
        cache.chunk_count = chunk_count
        cache.contradiction_count = contradiction_count
    else:
        cache = EntityAnalysisCache(
            entity_id=entity_id,
            content_hash=content_hash,
            chunk_count=chunk_count,
            contradiction_count=contradiction_count,
        )
        session.add(cache)

    session.commit()


def should_skip_entity(
    session, entity_id: int, doc_ids: Optional[List[int]], force_refresh: bool = False
) -> tuple[bool, str]:
    """
    Check if an entity can be skipped (already analyzed with same content).

    Returns (should_skip, reason) tuple.
    """
    if force_refresh:
        return False, "force refresh"

    cache = get_entity_cache(session, entity_id)
    if not cache:
        return False, "no cache"

    current_hash, current_count = compute_entity_content_hash(
        session, entity_id, doc_ids
    )

    if not current_hash:
        return False, "no content"

    if cache.content_hash == current_hash and cache.chunk_count == current_count:
        return True, f"cache hit (hash match, {cache.contradiction_count} existing)"

    return False, "content changed"


def get_setting(key: str, default: int) -> int:
    """Get a setting from Redis or return default."""
    value = redis_conn.get(f"contradiction_settings:{key}")
    if value:
        try:
            return int(value)
        except ValueError:
            pass
    return default


def update_job_status(job_id: str, **kwargs):
    """Update job status in Redis hash."""
    redis_conn.hset(f"contradiction_job:{job_id}", mapping=kwargs)
    # Set TTL of 1 hour on job status
    redis_conn.expire(f"contradiction_job:{job_id}", 3600)


def get_job_control(job_id: str) -> str:
    """Get control signal for job (run/pause/stop)."""
    control = redis_conn.get(f"contradiction_job:{job_id}:control")
    return control.decode() if control else "run"


def set_job_control(job_id: str, control: str):
    """Set control signal for job."""
    redis_conn.set(f"contradiction_job:{job_id}:control", control)
    redis_conn.expire(f"contradiction_job:{job_id}:control", 3600)


def wait_if_paused(job_id: str) -> bool:
    """
    Check if job is paused and wait until resumed or stopped.
    Returns False if job should stop, True to continue.
    """
    while True:
        control = get_job_control(job_id)
        if control == "run":
            return True
        elif control == "stop":
            return False
        elif control == "pause":
            update_job_status(job_id, status="paused")
            time.sleep(2)  # Check every 2 seconds
        else:
            return True


def detect_batch(
    entity_ids: List[int],
    doc_ids: Optional[List[int]] = None,
    job_id: Optional[str] = None,
    force_refresh: bool = False,
    batch_number: int = 1,
    auto_continue: bool = False,
) -> Dict:
    """
    Detect contradictions for a batch of entities.

    This is the main RQ job entry point for background detection.

    Args:
        entity_ids: List of canonical entity IDs to analyze
        doc_ids: Optional document filter
        job_id: Job ID for progress tracking (generated if not provided)
        force_refresh: If True, bypass cache and re-analyze all entities
        batch_number: Which batch this is (for batch tracking)
        auto_continue: Whether to auto-start next batch when done

    Returns:
        Dict with results summary
    """
    # Lazy import to avoid loading at worker startup
    from arkham.services.contradiction_service import get_contradiction_service

    if not job_id:
        job_id = str(uuid.uuid4())[:8]

    logger.info(
        f"[Job {job_id}] Starting batch detection for {len(entity_ids)} entities"
    )

    # Initialize job status
    update_job_status(
        job_id,
        status="running",
        total=len(entity_ids),
        processed=0,
        found=0,
        current_entity="",
        started_at=str(int(time.time())),
        error="",
    )

    # Get settings
    cooldown_entities = get_setting("cooldown_entities", DEFAULT_COOLDOWN_ENTITIES)
    cooldown_seconds = get_setting("cooldown_seconds", DEFAULT_COOLDOWN_SECONDS)
    max_runtime = get_setting("max_runtime_minutes", DEFAULT_MAX_RUNTIME_MINUTES)

    service = get_contradiction_service()
    session = service.Session()

    start_time = time.time()
    total_found = 0
    processed = 0

    try:
        # Get entity objects for names
        from arkham.services.db.models import CanonicalEntity

        entities = (
            session.query(CanonicalEntity)
            .filter(CanonicalEntity.id.in_(entity_ids))
            .all()
        )

        entity_map = {e.id: e for e in entities}

        for i, entity_id in enumerate(entity_ids):
            # Check for pause/stop
            if not wait_if_paused(job_id):
                logger.info(f"[Job {job_id}] Stopped by user")
                update_job_status(job_id, status="stopped")
                return {
                    "status": "stopped",
                    "processed": processed,
                    "found": total_found,
                }

            # Check max runtime
            elapsed_minutes = (time.time() - start_time) / 60
            if elapsed_minutes > max_runtime:
                logger.warning(
                    f"[Job {job_id}] Max runtime {max_runtime}min exceeded, stopping"
                )
                update_job_status(
                    job_id,
                    status="timeout",
                    error=f"Exceeded max runtime of {max_runtime} minutes",
                )
                return {
                    "status": "timeout",
                    "processed": processed,
                    "found": total_found,
                }

            entity = entity_map.get(entity_id)
            entity_name = entity.canonical_name if entity else f"Entity {entity_id}"

            update_job_status(
                job_id,
                status="running",
                current_entity=entity_name,
                processed=processed,
            )

            logger.info(
                f"[Job {job_id}] Processing entity {i + 1}/{len(entity_ids)}: {entity_name}"
            )

            # Phase 2: Check cache - skip if already analyzed with same content
            skip, skip_reason = should_skip_entity(
                session, entity_id, doc_ids, force_refresh
            )
            if skip:
                logger.info(f"[Job {job_id}] Skipped {entity_name}: {skip_reason}")
                processed += 1
                # Add existing contradiction count from cache
                cache = get_entity_cache(session, entity_id)
                if cache:
                    total_found += cache.contradiction_count
                update_job_status(job_id, processed=processed, found=total_found)
                continue

            # Run detection for this entity
            try:
                if entity:
                    contradictions = service._analyze_entity_contradictions(
                        session, entity, doc_ids
                    )
                    found_count = len(contradictions)
                    total_found += found_count
                    logger.info(
                        f"[Job {job_id}] Found {found_count} contradictions for {entity_name}"
                    )

                    # Phase 2: Update cache
                    content_hash, chunk_count = compute_entity_content_hash(
                        session, entity_id, doc_ids
                    )
                    if content_hash:
                        update_entity_cache(
                            session, entity_id, content_hash, chunk_count, found_count
                        )
                        logger.info(f"[Job {job_id}] Updated cache for {entity_name}")

            except Exception as e:
                logger.error(f"[Job {job_id}] Error processing {entity_name}: {e}")
                # Continue with next entity

            processed += 1
            update_job_status(job_id, processed=processed, found=total_found)

            # GPU cooldown
            if processed > 0 and processed % cooldown_entities == 0:
                logger.info(f"[Job {job_id}] Cooling down for {cooldown_seconds}s...")
                update_job_status(job_id, status="cooldown")
                time.sleep(cooldown_seconds)
                update_job_status(job_id, status="running")

        # Complete
        update_job_status(
            job_id,
            status="complete",
            processed=processed,
            found=total_found,
            current_entity="",
            completed_at=str(int(time.time())),
        )

        logger.info(
            f"[Job {job_id}] Completed: {processed} entities, {total_found} contradictions"
        )
        result = {
            "status": "complete",
            "processed": processed,
            "found": total_found,
            "job_id": job_id,
            "batch_number": batch_number,
        }

        # Update batch record in database
        try:
            from arkham.services.db.models import ContradictionBatch
            from datetime import datetime

            batch_record = (
                session.query(ContradictionBatch)
                .filter(ContradictionBatch.batch_number == batch_number)
                .first()
            )
            if batch_record:
                batch_record.status = "complete"
                batch_record.completed_at = datetime.utcnow()
                batch_record.contradictions_found = total_found
                session.commit()
                logger.info(
                    f"[Job {job_id}] Updated batch {batch_number} status to complete"
                )
        except Exception as e:
            logger.error(f"[Job {job_id}] Failed to update batch record: {e}")

        # Auto-continue to next batch if enabled
        if auto_continue:
            try:
                next_job_id = service.start_next_batch(
                    entity_ids=None,
                    doc_ids=doc_ids,
                    force_refresh=force_refresh,
                    auto_continue=True,
                )
                if next_job_id:
                    logger.info(
                        f"[Job {job_id}] Auto-continued to next batch: {next_job_id}"
                    )
                    result["next_job_id"] = next_job_id
                else:
                    logger.info(f"[Job {job_id}] All batches complete!")
            except Exception as e:
                logger.error(f"[Job {job_id}] Failed to start next batch: {e}")

        return result

    except Exception as e:
        logger.error(f"[Job {job_id}] Fatal error: {e}")
        update_job_status(job_id, status="failed", error=str(e))

        # Mark batch as incomplete
        try:
            from arkham.services.db.models import ContradictionBatch

            batch_record = (
                session.query(ContradictionBatch)
                .filter(ContradictionBatch.batch_number == batch_number)
                .first()
            )
            if batch_record:
                batch_record.status = "incomplete"
                batch_record.error = str(e)
                session.commit()
        except Exception:
            pass

        return {"status": "failed", "error": str(e)}
    finally:
        session.close()


def detect_all(job_id: Optional[str] = None) -> Dict:
    """
    Detect contradictions for all entities in the corpus.

    Entities are processed in order of connection count (most connected first).

    Args:
        job_id: Job ID for progress tracking

    Returns:
        Dict with results summary
    """
    # Lazy import
    from arkham.services.contradiction_service import get_contradiction_service
    from arkham.services.db.models import CanonicalEntity
    from sqlalchemy import desc

    if not job_id:
        job_id = str(uuid.uuid4())[:8]

    logger.info(f"[Job {job_id}] Starting full corpus detection")

    update_job_status(job_id, status="initializing", error="")

    service = get_contradiction_service()
    session = service.Session()

    try:
        # Get all entities ordered by total_mentions (proxy for connection count)
        entities = (
            session.query(CanonicalEntity)
            .order_by(desc(CanonicalEntity.total_mentions))
            .all()
        )

        entity_ids = [e.id for e in entities]
        session.close()

        if not entity_ids:
            update_job_status(job_id, status="complete", error="No entities found")
            return {"status": "complete", "processed": 0, "found": 0}

        logger.info(f"[Job {job_id}] Found {len(entity_ids)} entities to process")

        # Delegate to batch detection
        return detect_batch(entity_ids, doc_ids=None, job_id=job_id)

    except Exception as e:
        logger.error(f"[Job {job_id}] Error getting entities: {e}")
        update_job_status(job_id, status="failed", error=str(e))
        session.close()
        return {"status": "failed", "error": str(e)}


def detect_for_entity(entity_id: int, job_id: Optional[str] = None) -> Dict:
    """
    Detect contradictions for a single entity.

    Convenience wrapper around detect_batch for single entity.

    Args:
        entity_id: The canonical entity ID to analyze
        job_id: Optional job ID for tracking

    Returns:
        Dict with results
    """
    return detect_batch([entity_id], doc_ids=None, job_id=job_id)
