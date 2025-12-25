"""
Shard Interface - The contract all shards must follow.

This ABC (Abstract Base Class) is the "Constitution" for shard development.

Manifest Schema v5 - See SHARD_MANIFEST_SCHEMA_v5.md for full documentation.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Literal, TYPE_CHECKING

if TYPE_CHECKING:
    from arkham_frame import ArkhamFrame


# ============================================
# Manifest v5 Data Classes
# ============================================

@dataclass
class SubRoute:
    """Sub-route for navigation."""
    id: str
    label: str
    route: str
    icon: str
    badge_endpoint: Optional[str] = None
    badge_type: Optional[Literal["count", "dot"]] = None


@dataclass
class NavigationConfig:
    """Navigation configuration for v5 manifest."""
    category: Literal["System", "Data", "Search", "Analysis", "Visualize", "Export"]
    order: int
    icon: str
    label: str
    route: str
    badge_endpoint: Optional[str] = None
    badge_type: Optional[Literal["count", "dot"]] = None
    sub_routes: List[SubRoute] = field(default_factory=list)


@dataclass
class DependencyConfig:
    """Dependency configuration."""
    services: List[str] = field(default_factory=list)
    optional: List[str] = field(default_factory=list)
    shards: List[str] = field(default_factory=list)


@dataclass
class EventConfig:
    """Event pub/sub configuration."""
    publishes: List[str] = field(default_factory=list)
    subscribes: List[str] = field(default_factory=list)


@dataclass
class StateConfig:
    """State management configuration."""
    strategy: Literal["url", "local", "session", "none"] = "none"
    url_params: List[str] = field(default_factory=list)
    local_keys: List[str] = field(default_factory=list)


@dataclass
class UIConfig:
    """UI configuration for generic/custom rendering."""
    has_custom_ui: bool = False
    id_field: str = "id"
    selectable: bool = True
    list_endpoint: Optional[str] = None
    detail_endpoint: Optional[str] = None
    list_filters: List[Dict[str, Any]] = field(default_factory=list)
    list_columns: List[Dict[str, Any]] = field(default_factory=list)
    bulk_actions: List[Dict[str, Any]] = field(default_factory=list)
    row_actions: List[Dict[str, Any]] = field(default_factory=list)
    primary_action: Optional[Dict[str, Any]] = None
    actions: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class ShardManifest:
    """
    Shard manifest data from shard.yaml.

    Supports both legacy format (menu) and v5 format (navigation).
    """
    # Required fields
    name: str
    version: str
    description: str = ""
    entry_point: str = ""
    api_prefix: str = ""
    requires_frame: str = ">=0.1.0"

    # v5 Navigation (preferred)
    navigation: Optional[NavigationConfig] = None

    # v5 Optional configs
    dependencies: Optional[DependencyConfig] = None
    capabilities: List[str] = field(default_factory=list)
    events: Optional[EventConfig] = None
    state: Optional[StateConfig] = None
    ui: Optional[UIConfig] = None

    # Legacy fields (deprecated, for backward compatibility)
    schema: Optional[str] = None
    menu: List[Dict[str, Any]] = field(default_factory=list)
    requires: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert manifest to dictionary for API response."""
        result = {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "entry_point": self.entry_point,
            "api_prefix": self.api_prefix,
            "requires_frame": self.requires_frame,
        }

        if self.navigation:
            result["navigation"] = {
                "category": self.navigation.category,
                "order": self.navigation.order,
                "icon": self.navigation.icon,
                "label": self.navigation.label,
                "route": self.navigation.route,
                "badge_endpoint": self.navigation.badge_endpoint,
                "badge_type": self.navigation.badge_type,
                "sub_routes": [
                    {
                        "id": sr.id,
                        "label": sr.label,
                        "route": sr.route,
                        "icon": sr.icon,
                        "badge_endpoint": sr.badge_endpoint,
                        "badge_type": sr.badge_type,
                    }
                    for sr in self.navigation.sub_routes
                ] if self.navigation.sub_routes else [],
            }

        if self.dependencies:
            result["dependencies"] = {
                "services": self.dependencies.services,
                "optional": self.dependencies.optional,
                "shards": self.dependencies.shards,
            }

        if self.capabilities:
            result["capabilities"] = self.capabilities

        if self.events:
            result["events"] = {
                "publishes": self.events.publishes,
                "subscribes": self.events.subscribes,
            }

        if self.state:
            result["state"] = {
                "strategy": self.state.strategy,
                "url_params": self.state.url_params,
                "local_keys": self.state.local_keys,
            }

        if self.ui:
            result["ui"] = {
                "has_custom_ui": self.ui.has_custom_ui,
                "id_field": self.ui.id_field,
                "selectable": self.ui.selectable,
                "list_endpoint": self.ui.list_endpoint,
                "detail_endpoint": self.ui.detail_endpoint,
                "list_filters": self.ui.list_filters,
                "list_columns": self.ui.list_columns,
                "bulk_actions": self.ui.bulk_actions,
                "row_actions": self.ui.row_actions,
                "primary_action": self.ui.primary_action,
                "actions": self.ui.actions,
            }

        # Legacy fields for backward compatibility
        if self.menu:
            result["menu"] = self.menu
        if self.requires:
            result["requires"] = self.requires

        return result


class ArkhamShard(ABC):
    """
    Base class for all ArkhamMirror shards.

    RULES FOR SHARD DEVELOPERS:
    1. You MUST inherit from this class.
    2. You MUST NOT import other shards directly.
    3. You MUST access Frame data ONLY via self.frame.
    4. You MUST define your own schema for data storage (optional).
    5. You MUST implement initialize() and shutdown().

    The Frame is your only door to the outside world. Use it.
    """

    # Shards can define these as class attributes
    name: str = "unknown"
    version: str = "0.0.0"
    description: str = ""

    def __init__(self):
        """
        Shard constructor. Do not override with required args.
        Use initialize(frame) for setup that needs the Frame.
        """
        self.frame = None

    @abstractmethod
    async def initialize(self, frame: "ArkhamFrame") -> None:
        """
        Called when the shard is loaded.

        Args:
            frame: The ArkhamFrame instance providing all services.

        Set up event subscriptions, create schema if needed.
        Store frame reference as self.frame for later use.
        """
        pass

    @abstractmethod
    async def shutdown(self) -> None:
        """
        Called when the shard is being unloaded.
        Clean up resources, unsubscribe from events.
        """
        pass

    def get_routes(self):
        """
        Return the FastAPI router for this shard.
        Override in subclasses to provide API routes.
        """
        return None

    def get_api_router(self):
        """Alias for get_routes() for backwards compatibility."""
        return self.get_routes()
