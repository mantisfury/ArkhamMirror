"""Timeline Shard API endpoints."""

import logging
import time
from typing import Annotated, Optional, TYPE_CHECKING

from fastapi import APIRouter, HTTPException, Query, Request
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
