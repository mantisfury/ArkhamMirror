"""ACH Shard - Analysis of Competing Hypotheses."""

import logging

from arkham_frame.shard_interface import ArkhamShard

from .api import init_api, router
from .matrix import MatrixManager
from .scoring import ACHScorer
from .evidence import EvidenceAnalyzer
from .export import MatrixExporter

logger = logging.getLogger(__name__)


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
        super().__init__()  # Auto-loads manifest from shard.yaml
        self.matrix_manager: MatrixManager | None = None
        self.scorer: ACHScorer | None = None
        self.evidence_analyzer: EvidenceAnalyzer | None = None
        self.exporter: MatrixExporter | None = None
        self._frame = None
        self._event_bus = None
        self._llm_service = None

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
