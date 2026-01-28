"""Timeline Shard API endpoints."""

import logging
import time
from typing import Annotated, Any, Optional, TYPE_CHECKING

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .models import (
    TimelineEvent,
    EventType,
    DatePrecision,
    ConflictType,
    ConflictSeverity,
    MergeStrategy,
    DateRange,
    ExtractionContext,
)

if TYPE_CHECKING:
    from .shard import TimelineShard

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/timeline", tags=["timeline"])

# These get set by the shard on initialization
_extractor = None
_merger = None
_conflict_detector = None
_database_service = None
_documents_service = None
_entities_service = None
_event_bus = None


def init_api(
    extractor,
    merger,
    conflict_detector,
    database_service,
    documents_service,
    entities_service,
    event_bus
):
    """Initialize API with shard dependencies."""
    global _extractor, _merger, _conflict_detector
    global _database_service, _documents_service, _entities_service, _event_bus

    _extractor = extractor
    _merger = merger
    _conflict_detector = conflict_detector
    _database_service = database_service
    _documents_service = documents_service
    _entities_service = entities_service
    _event_bus = event_bus


def get_shard(request: Request) -> "TimelineShard":
    """Get the timeline shard instance from app state."""
    shard = getattr(request.app.state, "timeline_shard", None)
    if not shard:
        raise HTTPException(status_code=503, detail="Timeline shard not available")
    return shard


# --- Request/Response Models ---


class ExtractionRequest(BaseModel):
    text: Optional[str] = None
    document_id: Optional[str] = None
    context: Optional[dict] = None


class ExtractionResponse(BaseModel):
    events: list[dict]
    count: int
    duration_ms: float


class DocumentTimelineResponse(BaseModel):
    document_id: str
    events: list[dict]
    count: int
    date_range: Optional[dict] = None


class MergeRequest(BaseModel):
    document_ids: list[str]
    merge_strategy: str = "chronological"
    deduplicate: bool = True
    date_range: Optional[dict] = None
    priority_docs: Optional[list[str]] = None


class MergeResponse(BaseModel):
    events: list[dict]
    count: int
    sources: dict[str, int]
    date_range: dict
    duplicates_removed: int


class RangeResponse(BaseModel):
    events: list[dict]
    count: int
    total: int
    has_more: bool


class ConflictsRequest(BaseModel):
    document_ids: list[str]
    conflict_types: Optional[list[str]] = None
    tolerance_days: int = 0


class ConflictsResponse(BaseModel):
    conflicts: list[dict]
    count: int
    by_type: dict[str, int]


class EntityTimelineResponse(BaseModel):
    entity_id: str
    events: list[dict]
    count: int
    date_range: Optional[dict] = None


class NormalizeRequest(BaseModel):
    dates: list[str]
    reference_date: Optional[str] = None
    prefer_format: str = "iso"


class NormalizeResponse(BaseModel):
    normalized: list[dict]


class StatsResponse(BaseModel):
    total_events: int
    total_documents: int
    date_range: Optional[dict]
    by_precision: dict[str, int]
    by_type: dict[str, int]
    avg_confidence: float
    conflicts_detected: int


# --- Endpoints ---


@router.get("/health")
async def health_check(request: Request):
    """Health check endpoint."""
    shard = get_shard(request)

    # Count total events
    if shard.database_service:
        result = await shard.database_service.fetch_one(
            "SELECT COUNT(*) as count FROM arkham_timeline_events"
        )
        event_count = result["count"] if result else 0
    else:
        event_count = 0

    return {
        "status": "healthy",
        "shard": "timeline",
        "version": "0.1.0",
        "event_count": event_count,
    }


@router.get("/count")
async def get_event_count(request: Request):
    """Get count of timeline events (for badge)."""
    shard = get_shard(request)

    if shard.database_service:
        result = await shard.database_service.fetch_one(
            "SELECT COUNT(*) as count FROM arkham_timeline_events"
        )
        count = result["count"] if result else 0
    else:
        count = 0

    return {"count": count}


@router.get("/events")
async def list_all_events(
    request: Request,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
):
    """List all timeline events with pagination and optional date filtering."""
    shard = get_shard(request)

    if not shard.database_service:
        raise HTTPException(status_code=503, detail="Database service not available")

    # Build query
    query = "SELECT * FROM arkham_timeline_events WHERE 1=1"
    params = {}

    if start_date:
        query += " AND date_start >= :start_date"
        params["start_date"] = start_date

    if end_date:
        query += " AND date_start <= :end_date"
        params["end_date"] = end_date

    query += " ORDER BY date_start DESC LIMIT :limit OFFSET :offset"
    params["limit"] = limit
    params["offset"] = offset

    rows = await shard.database_service.fetch_all(query, params)
    events = [shard._row_to_event(row) for row in rows]

    return {
        "events": [_event_to_dict(e) for e in events],
        "count": len(events),
        "limit": limit,
        "offset": offset,
    }


@router.post("/extract", response_model=ExtractionResponse)
async def extract_timeline(request: ExtractionRequest):
    """
    Extract timeline events from text or document.

    Provide either 'text' directly or 'document_id' to extract from document.
    """
    if not _extractor:
        raise HTTPException(status_code=503, detail="Timeline service not initialized")

    start_time = time.time()

    # Get text to analyze
    if request.text:
        text = request.text
        doc_id = "adhoc"
    elif request.document_id:
        if not _documents_service:
            raise HTTPException(status_code=503, detail="Documents service not available")

        # Get document text
        try:
            doc = await _documents_service.get_document(request.document_id)
            text = doc.get("text", "")
            doc_id = request.document_id
        except Exception as e:
            logger.error(f"Failed to get document: {e}", exc_info=True)
            raise HTTPException(status_code=404, detail=f"Document not found: {request.document_id}")
    else:
        raise HTTPException(status_code=400, detail="Either 'text' or 'document_id' required")

    # Parse context
    context = ExtractionContext()
    if request.context:
        if "reference_date" in request.context:
            from datetime import datetime
            context.reference_date = datetime.fromisoformat(request.context["reference_date"])
        if "timezone" in request.context:
            context.timezone = request.context["timezone"]

    # Extract events
    try:
        events = _extractor.extract_events(text, doc_id, context)
    except Exception as e:
        logger.error(f"Extraction failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Extraction failed: {str(e)}")

    duration_ms = (time.time() - start_time) * 1000

    # Emit event
    if _event_bus:
        await _event_bus.emit(
            "timeline.events.extracted",
            {
                "document_id": doc_id,
                "event_count": len(events),
                "duration_ms": duration_ms,
            },
            source="timeline-shard",
        )

    return ExtractionResponse(
        events=[_event_to_dict(e) for e in events],
        count=len(events),
        duration_ms=duration_ms,
    )


