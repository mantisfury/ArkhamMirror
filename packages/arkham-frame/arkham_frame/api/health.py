"""
Health check endpoints.
"""

import os
from pathlib import Path
from fastapi import APIRouter
from fastapi.responses import FileResponse, JSONResponse
from typing import Dict, Any

router = APIRouter()


@router.get("/")
async def root():
    """Root endpoint - serves Shell UI in production, API info otherwise."""
    # Check if we should serve the Shell UI
    if os.environ.get("ARKHAM_SERVE_SHELL", "false").lower() == "true":
        # Look for the built frontend
        shell_dist = Path("/app/frontend/dist")
        index_path = shell_dist / "index.html"
        if index_path.exists():
            return FileResponse(index_path)

    # Default API response
    return JSONResponse({"message": "ArkhamFrame API", "version": "0.1.0"})


@router.get("/health")
@router.get("/api/health")
async def health_check() -> Dict[str, Any]:
    """Health check endpoint (available at /health and /api/health)."""
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
        # Only expose host/database, never credentials
        db_url = frame.config.database_url if frame.config else ""
        safe_url = db_url.split("@")[-1] if "@" in db_url else "configured"
        services["database"] = {
            "available": True,
            "url": safe_url,
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
