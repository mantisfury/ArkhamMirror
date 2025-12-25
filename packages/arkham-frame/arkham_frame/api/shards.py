"""
Shard management API endpoints.

Returns full v5 manifests for Shell integration.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List, Optional

router = APIRouter()


class LoadShardRequest(BaseModel):
    """Request body for loading a shard."""
    name: str
    path: Optional[str] = None


@router.get("/")
async def list_shards() -> Dict[str, Any]:
    """
    List all loaded shards with full v5 manifests.

    Returns manifests suitable for Shell navigation rendering.
    """
    from ..main import get_frame

    frame = get_frame()

    shards = []
    for name, shard in frame.shards.items():
        manifest = getattr(shard, "manifest", None)

        if manifest and hasattr(manifest, "to_dict"):
            # v5 manifest with to_dict method
            shard_data = manifest.to_dict()
            shard_data["loaded"] = True
        else:
            # Fallback for legacy shards
            shard_data = {
                "name": name,
                "version": getattr(shard, "version", "unknown"),
                "description": getattr(shard, "description", ""),
                "loaded": True,
            }

            # Try to extract manifest dict if available
            if manifest and isinstance(manifest, dict):
                shard_data.update(manifest)

        shards.append(shard_data)

    # Sort by navigation.order if available
    def get_order(s: Dict) -> int:
        nav = s.get("navigation", {})
        if isinstance(nav, dict):
            return nav.get("order", 99)
        return 99

    shards.sort(key=get_order)

    return {
        "shards": shards,
        "count": len(shards),
    }


@router.get("/{shard_name}")
async def get_shard(shard_name: str) -> Dict[str, Any]:
    """Get full v5 manifest for a specific shard."""
    from ..main import get_frame

    frame = get_frame()

    if shard_name not in frame.shards:
        raise HTTPException(status_code=404, detail=f"Shard '{shard_name}' not found")

    shard = frame.shards[shard_name]
    manifest = getattr(shard, "manifest", None)

    if manifest and hasattr(manifest, "to_dict"):
        # v5 manifest
        result = manifest.to_dict()
        result["loaded"] = True
        return result
    else:
        # Fallback
        return {
            "name": shard_name,
            "version": getattr(shard, "version", "unknown"),
            "description": getattr(shard, "description", ""),
            "manifest": manifest if isinstance(manifest, dict) else None,
            "loaded": True,
        }


@router.post("/load")
async def load_shard(request: LoadShardRequest) -> Dict[str, Any]:
    """Load a shard dynamically."""
    from ..main import get_frame

    frame = get_frame()

    if request.name in frame.shards:
        raise HTTPException(status_code=409, detail=f"Shard '{request.name}' already loaded")

    # TODO: Implement dynamic shard loading
    return {
        "status": "not_implemented",
        "message": "Dynamic shard loading not yet implemented",
    }


@router.post("/{shard_name}/unload")
async def unload_shard(shard_name: str) -> Dict[str, Any]:
    """Unload a shard."""
    from ..main import get_frame

    frame = get_frame()

    if shard_name not in frame.shards:
        raise HTTPException(status_code=404, detail=f"Shard '{shard_name}' not found")

    # TODO: Implement shard unloading
    return {
        "status": "not_implemented",
        "message": "Shard unloading not yet implemented",
    }


@router.get("/{shard_name}/routes")
async def get_shard_routes(shard_name: str) -> Dict[str, Any]:
    """Get API routes registered by a shard."""
    from ..main import get_frame

    frame = get_frame()

    if shard_name not in frame.shards:
        raise HTTPException(status_code=404, detail=f"Shard '{shard_name}' not found")

    shard = frame.shards[shard_name]
    routes = getattr(shard, "routes", [])

    return {
        "shard": shard_name,
        "routes": routes,
    }