class ExtractAllResponse(BaseModel):
    """Response for extracting from all documents."""
    total_documents: int
    successful: int
    failed: int
    total_events: int
    duration_ms: float
    results: list[dict]  # Per-document results


@router.post("/extract/all", response_model=ExtractAllResponse)
async def extract_all_documents(request: Request):
    """
    Extract timeline events from all documents.

    Processes all available documents and returns summary statistics.
    """
    shard = get_shard(request)
    start_time = time.time()

    if not shard.database_service:
        raise HTTPException(status_code=503, detail="Database service not available")

    try:
        # Get all document IDs
        doc_rows = await shard.database_service.fetch_all(
            """
            SELECT DISTINCT id, created_at FROM arkham_frame.documents
            ORDER BY created_at DESC
            """
        )
        document_ids = [row["id"] for row in doc_rows]
        total_documents = len(document_ids)

        if total_documents == 0:
            return ExtractAllResponse(
                total_documents=0,
                successful=0,
                failed=0,
                total_events=0,
                duration_ms=0.0,
                results=[],
            )

        # Extract from each document
        successful = 0
        failed = 0
        total_events = 0
        results = []

        for doc_id in document_ids:
            try:
                events = await shard.extract_timeline(doc_id)
                event_count = len(events)
                total_events += event_count
                successful += 1
                results.append({
                    "document_id": doc_id,
                    "success": True,
                    "event_count": event_count,
                })
            except Exception as e:
                logger.error(f"Failed to extract from document {doc_id}: {e}", exc_info=True)
                failed += 1
                results.append({
                    "document_id": doc_id,
                    "success": False,
                    "error": str(e),
                    "event_count": 0,
                })

        duration_ms = (time.time() - start_time) * 1000

        # Emit event
        if _event_bus:
            await _event_bus.emit(
                "timeline.all.extracted",
                {
                    "total_documents": total_documents,
                    "successful": successful,
                    "failed": failed,
                    "total_events": total_events,
                    "duration_ms": duration_ms,
                },
                source="timeline-shard",
            )

        return ExtractAllResponse(
            total_documents=total_documents,
            successful=successful,
            failed=failed,
            total_events=total_events,
            duration_ms=duration_ms,
            results=results,
        )

    except Exception as e:
        logger.error(f"Extract all failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Extract all failed: {str(e)}")


@router.post("/extract/{document_id}", response_model=ExtractionResponse)
async def extract_document_timeline(request: Request, document_id: str):
    """
    Extract timeline events from an existing document.

    This triggers timeline extraction for a specific document ID.
    """
    shard = get_shard(request)
    start_time = time.time()

    try:
        events = await shard.extract_timeline(document_id)
    except Exception as e:
        logger.error(f"Extraction failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Extraction failed: {str(e)}")

    duration_ms = (time.time() - start_time) * 1000

    # Emit event
    if _event_bus:
        await _event_bus.emit(
            "timeline.timeline.extracted",
            {
                "document_id": document_id,
                "event_count": len(events),
                "duration_ms": duration_ms,
            },
            source="timeline-shard",
        )

    return ExtractionResponse(
        events=[_event_to_dict(e) for e in events],
        count=len(events),
        duration_ms=duration_ms,
    )


