"""
Shard management API endpoints.

Returns full v5 manifests for Shell integration.
Supports dynamic shard activation/deactivation without restart.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

# Track which shards are disabled (persisted via settings shard)
_disabled_shards: set = set()

# Track available but not loaded shards (discovered at startup)
_available_shards: Dict[str, Any] = {}


class LoadShardRequest(BaseModel):
    """Request body for loading a shard."""
    name: str
    path: Optional[str] = None


class ShardStateRequest(BaseModel):
    """Request to change shard enabled state."""
    enabled: bool


def _discover_available_shards() -> Dict[str, Any]:
    """Discover all available shards from entry points."""
    global _available_shards

    if _available_shards:
        return _available_shards

    try:
        from importlib.metadata import entry_points
    except ImportError:
        from importlib_metadata import entry_points

    eps = entry_points(group="arkham.shards")

    for ep in eps:
        _available_shards[ep.name] = {
            "entry_point": ep,
            "module": ep.value,
        }

    return _available_shards


@router.get("/")
async def list_shards() -> Dict[str, Any]:
    """
    List all shards (loaded and available) with full v5 manifests.

    Returns manifests suitable for Shell navigation rendering.
    Includes enabled/disabled state for each shard.
    """
    from ..main import get_frame

    frame = get_frame()

    # Discover all available shards
    available = _discover_available_shards()

    shards = []

    # Add loaded shards
    for name, shard in frame.shards.items():
        manifest = getattr(shard, "manifest", None)

        if manifest and hasattr(manifest, "to_dict"):
            # v5 manifest with to_dict method
            shard_data = manifest.to_dict()
        else:
            # Fallback for legacy shards
            shard_data = {
                "name": name,
                "version": getattr(shard, "version", "unknown"),
                "description": getattr(shard, "description", ""),
            }

            # Try to extract manifest dict if available
            if manifest and isinstance(manifest, dict):
                shard_data.update(manifest)

        shard_data["loaded"] = True
        shard_data["enabled"] = name not in _disabled_shards
        shards.append(shard_data)

    # Add available but not loaded shards (disabled ones)
    for name in available:
        if name not in frame.shards:
            shards.append({
                "name": name,
                "version": "unknown",
                "description": "Shard available but not loaded",
                "loaded": False,
                "enabled": False,
            })

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
        "loaded_count": len(frame.shards),
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

    # Find the shard in available shards
    available = _discover_available_shards()
    if request.name not in available:
        raise HTTPException(status_code=404, detail=f"Shard '{request.name}' not found in available shards")

    try:
        ep = available[request.name]["entry_point"]

        # Load the shard class
        shard_class = ep.load()

        # Instantiate and initialize
        shard = shard_class()
        await shard.initialize(frame)

        # Register routes dynamically
        router = shard.get_routes() or getattr(shard, "get_api_router", lambda: None)()

        if router and hasattr(frame, "app") and frame.app:
            frame.app.include_router(
                router,
                tags=[request.name.capitalize()],
            )

        # Add to frame
        frame.shards[request.name] = shard

        # Remove from disabled set
        _disabled_shards.discard(request.name)

        logger.info(f"Dynamically loaded shard: {request.name}")

        return {
            "status": "success",
            "message": f"Shard '{request.name}' loaded successfully",
            "shard": request.name,
        }

    except Exception as e:
        logger.error(f"Failed to load shard {request.name}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load shard: {str(e)}")


@router.post("/{shard_name}/unload")
async def unload_shard(shard_name: str) -> Dict[str, Any]:
    """Unload a shard (deactivate without restart)."""
    from ..main import get_frame

    frame = get_frame()

    if shard_name not in frame.shards:
        raise HTTPException(status_code=404, detail=f"Shard '{shard_name}' not found")

    # Prevent unloading critical shards
    protected_shards = {"dashboard", "settings"}
    if shard_name in protected_shards:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot unload protected shard '{shard_name}'"
        )

    try:
        shard = frame.shards[shard_name]

        # Call shutdown
        await shard.shutdown()

        # Remove routes from FastAPI app
        # Note: FastAPI doesn't have a clean way to remove routes at runtime,
        # but we can mark the shard as disabled and filter requests
        if hasattr(frame, "app") and frame.app:
            # We can't easily remove routes, but the shard won't process requests
            # after shutdown. For full route removal, a restart is needed.
            pass

        # Remove from frame.shards
        del frame.shards[shard_name]

        # Add to disabled set
        _disabled_shards.add(shard_name)

        logger.info(f"Unloaded shard: {shard_name}")

        return {
            "status": "success",
            "message": f"Shard '{shard_name}' unloaded successfully",
            "shard": shard_name,
            "note": "Routes remain registered until restart, but shard is inactive",
        }

    except Exception as e:
        logger.error(f"Failed to unload shard {shard_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to unload shard: {str(e)}")


@router.patch("/{shard_name}")
async def set_shard_state(shard_name: str, request: ShardStateRequest) -> Dict[str, Any]:
    """
    Enable or disable a shard.

    This is the primary endpoint for the Settings UI to toggle shards.
    """
    from ..main import get_frame

    frame = get_frame()

    if request.enabled:
        # Enable/load the shard
        if shard_name in frame.shards:
            # Already loaded, just remove from disabled set
            _disabled_shards.discard(shard_name)
            return {
                "status": "success",
                "message": f"Shard '{shard_name}' is already enabled",
                "shard": shard_name,
                "enabled": True,
                "loaded": True,
            }
        else:
            # Need to load it
            result = await load_shard(LoadShardRequest(name=shard_name))
            return {
                "status": "success",
                "message": f"Shard '{shard_name}' enabled and loaded",
                "shard": shard_name,
                "enabled": True,
                "loaded": True,
            }
    else:
        # Disable/unload the shard
        if shard_name not in frame.shards:
            # Already not loaded
            _disabled_shards.add(shard_name)
            return {
                "status": "success",
                "message": f"Shard '{shard_name}' is already disabled",
                "shard": shard_name,
                "enabled": False,
                "loaded": False,
            }
        else:
            # Unload it
            result = await unload_shard(shard_name)
            return {
                "status": "success",
                "message": f"Shard '{shard_name}' disabled and unloaded",
                "shard": shard_name,
                "enabled": False,
                "loaded": False,
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
