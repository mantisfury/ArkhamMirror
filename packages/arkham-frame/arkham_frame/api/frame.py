"""
Frame-level API endpoints.

Provides Shell integration endpoints:
- /api/frame/badges - Aggregated badge counts from all shards
- /api/frame/health - Frame health status
"""

from fastapi import APIRouter
from typing import Dict, Any
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/badges")
async def get_all_badges() -> Dict[str, Any]:
    """
    Aggregate badge counts from all loaded shards.

    Returns a dictionary mapping badge keys to badge info:
    - Main nav badges: "{shardName}" -> {count, type}
    - Sub-route badges: "{shardName}:{subRouteId}" -> {count, type}

    Shards must implement get_badge_count() and/or get_subroute_badge_count(sub_id).
    """
    from ..main import get_frame

    frame = get_frame()
    badges: Dict[str, Any] = {}

    for name, shard in frame.shards.items():
        manifest = getattr(shard, "manifest", None)
        if not manifest:
            continue

        # Get navigation config
        nav = None
        if hasattr(manifest, "navigation") and manifest.navigation:
            nav = manifest.navigation
        elif isinstance(manifest, dict) and "navigation" in manifest:
            nav = manifest["navigation"]

        if not nav:
            continue

        # Main nav badge
        badge_endpoint = getattr(nav, "badge_endpoint", None) if hasattr(nav, "badge_endpoint") else nav.get("badge_endpoint")
        badge_type = getattr(nav, "badge_type", "count") if hasattr(nav, "badge_type") else nav.get("badge_type", "count")

        if badge_endpoint:
            try:
                # Check if shard has get_badge_count method
                if hasattr(shard, "get_badge_count"):
                    count = await shard.get_badge_count()
                    badges[name] = {
                        "count": count,
                        "type": badge_type or "count"
                    }
            except Exception as e:
                logger.warning(f"Failed to get badge for {name}: {e}")

        # Sub-route badges
        sub_routes = getattr(nav, "sub_routes", []) if hasattr(nav, "sub_routes") else nav.get("sub_routes", [])

        for sub in sub_routes:
            sub_badge_endpoint = sub.badge_endpoint if hasattr(sub, "badge_endpoint") else sub.get("badge_endpoint")
            sub_badge_type = sub.badge_type if hasattr(sub, "badge_type") else sub.get("badge_type", "count")
            sub_id = sub.id if hasattr(sub, "id") else sub.get("id")

            if sub_badge_endpoint and sub_id:
                try:
                    if hasattr(shard, "get_subroute_badge_count"):
                        count = await shard.get_subroute_badge_count(sub_id)
                        badges[f"{name}:{sub_id}"] = {
                            "count": count,
                            "type": sub_badge_type or "count"
                        }
                except Exception as e:
                    logger.warning(f"Failed to get badge for {name}:{sub_id}: {e}")

    return badges


@router.get("/health")
async def get_frame_health() -> Dict[str, Any]:
    """Get Frame health status for connection monitoring."""
    from ..main import get_frame

    try:
        frame = get_frame()
        return {
            "status": "healthy",
            "version": "0.1.0",
            "services": {
                "config": frame.config is not None,
                "database": frame.db is not None,
                "vectors": frame.vectors is not None,
                "llm": frame.llm is not None,
                "events": frame.events is not None,
            },
            "shards": list(frame.shards.keys()),
            "shard_count": len(frame.shards),
        }
    except Exception as e:
        return {
            "status": "degraded",
            "error": str(e),
        }


@router.get("/state")
async def get_frame_state() -> Dict[str, Any]:
    """Get detailed Frame state."""
    from ..main import get_frame

    frame = get_frame()
    return frame.get_state()
