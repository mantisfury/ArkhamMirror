"""Anomalies Shard API endpoints."""

import logging
import time
from typing import Annotated, Any, Dict, List, Optional, TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

if TYPE_CHECKING:
    from .shard import AnomaliesShard

from .models import (
    Anomaly,
    AnomalyType,
    AnomalyStatus,
    SeverityLevel,
    DetectRequest,
    DetectionConfig,
    PatternRequest,
    AnomalyResult,
    AnomalyList,
    AnomalyStats,
    StatusUpdate,
    AnalystNote,
    # Hidden content models
    HiddenContentConfig,
    HiddenContentScan,
    HiddenContentScanType,
    HiddenContentStats,
)

try:
    from arkham_frame.auth import (
        current_active_user,
        current_optional_user,
        require_project_member,
    )
except ImportError:
    async def current_active_user():
        return None

    async def current_optional_user():
        return None

    async def require_project_member(*args, **kwargs):
        return None

# Import wide event logging utilities (with fallback)
try:
    from arkham_frame import log_operation, emit_wide_error
    WIDE_EVENTS_AVAILABLE = True
except ImportError:
    WIDE_EVENTS_AVAILABLE = False
    from contextlib import contextmanager
    @contextmanager
    def log_operation(*args, **kwargs):
        yield None
    def emit_wide_error(*args, **kwargs):
        pass

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/anomalies", tags=["anomalies"])

# These get set by the shard on initialization
_detector = None
_hidden_detector = None
_store = None
_event_bus = None
_db = None
_vectors = None
_storage = None


def init_api(detector, store, event_bus, db=None, vectors=None, hidden_detector=None, storage=None):
    """Initialize API with shard dependencies."""
    global _detector, _hidden_detector, _store, _event_bus, _db, _vectors, _storage
    _detector = detector
    _hidden_detector = hidden_detector
    _store = store
    _event_bus = event_bus
    _db = db
    _vectors = vectors
    _storage = storage


def get_shard(request: Request) -> "AnomaliesShard":
    """Get the anomalies shard instance from app state."""
    shard = getattr(request.app.state, "anomalies_shard", None)
    if not shard:
        raise HTTPException(status_code=503, detail="Anomalies shard not available")
    return shard


async def _require_active_project_id(request: Request, shard: "AnomaliesShard", user: Any) -> str:
    """
    Resolve the user's active project_id and validate membership.

    Returns project_id (string). Raises HTTPException if none.
    """
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    frame = getattr(shard, "frame", None) or getattr(shard, "_frame", None)
    if not frame or not hasattr(frame, "get_active_project_id"):
        raise HTTPException(status_code=503, detail="Frame project service not available")

    user_id_str = str(getattr(user, "id", "")).lower().strip()
    project_id = await frame.get_active_project_id(user_id_str)
    if not project_id:
        raise HTTPException(status_code=400, detail="No active project selected")

    await require_project_member(str(project_id), user, request)
    return str(project_id)


# --- Request/Response Models ---


class DetectResponse(BaseModel):
    """Response from anomaly detection."""
    anomalies_detected: int
    duration_ms: float
    job_id: str | None = None


class AnomalyResponse(BaseModel):
    """Single anomaly response."""
    anomaly: dict


class AnomalyListResponse(BaseModel):
    """Paginated anomaly list response."""
    total: int
    items: list[dict]
    offset: int
    limit: int
    has_more: bool
    facets: dict


class StatsResponse(BaseModel):
    """Statistics response."""
    stats: dict


class StatusUpdateRequest(BaseModel):
    """Request to update anomaly status."""
    status: str
    notes: str = ""
    reviewed_by: str | None = None


class NoteRequest(BaseModel):
    """Request to add a note."""
    content: str
    author: str


# --- Endpoints ---


