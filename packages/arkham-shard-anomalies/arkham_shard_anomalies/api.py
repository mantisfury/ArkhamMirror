"""Anomalies Shard API endpoints."""

import logging
import time
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from .models import (
    Anomaly,
    AnomalyType,
    AnomalyStatus,
    SeverityLevel,
    DetectRequest,
    PatternRequest,
    AnomalyResult,
    AnomalyList,
    AnomalyStats,
    StatusUpdate,
    AnalystNote,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/anomalies", tags=["anomalies"])

# These get set by the shard on initialization
_detector = None
_store = None
_event_bus = None


def init_api(detector, store, event_bus):
    """Initialize API with shard dependencies."""
    global _detector, _store, _event_bus
    _detector = detector
    _store = store
    _event_bus = event_bus


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
    if not _detector or not _store:
        raise HTTPException(status_code=503, detail="Anomaly service not initialized")

    start_time = time.time()

    try:
        # In a real implementation, this would be a background job
        # For now, we'll just acknowledge the request
        logger.info(f"Anomaly detection requested for project: {request.project_id}")

        # Emit event
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

        duration_ms = (time.time() - start_time) * 1000

        return DetectResponse(
            anomalies_detected=0,
            duration_ms=duration_ms,
            job_id="job-123",  # Would be a real job ID
        )

    except Exception as e:
        logger.error(f"Anomaly detection failed: {e}", exc_info=True)
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

        # In a real implementation, fetch document and run detection
        # For now, just acknowledge

        duration_ms = (time.time() - start_time) * 1000

        return DetectResponse(
            anomalies_detected=0,
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