@router.get("/documents")
async def list_documents(
    request: Request,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """
    List available documents for timeline extraction.
    """
    shard = get_shard(request)

    if not shard.database_service:
        raise HTTPException(status_code=503, detail="Database service not available")

    try:
        # Get documents with their timeline event counts
        rows = await shard.database_service.fetch_all(
            """
            SELECT d.id, d.filename, d.created_at,
                   COUNT(te.id) as event_count
            FROM arkham_frame.documents d
            LEFT JOIN arkham_timeline_events te ON d.id = te.document_id
            GROUP BY d.id, d.filename, d.created_at
            ORDER BY d.created_at DESC
            LIMIT :limit OFFSET :offset
            """,
            {"limit": limit, "offset": offset}
        )

        documents = [
            {
                "id": row["id"],
                "filename": row.get("filename") or row["id"],
                "title": None,
                "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
                "event_count": row["event_count"],
            }
            for row in rows
        ]

        return {"documents": documents, "count": len(documents)}
    except Exception as e:
        logger.error(f"Failed to list documents: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list documents: {str(e)}")


# NOTE: Using /document/{document_id} instead of /{document_id} to avoid route conflicts
# with static routes like /range, /stats, /documents

@router.get("/range", response_model=RangeResponse)
async def get_events_in_range(
    request: Request,
    start_date: str,
    end_date: str,
    document_ids: Optional[str] = None,
    entity_ids: Optional[str] = None,
    event_types: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
):
    """
    Get events within a date range across all documents.

    Supports filtering by documents, entities, and event types.
    """
    shard = get_shard(request)

    if not shard.database_service:
        raise HTTPException(status_code=503, detail="Database service not available")

    # Parse comma-separated parameters
    doc_id_list = document_ids.split(",") if document_ids else None
    event_type_list = event_types.split(",") if event_types else None

    # Build parameterized query
    query = "SELECT * FROM arkham_timeline_events WHERE date_start >= :start_date AND date_start <= :end_date"
    params = {"start_date": start_date, "end_date": end_date}

    if doc_id_list:
        query += " AND document_id = ANY(:doc_ids)"
        params["doc_ids"] = doc_id_list

    if event_type_list:
        query += " AND event_type = ANY(:event_types)"
        params["event_types"] = event_type_list

    # Get total count
    count_query = query.replace("SELECT *", "SELECT COUNT(*) as count")
    try:
        count_result = await shard.database_service.fetch_one(count_query, params)
        total = count_result["count"] if count_result else 0
    except Exception as e:
        logger.error(f"Count query failed: {e}", exc_info=True)
        total = 0

    query += " ORDER BY date_start LIMIT :limit OFFSET :offset"
    params["limit"] = limit
    params["offset"] = offset

    try:
        rows = await shard.database_service.fetch_all(query, params)
        events = [shard._row_to_event(row) for row in rows]
    except Exception as e:
        logger.error(f"Query failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")

    return RangeResponse(
        events=[_event_to_dict(e) for e in events],
        count=len(events),
        total=total,
        has_more=(offset + len(events)) < total,
    )


@router.get("/stats", response_model=StatsResponse)
async def get_timeline_stats(
    request: Request,
    document_ids: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
):
    """
    Timeline statistics across all documents.

    Optionally filtered by documents and date range.
    """
    shard = get_shard(request)

    if not shard.database_service:
        raise HTTPException(status_code=503, detail="Database service not available")

    # Build parameterized query
    query = "SELECT * FROM arkham_timeline_events WHERE 1=1"
    params = {}

    if document_ids:
        doc_id_list = document_ids.split(",")
        query += " AND document_id = ANY(:doc_ids)"
        params["doc_ids"] = doc_id_list

    if start_date:
        query += " AND date_start >= :start_date"
        params["start_date"] = start_date
    if end_date:
        query += " AND date_start <= :end_date"
        params["end_date"] = end_date

    try:
        rows = await shard.database_service.fetch_all(query, params)
        events = [shard._row_to_event(row) for row in rows]
    except Exception as e:
        logger.error(f"Query failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")

    # Calculate stats
    total_events = len(events)
    total_documents = len(set(e.document_id for e in events)) if events else 0

    date_range = None
    if events:
        dates = [e.date_start for e in events]
        date_range = {
            "earliest": min(dates).isoformat(),
            "latest": max(dates).isoformat(),
        }

    by_precision = {}
    by_type = {}
    total_confidence = 0.0

    for event in events:
        # Count by precision
        prec = event.precision.value
        by_precision[prec] = by_precision.get(prec, 0) + 1

        # Count by type
        evt_type = event.event_type.value
        by_type[evt_type] = by_type.get(evt_type, 0) + 1

        # Sum confidence
        total_confidence += event.confidence

    avg_confidence = total_confidence / total_events if total_events > 0 else 0.0

    # Get conflict count
    conflicts_count = 0
    try:
        conflict_result = await shard.database_service.fetch_one(
            "SELECT COUNT(*) as count FROM arkham_timeline_conflicts"
        )
        conflicts_count = conflict_result["count"] if conflict_result else 0
    except Exception:
        pass

    return StatsResponse(
        total_events=total_events,
        total_documents=total_documents,
        date_range=date_range,
        by_precision=by_precision,
        by_type=by_type,
        avg_confidence=round(avg_confidence, 2),
        conflicts_detected=conflicts_count,
    )


@router.get("/document/{document_id}", response_model=DocumentTimelineResponse)
async def get_document_timeline(
    request: Request,
    document_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    event_type: Optional[str] = None,
    min_confidence: float = 0.0,
):
    """
    Get timeline for a specific document.

    Supports filtering by date range, event type, and confidence.
    """
    shard = get_shard(request)

    if not shard.database_service:
        raise HTTPException(status_code=503, detail="Database service not available")

    # Build parameterized query
    query = "SELECT * FROM arkham_timeline_events WHERE document_id = :document_id"
    params = {"document_id": document_id}

    if start_date:
        query += " AND date_start >= :start_date"
        params["start_date"] = start_date
    if end_date:
        query += " AND date_start <= :end_date"
        params["end_date"] = end_date
    if event_type:
        query += " AND event_type = :event_type"
        params["event_type"] = event_type
    if min_confidence > 0:
        query += " AND confidence >= :min_confidence"
        params["min_confidence"] = min_confidence

    query += " ORDER BY date_start"

    try:
        rows = await shard.database_service.fetch_all(query, params)
        events = [shard._row_to_event(row) for row in rows]
    except Exception as e:
        logger.error(f"Database query failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")

    # Calculate date range
    date_range = None
    if events:
        dates = [e.date_start for e in events]
        date_range = {
            "earliest": min(dates).isoformat(),
            "latest": max(dates).isoformat(),
        }

    return DocumentTimelineResponse(
        document_id=document_id,
        events=[_event_to_dict(e) for e in events],
        count=len(events),
        date_range=date_range,
    )


@router.post("/merge", response_model=MergeResponse)
async def merge_timelines(http_request: Request, request: MergeRequest):
    """
    Merge timelines from multiple documents.

    Supports various merge strategies and deduplication.
    """
    shard = get_shard(http_request)

    if not shard.merger:
        raise HTTPException(status_code=503, detail="Timeline service not initialized")

    if not shard.database_service:
        raise HTTPException(status_code=503, detail="Database service not available")

    # Get events for all documents
    all_events = []
    for doc_id in request.document_ids:
        try:
            events = await shard._get_events_for_document(doc_id)
            all_events.extend(events)
        except Exception as e:
            logger.error(f"Failed to get events for {doc_id}: {e}")

    # Apply date range filter if provided
    if request.date_range:
        from datetime import datetime
        start = datetime.fromisoformat(request.date_range.get("start")) if request.date_range.get("start") else None
        end = datetime.fromisoformat(request.date_range.get("end")) if request.date_range.get("end") else None

        if start or end:
            filtered_events = []
            for event in all_events:
                if start and event.date_start < start:
                    continue
                if end and event.date_start > end:
                    continue
                filtered_events.append(event)
            all_events = filtered_events

    # Parse merge strategy
    try:
        strategy = MergeStrategy(request.merge_strategy.lower())
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid merge strategy: {request.merge_strategy}")

    # Merge
    try:
        result = shard.merger.merge(
            all_events,
            strategy=strategy,
            priority_docs=request.priority_docs,
        )
    except Exception as e:
        logger.error(f"Merge failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Merge failed: {str(e)}")

    # Emit event
    if _event_bus:
        await _event_bus.emit(
            "timeline.timeline.merged",
            {
                "document_ids": request.document_ids,
                "event_count": result.count,
                "strategy": request.merge_strategy,
            },
            source="timeline-shard",
        )

    return MergeResponse(
        events=[_event_to_dict(e) for e in result.events],
        count=result.count,
        sources=result.sources,
        date_range={
            "earliest": result.date_range.start.isoformat() if result.date_range.start else None,
            "latest": result.date_range.end.isoformat() if result.date_range.end else None,
        },
        duplicates_removed=result.duplicates_removed,
    )


@router.post("/conflicts", response_model=ConflictsResponse)
async def detect_conflicts(http_request: Request, request: ConflictsRequest):
    """
    Find temporal conflicts across documents.

    Detects contradictions, inconsistencies, gaps, and overlaps.
    """
    shard = get_shard(http_request)

    if not shard.conflict_detector:
        raise HTTPException(status_code=503, detail="Timeline service not initialized")

    if not shard.database_service:
        raise HTTPException(status_code=503, detail="Database service not available")

    # Get events for all documents
    all_events = []
    for doc_id in request.document_ids:
        try:
            events = await shard._get_events_for_document(doc_id)
            all_events.extend(events)
        except Exception as e:
            logger.error(f"Failed to get events for {doc_id}: {e}")

    # Parse conflict types
    conflict_types = None
    if request.conflict_types:
        try:
            conflict_types = [ConflictType(ct.lower()) for ct in request.conflict_types]
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid conflict type: {e}")

    # Update detector tolerance
    if request.tolerance_days != shard.conflict_detector.tolerance_days:
        from .conflicts import ConflictDetector
        temp_detector = ConflictDetector(tolerance_days=request.tolerance_days)
    else:
        temp_detector = shard.conflict_detector

    # Detect conflicts
    try:
        conflicts = temp_detector.detect_conflicts(all_events, conflict_types)
    except Exception as e:
        logger.error(f"Conflict detection failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Conflict detection failed: {str(e)}")

    # Store conflicts
    if conflicts:
        try:
            await shard._store_conflicts(conflicts)
        except Exception as e:
            logger.error(f"Failed to store conflicts: {e}")

    # Count by type
    by_type = {}
    for conflict in conflicts:
        type_str = conflict.type.value
        by_type[type_str] = by_type.get(type_str, 0) + 1

    # Emit event
    if _event_bus:
        await _event_bus.emit(
            "timeline.conflict.detected",
            {
                "document_ids": request.document_ids,
                "conflict_count": len(conflicts),
                "by_type": by_type,
            },
            source="timeline-shard",
        )

    return ConflictsResponse(
        conflicts=[_conflict_to_dict(c) for c in conflicts],
        count=len(conflicts),
        by_type=by_type,
    )


@router.get("/entity/{entity_id}", response_model=EntityTimelineResponse)
async def get_entity_timeline(
    request: Request,
    entity_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    include_related: bool = False,
):
    """
    Get timeline for a specific entity.

    Optionally includes events from related entities.
    """
    shard = get_shard(request)

    if not shard.database_service:
        raise HTTPException(status_code=503, detail="Database service not available")

    # Query events mentioning this entity (using JSONB containment)
    query = "SELECT * FROM arkham_timeline_events WHERE entities::jsonb @> :entity_array::jsonb"
    params = {"entity_array": f'["{entity_id}"]'}

    if start_date:
        query += " AND date_start >= :start_date"
        params["start_date"] = start_date
    if end_date:
        query += " AND date_start <= :end_date"
        params["end_date"] = end_date

    query += " ORDER BY date_start"

    try:
        rows = await shard.database_service.fetch_all(query, params)
        events = [shard._row_to_event(row) for row in rows]
    except Exception as e:
        logger.error(f"Query failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")

    # Calculate date range
    date_range = None
    if events:
        dates = [e.date_start for e in events]
        date_range = {
            "earliest": min(dates).isoformat(),
            "latest": max(dates).isoformat(),
        }

    return EntityTimelineResponse(
        entity_id=entity_id,
        events=[_event_to_dict(e) for e in events],
        count=len(events),
        date_range=date_range,
    )


class DeleteResponse(BaseModel):
    deleted: int
    message: str


@router.delete("/events/{event_id}", response_model=DeleteResponse)
async def delete_event(request: Request, event_id: str):
    """
    Delete a single timeline event by ID.
    """
    shard = get_shard(request)

    if not shard.database_service:
        raise HTTPException(status_code=503, detail="Database service not available")

    try:
        result = await shard.database_service.execute(
            "DELETE FROM arkham_timeline_events WHERE id = :event_id",
            {"event_id": event_id}
        )
        deleted = result.rowcount if hasattr(result, 'rowcount') else 1

        if deleted == 0:
            raise HTTPException(status_code=404, detail=f"Event not found: {event_id}")

        # Emit event
        if _event_bus:
            await _event_bus.emit(
                "timeline.event.deleted",
                {"event_id": event_id},
                source="timeline-shard",
            )

        return DeleteResponse(deleted=1, message=f"Event {event_id} deleted")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete event: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to delete event: {str(e)}")


@router.delete("/document/{document_id}/events", response_model=DeleteResponse)
async def delete_document_events(request: Request, document_id: str):
    """
    Delete all timeline events for a specific document.
    """
    shard = get_shard(request)

    if not shard.database_service:
        raise HTTPException(status_code=503, detail="Database service not available")

    try:
        # First count how many will be deleted
        count_result = await shard.database_service.fetch_one(
            "SELECT COUNT(*) as count FROM arkham_timeline_events WHERE document_id = :doc_id",
            {"doc_id": document_id}
        )
        count = count_result["count"] if count_result else 0

        if count == 0:
            return DeleteResponse(deleted=0, message=f"No events found for document {document_id}")

        # Delete all events for this document
        await shard.database_service.execute(
            "DELETE FROM arkham_timeline_events WHERE document_id = :doc_id",
            {"doc_id": document_id}
        )

        # Emit event
        if _event_bus:
            await _event_bus.emit(
                "timeline.document.events_deleted",
                {"document_id": document_id, "count": count},
                source="timeline-shard",
            )

        return DeleteResponse(deleted=count, message=f"Deleted {count} events from document {document_id}")
    except Exception as e:
        logger.error(f"Failed to delete document events: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to delete events: {str(e)}")


@router.delete("/events", response_model=DeleteResponse)
async def delete_all_events(
    request: Request,
    confirm: bool = Query(False, description="Must be true to confirm deletion of all events")
):
    """
    Delete all timeline events. Requires confirm=true query parameter.
    """
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Must pass confirm=true query parameter to delete all events"
        )

    shard = get_shard(request)

    if not shard.database_service:
        raise HTTPException(status_code=503, detail="Database service not available")

    try:
        # Count events first
        count_result = await shard.database_service.fetch_one(
            "SELECT COUNT(*) as count FROM arkham_timeline_events"
        )
        count = count_result["count"] if count_result else 0

        if count == 0:
            return DeleteResponse(deleted=0, message="No events to delete")

        # Delete all events
        await shard.database_service.execute("DELETE FROM arkham_timeline_events")

        # Emit event
        if _event_bus:
            await _event_bus.emit(
                "timeline.events.cleared",
                {"count": count},
                source="timeline-shard",
            )

        return DeleteResponse(deleted=count, message=f"Deleted all {count} events")
    except Exception as e:
        logger.error(f"Failed to delete all events: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to delete events: {str(e)}")