@router.post("/detect", response_model=DetectResponse)
async def detect_anomalies(request: DetectRequest):
    """
    Run anomaly detection on documents.

    Detects multiple types of anomalies:
    - Content: Semantically distant documents
    - Metadata: Unusual file properties
    - Temporal: Unexpected dates
    - Structural: Unusual document structure
    - Statistical: Unusual text patterns
    - Red flags: Sensitive content indicators

    This endpoint may run as a background job for large corpora.
    """
    with log_operation("anomalies.detect", project_id=request.project_id) as event:
        if event:
            event.context("shard", "anomalies")
            event.context("operation", "detect")
            event.input(
                project_id=request.project_id,
                doc_count=len(request.doc_ids) if request.doc_ids else 0,
                has_config=request.config is not None,
            )
            if request.project_id:
                event.context("project_id", request.project_id)
        
        if not _detector or not _store:
            if event:
                event.error("ServiceUnavailable", "Anomaly service not initialized")
            raise HTTPException(status_code=503, detail="Anomaly service not initialized")

        start_time = time.time()

        try:
            logger.info(f"Anomaly detection requested for project: {request.project_id}")

            # Emit detection started event
            if _event_bus:
                await _event_bus.emit(
                    "anomalies.detection_started",
                    {
                        "project_id": request.project_id,
                        "doc_ids": request.doc_ids,
                        "config": request.config.__dict__ if request.config else None,
                    },
                    source="anomalies-shard",
                )

            # Get documents to analyze
            doc_ids = request.doc_ids
            if not doc_ids and _db:
                # If no specific doc_ids, get all documents from arkham_frame.documents
                rows = await _db.fetch_all(
                    "SELECT id FROM arkham_frame.documents WHERE project_id = :project_id LIMIT 1000",
                    {"project_id": str(request.project_id)},
                )
                doc_ids = [row["id"] for row in rows] if rows else []

            detected_anomalies = []
            config = request.config or DetectionConfig()

            # Run detection on each document
            for doc_id in doc_ids:
                try:
                    doc_anomalies = await _detect_document_anomalies_internal(doc_id, config)
                    for anomaly in doc_anomalies:
                        await _store.create_anomaly(anomaly)
                        detected_anomalies.append(anomaly)
                except Exception as doc_error:
                    logger.warning(f"Failed to detect anomalies for doc {doc_id}: {doc_error}")

            duration_ms = (time.time() - start_time) * 1000

            # Emit detection completed event
            if _event_bus:
                await _event_bus.emit(
                    "anomalies.detection_completed",
                    {
                        "project_id": request.project_id,
                        "doc_ids": doc_ids,
                        "anomalies_detected": len(detected_anomalies),
                        "duration_ms": duration_ms,
                    },
                    source="anomalies-shard",
                )

            if event:
                event.output(
                    anomalies_detected=len(detected_anomalies),
                    documents_analyzed=len(doc_ids),
                    duration_ms=duration_ms,
                )

            return DetectResponse(
                anomalies_detected=len(detected_anomalies),
                duration_ms=duration_ms,
                job_id=f"detect-{int(start_time)}",
            )

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Anomaly detection failed: {e}", exc_info=True)
            emit_wide_error(event, "AnomalyDetectionFailed", str(e), exc=e)
            raise HTTPException(status_code=500, detail=f"Detection failed: {str(e)}")


@router.post("/document/{doc_id}", response_model=DetectResponse)
async def detect_document_anomalies(doc_id: str):
    """
    Check if a specific document is anomalous.

    Runs all detection strategies on a single document
    and returns any anomalies found.
    """
    if not _detector or not _store:
        raise HTTPException(status_code=503, detail="Anomaly service not initialized")

    start_time = time.time()

    try:
        logger.info(f"Checking document {doc_id} for anomalies")

        # Run detection for this document
        config = DetectionConfig()
        detected_anomalies = await _detect_document_anomalies_internal(doc_id, config)

        # Store detected anomalies
        for anomaly in detected_anomalies:
            await _store.create_anomaly(anomaly)

        duration_ms = (time.time() - start_time) * 1000

        # Emit event if anomalies found
        if _event_bus and detected_anomalies:
            await _event_bus.emit(
                "anomalies.detected",
                {
                    "doc_id": doc_id,
                    "count": len(detected_anomalies),
                    "types": [a.anomaly_type.value for a in detected_anomalies],
                },
                source="anomalies-shard",
            )

        return DetectResponse(
            anomalies_detected=len(detected_anomalies),
            duration_ms=duration_ms,
        )

    except Exception as e:
        logger.error(f"Document anomaly check failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Check failed: {str(e)}")


@router.get("/list", response_model=AnomalyListResponse)
async def list_anomalies(
    offset: int = 0,
    limit: int = 20,
    anomaly_type: str | None = None,
    status: str | None = None,
    severity: str | None = None,
    doc_id: str | None = None,
):
    """
    List detected anomalies with filtering and pagination.

    Supports filtering by:
    - Type (content, metadata, temporal, structural, statistical, red_flag)
    - Status (detected, confirmed, dismissed, false_positive)
    - Severity (critical, high, medium, low)
    - Document ID
    """
    if not _store:
        raise HTTPException(status_code=503, detail="Anomaly service not initialized")

    try:
        # Parse filters
        type_filter = None
        if anomaly_type:
            try:
                type_filter = AnomalyType(anomaly_type.lower())
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid anomaly type: {anomaly_type}")

        status_filter = None
        if status:
            try:
                status_filter = AnomalyStatus(status.lower())
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

        severity_filter = None
        if severity:
            try:
                severity_filter = SeverityLevel(severity.lower())
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid severity: {severity}")

        # Query
        anomalies, total = await _store.list_anomalies(
            offset=offset,
            limit=limit,
            anomaly_type=type_filter,
            status=status_filter,
            severity=severity_filter,
            doc_id=doc_id,
        )

        # Get facets
        facets = await _store.get_facets()

        has_more = (offset + len(anomalies)) < total

        return AnomalyListResponse(
            total=total,
            items=[_anomaly_to_dict(a) for a in anomalies],
            offset=offset,
            limit=limit,
            has_more=has_more,
            facets=facets,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list anomalies: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"List failed: {str(e)}")


