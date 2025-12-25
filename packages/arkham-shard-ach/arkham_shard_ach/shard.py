"""ACH Shard - Analysis of Competing Hypotheses."""

import logging
from pathlib import Path

import yaml

from arkham_frame.shard_interface import (
    ArkhamShard,
    ShardManifest,
    NavigationConfig,
    SubRoute,
    DependencyConfig,
    EventConfig,
    StateConfig,
    UIConfig,
)

from .api import init_api, router
from .matrix import MatrixManager
from .scoring import ACHScorer
from .evidence import EvidenceAnalyzer
from .export import MatrixExporter

logger = logging.getLogger(__name__)


def load_manifest_from_yaml(yaml_path: Path) -> ShardManifest:
    """Load and parse a shard.yaml file into a ShardManifest."""
    with open(yaml_path, "r") as f:
        data = yaml.safe_load(f)

    # Parse navigation config
    nav_data = data.get("navigation", {})
    navigation = None
    if nav_data:
        sub_routes = []
        for sr in nav_data.get("sub_routes", []):
            sub_routes.append(SubRoute(
                id=sr["id"],
                label=sr["label"],
                route=sr["route"],
                icon=sr.get("icon", "Circle"),
                badge_endpoint=sr.get("badge_endpoint"),
                badge_type=sr.get("badge_type"),
            ))

        navigation = NavigationConfig(
            category=nav_data.get("category", "Analysis"),
            order=nav_data.get("order", 99),
            icon=nav_data.get("icon", "Circle"),
            label=nav_data.get("label", data.get("name", "Unknown")),
            route=nav_data.get("route", f"/{data.get('name', 'unknown')}"),
            badge_endpoint=nav_data.get("badge_endpoint"),
            badge_type=nav_data.get("badge_type"),
            sub_routes=sub_routes,
        )

    # Parse dependencies
    deps_data = data.get("dependencies", {})
    dependencies = None
    if deps_data:
        dependencies = DependencyConfig(
            services=deps_data.get("services", []),
            optional=deps_data.get("optional", []),
            shards=deps_data.get("shards", []),
        )

    # Parse events
    events_data = data.get("events", {})
    events = None
    if events_data:
        events = EventConfig(
            publishes=events_data.get("publishes", []),
            subscribes=events_data.get("subscribes", []),
        )

    # Parse state
    state_data = data.get("state", {})
    state = None
    if state_data:
        state = StateConfig(
            strategy=state_data.get("strategy", "none"),
            url_params=state_data.get("url_params", []),
            local_keys=state_data.get("local_keys", []),
        )

    # Parse UI config
    ui_data = data.get("ui", {})
    ui = None
    if ui_data:
        ui = UIConfig(
            has_custom_ui=ui_data.get("has_custom_ui", False),
            id_field=ui_data.get("id_field", "id"),
            selectable=ui_data.get("selectable", True),
            list_endpoint=ui_data.get("list_endpoint"),
            detail_endpoint=ui_data.get("detail_endpoint"),
            list_filters=ui_data.get("list_filters", []),
            list_columns=ui_data.get("list_columns", []),
            bulk_actions=ui_data.get("bulk_actions", []),
            row_actions=ui_data.get("row_actions", []),
            primary_action=ui_data.get("primary_action"),
            actions=ui_data.get("actions", []),
        )

    return ShardManifest(
        name=data.get("name", "unknown"),
        version=data.get("version", "0.0.0"),
        description=data.get("description", ""),
        entry_point=data.get("entry_point", ""),
        api_prefix=data.get("api_prefix", ""),
        requires_frame=data.get("requires_frame", ">=0.1.0"),
        navigation=navigation,
        dependencies=dependencies,
        capabilities=data.get("capabilities", []),
        events=events,
        state=state,
        ui=ui,
    )


