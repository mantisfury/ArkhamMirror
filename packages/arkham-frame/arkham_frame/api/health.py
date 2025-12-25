"""
Health check endpoints.
"""

from fastapi import APIRouter
from typing import Dict, Any

router = APIRouter()


@router.get("/")
async def root() -> Dict[str, str]:
    """Root endpoint."""
    return {"message": "ArkhamFrame API", "version": "0.1.0"}


@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """Health check endpoint."""
    from ..main import get_frame

    try:
        frame = get_frame()
        return {
            "status": "healthy",
            "frame": frame.get_state(),
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
        }


@router.get("/api/status")
async def api_status() -> Dict[str, Any]:
    """Get detailed API status."""
    from ..main import get_frame

    frame = get_frame()

    services = {}

    # Database status
    if frame.db:
        services["database"] = {
            "available": True,
            "url": frame.config.database_url[:30] + "..." if frame.config else "N/A",
        }
    else:
        services["database"] = {"available": False}

    # Vector store status
    if frame.vectors:
        services["vectors"] = {
            "available": frame.vectors.is_available(),
        }
    else:
        services["vectors"] = {"available": False}

    # LLM status
    if frame.llm:
        services["llm"] = {
            "available": frame.llm.is_available(),
            "endpoint": frame.llm.get_endpoint() if frame.llm.is_available() else None,
        }
    else:
        services["llm"] = {"available": False}

    # Workers status
    if frame.workers:
        services["workers"] = {
            "available": frame.workers.is_available(),
        }
    else:
        services["workers"] = {"available": False}

    return {
        "status": "ok",
        "services": services,
        "shards": list(frame.shards.keys()),
    }