@router.get("/outliers", response_model=AnomalyListResponse)
async def get_outliers(
    limit: int = 20,
    min_z_score: float = 3.0,
):
    """
    Get statistical outliers based on embedding distance.

    Returns documents that are semantically distant from
    the corpus centroid.
    """
    if not _store:
        raise HTTPException(status_code=503, detail="Anomaly service not initialized")

    try:
        # Filter to content anomalies with high scores
        anomalies, total = await _store.list_anomalies(
            offset=0,
            limit=limit,
            anomaly_type=AnomalyType.CONTENT,
        )

        # Filter by z-score
        filtered = [a for a in anomalies if a.score >= min_z_score]

        return AnomalyListResponse(
            total=len(filtered),
            items=[_anomaly_to_dict(a) for a in filtered],
            offset=0,
            limit=limit,
            has_more=False,
            facets={},
        )

    except Exception as e:
        logger.error(f"Failed to get outliers: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Outliers failed: {str(e)}")


@router.post("/patterns", response_model=dict)
async def detect_patterns(request: PatternRequest):
    """
    Detect unusual patterns across anomalies.

    Looks for recurring patterns that might indicate:
    - Systematic issues
    - Data quality problems
    - Coordinated anomalies
    """
    if not _store:
        raise HTTPException(status_code=503, detail="Anomaly service not initialized")

    try:
        logger.info("Pattern detection requested")

        # In a real implementation, this would analyze anomalies for patterns
        patterns = await _store.list_patterns()

        return {
            "patterns_found": len(patterns),
            "patterns": [_pattern_to_dict(p) for p in patterns],
        }

    except Exception as e:
        logger.error(f"Pattern detection failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Pattern detection failed: {str(e)}")


@router.get("/stats", response_model=StatsResponse)
async def get_stats():
    """
    Get anomaly statistics.

    Returns aggregated statistics including:
    - Total counts by type, status, severity
    - Recent activity (last 24h)
    - Quality metrics (false positive rate, avg confidence)
    """
    if not _store:
        raise HTTPException(status_code=503, detail="Anomaly service not initialized")

    try:
        stats = await _store.get_stats()

        return StatsResponse(
            stats={
                "total_anomalies": stats.total_anomalies,
                "by_type": stats.by_type,
                "by_status": stats.by_status,
                "by_severity": stats.by_severity,
                "detected_last_24h": stats.detected_last_24h,
                "confirmed_last_24h": stats.confirmed_last_24h,
                "dismissed_last_24h": stats.dismissed_last_24h,
                "false_positive_rate": stats.false_positive_rate,
                "avg_confidence": stats.avg_confidence,
                "calculated_at": stats.calculated_at.isoformat(),
            }
        )

    except Exception as e:
        logger.error(f"Failed to get stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Stats failed: {str(e)}")


@router.get("/{anomaly_id}", response_model=AnomalyResponse)
async def get_anomaly(anomaly_id: str):
    """
    Get details for a specific anomaly.

    Returns full anomaly information including:
    - Detection details
    - Scoring information
    - Analyst notes
    - Status history
    """
    if not _store:
        raise HTTPException(status_code=503, detail="Anomaly service not initialized")

    try:
        anomaly = await _store.get_anomaly(anomaly_id)
        if not anomaly:
            raise HTTPException(status_code=404, detail=f"Anomaly {anomaly_id} not found")

        return AnomalyResponse(anomaly=_anomaly_to_dict(anomaly))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get anomaly: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Get failed: {str(e)}")


@router.put("/{anomaly_id}/status", response_model=AnomalyResponse)
async def update_anomaly_status(anomaly_id: str, request: StatusUpdateRequest):
    """
    Update anomaly status.

    Allows analysts to:
    - Confirm anomaly as legitimate
    - Dismiss as normal
    - Mark as false positive

    Status updates are tracked with timestamps and reviewer information.
    """
    if not _store:
        raise HTTPException(status_code=503, detail="Anomaly service not initialized")

    try:
        # Parse status
        try:
            new_status = AnomalyStatus(request.status.lower())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {request.status}")

        # Update
        anomaly = await _store.update_status(
            anomaly_id=anomaly_id,
            status=new_status,
            reviewed_by=request.reviewed_by,
            notes=request.notes,
        )

        if not anomaly:
            raise HTTPException(status_code=404, detail=f"Anomaly {anomaly_id} not found")

        # Emit event
        if _event_bus:
            await _event_bus.emit(
                f"anomalies.{new_status.value}",
                {
                    "anomaly_id": anomaly_id,
                    "doc_id": anomaly.doc_id,
                    "reviewed_by": request.reviewed_by,
                },
                source="anomalies-shard",
            )

        return AnomalyResponse(anomaly=_anomaly_to_dict(anomaly))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Update failed: {str(e)}")


