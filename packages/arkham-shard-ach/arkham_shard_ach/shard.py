"""ACH Shard - Analysis of Competing Hypotheses."""

import json
import logging
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
    FailureMode,
    FailureModeType,
    PremortemAnalysis,
    PremortemConversionType,
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

        # Create managers
        self.matrix_manager = MatrixManager()
        self.scorer = ACHScorer()
        self.evidence_analyzer = EvidenceAnalyzer()
        self.exporter = MatrixExporter()

        # Get Frame services
        self._db = frame.database
        self._event_bus = frame.get_service("events")
        self._llm_service = frame.get_service("llm")
        self._vectors_service = frame.get_service("vectors")
        self._documents_service = frame.get_service("documents")

        # Create database schema for premortem and scenarios
        await self._create_schema()

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
        """Create database schema for premortem and scenarios."""
        if not self._db:
            logger.warning("Database service not available - persistence disabled")
            return

        try:
            # Create schema
            await self._db.execute("CREATE SCHEMA IF NOT EXISTS arkham_ach")

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