@router.post("/normalize", response_model=NormalizeResponse)
async def normalize_dates(request: NormalizeRequest):
    """
    Normalize date formats from various inputs.

    Converts dates to ISO format with precision and confidence.
    """
    if not _extractor:
        raise HTTPException(status_code=503, detail="Timeline service not initialized")

    # Parse reference date
    from datetime import datetime
    ref_date = None
    if request.reference_date:
        try:
            ref_date = datetime.fromisoformat(request.reference_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid reference_date format")

    context = ExtractionContext(reference_date=ref_date or datetime.now())

    # Normalize each date
    results = []
    for date_str in request.dates:
        try:
            normalized = _extractor.normalize_date(date_str, context)
            if normalized:
                results.append({
                    "original": normalized.original,
                    "normalized": normalized.normalized.isoformat(),
                    "precision": normalized.precision.value,
                    "confidence": round(normalized.confidence, 2),
                    "is_range": normalized.is_range,
                    "range_end": normalized.range_end.isoformat() if normalized.range_end else None,
                })
            else:
                results.append({
                    "original": date_str,
                    "normalized": None,
                    "precision": None,
                    "confidence": 0.0,
                    "is_range": False,
                    "range_end": None,
                })
        except Exception as e:
            logger.error(f"Failed to normalize date '{date_str}': {e}")
            results.append({
                "original": date_str,
                "normalized": None,
                "precision": None,
                "confidence": 0.0,
                "is_range": False,
                "range_end": None,
            })

    return NormalizeResponse(normalized=results)


class EntityWithTimelineEvents(BaseModel):
    """Entity with timeline event count."""
    entity_id: str
    name: str
    entity_type: str
    event_count: int


class EntitiesWithEventsResponse(BaseModel):
    """Response for entities with timeline events."""
    entities: list[EntityWithTimelineEvents]
    count: int


@router.get("/entities", response_model=EntitiesWithEventsResponse)
async def list_entities_with_events(
    request: Request,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    min_events: int = Query(1, ge=1, description="Minimum number of events to include entity"),
):
    """
    List entities that have timeline events.

    Returns entities from arkham_entities that are mentioned in timeline events,
    along with the count of events for each entity.
    """
    shard = get_shard(request)

    if not shard.database_service:
        raise HTTPException(status_code=503, detail="Database service not available")

    try:
        # Query entities mentioned in timeline events
        # This uses JSONB array to find entity IDs in the entities column
        rows = await shard.database_service.fetch_all(
            """
            WITH entity_counts AS (
                SELECT
                    jsonb_array_elements_text(entities) as entity_id,
                    COUNT(*) as event_count
                FROM arkham_timeline_events
                WHERE jsonb_array_length(entities) > 0
                GROUP BY jsonb_array_elements_text(entities)
                HAVING COUNT(*) >= :min_events
            )
            SELECT
                e.id as entity_id,
                e.name,
                e.entity_type,
                COALESCE(ec.event_count, 0) as event_count
            FROM arkham_entities e
            INNER JOIN entity_counts ec ON e.id = ec.entity_id
            ORDER BY ec.event_count DESC, e.name
            LIMIT :limit OFFSET :offset
            """,
            {"limit": limit, "offset": offset, "min_events": min_events}
        )

        entities = [
            EntityWithTimelineEvents(
                entity_id=row["entity_id"],
                name=row["name"],
                entity_type=row["entity_type"],
                event_count=row["event_count"],
            )
            for row in rows
        ]

        return EntitiesWithEventsResponse(
            entities=entities,
            count=len(entities),
        )

    except Exception as e:
        logger.error(f"Failed to list entities with events: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")


# ========== Event Management ==========


class UpdateEventRequest(BaseModel):
    """Request to update a timeline event."""
    text: Optional[str] = None
    date_start: Optional[str] = None
    date_end: Optional[str] = None
    event_type: Optional[str] = None
    precision: Optional[str] = None
    entities: Optional[list[str]] = None


class UpdateEventResponse(BaseModel):
    """Response after updating an event."""
    id: str
    updated: bool
    message: str


@router.put("/events/{event_id}", response_model=UpdateEventResponse)
async def update_event(
    request: Request,
    event_id: str,
    update: UpdateEventRequest,
):
    """
    Update a timeline event.

    Allows updating text, dates, event type, precision, and entities.
    """
    shard = get_shard(request)

    if not shard.database_service:
        raise HTTPException(status_code=503, detail="Database service not available")

    try:
        # Check if event exists
        existing = await shard.database_service.fetch_one(
            "SELECT id FROM arkham_timeline_events WHERE id = :event_id",
            {"event_id": event_id}
        )
        if not existing:
            raise HTTPException(status_code=404, detail=f"Event not found: {event_id}")

        # Build update query dynamically
        updates = []
        params = {"event_id": event_id}

        if update.text is not None:
            updates.append("text = :text")
            params["text"] = update.text

        if update.date_start is not None:
            updates.append("date_start = :date_start")
            params["date_start"] = update.date_start

        if update.date_end is not None:
            updates.append("date_end = :date_end")
            params["date_end"] = update.date_end if update.date_end else None

        if update.event_type is not None:
            updates.append("event_type = :event_type")
            params["event_type"] = update.event_type

        if update.precision is not None:
            updates.append("precision = :precision")
            params["precision"] = update.precision

        if update.entities is not None:
            import json
            updates.append("entities = :entities")
            params["entities"] = json.dumps(update.entities)

        if not updates:
            return UpdateEventResponse(
                id=event_id,
                updated=False,
                message="No fields to update"
            )

        query = f"UPDATE arkham_timeline_events SET {', '.join(updates)} WHERE id = :event_id"
        await shard.database_service.execute(query, params)

        # Emit event
        if _event_bus:
            await _event_bus.emit(
                "timeline.event.updated",
                {"event_id": event_id, "fields": list(params.keys())},
                source="timeline-shard",
            )

        return UpdateEventResponse(
            id=event_id,
            updated=True,
            message=f"Updated {len(updates)} field(s)"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update event: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to update event: {str(e)}")


class AddNoteRequest(BaseModel):
    """Request to add a note to an event."""
    note: str
    author: Optional[str] = None


class NoteResponse(BaseModel):
    """A single note/annotation."""
    id: str
    event_id: str
    note: str
    author: Optional[str]
    created_at: str


class NotesListResponse(BaseModel):
    """List of notes for an event."""
    notes: list[NoteResponse]
    count: int


@router.post("/events/{event_id}/notes", response_model=NoteResponse)
async def add_event_note(
    request: Request,
    event_id: str,
    note_request: AddNoteRequest,
):
    """
    Add an annotation/note to a timeline event.
    """
    shard = get_shard(request)

    if not shard.database_service:
        raise HTTPException(status_code=503, detail="Database service not available")

    try:
        # Check if event exists
        existing = await shard.database_service.fetch_one(
            "SELECT id FROM arkham_timeline_events WHERE id = :event_id",
            {"event_id": event_id}
        )
        if not existing:
            raise HTTPException(status_code=404, detail=f"Event not found: {event_id}")

        import uuid
        from datetime import datetime

        note_id = str(uuid.uuid4())
        created_at = datetime.utcnow()

        await shard.database_service.execute(
            """
            INSERT INTO arkham_timeline_annotations (id, event_id, note, author, created_at, updated_at)
            VALUES (:id, :event_id, :note, :author, :created_at, :updated_at)
            """,
            {
                "id": note_id,
                "event_id": event_id,
                "note": note_request.note,
                "author": note_request.author,
                "created_at": created_at,
                "updated_at": created_at,
            }
        )

        # Emit event
        if _event_bus:
            await _event_bus.emit(
                "timeline.note.added",
                {"event_id": event_id, "note_id": note_id},
                source="timeline-shard",
            )

        return NoteResponse(
            id=note_id,
            event_id=event_id,
            note=note_request.note,
            author=note_request.author,
            created_at=created_at.isoformat(),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to add note: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to add note: {str(e)}")


@router.get("/events/{event_id}/notes", response_model=NotesListResponse)
async def get_event_notes(
    request: Request,
    event_id: str,
):
    """
    Get all annotations/notes for a timeline event.
    """
    shard = get_shard(request)

    if not shard.database_service:
        raise HTTPException(status_code=503, detail="Database service not available")

    try:
        rows = await shard.database_service.fetch_all(
            """
            SELECT id, event_id, note, author, created_at
            FROM arkham_timeline_annotations
            WHERE event_id = :event_id
            ORDER BY created_at DESC
            """,
            {"event_id": event_id}
        )

        notes = [
            NoteResponse(
                id=row["id"],
                event_id=row["event_id"],
                note=row["note"],
                author=row.get("author"),
                created_at=row["created_at"].isoformat() if row.get("created_at") else "",
            )
            for row in rows
        ]

        return NotesListResponse(notes=notes, count=len(notes))

    except Exception as e:
        logger.error(f"Failed to get notes: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get notes: {str(e)}")


@router.delete("/events/{event_id}/notes/{note_id}")
async def delete_event_note(
    request: Request,
    event_id: str,
    note_id: str,
):
    """
    Delete an annotation/note from a timeline event.
    """
    shard = get_shard(request)

    if not shard.database_service:
        raise HTTPException(status_code=503, detail="Database service not available")

    try:
        result = await shard.database_service.execute(
            "DELETE FROM arkham_timeline_annotations WHERE id = :note_id AND event_id = :event_id",
            {"note_id": note_id, "event_id": event_id}
        )

        deleted = result.rowcount if hasattr(result, 'rowcount') else 1

        if deleted == 0:
            raise HTTPException(status_code=404, detail=f"Note not found: {note_id}")

        return {"deleted": True, "note_id": note_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete note: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to delete note: {str(e)}")


class TimelineGap(BaseModel):
    """A gap in the timeline."""
    start_date: str
    end_date: str
    gap_days: int
    before_event_id: str
    after_event_id: str
    severity: str  # low, medium, high


class GapsResponse(BaseModel):
    """Response for timeline gaps analysis."""
    gaps: list[TimelineGap]
    count: int
    total_gap_days: int
    median_gap_days: int
    coverage_percent: float


@router.get("/gaps", response_model=GapsResponse)
async def get_timeline_gaps(
    request: Request,
    min_gap_days: int = Query(30, ge=1, description="Minimum gap size in days to report"),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
):
    """
    Analyze timeline for gaps (periods with no events).

    Returns gaps larger than min_gap_days, along with statistics about timeline coverage.
    """
    shard = get_shard(request)

    if not shard.database_service:
        raise HTTPException(status_code=503, detail="Database service not available")

    try:
        # Build query
        query = "SELECT * FROM arkham_timeline_events WHERE 1=1"
        params = {}

        if start_date:
            query += " AND date_start >= :start_date"
            params["start_date"] = start_date
        if end_date:
            query += " AND date_start <= :end_date"
            params["end_date"] = end_date

        query += " ORDER BY date_start"

        rows = await shard.database_service.fetch_all(query, params)
        events = [shard._row_to_event(row) for row in rows]

        if len(events) < 2:
            return GapsResponse(
                gaps=[],
                count=0,
                total_gap_days=0,
                median_gap_days=0,
                coverage_percent=100.0,
            )

        # Analyze gaps
        gaps = []
        all_gap_days = []

        for i in range(len(events) - 1):
            event1 = events[i]
            event2 = events[i + 1]
            gap_days = (event2.date_start - event1.date_start).days

            all_gap_days.append(gap_days)

            if gap_days >= min_gap_days:
                # Determine severity based on gap size
                if gap_days >= 365:
                    severity = "high"
                elif gap_days >= 90:
                    severity = "medium"
                else:
                    severity = "low"

                gaps.append(TimelineGap(
                    start_date=event1.date_start.isoformat(),
                    end_date=event2.date_start.isoformat(),
                    gap_days=gap_days,
                    before_event_id=event1.id,
                    after_event_id=event2.id,
                    severity=severity,
                ))

        # Calculate statistics
        total_gap_days = sum(all_gap_days)
        sorted_gaps = sorted(all_gap_days)
        median_gap_days = sorted_gaps[len(sorted_gaps) // 2] if sorted_gaps else 0

        # Calculate coverage (rough estimate)
        if events:
            timeline_span = (events[-1].date_start - events[0].date_start).days
            if timeline_span > 0:
                # Assume events "cover" 1 day each
                coverage_percent = min(100.0, (len(events) / timeline_span) * 100)
            else:
                coverage_percent = 100.0
        else:
            coverage_percent = 0.0

        return GapsResponse(
            gaps=gaps,
            count=len(gaps),
            total_gap_days=total_gap_days,
            median_gap_days=median_gap_days,
            coverage_percent=round(coverage_percent, 1),
        )

    except Exception as e:
        logger.error(f"Failed to analyze gaps: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to analyze gaps: {str(e)}")


class ConflictDetail(BaseModel):
    """Detailed conflict information."""
    id: str
    type: str
    severity: str
    event_ids: list[str]
    description: str
    documents: list[str]
    suggested_resolution: Optional[str]
    metadata: dict


class ConflictsDetailResponse(BaseModel):
    """Enhanced conflicts response with full details."""
    conflicts: list[ConflictDetail]
    count: int
    by_type: dict[str, int]
    by_severity: dict[str, int]


@router.get("/conflicts/analyze")
async def analyze_conflicts(
    request: Request,
    tolerance_days: int = Query(0, ge=0, description="Days of tolerance for date matching"),
):
    """
    Analyze all events for conflicts.

    Detects contradictions, inconsistencies, gaps, and overlaps.
    Returns detailed conflict information.
    """
    shard = get_shard(request)

    if not shard.database_service:
        raise HTTPException(status_code=503, detail="Database service not available")

    try:
        # Get all events
        rows = await shard.database_service.fetch_all(
            "SELECT * FROM arkham_timeline_events ORDER BY date_start"
        )
        events = [shard._row_to_event(row) for row in rows]

        if len(events) < 2:
            return ConflictsDetailResponse(
                conflicts=[],
                count=0,
                by_type={},
                by_severity={},
            )

        # Run conflict detection
        from .conflicts import ConflictDetector
        detector = ConflictDetector(tolerance_days=tolerance_days)
        conflicts = detector.detect_conflicts(events)

        # Convert to response format
        conflict_details = []
        by_type: dict[str, int] = {}
        by_severity: dict[str, int] = {}

        for conflict in conflicts:
            type_str = conflict.type.value
            severity_str = conflict.severity.value

            by_type[type_str] = by_type.get(type_str, 0) + 1
            by_severity[severity_str] = by_severity.get(severity_str, 0) + 1

            conflict_details.append(ConflictDetail(
                id=conflict.id,
                type=type_str,
                severity=severity_str,
                event_ids=conflict.events,
                description=conflict.description,
                documents=conflict.documents,
                suggested_resolution=conflict.suggested_resolution,
                metadata=conflict.metadata or {},
            ))

        # Store conflicts for future reference
        if conflicts:
            try:
                await shard._store_conflicts(conflicts)
            except Exception as e:
                logger.warning(f"Failed to store conflicts: {e}")

        return ConflictsDetailResponse(
            conflicts=conflict_details,
            count=len(conflict_details),
            by_type=by_type,
            by_severity=by_severity,
        )

    except Exception as e:
        logger.error(f"Failed to analyze conflicts: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to analyze conflicts: {str(e)}")


class MergeEventsRequest(BaseModel):
    """Request to merge multiple events."""
    event_ids: list[str]
    keep_event_id: Optional[str] = None  # If specified, merge into this event; otherwise use first


class MergeEventsResponse(BaseModel):
    """Response after merging events."""
    merged_event_id: str
    merged_count: int
    deleted_ids: list[str]


@router.post("/events/merge", response_model=MergeEventsResponse)
async def merge_events(
    request: Request,
    merge_request: MergeEventsRequest,
):
    """
    Merge multiple timeline events into one.

    Combines text and entities from all events into the kept event.
    Other events are deleted.
    """
    shard = get_shard(request)

    if not shard.database_service:
        raise HTTPException(status_code=503, detail="Database service not available")

    if len(merge_request.event_ids) < 2:
        raise HTTPException(status_code=400, detail="At least 2 events required for merge")

    try:
        import json

        # Fetch all events to merge
        placeholders = ", ".join([f":id{i}" for i in range(len(merge_request.event_ids))])
        params = {f"id{i}": eid for i, eid in enumerate(merge_request.event_ids)}

        rows = await shard.database_service.fetch_all(
            f"SELECT * FROM arkham_timeline_events WHERE id IN ({placeholders})",
            params
        )

        if len(rows) < 2:
            raise HTTPException(status_code=404, detail="Not enough events found to merge")

        # Determine which event to keep
        keep_id = merge_request.keep_event_id or merge_request.event_ids[0]
        keep_event = None
        merge_events_list = []

        for row in rows:
            if row["id"] == keep_id:
                keep_event = row
            else:
                merge_events_list.append(row)

        if not keep_event:
            # Keep the first found event
            keep_event = rows[0]
            merge_events_list = rows[1:]
            keep_id = keep_event["id"]

        # Combine text (join with newline)
        texts = [keep_event["text"]]
        for ev in merge_events_list:
            if ev.get("text") and ev["text"] not in texts:
                texts.append(ev["text"])
        combined_text = "\n---\n".join(texts)

        # Combine entities (union)
        all_entities = set()
        keep_entities = keep_event.get("entities", [])
        if isinstance(keep_entities, str):
            keep_entities = json.loads(keep_entities) if keep_entities else []
        all_entities.update(keep_entities)

        for ev in merge_events_list:
            ev_entities = ev.get("entities", [])
            if isinstance(ev_entities, str):
                ev_entities = json.loads(ev_entities) if ev_entities else []
            all_entities.update(ev_entities)

        # Update the kept event
        await shard.database_service.execute(
            """
            UPDATE arkham_timeline_events
            SET text = :text, entities = :entities
            WHERE id = :event_id
            """,
            {
                "event_id": keep_id,
                "text": combined_text,
                "entities": json.dumps(list(all_entities)),
            }
        )

        # Delete the merged events
        deleted_ids = [ev["id"] for ev in merge_events_list]
        for eid in deleted_ids:
            await shard.database_service.execute(
                "DELETE FROM arkham_timeline_events WHERE id = :event_id",
                {"event_id": eid}
            )

        # Emit event
        if _event_bus:
            await _event_bus.emit(
                "timeline.events.merged",
                {"kept_event_id": keep_id, "merged_count": len(deleted_ids), "deleted_ids": deleted_ids},
                source="timeline-shard",
            )

        return MergeEventsResponse(
            merged_event_id=keep_id,
            merged_count=len(deleted_ids) + 1,
            deleted_ids=deleted_ids,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to merge events: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to merge events: {str(e)}")


# --- AI Junior Analyst ---


class AIJuniorAnalystRequest(BaseModel):
    """Request for AI Junior Analyst analysis."""
    target_id: str
    context: dict[str, Any] = {}
    depth: str = "quick"
    session_id: str | None = None
    message: str | None = None
    conversation_history: list[dict[str, str]] | None = None


@router.post("/ai/junior-analyst")
async def ai_junior_analyst(request: Request, body: AIJuniorAnalystRequest):
    """
    AI Junior Analyst endpoint for timeline analysis.

    Provides AI-powered interpretation of timeline data including:
    - Activity clusters and patterns
    - Suspicious gaps
    - Sequences suggesting coordination
    - Before/after patterns
    - Temporal anomalies
    """
    shard = get_shard(request)
    frame = shard.frame

    if not frame or not getattr(frame, "ai_analyst", None):
        raise HTTPException(
            status_code=503,
            detail="AI Analyst service not available"
        )

    # Build context from request
    from arkham_frame.services import AnalysisRequest, AnalysisDepth, AnalystMessage

    # Parse depth
    try:
        depth = AnalysisDepth(body.depth)
    except ValueError:
        depth = AnalysisDepth.QUICK

    # Build conversation history
    history = None
    if body.conversation_history:
        history = [
            AnalystMessage(role=msg["role"], content=msg["content"])
            for msg in body.conversation_history
        ]

    analysis_request = AnalysisRequest(
        shard="timeline",
        target_id=body.target_id,
        context=body.context,
        depth=depth,
        session_id=body.session_id,
        message=body.message,
        conversation_history=history,
    )

    # Stream the response
    return StreamingResponse(
        frame.ai_analyst.stream_analyze(analysis_request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# --- Helper Functions ---


def _event_to_dict(event: TimelineEvent) -> dict:
    """Convert TimelineEvent to dictionary for JSON response."""
    return {
        "id": event.id,
        "document_id": event.document_id,
        "text": event.text,
        "date_start": event.date_start.isoformat(),
        "date_end": event.date_end.isoformat() if event.date_end else None,
        "precision": event.precision.value,
        "confidence": round(event.confidence, 2),
        "entities": event.entities,
        "event_type": event.event_type.value,
        "span": event.span,
        "metadata": event.metadata,
    }


def _conflict_to_dict(conflict) -> dict:
    """Convert TemporalConflict to dictionary for JSON response."""
    return {
        "id": conflict.id,
        "type": conflict.type.value,
        "severity": conflict.severity.value,
        "events": conflict.events,
        "description": conflict.description,
        "documents": conflict.documents,
        "suggested_resolution": conflict.suggested_resolution,
        "metadata": conflict.metadata,
    }
