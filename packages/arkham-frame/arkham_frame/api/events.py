"""
Event API endpoints.
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Dict, Any, List, Optional

router = APIRouter()


class EmitEventRequest(BaseModel):
    """Request body for emitting an event."""
    event_type: str
    payload: Dict[str, Any]
    source: str = "api"


@router.get("/")
async def list_events(
    source: Optional[str] = None,
    limit: int = Query(default=50, le=500),
) -> Dict[str, Any]:
    """List recent events."""
    from ..main import get_frame

    frame = get_frame()

    if not frame.events:
        raise HTTPException(status_code=503, detail="Event service unavailable")

    events = frame.events.get_events(source=source, limit=limit)

    return {
        "events": [
            {
                "event_type": e.event_type,
                "payload": e.payload,
                "source": e.source,
                "timestamp": e.timestamp.isoformat(),
                "sequence": e.sequence,
            }
            for e in events
        ],
        "count": len(events),
    }


@router.post("/emit")
async def emit_event(request: EmitEventRequest) -> Dict[str, Any]:
    """Emit an event."""
    from ..main import get_frame

    frame = get_frame()

    if not frame.events:
        raise HTTPException(status_code=503, detail="Event service unavailable")

    await frame.events.emit(
        event_type=request.event_type,
        payload=request.payload,
        source=request.source,
    )

    return {
        "status": "emitted",
        "event_type": request.event_type,
    }