@router.post("/{anomaly_id}/notes")
async def add_note(anomaly_id: str, request: NoteRequest):
    """
    Add an analyst note to an anomaly.

    Notes provide context and reasoning for analyst decisions.
    """
    if not _store:
        raise HTTPException(status_code=503, detail="Anomaly service not initialized")

    try:
        # Verify anomaly exists
        anomaly = await _store.get_anomaly(anomaly_id)
        if not anomaly:
            raise HTTPException(status_code=404, detail=f"Anomaly {anomaly_id} not found")

        # Create note
        import uuid
        note = AnalystNote(
            id=str(uuid.uuid4()),
            anomaly_id=anomaly_id,
            author=request.author,
            content=request.content,
        )

        await _store.add_note(note)

        return {"success": True, "note_id": note.id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to add note: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Add note failed: {str(e)}")


@router.post("/bulk-status")
async def bulk_update_status(
    anomaly_ids: List[str],
    status: str,
    notes: str = "",
    reviewed_by: Optional[str] = None,
):
    """
    Bulk update status for multiple anomalies.

    Allows analysts to quickly triage multiple anomalies at once.
    """
    if not _store:
        raise HTTPException(status_code=503, detail="Anomaly service not initialized")

    try:
        # Parse status
        try:
            new_status = AnomalyStatus(status.lower())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

        updated_count = 0
        failed_ids = []

        for anomaly_id in anomaly_ids:
            try:
                anomaly = await _store.update_status(
                    anomaly_id=anomaly_id,
                    status=new_status,
                    reviewed_by=reviewed_by,
                    notes=notes,
                )
                if anomaly:
                    updated_count += 1
                else:
                    failed_ids.append(anomaly_id)
            except Exception as update_err:
                logger.warning(f"Failed to update {anomaly_id}: {update_err}")
                failed_ids.append(anomaly_id)

        # Emit bulk event
        if _event_bus and updated_count > 0:
            await _event_bus.emit(
                f"anomalies.bulk_{new_status.value}",
                {
                    "count": updated_count,
                    "anomaly_ids": [aid for aid in anomaly_ids if aid not in failed_ids],
                    "reviewed_by": reviewed_by,
                },
                source="anomalies-shard",
            )

        return {
            "success": True,
            "updated_count": updated_count,
            "failed_count": len(failed_ids),
            "failed_ids": failed_ids,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Bulk status update failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Bulk update failed: {str(e)}")


@router.get("/{anomaly_id}/related")
async def get_related_anomalies(anomaly_id: str, limit: int = 10):
    """
    Get anomalies related to the specified anomaly.

    Finds anomalies from the same document or with similar patterns.
    """
    if not _store:
        raise HTTPException(status_code=503, detail="Anomaly service not initialized")

    try:
        # Get the source anomaly
        anomaly = await _store.get_anomaly(anomaly_id)
        if not anomaly:
            raise HTTPException(status_code=404, detail=f"Anomaly {anomaly_id} not found")

        # Get anomalies for the same document
        same_doc_anomalies, _ = await _store.list_anomalies(
            offset=0,
            limit=limit,
            doc_id=anomaly.doc_id,
        )

        # Get anomalies of the same type
        same_type_anomalies, _ = await _store.list_anomalies(
            offset=0,
            limit=limit,
            anomaly_type=anomaly.anomaly_type,
        )

        # Combine and deduplicate
        seen_ids = {anomaly_id}
        related = []

        for a in same_doc_anomalies:
            if a.id not in seen_ids:
                seen_ids.add(a.id)
                related.append({
                    **_anomaly_to_dict(a),
                    "relation": "same_document",
                })

        for a in same_type_anomalies:
            if a.id not in seen_ids and len(related) < limit:
                seen_ids.add(a.id)
                related.append({
                    **_anomaly_to_dict(a),
                    "relation": "same_type",
                })

        return {
            "related": related[:limit],
            "total": len(related),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get related anomalies: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Get related failed: {str(e)}")


@router.get("/{anomaly_id}/notes")
async def get_notes(anomaly_id: str):
    """
    Get all analyst notes for an anomaly.
    """
    if not _store:
        raise HTTPException(status_code=503, detail="Anomaly service not initialized")

    try:
        notes = await _store.get_notes(anomaly_id)
        return {
            "notes": [
                {
                    "id": note.id,
                    "author": note.author,
                    "content": note.content,
                    "created_at": note.created_at.isoformat(),
                }
                for note in notes
            ],
            "total": len(notes),
        }

    except Exception as e:
        logger.error(f"Failed to get notes: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Get notes failed: {str(e)}")


@router.get("/document/{doc_id}/preview")
async def get_document_preview(doc_id: str):
    """
    Get a preview of document content for anomaly context.
    """
    if not _db:
        raise HTTPException(status_code=503, detail="Database service not initialized")

    try:
        row = await _db.fetch_one(
            """SELECT id, file_name, file_type, file_size, content, created_at
               FROM arkham_frame.documents WHERE id = :doc_id""",
            {"doc_id": doc_id}
        )

        if not row:
            raise HTTPException(status_code=404, detail=f"Document {doc_id} not found")

        content = row.get("content") or ""
        # Return first 2000 chars as preview
        preview = content[:2000] + ("..." if len(content) > 2000 else "")

        return {
            "id": row["id"],
            "file_name": row.get("file_name"),
            "file_type": row.get("file_type"),
            "file_size": row.get("file_size"),
            "preview": preview,
            "full_length": len(content),
            "created_at": row.get("created_at"),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get document preview: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Preview failed: {str(e)}")


# --- Helper Functions ---


def _anomaly_to_dict(anomaly: Anomaly) -> dict:
    """Convert Anomaly to dictionary for JSON response."""
    return {
        "id": anomaly.id,
        "doc_id": anomaly.doc_id,
        "anomaly_type": anomaly.anomaly_type.value,
        "status": anomaly.status.value,
        "score": round(anomaly.score, 4),
        "severity": anomaly.severity.value,
        "confidence": round(anomaly.confidence, 4),
        "explanation": anomaly.explanation,
        "details": anomaly.details,
        "field_name": anomaly.field_name,
        "expected_range": anomaly.expected_range,
        "actual_value": anomaly.actual_value,
        "detected_at": anomaly.detected_at.isoformat(),
        "updated_at": anomaly.updated_at.isoformat(),
        "reviewed_by": anomaly.reviewed_by,
        "reviewed_at": anomaly.reviewed_at.isoformat() if anomaly.reviewed_at else None,
        "notes": anomaly.notes,
        "tags": anomaly.tags,
    }


def _pattern_to_dict(pattern) -> dict:
    """Convert AnomalyPattern to dictionary for JSON response."""
    return {
        "id": pattern.id,
        "pattern_type": pattern.pattern_type,
        "description": pattern.description,
        "anomaly_ids": pattern.anomaly_ids,
        "doc_ids": pattern.doc_ids,
        "frequency": pattern.frequency,
        "confidence": round(pattern.confidence, 4),
        "detected_at": pattern.detected_at.isoformat(),
        "notes": pattern.notes,
    }


async def _detect_document_anomalies_internal(
    doc_id: str,
    config: DetectionConfig,
) -> List[Anomaly]:
    """
    Internal function to run anomaly detection on a single document.

    Args:
        doc_id: Document ID to analyze
        config: Detection configuration

    Returns:
        List of detected anomalies
    """
    anomalies: List[Anomaly] = []

    if not _detector or not _db:
        logger.warning("Detector or database not available for anomaly detection")
        return anomalies

    try:
        # Fetch document metadata from database
        doc_row = await _db.fetch_one(
            "SELECT id, filename, file_size, mime_type, created_at, metadata FROM arkham_frame.documents WHERE id = :doc_id",
            {"doc_id": doc_id}
        )

        if not doc_row:
            logger.warning(f"Document {doc_id} not found in database")
            return anomalies

        metadata = {}
        if doc_row.get("metadata"):
            import json
            try:
                if isinstance(doc_row["metadata"], str):
                    metadata = json.loads(doc_row["metadata"])
                else:
                    metadata = dict(doc_row["metadata"])
            except (json.JSONDecodeError, TypeError):
                metadata = {}

        # Add file info to metadata
        metadata["file_name"] = doc_row.get("filename")
        metadata["file_size"] = doc_row.get("file_size")
        metadata["file_type"] = doc_row.get("mime_type")

        # Fetch content from chunks
        chunk_rows = await _db.fetch_all(
            "SELECT text FROM arkham_frame.chunks WHERE document_id = :doc_id ORDER BY chunk_index",
            {"doc_id": doc_id}
        )

        text = "\n".join(row.get("text", "") for row in chunk_rows if row.get("text")) if chunk_rows else ""

        # Run red flag detection (always runs, no corpus stats needed)
        if config.detect_red_flags:
            red_flag_anomalies = _detector.detect_red_flags(doc_id, text, metadata)
            anomalies.extend(red_flag_anomalies)

        # Run statistical detection if we can get corpus stats
        if config.detect_statistical:
            try:
                corpus_stats = await _get_corpus_stats()
                if corpus_stats:
                    stat_anomalies = _detector.detect_statistical_anomalies(
                        doc_id, text, corpus_stats
                    )
                    anomalies.extend(stat_anomalies)
            except Exception as stat_error:
                logger.debug(f"Statistical detection failed: {stat_error}")

        # Run metadata detection if we can get corpus metadata stats
        if config.detect_metadata:
            try:
                corpus_metadata_stats = await _get_corpus_metadata_stats()
                if corpus_metadata_stats:
                    meta_anomalies = _detector.detect_metadata_anomalies(
                        doc_id, metadata, corpus_metadata_stats
                    )
                    anomalies.extend(meta_anomalies)
            except Exception as meta_error:
                logger.debug(f"Metadata detection failed: {meta_error}")

        # Run content/embedding-based detection if vectors are available
        if config.detect_content and _vectors:
            try:
                content_anomalies = await _detect_content_anomalies(doc_id, text)
                anomalies.extend(content_anomalies)
            except Exception as content_error:
                logger.debug(f"Content detection failed: {content_error}")

        logger.info(f"Detected {len(anomalies)} anomalies for document {doc_id}")

    except Exception as e:
        logger.error(f"Error during anomaly detection for {doc_id}: {e}", exc_info=True)

    return anomalies


async def _get_corpus_stats() -> Dict[str, Any]:
    """
    Calculate corpus-wide text statistics for comparison.

    Returns:
        Dictionary of corpus statistics by metric
    """
    if not _db:
        return {}

    try:
        # Get aggregate text stats from chunks table
        rows = await _db.fetch_all(
            """SELECT
                AVG(LENGTH(text)) as avg_char_count,
                AVG(LENGTH(text) - LENGTH(REPLACE(text, ' ', '')) + 1) as avg_word_count
               FROM arkham_frame.chunks
               WHERE text IS NOT NULL AND LENGTH(text) > 0
               LIMIT 1000"""
        )

        if not rows or not rows[0]:
            return {}

        row = rows[0]

        # Build corpus stats structure
        corpus_stats = {
            'char_count': {
                'mean': float(row.get('avg_char_count') or 0),
                'std': float(row.get('avg_char_count', 0) or 0) * 0.5,  # Estimate std as 50% of mean
            },
            'word_count': {
                'mean': float(row.get('avg_word_count') or 0),
                'std': float(row.get('avg_word_count', 0) or 0) * 0.5,
            },
        }

        return corpus_stats

    except Exception as e:
        logger.debug(f"Failed to get corpus stats: {e}")
        return {}


async def _get_corpus_metadata_stats() -> Dict[str, Any]:
    """
    Calculate corpus-wide metadata statistics for comparison.

    Returns:
        Dictionary of metadata statistics
    """
    if not _db:
        return {}

    try:
        # Get file size stats
        row = await _db.fetch_one(
            """SELECT
                AVG(file_size) as avg_size,
                MIN(file_size) as min_size,
                MAX(file_size) as max_size
               FROM arkham_frame.documents
               WHERE file_size IS NOT NULL"""
        )

        if not row:
            return {}

        avg_size = float(row.get('avg_size') or 0)
        min_size = float(row.get('min_size') or 0)
        max_size = float(row.get('max_size') or 0)

        # Estimate std from range
        estimated_std = (max_size - min_size) / 4 if max_size > min_size else avg_size * 0.5

        return {
            'file_size': {
                'mean': avg_size,
                'std': estimated_std,
            }
        }

    except Exception as e:
        logger.debug(f"Failed to get corpus metadata stats: {e}")
        return {}


async def _detect_content_anomalies(doc_id: str, text: str) -> List[Anomaly]:
    """
    Detect content anomalies using vector embeddings.

    Args:
        doc_id: Document ID
        text: Document text

    Returns:
        List of content anomalies
    """
    if not _vectors or not _detector:
        return []

    try:
        # This would use the vector service to get embeddings and compare
        # For now, return empty as this requires a working vector service
        # The detection would be:
        # 1. Get embedding for this document
        # 2. Get embeddings for corpus
        # 3. Call _detector.detect_content_anomalies()

        # Check if vector text search is available (embeds text then searches)
        if hasattr(_vectors, 'search_text'):
            # Search for similar documents using text query
            # search_text handles embedding internally
            results = await _vectors.search_text(
                collection="arkham_documents",  # Use correct collection name
                text=text[:1000],  # Use first 1000 chars as query
                limit=10,
            )

            # If this document is very different from results, it might be anomalous
            if results and len(results) > 0:
                # SearchResult is a dataclass with .score attribute
                avg_score = sum(r.score if hasattr(r, 'score') else r.get('score', 0) for r in results) / len(results)
                if avg_score < 0.3:  # Low similarity to corpus
                    import uuid
                    from datetime import datetime
                    return [Anomaly(
                        id=str(uuid.uuid4()),
                        doc_id=doc_id,
                        anomaly_type=AnomalyType.CONTENT,
                        score=1.0 - avg_score,
                        severity=SeverityLevel.MEDIUM,
                        confidence=0.7,
                        explanation=f"Document is semantically distant from corpus (avg similarity: {avg_score:.2f})",
                        details={'avg_similarity': avg_score, 'compared_to': len(results)},
                    )]

        return []

    except Exception as e:
        logger.debug(f"Content anomaly detection failed: {e}")
        return []


@router.get("/count")
async def get_anomaly_count(status: Optional[str] = None):
    """
    Get count of anomalies, optionally filtered by status.

    Used for navigation badge.
    """
    if not _store:
        return {"count": 0}

    try:
        status_filter = None
        if status:
            try:
                status_filter = AnomalyStatus(status.lower())
            except ValueError:
                pass

        anomalies, total = await _store.list_anomalies(
            offset=0,
            limit=1,
            status=status_filter,
        )

        return {"count": total}

    except Exception as e:
        logger.error(f"Failed to get count: {e}")
        return {"count": 0}


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
    AI Junior Analyst endpoint for anomaly analysis.

    Provides AI-powered interpretation of anomalies including:
    - Anomaly severity assessment
    - Root cause hypothesis
    - Related anomaly correlation
    - Remediation suggestions
    - False positive identification
    """
    shard = get_shard(request)
    frame = shard._frame

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
        shard="anomalies",
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


# =============================================================================
# Hidden Content Detection Endpoints
# =============================================================================


class HiddenContentScanRequest(BaseModel):
    """Request to scan document for hidden content."""
    doc_id: str
    scan_type: str = "stego"  # entropy, lsb, magic, stego (full)
    config: dict = {}


class HiddenContentQuickScanRequest(BaseModel):
    """Request for quick entropy-only scan."""
    doc_ids: list[str]


class HiddenContentScanResponse(BaseModel):
    """Response from hidden content scan."""
    scan: dict
    anomaly_created: bool = False


class HiddenContentListResponse(BaseModel):
    """Paginated list of hidden content scans."""
    total: int
    items: list[dict]
    offset: int
    limit: int


class HiddenContentStatsResponse(BaseModel):
    """Hidden content detection statistics."""
    stats: dict


@router.post("/hidden-content/scan", response_model=HiddenContentScanResponse)
async def scan_hidden_content(
    request: Request,
    body: HiddenContentScanRequest,
    user=Depends(current_active_user),
):
    """
    Scan a document for hidden content.

    Performs steganography and hidden data detection:
    - Entropy analysis (detects encrypted/compressed data)
    - LSB pattern analysis (detects image steganography)
    - File type mismatch detection
    - Histogram analysis for images

    Args:
        body: Scan request with doc_id and options

    Returns:
        Scan results with findings
    """
    shard = get_shard(request)
    active_project_id = await _require_active_project_id(request, shard, user)

    if not shard.hidden_detector:
        raise HTTPException(
            status_code=503,
            detail="Hidden content detector not available"
        )

    # Get document metadata and file path
    if not _db:
        raise HTTPException(status_code=503, detail="Database not available")

    doc_row = await _db.fetch_one(
        """SELECT id, filename, storage_id, mime_type, file_size, metadata
           FROM arkham_frame.documents WHERE id = :doc_id AND project_id = :project_id""",
        {"doc_id": body.doc_id, "project_id": active_project_id}
    )

    if not doc_row:
        raise HTTPException(status_code=404, detail=f"Document {body.doc_id} not found")

    # Get storage path from storage_id or metadata
    storage_id = doc_row.get("storage_id")
    metadata = doc_row.get("metadata") or {}
    if isinstance(metadata, str):
        import json
        try:
            metadata = json.loads(metadata)
        except json.JSONDecodeError:
            metadata = {}

    storage_path = metadata.get("storage_path")
    if not storage_id and not storage_path:
        raise HTTPException(
            status_code=400,
            detail="Document has no associated file storage"
        )

    # Read file content using storage service
    try:
        if _storage and storage_id:
            file_data = (await _storage.retrieve(storage_id))[0]
        elif storage_path:
            from pathlib import Path
            file_data = Path(storage_path).read_bytes()
        else:
            raise ValueError("No storage path available")
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to read file: {e}"
        )

    # Get file extension
    filename = doc_row.get("filename", "")
    file_ext = "." + filename.rsplit(".", 1)[-1] if "." in filename else ""
    mime_type = doc_row.get("mime_type", "")

    # Configure detector if custom config provided
    if body.config:
        config = HiddenContentConfig(**body.config)
        shard.hidden_detector.config = config

    # Perform scan (use storage_path for file path reference)
    file_path = storage_path or storage_id
    scan_result = shard.hidden_detector.full_scan(
        doc_id=body.doc_id,
        file_path=file_path,
        file_data=file_data,
        file_extension=file_ext,
        mime_type=mime_type,
    )

    # Store the scan result
    await shard._store_hidden_content_scan(scan_result)

    # Create anomaly if significant findings
    anomaly_created = False
    if scan_result.stego_confidence >= 0.7 or scan_result.file_mismatch:
        import uuid
        from datetime import datetime
        from .models import AnomalyType, SeverityLevel, AnomalyStatus

        severity = SeverityLevel.HIGH if scan_result.stego_confidence >= 0.8 else SeverityLevel.MEDIUM

        anomaly = Anomaly(
            id=str(uuid.uuid4()),
            doc_id=body.doc_id,
            anomaly_type=AnomalyType.HIDDEN_CONTENT,
            status=AnomalyStatus.DETECTED,
            score=scan_result.stego_confidence,
            severity=severity,
            confidence=scan_result.stego_confidence,
            explanation="; ".join(scan_result.findings) if scan_result.findings else "Hidden content detected",
            details={
                "scan_id": scan_result.id,
                "indicators": len(scan_result.stego_indicators),
                "file_mismatch": scan_result.file_mismatch,
                "entropy_global": scan_result.entropy_global,
            },
            detected_at=datetime.utcnow(),
        )

        await _store.create_anomaly(anomaly)
        scan_result.anomaly_created = True
        anomaly_created = True

        # Emit event
        if _event_bus:
            await _event_bus.emit(
                "anomalies.hidden_content.detected",
                {
                    "doc_id": body.doc_id,
                    "scan_id": scan_result.id,
                    "confidence": scan_result.stego_confidence,
                    "findings_count": len(scan_result.findings),
                },
                source="anomalies-shard",
            )

    # Convert to response dict
    scan_dict = {
        "id": scan_result.id,
        "doc_id": scan_result.doc_id,
        "scan_type": scan_result.scan_type.value,
        "scan_status": scan_result.scan_status.value,
        "entropy_global": scan_result.entropy_global,
        "entropy_regions": [
            {
                "start_offset": r.start_offset,
                "end_offset": r.end_offset,
                "entropy_value": r.entropy_value,
                "is_anomalous": r.is_anomalous,
                "description": r.description,
            }
            for r in scan_result.entropy_regions
        ],
        "magic_expected": scan_result.magic_expected,
        "magic_actual": scan_result.magic_actual,
        "file_mismatch": scan_result.file_mismatch,
        "lsb_result": {
            "bit_ratio": scan_result.lsb_result.bit_ratio,
            "chi_square_value": scan_result.lsb_result.chi_square_value,
            "chi_square_p_value": scan_result.lsb_result.chi_square_p_value,
            "is_suspicious": scan_result.lsb_result.is_suspicious,
            "confidence": scan_result.lsb_result.confidence,
            "sample_size": scan_result.lsb_result.sample_size,
        } if scan_result.lsb_result else None,
        "stego_indicators": [
            {
                "indicator_type": i.indicator_type,
                "confidence": i.confidence,
                "location": i.location,
                "details": i.details,
            }
            for i in scan_result.stego_indicators
        ],
        "stego_confidence": scan_result.stego_confidence,
        "findings": scan_result.findings,
        "created_at": scan_result.created_at.isoformat() if scan_result.created_at else None,
        "completed_at": scan_result.completed_at.isoformat() if scan_result.completed_at else None,
    }

    return HiddenContentScanResponse(scan=scan_dict, anomaly_created=anomaly_created)


@router.post("/hidden-content/quick-scan")
async def quick_scan_hidden_content(
    request: Request,
    body: HiddenContentQuickScanRequest,
    user=Depends(current_active_user),
):
    """
    Perform quick entropy-only scan on multiple documents.

    Useful for fast screening of large document sets to identify
    candidates for full steganography analysis.

    Args:
        body: Request with list of doc_ids

    Returns:
        List of quick scan results with recommendations
    """
    shard = get_shard(request)
    active_project_id = await _require_active_project_id(request, shard, user)

    if not shard.hidden_detector:
        raise HTTPException(
            status_code=503,
            detail="Hidden content detector not available"
        )

    if not _db:
        raise HTTPException(status_code=503, detail="Database not available")

    results = []

    for doc_id in body.doc_ids:
        try:
            # Get document file path
            doc_row = await _db.fetch_one(
                """SELECT storage_id, metadata FROM arkham_frame.documents
                   WHERE id = :doc_id AND project_id = :project_id""",
                {"doc_id": doc_id, "project_id": active_project_id}
            )

            if not doc_row:
                results.append({
                    "doc_id": doc_id,
                    "error": "Document not found",
                })
                continue

            # Get storage path from storage_id or metadata
            storage_id = doc_row.get("storage_id")
            doc_metadata = doc_row.get("metadata") or {}
            if isinstance(doc_metadata, str):
                import json
                try:
                    doc_metadata = json.loads(doc_metadata)
                except json.JSONDecodeError:
                    doc_metadata = {}

            storage_path = doc_metadata.get("storage_path")
            if not storage_id and not storage_path:
                results.append({
                    "doc_id": doc_id,
                    "error": "Document has no storage path",
                })
                continue

            # Read file content
            try:
                if _storage and storage_id:
                    file_data = (await _storage.retrieve(storage_id))[0]
                elif storage_path:
                    from pathlib import Path
                    file_data = Path(storage_path).read_bytes()
                else:
                    raise ValueError("No storage path available")
            except Exception as e:
                results.append({
                    "doc_id": doc_id,
                    "error": f"Failed to read file: {e}",
                })
                continue

            # Quick entropy scan
            quick_result = shard.hidden_detector.quick_scan(doc_id, file_data)
            results.append(quick_result)

        except Exception as e:
            results.append({
                "doc_id": doc_id,
                "error": str(e),
            })

    # Summary
    requires_full_scan = [r for r in results if r.get("requires_full_scan")]

    return {
        "scanned": len(body.doc_ids),
        "results": results,
        "requires_full_scan_count": len(requires_full_scan),
        "requires_full_scan": [r.get("doc_id") for r in requires_full_scan],
    }


@router.get("/hidden-content/stats", response_model=HiddenContentStatsResponse)
async def get_hidden_content_stats(request: Request, user=Depends(current_active_user)):
    """
    Get hidden content detection statistics.

    Returns aggregated statistics about hidden content scans:
    - Total scans performed
    - Scans by type
    - Documents with findings
    - High entropy files
    - Steganography candidates
    """
    shard = get_shard(request)
    active_project_id = await _require_active_project_id(request, shard, user)

    stats = await shard.get_hidden_content_stats(project_id=active_project_id)
    return HiddenContentStatsResponse(stats=stats)


@router.get("/hidden-content/document/{doc_id}")
async def get_document_hidden_scans(
    request: Request,
    doc_id: str,
    user=Depends(current_active_user),
):
    """
    Get all hidden content scans for a document.

    Args:
        doc_id: Document ID

    Returns:
        List of scans for the document
    """
    shard = get_shard(request)
    active_project_id = await _require_active_project_id(request, shard, user)

    scans = await shard.get_document_hidden_scans(doc_id, project_id=active_project_id)
    return {"scans": scans, "total": len(scans)}


@router.get("/hidden-content/{scan_id}")
async def get_hidden_content_scan(
    request: Request,
    scan_id: str,
    user=Depends(current_active_user),
):
    """
    Get a specific hidden content scan by ID.

    Args:
        scan_id: Scan ID to retrieve

    Returns:
        Scan details
    """
    shard = get_shard(request)
    active_project_id = await _require_active_project_id(request, shard, user)

    scan = await shard.get_hidden_content_scan(scan_id, project_id=active_project_id)
    if not scan:
        raise HTTPException(status_code=404, detail=f"Scan {scan_id} not found")

    return {"scan": scan}