class ACHShard(ArkhamShard):
    """
    Analysis of Competing Hypotheses shard for ArkhamFrame.

    Provides structured intelligence analysis methodology for
    evaluating multiple competing hypotheses against evidence.

    Handles:
    - Matrix creation and management
    - Hypothesis and evidence tracking
    - Consistency rating between evidence and hypotheses
    - Automated scoring and ranking
    - Devil's advocate mode (requires LLM)
    - Export to multiple formats
    """

    name = "ach"
    version = "0.1.0"
    description = "Analysis of Competing Hypotheses matrix for intelligence analysis"

    def __init__(self):
        super().__init__()
        self.matrix_manager: MatrixManager | None = None
        self.scorer: ACHScorer | None = None
        self.evidence_analyzer: EvidenceAnalyzer | None = None
        self.exporter: MatrixExporter | None = None
        self._frame = None
        self._event_bus = None
        self._llm_service = None

        # Load manifest from shard.yaml
        self.manifest = self._load_manifest()

    def _load_manifest(self) -> ShardManifest:
        """Load the shard manifest from shard.yaml."""
        # Find shard.yaml relative to this file
        shard_dir = Path(__file__).parent.parent
        yaml_path = shard_dir / "shard.yaml"

        if yaml_path.exists():
            try:
                return load_manifest_from_yaml(yaml_path)
            except Exception as e:
                logger.warning(f"Failed to load shard.yaml: {e}")

        # Fallback to minimal manifest
        return ShardManifest(
            name=self.name,
            version=self.version,
            description=self.description,
            navigation=NavigationConfig(
                category="Analysis",
                order=30,
                icon="Scale",
                label="ACH Analysis",
                route="/ach",
            ),
        )

    async def initialize(self, frame) -> None:
        """
        Initialize the ACH shard with Frame services.

        Args:
            frame: The ArkhamFrame instance
        """
        self._frame = frame

        logger.info("Initializing ACH Shard...")

        # Create managers
        self.matrix_manager = MatrixManager()
        self.scorer = ACHScorer()
        self.evidence_analyzer = EvidenceAnalyzer()
        self.exporter = MatrixExporter()

        # Get Frame services
        self._event_bus = frame.get_service("events")
        self._llm_service = frame.get_service("llm")

        if not self._llm_service:
            logger.warning("LLM service not available - devil's advocate mode disabled")

        # Initialize API with our instances
        init_api(
            matrix_manager=self.matrix_manager,
            scorer=self.scorer,
            evidence_analyzer=self.evidence_analyzer,
            exporter=self.exporter,
            event_bus=self._event_bus,
            llm_service=self._llm_service,
        )

        # Subscribe to events if needed
        if self._event_bus:
            # We could subscribe to events from other shards here
            # For example, when documents are added, we could link them to evidence
            pass

        logger.info("ACH Shard initialized")

    async def shutdown(self) -> None:
        """Clean up shard resources."""
        logger.info("Shutting down ACH Shard...")

        # Unsubscribe from events
        if self._event_bus:
            # Unsubscribe from any events we subscribed to
            pass

        # Clear managers
        self.matrix_manager = None
        self.scorer = None
        self.evidence_analyzer = None
        self.exporter = None

        logger.info("ACH Shard shutdown complete")

    def get_routes(self):
        """Return FastAPI router for this shard."""
        return router

    # --- Public API for other shards ---

    def create_matrix(
        self,
        title: str,
        description: str = "",
        created_by: str | None = None,
        project_id: str | None = None,
    ):
        """
        Public method for other shards to create an ACH matrix.

        Args:
            title: Matrix title
            description: Matrix description
            created_by: Creator identifier
            project_id: Associated project ID

        Returns:
            ACHMatrix instance
        """
        if not self.matrix_manager:
            raise RuntimeError("ACH Shard not initialized")

        return self.matrix_manager.create_matrix(
            title=title,
            description=description,
            created_by=created_by,
            project_id=project_id,
        )

    def get_matrix(self, matrix_id: str):
        """
        Public method to get a matrix.

        Args:
            matrix_id: Matrix ID

        Returns:
            ACHMatrix instance or None
        """
        if not self.matrix_manager:
            raise RuntimeError("ACH Shard not initialized")

        return self.matrix_manager.get_matrix(matrix_id)

    def calculate_scores(self, matrix_id: str):
        """
        Public method to calculate scores for a matrix.

        Args:
            matrix_id: Matrix ID

        Returns:
            List of HypothesisScore objects
        """
        if not self.matrix_manager or not self.scorer:
            raise RuntimeError("ACH Shard not initialized")

        matrix = self.matrix_manager.get_matrix(matrix_id)
        if not matrix:
            return None

        return self.scorer.calculate_scores(matrix)

    def export_matrix(self, matrix_id: str, format: str = "json"):
        """
        Public method to export a matrix.

        Args:
            matrix_id: Matrix ID
            format: Export format (json, csv, html, markdown)

        Returns:
            MatrixExport instance
        """
        if not self.matrix_manager or not self.exporter:
            raise RuntimeError("ACH Shard not initialized")

        matrix = self.matrix_manager.get_matrix(matrix_id)
        if not matrix:
            return None

        return self.exporter.export(matrix, format=format)
