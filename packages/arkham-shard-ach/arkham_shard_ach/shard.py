"""ACH Shard - Analysis of Competing Hypotheses."""

import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from arkham_frame.shard_interface import ArkhamShard

from .api import init_api, router
from .matrix import MatrixManager
from .scoring import ACHScorer
from .evidence import EvidenceAnalyzer
from .export import MatrixExporter
from .corpus import CorpusSearchService
from .models import (
    ACHMatrix,
    ConsistencyRating,
    Evidence,
    EvidenceType,
    FailureMode,
    FailureModeType,
    Hypothesis,
    MatrixStatus,
    PremortemAnalysis,
    PremortemConversionType,
    Rating,
    ScenarioDriver,
    ScenarioIndicator,
    ScenarioNode,
    ScenarioStatus,
    ScenarioTree,
)

logger = logging.getLogger(__name__)


def _parse_json_field(value: Any, default: Any = None) -> Any:
    """Parse a JSON field that may already be parsed by the database driver."""
    if value is None:
        return default if default is not None else []
    if isinstance(value, (list, dict)):
        return value  # Already parsed by PostgreSQL JSONB
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return default if default is not None else []
    return default if default is not None else []


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
        self._db = None
        self._event_bus = None
        self._llm_service = None
        self._vectors_service = None
        self._documents_service = None
        self.corpus_service: CorpusSearchService | None = None

    async def initialize(self, frame) -> None:
        """
        Initialize the ACH shard with Frame services.

        Args:
            frame: The ArkhamFrame instance
        """
        self._frame = frame

        logger.info("Initializing ACH Shard...")

        # Get Frame services first (needed for MatrixManager persistence)
        self._db = frame.database
        self._event_bus = frame.get_service("events")
        self._llm_service = frame.get_service("llm")
        self._vectors_service = frame.get_service("vectors")
        self._documents_service = frame.get_service("documents")

        # Create database schema for ACH tables
        await self._create_schema()

        # Create managers with shard reference for persistence
        self.matrix_manager = MatrixManager(shard=self)
        self.scorer = ACHScorer()
        self.evidence_analyzer = EvidenceAnalyzer()
        self.exporter = MatrixExporter()

        if not self._llm_service:
            logger.warning("LLM service not available - devil's advocate mode disabled")

        # Initialize corpus search service if dependencies available
        if self._vectors_service and self._llm_service:
            self.corpus_service = CorpusSearchService(
                vectors_service=self._vectors_service,
                documents_service=self._documents_service,
                llm_service=self._llm_service,
            )
            logger.info("Corpus search service initialized")
        else:
            logger.warning("Corpus search not available (requires vectors + LLM)")

        # Initialize API with our instances
        init_api(
            matrix_manager=self.matrix_manager,
            scorer=self.scorer,
            evidence_analyzer=self.evidence_analyzer,
            exporter=self.exporter,
            event_bus=self._event_bus,
            llm_service=self._llm_service,
            corpus_service=self.corpus_service,
            shard=self,
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
        self.corpus_service = None

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

    # --- Database Schema and Persistence ---

    async def _create_schema(self) -> None:
        """Create database schema for ACH matrices, premortem, and scenarios."""
        if not self._db:
            logger.warning("Database service not available - persistence disabled")
            return

        try:
            # Create schema
            await self._db.execute("CREATE SCHEMA IF NOT EXISTS arkham_ach")

            # ===========================================
            # ACH Matrix Tables
            # ===========================================

            # Matrices table
            await self._db.execute("""
                CREATE TABLE IF NOT EXISTS arkham_ach.matrices (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT,
                    question TEXT,
                    project_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_by TEXT,
                    status TEXT DEFAULT 'active',
                    settings JSONB DEFAULT '{}',
                    metadata JSONB DEFAULT '{}'
                )
            """)

            # Hypotheses table
            await self._db.execute("""
                CREATE TABLE IF NOT EXISTS arkham_ach.hypotheses (
                    id TEXT PRIMARY KEY,
                    matrix_id TEXT NOT NULL REFERENCES arkham_ach.matrices(id) ON DELETE CASCADE,
                    title TEXT NOT NULL,
                    description TEXT,
                    column_index INTEGER DEFAULT 0,
                    is_lead BOOLEAN DEFAULT FALSE,
                    notes TEXT,
                    author TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Evidence table
            await self._db.execute("""
                CREATE TABLE IF NOT EXISTS arkham_ach.evidence (
                    id TEXT PRIMARY KEY,
                    matrix_id TEXT NOT NULL REFERENCES arkham_ach.matrices(id) ON DELETE CASCADE,
                    description TEXT NOT NULL,
                    source TEXT,
                    evidence_type TEXT DEFAULT 'FACT',
                    credibility REAL DEFAULT 1.0,
                    relevance REAL DEFAULT 1.0,
                    row_index INTEGER DEFAULT 0,
                    notes TEXT,
                    author TEXT,
                    document_ids JSONB DEFAULT '[]',
                    source_document_id TEXT,
                    source_chunk_id TEXT,
                    source_page_number INTEGER,
                    source_quote TEXT,
                    extraction_method TEXT DEFAULT 'manual',
                    similarity_score REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Ratings table
            await self._db.execute("""
                CREATE TABLE IF NOT EXISTS arkham_ach.ratings (
                    id TEXT PRIMARY KEY,
                    matrix_id TEXT NOT NULL REFERENCES arkham_ach.matrices(id) ON DELETE CASCADE,
                    hypothesis_id TEXT NOT NULL,
                    evidence_id TEXT NOT NULL,
                    rating TEXT NOT NULL,
                    notes TEXT,
                    rated_by TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(matrix_id, hypothesis_id, evidence_id)
                )
            """)

            # Matrix indexes
            await self._db.execute(
                "CREATE INDEX IF NOT EXISTS idx_ach_matrices_project ON arkham_ach.matrices(project_id)"
            )
            await self._db.execute(
                "CREATE INDEX IF NOT EXISTS idx_ach_hypotheses_matrix ON arkham_ach.hypotheses(matrix_id)"
            )
            await self._db.execute(
                "CREATE INDEX IF NOT EXISTS idx_ach_evidence_matrix ON arkham_ach.evidence(matrix_id)"
            )
            await self._db.execute(
                "CREATE INDEX IF NOT EXISTS idx_ach_ratings_matrix ON arkham_ach.ratings(matrix_id)"
            )

            # ===========================================
            # Premortem and Scenario Tables
            # ===========================================

            # Premortem analysis table
            await self._db.execute("""
                CREATE TABLE IF NOT EXISTS arkham_ach.premortems (
                    id TEXT PRIMARY KEY,
                    matrix_id TEXT NOT NULL,
                    hypothesis_id TEXT NOT NULL,
                    hypothesis_title TEXT NOT NULL,
                    scenario_description TEXT,
                    overall_vulnerability TEXT DEFAULT 'medium',
                    key_risks JSONB DEFAULT '[]',
                    recommendations JSONB DEFAULT '[]',
                    model_used TEXT,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW(),
                    created_by TEXT
                )
            """)

            # Failure modes table
            await self._db.execute("""
                CREATE TABLE IF NOT EXISTS arkham_ach.failure_modes (
                    id TEXT PRIMARY KEY,
                    premortem_id TEXT NOT NULL REFERENCES arkham_ach.premortems(id) ON DELETE CASCADE,
                    failure_type TEXT NOT NULL,
                    description TEXT NOT NULL,
                    likelihood TEXT DEFAULT 'medium',
                    early_warning_indicator TEXT,
                    mitigation_action TEXT,
                    converted_to TEXT,
                    converted_id TEXT,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)

            # Scenario trees table
            await self._db.execute("""
                CREATE TABLE IF NOT EXISTS arkham_ach.scenario_trees (
                    id TEXT PRIMARY KEY,
                    matrix_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT,
                    situation_summary TEXT,
                    root_node_id TEXT,
                    model_used TEXT,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW(),
                    created_by TEXT
                )
            """)

            # Scenario nodes table
            await self._db.execute("""
                CREATE TABLE IF NOT EXISTS arkham_ach.scenario_nodes (
                    id TEXT PRIMARY KEY,
                    tree_id TEXT NOT NULL REFERENCES arkham_ach.scenario_trees(id) ON DELETE CASCADE,
                    parent_id TEXT,
                    title TEXT NOT NULL,
                    description TEXT,
                    probability REAL DEFAULT 0.0,
                    timeframe TEXT,
                    key_drivers JSONB DEFAULT '[]',
                    trigger_conditions JSONB DEFAULT '[]',
                    status TEXT DEFAULT 'active',
                    converted_hypothesis_id TEXT,
                    depth INTEGER DEFAULT 0,
                    branch_order INTEGER DEFAULT 0,
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            """)

            # Scenario indicators table
            await self._db.execute("""
                CREATE TABLE IF NOT EXISTS arkham_ach.scenario_indicators (
                    id TEXT PRIMARY KEY,
                    scenario_id TEXT NOT NULL REFERENCES arkham_ach.scenario_nodes(id) ON DELETE CASCADE,
                    description TEXT NOT NULL,
                    is_triggered BOOLEAN DEFAULT FALSE,
                    triggered_at TIMESTAMP,
                    notes TEXT
                )
            """)

            # Scenario drivers table
            await self._db.execute("""
                CREATE TABLE IF NOT EXISTS arkham_ach.scenario_drivers (
                    id TEXT PRIMARY KEY,
                    tree_id TEXT NOT NULL REFERENCES arkham_ach.scenario_trees(id) ON DELETE CASCADE,
                    name TEXT NOT NULL,
                    description TEXT,
                    current_state TEXT,
                    possible_states JSONB DEFAULT '[]'
                )
            """)

            # Create indexes
            await self._db.execute(
                "CREATE INDEX IF NOT EXISTS idx_premortems_matrix ON arkham_ach.premortems(matrix_id)"
            )
            await self._db.execute(
                "CREATE INDEX IF NOT EXISTS idx_premortems_hypothesis ON arkham_ach.premortems(hypothesis_id)"
            )
            await self._db.execute(
                "CREATE INDEX IF NOT EXISTS idx_scenario_trees_matrix ON arkham_ach.scenario_trees(matrix_id)"
            )
            await self._db.execute(
                "CREATE INDEX IF NOT EXISTS idx_scenario_nodes_tree ON arkham_ach.scenario_nodes(tree_id)"
            )

            logger.info("ACH database schema created")

        except Exception as e:
            logger.error(f"Failed to create ACH schema: {e}")

    # --- Premortem Persistence ---

    async def save_premortem(self, premortem: PremortemAnalysis) -> PremortemAnalysis:
        """Save a premortem analysis to the database."""
        if not self._db:
            raise RuntimeError("Database service not available")

        await self._db.execute(
            """
            INSERT INTO arkham_ach.premortems
            (id, matrix_id, hypothesis_id, hypothesis_title, scenario_description,
             overall_vulnerability, key_risks, recommendations, model_used,
             created_at, updated_at, created_by)
            VALUES (:id, :matrix_id, :hypothesis_id, :hypothesis_title, :scenario_description,
                    :overall_vulnerability, :key_risks, :recommendations, :model_used,
                    :created_at, :updated_at, :created_by)
            ON CONFLICT (id) DO UPDATE SET
                scenario_description = EXCLUDED.scenario_description,
                overall_vulnerability = EXCLUDED.overall_vulnerability,
                key_risks = EXCLUDED.key_risks,
                recommendations = EXCLUDED.recommendations,
                updated_at = NOW()
            """,
            {
                "id": premortem.id,
                "matrix_id": premortem.matrix_id,
                "hypothesis_id": premortem.hypothesis_id,
                "hypothesis_title": premortem.hypothesis_title,
                "scenario_description": premortem.scenario_description,
                "overall_vulnerability": premortem.overall_vulnerability,
                "key_risks": json.dumps(premortem.key_risks),
                "recommendations": json.dumps(premortem.recommendations),
                "model_used": premortem.model_used,
                "created_at": premortem.created_at,
                "updated_at": premortem.updated_at,
                "created_by": premortem.created_by,
            }
        )

        # Save failure modes
        for fm in premortem.failure_modes:
            await self._db.execute(
                """
                INSERT INTO arkham_ach.failure_modes
                (id, premortem_id, failure_type, description, likelihood,
                 early_warning_indicator, mitigation_action, converted_to,
                 converted_id, created_at)
                VALUES (:id, :premortem_id, :failure_type, :description, :likelihood,
                        :early_warning_indicator, :mitigation_action, :converted_to,
                        :converted_id, :created_at)
                ON CONFLICT (id) DO UPDATE SET
                    description = EXCLUDED.description,
                    likelihood = EXCLUDED.likelihood,
                    early_warning_indicator = EXCLUDED.early_warning_indicator,
                    mitigation_action = EXCLUDED.mitigation_action,
                    converted_to = EXCLUDED.converted_to,
                    converted_id = EXCLUDED.converted_id
                """,
                {
                    "id": fm.id,
                    "premortem_id": fm.premortem_id,
                    "failure_type": fm.failure_type.value,
                    "description": fm.description,
                    "likelihood": fm.likelihood,
                    "early_warning_indicator": fm.early_warning_indicator,
                    "mitigation_action": fm.mitigation_action,
                    "converted_to": fm.converted_to.value if fm.converted_to else None,
                    "converted_id": fm.converted_id,
                    "created_at": fm.created_at,
                }
            )

        return premortem

    async def get_premortems(self, matrix_id: str) -> List[PremortemAnalysis]:
        """Get all premortems for a matrix."""
        if not self._db:
            return []

        rows = await self._db.fetch_all(
            """
            SELECT * FROM arkham_ach.premortems
            WHERE matrix_id = :matrix_id
            ORDER BY created_at DESC
            """,
            {"matrix_id": matrix_id}
        )

        premortems = []
        for row in rows:
            # Get failure modes
            fm_rows = await self._db.fetch_all(
                """
                SELECT * FROM arkham_ach.failure_modes
                WHERE premortem_id = :premortem_id
                ORDER BY created_at
                """,
                {"premortem_id": row["id"]}
            )

            failure_modes = [
                FailureMode(
                    id=fm["id"],
                    premortem_id=fm["premortem_id"],
                    failure_type=FailureModeType(fm["failure_type"]),
                    description=fm["description"],
                    likelihood=fm["likelihood"],
                    early_warning_indicator=fm["early_warning_indicator"] or "",
                    mitigation_action=fm["mitigation_action"] or "",
                    converted_to=PremortemConversionType(fm["converted_to"]) if fm["converted_to"] else None,
                    converted_id=fm["converted_id"],
                    created_at=fm["created_at"],
                )
                for fm in fm_rows
            ]

            premortems.append(PremortemAnalysis(
                id=row["id"],
                matrix_id=row["matrix_id"],
                hypothesis_id=row["hypothesis_id"],
                hypothesis_title=row["hypothesis_title"],
                scenario_description=row["scenario_description"] or "",
                failure_modes=failure_modes,
                overall_vulnerability=row["overall_vulnerability"],
                key_risks=_parse_json_field(row["key_risks"]),
                recommendations=_parse_json_field(row["recommendations"]),
                model_used=row["model_used"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                created_by=row["created_by"],
            ))

        return premortems

    async def get_premortem(self, premortem_id: str) -> Optional[PremortemAnalysis]:
        """Get a single premortem by ID."""
        if not self._db:
            return None

        row = await self._db.fetch_one(
            "SELECT * FROM arkham_ach.premortems WHERE id = :id",
            {"id": premortem_id}
        )

        if not row:
            return None

        # Get failure modes
        fm_rows = await self._db.fetch_all(
            """
            SELECT * FROM arkham_ach.failure_modes
            WHERE premortem_id = :premortem_id
            ORDER BY created_at
            """,
            {"premortem_id": premortem_id}
        )

        failure_modes = [
            FailureMode(
                id=fm["id"],
                premortem_id=fm["premortem_id"],
                failure_type=FailureModeType(fm["failure_type"]),
                description=fm["description"],
                likelihood=fm["likelihood"],
                early_warning_indicator=fm["early_warning_indicator"] or "",
                mitigation_action=fm["mitigation_action"] or "",
                converted_to=PremortemConversionType(fm["converted_to"]) if fm["converted_to"] else None,
                converted_id=fm["converted_id"],
                created_at=fm["created_at"],
            )
            for fm in fm_rows
        ]

        return PremortemAnalysis(
            id=row["id"],
            matrix_id=row["matrix_id"],
            hypothesis_id=row["hypothesis_id"],
            hypothesis_title=row["hypothesis_title"],
            scenario_description=row["scenario_description"] or "",
            failure_modes=failure_modes,
            overall_vulnerability=row["overall_vulnerability"],
            key_risks=_parse_json_field(row["key_risks"]),
            recommendations=_parse_json_field(row["recommendations"]),
            model_used=row["model_used"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            created_by=row["created_by"],
        )

    async def delete_premortem(self, premortem_id: str) -> bool:
        """Delete a premortem (cascades to failure modes)."""
        if not self._db:
            return False

        result = await self._db.execute(
            "DELETE FROM arkham_ach.premortems WHERE id = :id",
            {"id": premortem_id}
        )
        return True

    # --- Scenario Tree Persistence ---

    async def save_scenario_tree(self, tree: ScenarioTree) -> ScenarioTree:
        """Save a scenario tree to the database."""
        if not self._db:
            raise RuntimeError("Database service not available")

        await self._db.execute(
            """
            INSERT INTO arkham_ach.scenario_trees
            (id, matrix_id, title, description, situation_summary, root_node_id,
             model_used, created_at, updated_at, created_by)
            VALUES (:id, :matrix_id, :title, :description, :situation_summary, :root_node_id,
                    :model_used, :created_at, :updated_at, :created_by)
            ON CONFLICT (id) DO UPDATE SET
                title = EXCLUDED.title,
                description = EXCLUDED.description,
                situation_summary = EXCLUDED.situation_summary,
                root_node_id = EXCLUDED.root_node_id,
                updated_at = NOW()
            """,
            {
                "id": tree.id,
                "matrix_id": tree.matrix_id,
                "title": tree.title,
                "description": tree.description,
                "situation_summary": tree.situation_summary,
                "root_node_id": tree.root_node_id,
                "model_used": tree.model_used,
                "created_at": tree.created_at,
                "updated_at": tree.updated_at,
                "created_by": tree.created_by,
            }
        )

        # Save nodes
        for node in tree.nodes:
            await self._save_scenario_node(node)

        # Save drivers
        for driver in tree.drivers:
            await self._db.execute(
                """
                INSERT INTO arkham_ach.scenario_drivers
                (id, tree_id, name, description, current_state, possible_states)
                VALUES (:id, :tree_id, :name, :description, :current_state, :possible_states)
                ON CONFLICT (id) DO UPDATE SET
                    name = EXCLUDED.name,
                    description = EXCLUDED.description,
                    current_state = EXCLUDED.current_state,
                    possible_states = EXCLUDED.possible_states
                """,
                {
                    "id": driver.id,
                    "tree_id": driver.tree_id,
                    "name": driver.name,
                    "description": driver.description,
                    "current_state": driver.current_state,
                    "possible_states": json.dumps(driver.possible_states),
                }
            )

        return tree

    async def _save_scenario_node(self, node: ScenarioNode) -> None:
        """Save a single scenario node."""
        await self._db.execute(
            """
            INSERT INTO arkham_ach.scenario_nodes
            (id, tree_id, parent_id, title, description, probability, timeframe,
             key_drivers, trigger_conditions, status, converted_hypothesis_id,
             depth, branch_order, notes, created_at, updated_at)
            VALUES (:id, :tree_id, :parent_id, :title, :description, :probability, :timeframe,
                    :key_drivers, :trigger_conditions, :status, :converted_hypothesis_id,
                    :depth, :branch_order, :notes, :created_at, :updated_at)
            ON CONFLICT (id) DO UPDATE SET
                title = EXCLUDED.title,
                description = EXCLUDED.description,
                probability = EXCLUDED.probability,
                timeframe = EXCLUDED.timeframe,
                key_drivers = EXCLUDED.key_drivers,
                trigger_conditions = EXCLUDED.trigger_conditions,
                status = EXCLUDED.status,
                converted_hypothesis_id = EXCLUDED.converted_hypothesis_id,
                notes = EXCLUDED.notes,
                updated_at = NOW()
            """,
            {
                "id": node.id,
                "tree_id": node.tree_id,
                "parent_id": node.parent_id,
                "title": node.title,
                "description": node.description,
                "probability": node.probability,
                "timeframe": node.timeframe,
                "key_drivers": json.dumps(node.key_drivers),
                "trigger_conditions": json.dumps(node.trigger_conditions),
                "status": node.status.value,
                "converted_hypothesis_id": node.converted_hypothesis_id,
                "depth": node.depth,
                "branch_order": node.branch_order,
                "notes": node.notes,
                "created_at": node.created_at,
                "updated_at": node.updated_at,
            }
        )

        # Save indicators
        for ind in node.indicators:
            await self._db.execute(
                """
                INSERT INTO arkham_ach.scenario_indicators
                (id, scenario_id, description, is_triggered, triggered_at, notes)
                VALUES (:id, :scenario_id, :description, :is_triggered, :triggered_at, :notes)
                ON CONFLICT (id) DO UPDATE SET
                    description = EXCLUDED.description,
                    is_triggered = EXCLUDED.is_triggered,
                    triggered_at = EXCLUDED.triggered_at,
                    notes = EXCLUDED.notes
                """,
                {
                    "id": ind.id,
                    "scenario_id": ind.scenario_id,
                    "description": ind.description,
                    "is_triggered": ind.is_triggered,
                    "triggered_at": ind.triggered_at,
                    "notes": ind.notes,
                }
            )

    async def get_scenario_trees(self, matrix_id: str) -> List[ScenarioTree]:
        """Get all scenario trees for a matrix."""
        if not self._db:
            return []

        rows = await self._db.fetch_all(
            """
            SELECT * FROM arkham_ach.scenario_trees
            WHERE matrix_id = :matrix_id
            ORDER BY created_at DESC
            """,
            {"matrix_id": matrix_id}
        )

        trees = []
        for row in rows:
            tree = await self._load_scenario_tree(row)
            if tree:
                trees.append(tree)

        return trees

    async def get_scenario_tree(self, tree_id: str) -> Optional[ScenarioTree]:
        """Get a single scenario tree by ID."""
        if not self._db:
            return None

        row = await self._db.fetch_one(
            "SELECT * FROM arkham_ach.scenario_trees WHERE id = :id",
            {"id": tree_id}
        )

        if not row:
            return None

        return await self._load_scenario_tree(row)

    async def _load_scenario_tree(self, row: Dict[str, Any]) -> ScenarioTree:
        """Load a scenario tree from a database row."""
        tree_id = row["id"]

        # Load nodes
        node_rows = await self._db.fetch_all(
            """
            SELECT * FROM arkham_ach.scenario_nodes
            WHERE tree_id = :tree_id
            ORDER BY depth, branch_order
            """,
            {"tree_id": tree_id}
        )

        nodes = []
        for nr in node_rows:
            # Load indicators for this node
            ind_rows = await self._db.fetch_all(
                """
                SELECT * FROM arkham_ach.scenario_indicators
                WHERE scenario_id = :scenario_id
                """,
                {"scenario_id": nr["id"]}
            )

            indicators = [
                ScenarioIndicator(
                    id=ir["id"],
                    scenario_id=ir["scenario_id"],
                    description=ir["description"],
                    is_triggered=ir["is_triggered"],
                    triggered_at=ir["triggered_at"],
                    notes=ir["notes"] or "",
                )
                for ir in ind_rows
            ]

            nodes.append(ScenarioNode(
                id=nr["id"],
                tree_id=nr["tree_id"],
                parent_id=nr["parent_id"],
                title=nr["title"],
                description=nr["description"] or "",
                probability=nr["probability"],
                timeframe=nr["timeframe"] or "",
                key_drivers=_parse_json_field(nr["key_drivers"]),
                trigger_conditions=_parse_json_field(nr["trigger_conditions"]),
                indicators=indicators,
                status=ScenarioStatus(nr["status"]),
                converted_hypothesis_id=nr["converted_hypothesis_id"],
                depth=nr["depth"],
                branch_order=nr["branch_order"],
                notes=nr["notes"] or "",
                created_at=nr["created_at"],
                updated_at=nr["updated_at"],
            ))

        # Load drivers
        driver_rows = await self._db.fetch_all(
            """
            SELECT * FROM arkham_ach.scenario_drivers
            WHERE tree_id = :tree_id
            """,
            {"tree_id": tree_id}
        )

        drivers = [
            ScenarioDriver(
                id=dr["id"],
                tree_id=dr["tree_id"],
                name=dr["name"],
                description=dr["description"] or "",
                current_state=dr["current_state"] or "",
                possible_states=_parse_json_field(dr["possible_states"]),
            )
            for dr in driver_rows
        ]

        return ScenarioTree(
            id=tree_id,
            matrix_id=row["matrix_id"],
            title=row["title"],
            description=row["description"] or "",
            situation_summary=row["situation_summary"] or "",
            root_node_id=row["root_node_id"],
            nodes=nodes,
            drivers=drivers,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            created_by=row["created_by"],
            model_used=row["model_used"],
        )

    async def delete_scenario_tree(self, tree_id: str) -> bool:
        """Delete a scenario tree (cascades to nodes, indicators, drivers)."""
        if not self._db:
            return False

        await self._db.execute(
            "DELETE FROM arkham_ach.scenario_trees WHERE id = :id",
            {"id": tree_id}
        )
        return True

    async def update_scenario_node(self, node: ScenarioNode) -> ScenarioNode:
        """Update a single scenario node."""
        if not self._db:
            raise RuntimeError("Database service not available")

        await self._save_scenario_node(node)
        return node

    # --- ACH Matrix Persistence ---

    async def _save_matrix(self, matrix: ACHMatrix) -> ACHMatrix:
        """
        Save an ACH matrix and all its components to the database.

        This saves the matrix metadata, hypotheses, evidence, and ratings
        to their respective tables. Uses upsert (INSERT ... ON CONFLICT)
        to handle both new and updated records.

        Args:
            matrix: The ACHMatrix instance to save

        Returns:
            The saved ACHMatrix instance
        """
        if not self._db:
            raise RuntimeError("Database service not available")

        try:
            # Build metadata dict from matrix fields that aren't in main columns
            metadata = {
                "tags": matrix.tags,
                "notes": matrix.notes,
                "linked_document_ids": matrix.linked_document_ids,
            }

            # Save the matrix record
            await self._db.execute(
                """
                INSERT INTO arkham_ach.matrices
                (id, title, description, project_id, created_at, updated_at,
                 created_by, status, metadata)
                VALUES (:id, :title, :description, :project_id, :created_at, :updated_at,
                        :created_by, :status, :metadata)
                ON CONFLICT (id) DO UPDATE SET
                    title = EXCLUDED.title,
                    description = EXCLUDED.description,
                    project_id = EXCLUDED.project_id,
                    status = EXCLUDED.status,
                    metadata = EXCLUDED.metadata,
                    updated_at = NOW()
                """,
                {
                    "id": matrix.id,
                    "title": matrix.title,
                    "description": matrix.description,
                    "project_id": matrix.project_id,
                    "created_at": matrix.created_at,
                    "updated_at": matrix.updated_at,
                    "created_by": matrix.created_by,
                    "status": matrix.status.value,
                    "metadata": json.dumps(metadata),
                }
            )

            # Save hypotheses
            for hyp in matrix.hypotheses:
                await self._db.execute(
                    """
                    INSERT INTO arkham_ach.hypotheses
                    (id, matrix_id, title, description, column_index, is_lead,
                     notes, author, created_at, updated_at)
                    VALUES (:id, :matrix_id, :title, :description, :column_index, :is_lead,
                            :notes, :author, :created_at, :updated_at)
                    ON CONFLICT (id) DO UPDATE SET
                        title = EXCLUDED.title,
                        description = EXCLUDED.description,
                        column_index = EXCLUDED.column_index,
                        is_lead = EXCLUDED.is_lead,
                        notes = EXCLUDED.notes,
                        updated_at = NOW()
                    """,
                    {
                        "id": hyp.id,
                        "matrix_id": hyp.matrix_id,
                        "title": hyp.title,
                        "description": hyp.description,
                        "column_index": hyp.column_index,
                        "is_lead": hyp.is_lead,
                        "notes": hyp.notes,
                        "author": hyp.author,
                        "created_at": hyp.created_at,
                        "updated_at": hyp.updated_at,
                    }
                )

            # Save evidence items
            for ev in matrix.evidence:
                await self._db.execute(
                    """
                    INSERT INTO arkham_ach.evidence
                    (id, matrix_id, description, source, evidence_type, credibility,
                     relevance, row_index, notes, author, document_ids,
                     source_document_id, source_chunk_id, source_page_number,
                     source_quote, extraction_method, similarity_score,
                     created_at, updated_at)
                    VALUES (:id, :matrix_id, :description, :source, :evidence_type, :credibility,
                            :relevance, :row_index, :notes, :author, :document_ids,
                            :source_document_id, :source_chunk_id, :source_page_number,
                            :source_quote, :extraction_method, :similarity_score,
                            :created_at, :updated_at)
                    ON CONFLICT (id) DO UPDATE SET
                        description = EXCLUDED.description,
                        source = EXCLUDED.source,
                        evidence_type = EXCLUDED.evidence_type,
                        credibility = EXCLUDED.credibility,
                        relevance = EXCLUDED.relevance,
                        row_index = EXCLUDED.row_index,
                        notes = EXCLUDED.notes,
                        document_ids = EXCLUDED.document_ids,
                        updated_at = NOW()
                    """,
                    {
                        "id": ev.id,
                        "matrix_id": ev.matrix_id,
                        "description": ev.description,
                        "source": ev.source,
                        "evidence_type": ev.evidence_type.value,
                        "credibility": ev.credibility,
                        "relevance": ev.relevance,
                        "row_index": ev.row_index,
                        "notes": ev.notes,
                        "author": ev.author,
                        "document_ids": json.dumps(ev.document_ids),
                        "source_document_id": ev.source_document_id,
                        "source_chunk_id": ev.source_chunk_id,
                        "source_page_number": ev.source_page_number,
                        "source_quote": ev.source_quote,
                        "extraction_method": ev.extraction_method,
                        "similarity_score": ev.similarity_score,
                        "created_at": ev.created_at,
                        "updated_at": ev.updated_at,
                    }
                )

            # Save ratings
            for rating in matrix.ratings:
                rating_id = f"{rating.matrix_id}_{rating.hypothesis_id}_{rating.evidence_id}"
                await self._db.execute(
                    """
                    INSERT INTO arkham_ach.ratings
                    (id, matrix_id, hypothesis_id, evidence_id, rating, notes,
                     rated_by, created_at, updated_at)
                    VALUES (:id, :matrix_id, :hypothesis_id, :evidence_id, :rating, :notes,
                            :rated_by, :created_at, :updated_at)
                    ON CONFLICT (matrix_id, hypothesis_id, evidence_id) DO UPDATE SET
                        rating = EXCLUDED.rating,
                        notes = EXCLUDED.notes,
                        updated_at = NOW()
                    """,
                    {
                        "id": rating_id,
                        "matrix_id": rating.matrix_id,
                        "hypothesis_id": rating.hypothesis_id,
                        "evidence_id": rating.evidence_id,
                        "rating": rating.rating.value,
                        "notes": rating.reasoning,
                        "rated_by": rating.author,
                        "created_at": rating.created_at,
                        "updated_at": rating.updated_at,
                    }
                )

            logger.debug(f"Saved matrix {matrix.id} to database")
            return matrix

        except Exception as e:
            logger.error(f"Failed to save matrix {matrix.id}: {e}")
            raise

    async def _load_matrix(self, matrix_id: str) -> Optional[ACHMatrix]:
        """
        Load an ACH matrix and all its components from the database.

        Args:
            matrix_id: The ID of the matrix to load

        Returns:
            The loaded ACHMatrix instance, or None if not found
        """
        if not self._db:
            return None

        try:
            # Load matrix record
            row = await self._db.fetch_one(
                "SELECT * FROM arkham_ach.matrices WHERE id = :id",
                {"id": matrix_id}
            )

            if not row:
                return None

            # Parse metadata
            metadata = _parse_json_field(row["metadata"], {})

            # Load hypotheses
            hyp_rows = await self._db.fetch_all(
                """
                SELECT * FROM arkham_ach.hypotheses
                WHERE matrix_id = :matrix_id
                ORDER BY column_index
                """,
                {"matrix_id": matrix_id}
            )

            hypotheses = [
                Hypothesis(
                    id=hr["id"],
                    matrix_id=hr["matrix_id"],
                    title=hr["title"],
                    description=hr["description"] or "",
                    column_index=hr["column_index"],
                    is_lead=hr["is_lead"],
                    notes=hr["notes"] or "",
                    author=hr["author"],
                    created_at=hr["created_at"],
                    updated_at=hr["updated_at"],
                )
                for hr in hyp_rows
            ]

            # Load evidence
            ev_rows = await self._db.fetch_all(
                """
                SELECT * FROM arkham_ach.evidence
                WHERE matrix_id = :matrix_id
                ORDER BY row_index
                """,
                {"matrix_id": matrix_id}
            )

            evidence = [
                Evidence(
                    id=er["id"],
                    matrix_id=er["matrix_id"],
                    description=er["description"],
                    source=er["source"] or "",
                    evidence_type=EvidenceType(er["evidence_type"]) if er["evidence_type"] else EvidenceType.FACT,
                    credibility=er["credibility"],
                    relevance=er["relevance"],
                    row_index=er["row_index"],
                    notes=er["notes"] or "",
                    author=er["author"],
                    document_ids=_parse_json_field(er["document_ids"], []),
                    source_document_id=er["source_document_id"],
                    source_chunk_id=er["source_chunk_id"],
                    source_page_number=er["source_page_number"],
                    source_quote=er["source_quote"],
                    extraction_method=er["extraction_method"] or "manual",
                    similarity_score=er["similarity_score"],
                    created_at=er["created_at"],
                    updated_at=er["updated_at"],
                )
                for er in ev_rows
            ]

            # Load ratings
            rating_rows = await self._db.fetch_all(
                """
                SELECT * FROM arkham_ach.ratings
                WHERE matrix_id = :matrix_id
                """,
                {"matrix_id": matrix_id}
            )

            ratings = [
                Rating(
                    matrix_id=rr["matrix_id"],
                    hypothesis_id=rr["hypothesis_id"],
                    evidence_id=rr["evidence_id"],
                    rating=ConsistencyRating(rr["rating"]),
                    reasoning=rr["notes"] or "",
                    author=rr["rated_by"],
                    created_at=rr["created_at"],
                    updated_at=rr["updated_at"],
                )
                for rr in rating_rows
            ]

            # Construct the matrix
            matrix = ACHMatrix(
                id=row["id"],
                title=row["title"],
                description=row["description"] or "",
                status=MatrixStatus(row["status"]) if row["status"] else MatrixStatus.DRAFT,
                hypotheses=hypotheses,
                evidence=evidence,
                ratings=ratings,
                scores=[],  # Scores are calculated, not stored
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                created_by=row["created_by"],
                project_id=row["project_id"],
                tags=metadata.get("tags", []),
                notes=metadata.get("notes", ""),
                linked_document_ids=metadata.get("linked_document_ids", []),
            )

            logger.debug(f"Loaded matrix {matrix_id} from database")
            return matrix

        except Exception as e:
            logger.error(f"Failed to load matrix {matrix_id}: {e}")
            return None

    async def _load_all_matrices(
        self,
        project_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[ACHMatrix]:
        """
        Load all ACH matrices from the database with optional filtering.

        Args:
            project_id: Optional project ID to filter by
            status: Optional status to filter by
            limit: Maximum number of matrices to return
            offset: Number of matrices to skip

        Returns:
            List of ACHMatrix instances
        """
        if not self._db:
            return []

        try:
            # Build query with optional filters
            query = "SELECT id FROM arkham_ach.matrices WHERE 1=1"
            params: Dict[str, Any] = {"limit": limit, "offset": offset}

            if project_id:
                query += " AND project_id = :project_id"
                params["project_id"] = project_id

            if status:
                query += " AND status = :status"
                params["status"] = status

            query += " ORDER BY updated_at DESC LIMIT :limit OFFSET :offset"

            # Get matrix IDs
            rows = await self._db.fetch_all(query, params)

            # Load each matrix fully
            matrices = []
            for row in rows:
                matrix = await self._load_matrix(row["id"])
                if matrix:
                    matrices.append(matrix)

            logger.debug(f"Loaded {len(matrices)} matrices from database")
            return matrices

        except Exception as e:
            logger.error(f"Failed to load matrices: {e}")
            return []

    async def _delete_matrix_from_db(self, matrix_id: str) -> bool:
        """
        Delete an ACH matrix and all its components from the database.

        Due to CASCADE constraints, deleting the matrix will automatically
        delete associated hypotheses, evidence, and ratings.

        Args:
            matrix_id: The ID of the matrix to delete

        Returns:
            True if deleted successfully, False otherwise
        """
        if not self._db:
            return False

        try:
            await self._db.execute(
                "DELETE FROM arkham_ach.matrices WHERE id = :id",
                {"id": matrix_id}
            )
            logger.info(f"Deleted matrix {matrix_id} from database")
            return True

        except Exception as e:
            logger.error(f"Failed to delete matrix {matrix_id}: {e}")
            return False

    async def _delete_hypothesis_from_db(self, hypothesis_id: str) -> bool:
        """
        Delete a hypothesis from the database.

        Also deletes associated ratings for this hypothesis.

        Args:
            hypothesis_id: The ID of the hypothesis to delete

        Returns:
            True if deleted successfully, False otherwise
        """
        if not self._db:
            return False

        try:
            # Delete ratings for this hypothesis first
            await self._db.execute(
                "DELETE FROM arkham_ach.ratings WHERE hypothesis_id = :id",
                {"id": hypothesis_id}
            )
            # Delete the hypothesis
            await self._db.execute(
                "DELETE FROM arkham_ach.hypotheses WHERE id = :id",
                {"id": hypothesis_id}
            )
            logger.debug(f"Deleted hypothesis {hypothesis_id} from database")
            return True

        except Exception as e:
            logger.error(f"Failed to delete hypothesis {hypothesis_id}: {e}")
            return False

    async def _delete_evidence_from_db(self, evidence_id: str) -> bool:
        """
        Delete evidence from the database.

        Also deletes associated ratings for this evidence.

        Args:
            evidence_id: The ID of the evidence to delete

        Returns:
            True if deleted successfully, False otherwise
        """
        if not self._db:
            return False

        try:
            # Delete ratings for this evidence first
            await self._db.execute(
                "DELETE FROM arkham_ach.ratings WHERE evidence_id = :id",
                {"id": evidence_id}
            )
            # Delete the evidence
            await self._db.execute(
                "DELETE FROM arkham_ach.evidence WHERE id = :id",
                {"id": evidence_id}
            )
            logger.debug(f"Deleted evidence {evidence_id} from database")
            return True

        except Exception as e:
            logger.error(f"Failed to delete evidence {evidence_id}: {e}")
            return False

    async def _get_matrix_count(self, project_id: Optional[str] = None) -> int:
        """
        Get the count of matrices in the database.

        Args:
            project_id: Optional project ID to filter by

        Returns:
            Number of matrices
        """
        if not self._db:
            return 0

        try:
            if project_id:
                row = await self._db.fetch_one(
                    "SELECT COUNT(*) as count FROM arkham_ach.matrices WHERE project_id = :project_id",
                    {"project_id": project_id}
                )
            else:
                row = await self._db.fetch_one(
                    "SELECT COUNT(*) as count FROM arkham_ach.matrices",
                    {}
                )

            return row["count"] if row else 0

        except Exception as e:
            logger.error(f"Failed to get matrix count: {e}")
            return 0

    # --- Individual Item Persistence Methods ---
    # These methods are used by MatrixManager for real-time persistence
    # when individual hypotheses, evidence, or ratings are added/updated/deleted.

    async def _save_hypothesis(self, hypothesis: Hypothesis) -> Hypothesis:
        """Save a single hypothesis to the database."""
        if not self._db:
            logger.warning("Database not available - hypothesis not persisted")
            return hypothesis

        try:
            await self._db.execute(
                """
                INSERT INTO arkham_ach.hypotheses
                (id, matrix_id, title, description, column_index, is_lead, notes, author,
                 created_at, updated_at)
                VALUES (:id, :matrix_id, :title, :description, :column_index, :is_lead, :notes, :author,
                        :created_at, :updated_at)
                ON CONFLICT (id) DO UPDATE SET
                    title = EXCLUDED.title,
                    description = EXCLUDED.description,
                    column_index = EXCLUDED.column_index,
                    is_lead = EXCLUDED.is_lead,
                    notes = EXCLUDED.notes,
                    author = EXCLUDED.author,
                    updated_at = NOW()
                """,
                {
                    "id": hypothesis.id,
                    "matrix_id": hypothesis.matrix_id,
                    "title": hypothesis.title,
                    "description": hypothesis.description or "",
                    "column_index": hypothesis.column_index,
                    "is_lead": hypothesis.is_lead,
                    "notes": hypothesis.notes or "",
                    "author": hypothesis.author,
                    "created_at": hypothesis.created_at,
                    "updated_at": hypothesis.updated_at,
                }
            )
            logger.debug(f"Saved hypothesis {hypothesis.id} for matrix {hypothesis.matrix_id}")
            return hypothesis
        except Exception as e:
            logger.error(f"Failed to save hypothesis {hypothesis.id}: {e}")
            raise

    async def _load_hypotheses(self, matrix_id: str) -> List[Hypothesis]:
        """Load all hypotheses for a matrix from the database."""
        if not self._db:
            return []

        try:
            rows = await self._db.fetch_all(
                """
                SELECT * FROM arkham_ach.hypotheses
                WHERE matrix_id = :matrix_id
                ORDER BY column_index
                """,
                {"matrix_id": matrix_id}
            )

            return [
                Hypothesis(
                    id=row["id"],
                    matrix_id=row["matrix_id"],
                    title=row["title"],
                    description=row["description"] or "",
                    column_index=row["column_index"],
                    is_lead=row["is_lead"],
                    notes=row["notes"] or "",
                    author=row["author"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )
                for row in rows
            ]
        except Exception as e:
            logger.error(f"Failed to load hypotheses for matrix {matrix_id}: {e}")
            return []

    async def _delete_hypothesis(self, hypothesis_id: str) -> bool:
        """Delete a hypothesis from the database (also deletes associated ratings)."""
        if not self._db:
            return False

        try:
            # Delete ratings for this hypothesis first
            await self._db.execute(
                "DELETE FROM arkham_ach.ratings WHERE hypothesis_id = :id",
                {"id": hypothesis_id}
            )
            # Delete the hypothesis
            await self._db.execute(
                "DELETE FROM arkham_ach.hypotheses WHERE id = :id",
                {"id": hypothesis_id}
            )
            logger.debug(f"Deleted hypothesis {hypothesis_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete hypothesis {hypothesis_id}: {e}")
            return False

    async def _update_hypothesis_indexes(self, matrix_id: str, hypotheses: List[Hypothesis]) -> None:
        """Update column indexes for all hypotheses in a matrix."""
        if not self._db:
            return

        try:
            for h in hypotheses:
                await self._db.execute(
                    """
                    UPDATE arkham_ach.hypotheses
                    SET column_index = :column_index, updated_at = NOW()
                    WHERE id = :id
                    """,
                    {"id": h.id, "column_index": h.column_index}
                )
        except Exception as e:
            logger.error(f"Failed to update hypothesis indexes for matrix {matrix_id}: {e}")

    async def _save_evidence(self, evidence: Evidence) -> Evidence:
        """Save a single evidence item to the database."""
        if not self._db:
            logger.warning("Database not available - evidence not persisted")
            return evidence

        try:
            await self._db.execute(
                """
                INSERT INTO arkham_ach.evidence
                (id, matrix_id, description, source, evidence_type, credibility, relevance,
                 row_index, notes, author, document_ids, source_document_id, source_chunk_id,
                 source_page_number, source_quote, extraction_method, similarity_score,
                 created_at, updated_at)
                VALUES (:id, :matrix_id, :description, :source, :evidence_type, :credibility, :relevance,
                        :row_index, :notes, :author, :document_ids, :source_document_id, :source_chunk_id,
                        :source_page_number, :source_quote, :extraction_method, :similarity_score,
                        :created_at, :updated_at)
                ON CONFLICT (id) DO UPDATE SET
                    description = EXCLUDED.description,
                    source = EXCLUDED.source,
                    evidence_type = EXCLUDED.evidence_type,
                    credibility = EXCLUDED.credibility,
                    relevance = EXCLUDED.relevance,
                    row_index = EXCLUDED.row_index,
                    notes = EXCLUDED.notes,
                    author = EXCLUDED.author,
                    document_ids = EXCLUDED.document_ids,
                    source_document_id = EXCLUDED.source_document_id,
                    source_chunk_id = EXCLUDED.source_chunk_id,
                    source_page_number = EXCLUDED.source_page_number,
                    source_quote = EXCLUDED.source_quote,
                    extraction_method = EXCLUDED.extraction_method,
                    similarity_score = EXCLUDED.similarity_score,
                    updated_at = NOW()
                """,
                {
                    "id": evidence.id,
                    "matrix_id": evidence.matrix_id,
                    "description": evidence.description,
                    "source": evidence.source or "",
                    "evidence_type": evidence.evidence_type.value,
                    "credibility": evidence.credibility,
                    "relevance": evidence.relevance,
                    "row_index": evidence.row_index,
                    "notes": evidence.notes or "",
                    "author": evidence.author,
                    "document_ids": json.dumps(evidence.document_ids),
                    "source_document_id": evidence.source_document_id,
                    "source_chunk_id": evidence.source_chunk_id,
                    "source_page_number": evidence.source_page_number,
                    "source_quote": evidence.source_quote,
                    "extraction_method": evidence.extraction_method,
                    "similarity_score": evidence.similarity_score,
                    "created_at": evidence.created_at,
                    "updated_at": evidence.updated_at,
                }
            )
            logger.debug(f"Saved evidence {evidence.id} for matrix {evidence.matrix_id}")
            return evidence
        except Exception as e:
            logger.error(f"Failed to save evidence {evidence.id}: {e}")
            raise

    async def _load_evidence(self, matrix_id: str) -> List[Evidence]:
        """Load all evidence for a matrix from the database."""
        if not self._db:
            return []

        try:
            rows = await self._db.fetch_all(
                """
                SELECT * FROM arkham_ach.evidence
                WHERE matrix_id = :matrix_id
                ORDER BY row_index
                """,
                {"matrix_id": matrix_id}
            )

            return [
                Evidence(
                    id=row["id"],
                    matrix_id=row["matrix_id"],
                    description=row["description"],
                    source=row["source"] or "",
                    evidence_type=EvidenceType(row["evidence_type"]) if row["evidence_type"] else EvidenceType.FACT,
                    credibility=row["credibility"],
                    relevance=row["relevance"],
                    row_index=row["row_index"],
                    notes=row["notes"] or "",
                    author=row["author"],
                    document_ids=_parse_json_field(row["document_ids"]),
                    source_document_id=row["source_document_id"],
                    source_chunk_id=row["source_chunk_id"],
                    source_page_number=row["source_page_number"],
                    source_quote=row["source_quote"],
                    extraction_method=row["extraction_method"] or "manual",
                    similarity_score=row["similarity_score"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )
                for row in rows
            ]
        except Exception as e:
            logger.error(f"Failed to load evidence for matrix {matrix_id}: {e}")
            return []

    async def _delete_evidence(self, evidence_id: str) -> bool:
        """Delete evidence from the database (also deletes associated ratings)."""
        if not self._db:
            return False

        try:
            # Delete ratings for this evidence first
            await self._db.execute(
                "DELETE FROM arkham_ach.ratings WHERE evidence_id = :id",
                {"id": evidence_id}
            )
            # Delete the evidence
            await self._db.execute(
                "DELETE FROM arkham_ach.evidence WHERE id = :id",
                {"id": evidence_id}
            )
            logger.debug(f"Deleted evidence {evidence_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete evidence {evidence_id}: {e}")
            return False

    async def _update_evidence_indexes(self, matrix_id: str, evidence_list: List[Evidence]) -> None:
        """Update row indexes for all evidence in a matrix."""
        if not self._db:
            return

        try:
            for e in evidence_list:
                await self._db.execute(
                    """
                    UPDATE arkham_ach.evidence
                    SET row_index = :row_index, updated_at = NOW()
                    WHERE id = :id
                    """,
                    {"id": e.id, "row_index": e.row_index}
                )
        except Exception as e:
            logger.error(f"Failed to update evidence indexes for matrix {matrix_id}: {e}")

    async def _save_rating(self, rating: Rating) -> Rating:
        """Save a single rating to the database."""
        if not self._db:
            logger.warning("Database not available - rating not persisted")
            return rating

        try:
            rating_id = str(uuid.uuid4())

            await self._db.execute(
                """
                INSERT INTO arkham_ach.ratings
                (id, matrix_id, hypothesis_id, evidence_id, rating, notes, rated_by, created_at, updated_at)
                VALUES (:id, :matrix_id, :hypothesis_id, :evidence_id, :rating, :notes, :rated_by, :created_at, :updated_at)
                ON CONFLICT (matrix_id, hypothesis_id, evidence_id) DO UPDATE SET
                    rating = EXCLUDED.rating,
                    notes = EXCLUDED.notes,
                    rated_by = EXCLUDED.rated_by,
                    updated_at = NOW()
                """,
                {
                    "id": rating_id,
                    "matrix_id": rating.matrix_id,
                    "hypothesis_id": rating.hypothesis_id,
                    "evidence_id": rating.evidence_id,
                    "rating": rating.rating.value,
                    "notes": rating.reasoning or "",
                    "rated_by": rating.author,
                    "created_at": rating.created_at,
                    "updated_at": rating.updated_at,
                }
            )
            logger.debug(f"Saved rating for hypothesis {rating.hypothesis_id}, evidence {rating.evidence_id}")
            return rating
        except Exception as e:
            logger.error(f"Failed to save rating: {e}")
            raise

    async def _upsert_rating(self, rating: Rating) -> Rating:
        """Insert or update a rating in the database."""
        return await self._save_rating(rating)

    async def _load_ratings(self, matrix_id: str) -> List[Rating]:
        """Load all ratings for a matrix from the database."""
        if not self._db:
            return []

        try:
            rows = await self._db.fetch_all(
                """
                SELECT * FROM arkham_ach.ratings
                WHERE matrix_id = :matrix_id
                """,
                {"matrix_id": matrix_id}
            )

            ratings = []
            for row in rows:
                try:
                    rating_value = ConsistencyRating(row["rating"])
                except (ValueError, KeyError):
                    rating_value = ConsistencyRating.NEUTRAL

                ratings.append(Rating(
                    matrix_id=row["matrix_id"],
                    evidence_id=row["evidence_id"],
                    hypothesis_id=row["hypothesis_id"],
                    rating=rating_value,
                    reasoning=row["notes"] or "",
                    confidence=1.0,
                    author=row["rated_by"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                ))

            return ratings
        except Exception as e:
            logger.error(f"Failed to load ratings for matrix {matrix_id}: {e}")
            return []

    async def _delete_rating(self, matrix_id: str, hypothesis_id: str, evidence_id: str) -> bool:
        """Delete a specific rating from the database."""
        if not self._db:
            return False

        try:
            await self._db.execute(
                """
                DELETE FROM arkham_ach.ratings
                WHERE matrix_id = :matrix_id AND hypothesis_id = :hypothesis_id AND evidence_id = :evidence_id
                """,
                {"matrix_id": matrix_id, "hypothesis_id": hypothesis_id, "evidence_id": evidence_id}
            )
            logger.debug(f"Deleted rating for hypothesis {hypothesis_id}, evidence {evidence_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete rating: {e}")
            return False

    async def _delete_ratings_for_hypothesis(self, hypothesis_id: str) -> bool:
        """Delete all ratings for a hypothesis."""
        if not self._db:
            return False

        try:
            await self._db.execute(
                "DELETE FROM arkham_ach.ratings WHERE hypothesis_id = :hypothesis_id",
                {"hypothesis_id": hypothesis_id}
            )
            logger.debug(f"Deleted all ratings for hypothesis {hypothesis_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete ratings for hypothesis {hypothesis_id}: {e}")
            return False

    async def _delete_ratings_for_evidence(self, evidence_id: str) -> bool:
        """Delete all ratings for an evidence item."""
        if not self._db:
            return False

        try:
            await self._db.execute(
                "DELETE FROM arkham_ach.ratings WHERE evidence_id = :evidence_id",
                {"evidence_id": evidence_id}
            )
            logger.debug(f"Deleted all ratings for evidence {evidence_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete ratings for evidence {evidence_id}: {e}")
            return False
