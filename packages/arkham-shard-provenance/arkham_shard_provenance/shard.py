"""Provenance Shard - Evidence Chain Tracking and Data Lineage."""

import logging
from typing import Any, Dict, List, Optional

from arkham_frame.shard_interface import ArkhamShard

from .api import init_api, router

logger = logging.getLogger(__name__)


class ProvenanceShard(ArkhamShard):
    """
    Provenance Shard for ArkhamFrame.

    Tracks evidence chains and data lineage throughout the system,
    providing critical audit trail capabilities for legal and journalism
    use cases.

    Handles:
    - Evidence chain creation and management
    - Artifact linkage and tracking
    - Data lineage visualization
    - Comprehensive audit trail
    - Chain verification and integrity checking
    - Export of chains and audit reports

    Events Published:
        - provenance.chain.created
        - provenance.chain.updated
        - provenance.chain.deleted
        - provenance.link.added
        - provenance.link.removed
        - provenance.link.verified
        - provenance.audit.generated
        - provenance.export.completed

    Events Subscribed:
        - *.*.created (wildcard - all creation events)
        - *.*.completed (wildcard - all completion events)
        - document.processed
    """

    name = "provenance"
    version = "0.1.0"
    description = "Track evidence chains and data lineage for legal and journalism analysis"

    def __init__(self):
        super().__init__()  # Auto-loads manifest from shard.yaml
        self._frame = None
        self._db = None
        self._event_bus = None
        self._storage = None

        # Component managers (to be implemented)
        self._chain_manager = None
        self._lineage_tracker = None
        self._audit_logger = None

    async def initialize(self, frame) -> None:
        """
        Initialize the Provenance shard with Frame services.

        Args:
            frame: The ArkhamFrame instance
        """
        self._frame = frame

        logger.info("Initializing Provenance Shard...")

        # Get required Frame services
        self._db = frame.get_service("database")
        self._event_bus = frame.get_service("events")

        if not self._db:
            raise RuntimeError(f"{self.name}: Database service required")

        if not self._event_bus:
            raise RuntimeError(f"{self.name}: Event bus service required")

        # Get optional services
        self._storage = frame.get_service("storage")
        if not self._storage:
            logger.warning("Storage service not available - audit export limited")

        # Create database schema
        await self._create_schema()

        # Initialize component managers (stubs for now)
        # TODO: Implement ChainManager, LineageTracker, AuditLogger
        # self._chain_manager = ChainManager(self._db, self._event_bus)
        # self._lineage_tracker = LineageTracker(self._db)
        # self._audit_logger = AuditLogger(self._db)

        # Initialize API with our instances
        init_api(
            chain_manager=None,  # TODO: Pass actual manager
            lineage_tracker=None,  # TODO: Pass actual tracker
            audit_logger=None,  # TODO: Pass actual logger
            event_bus=self._event_bus,
            storage=self._storage,
        )

        # Subscribe to events for automatic tracking
        if self._event_bus:
            # Subscribe to all creation events
            await self._event_bus.subscribe("*.*.created", self._on_entity_created)
            # Subscribe to all completion events
            await self._event_bus.subscribe("*.*.completed", self._on_process_completed)
            # Subscribe to document processing
            await self._event_bus.subscribe("document.processed", self._on_document_processed)
            logger.info("Subscribed to provenance tracking events")

        # Register self in app state for API access
        if hasattr(frame, "app") and frame.app:
            frame.app.state.provenance_shard = self

        logger.info("Provenance Shard initialized")

    async def shutdown(self) -> None:
        """Clean up shard resources."""
        logger.info("Shutting down Provenance Shard...")

        # Unsubscribe from events
        if self._event_bus:
            await self._event_bus.unsubscribe("*.*.created", self._on_entity_created)
            await self._event_bus.unsubscribe("*.*.completed", self._on_process_completed)
            await self._event_bus.unsubscribe("document.processed", self._on_document_processed)
            logger.info("Unsubscribed from provenance tracking events")

        # Clear managers
        self._chain_manager = None
        self._lineage_tracker = None
        self._audit_logger = None

        logger.info("Provenance Shard shutdown complete")

    def get_routes(self):
        """Return FastAPI router for this shard."""
        return router

    async def _create_schema(self) -> None:
        """Create database schema for provenance tracking."""
        if not self._db:
            return

        logger.info("Creating provenance schema...")

        # Records table - tracks provenance records
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS arkham_provenance_records (
                id TEXT PRIMARY KEY,
                entity_type TEXT NOT NULL,
                entity_id TEXT NOT NULL,
                source_type TEXT,
                source_id TEXT,
                source_url TEXT,
                imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                imported_by TEXT,
                metadata JSONB DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Transformations table - tracks processing history
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS arkham_provenance_transformations (
                id TEXT PRIMARY KEY,
                record_id TEXT NOT NULL REFERENCES arkham_provenance_records(id) ON DELETE CASCADE,
                transformation_type TEXT NOT NULL,
                input_hash TEXT,
                output_hash TEXT,
                transformed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                transformer TEXT,
                parameters JSONB DEFAULT '{}',
                metadata JSONB DEFAULT '{}'
            )
        """)

        # Audit table - tracks access and modifications
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS arkham_provenance_audit (
                id TEXT PRIMARY KEY,
                record_id TEXT NOT NULL REFERENCES arkham_provenance_records(id) ON DELETE CASCADE,
                action TEXT NOT NULL,
                actor TEXT,
                details JSONB DEFAULT '{}',
                occurred_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create indexes
        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_provenance_entity_type
            ON arkham_provenance_records(entity_type)
        """)

        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_provenance_entity_id
            ON arkham_provenance_records(entity_id)
        """)

        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_provenance_source_type
            ON arkham_provenance_records(source_type)
        """)

        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_transformations_record
            ON arkham_provenance_transformations(record_id)
        """)

        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_record
            ON arkham_provenance_audit(record_id)
        """)

        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_occurred
            ON arkham_provenance_audit(occurred_at DESC)
        """)

        logger.info("Provenance database schema created")

    def _parse_jsonb(self, value: Any, default: Any = None) -> Any:
        """Parse a JSONB field that may be str, dict, list, or None.

        PostgreSQL JSONB with SQLAlchemy may return:
        - Already parsed Python objects (dict, list, bool, int, float)
        - String that IS the value (when JSON string was stored)
        - String that needs parsing (raw JSON)
        """
        if value is None:
            return default
        if isinstance(value, (dict, list, bool, int, float)):
            return value
        if isinstance(value, str):
            if not value or value.strip() == "":
                return default
            # Try to parse as JSON first (for complex values)
            try:
                import json
                return json.loads(value)
            except json.JSONDecodeError:
                # If it's not valid JSON, it's already the string value
                return value
        return default

    def _row_to_record(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """Convert database row to record object."""
        import json
        metadata = self._parse_jsonb(row.get("metadata"), {})

        return {
            "id": row["id"],
            "entity_type": row["entity_type"],
            "entity_id": row["entity_id"],
            "source_type": row.get("source_type"),
            "source_id": row.get("source_id"),
            "source_url": row.get("source_url"),
            "imported_at": row.get("imported_at").isoformat() if row.get("imported_at") else None,
            "imported_by": row.get("imported_by"),
            "metadata": metadata,
            "created_at": row.get("created_at").isoformat() if row.get("created_at") else None,
        }

    def _row_to_transformation(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """Convert database row to transformation object."""
        parameters = self._parse_jsonb(row.get("parameters"), {})
        metadata = self._parse_jsonb(row.get("metadata"), {})

        return {
            "id": row["id"],
            "record_id": row["record_id"],
            "transformation_type": row["transformation_type"],
            "input_hash": row.get("input_hash"),
            "output_hash": row.get("output_hash"),
            "transformed_at": row.get("transformed_at").isoformat() if row.get("transformed_at") else None,
            "transformer": row.get("transformer"),
            "parameters": parameters,
            "metadata": metadata,
        }

    def _row_to_audit(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """Convert database row to audit object."""
        details = self._parse_jsonb(row.get("details"), {})

        return {
            "id": row["id"],
            "record_id": row["record_id"],
            "action": row["action"],
            "actor": row.get("actor"),
            "details": details,
            "occurred_at": row.get("occurred_at").isoformat() if row.get("occurred_at") else None,
        }

    # --- Public Service Methods ---

    async def list_records(
        self,
        entity_type: Optional[str] = None,
        limit: int = 20,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        List provenance records with optional filtering.

        Args:
            entity_type: Filter by entity type
            limit: Maximum records to return
            offset: Number of records to skip

        Returns:
            List of provenance records
        """
        if not self._db:
            raise RuntimeError("Shard not initialized")

        query = "SELECT * FROM arkham_provenance_records"
        params: Dict[str, Any] = {}

        if entity_type:
            query += " WHERE entity_type = :entity_type"
            params["entity_type"] = entity_type

        query += " ORDER BY created_at DESC LIMIT :limit OFFSET :offset"
        params["limit"] = limit
        params["offset"] = offset

        rows = await self._db.fetch_all(query, params)
        return [self._row_to_record(row) for row in rows]

    async def get_record(self, id: str) -> Optional[Dict[str, Any]]:
        """
        Get a provenance record by ID.

        Args:
            id: Record ID

        Returns:
            Record object or None
        """
        if not self._db:
            raise RuntimeError("Shard not initialized")

        row = await self._db.fetch_one(
            "SELECT * FROM arkham_provenance_records WHERE id = :id",
            {"id": id}
        )

        if row:
            return self._row_to_record(row)
        return None

    async def get_record_for_entity(
        self,
        entity_type: str,
        entity_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get provenance record for a specific entity.

        Args:
            entity_type: Type of entity
            entity_id: Entity ID

        Returns:
            Record object or None
        """
        if not self._db:
            raise RuntimeError("Shard not initialized")

        row = await self._db.fetch_one(
            """
            SELECT * FROM arkham_provenance_records
            WHERE entity_type = :entity_type AND entity_id = :entity_id
            """,
            {"entity_type": entity_type, "entity_id": entity_id}
        )

        if row:
            return self._row_to_record(row)
        return None

    async def get_transformations(self, record_id: str) -> List[Dict[str, Any]]:
        """
        Get transformation history for a record.

        Args:
            record_id: Record ID

        Returns:
            List of transformations
        """
        if not self._db:
            raise RuntimeError("Shard not initialized")

        rows = await self._db.fetch_all(
            """
            SELECT * FROM arkham_provenance_transformations
            WHERE record_id = :record_id
            ORDER BY transformed_at DESC
            """,
            {"record_id": record_id}
        )

        return [self._row_to_transformation(row) for row in rows]

    async def get_audit_trail(self, record_id: str) -> List[Dict[str, Any]]:
        """
        Get audit trail for a record.

        Args:
            record_id: Record ID

        Returns:
            List of audit records
        """
        if not self._db:
            raise RuntimeError("Shard not initialized")

        rows = await self._db.fetch_all(
            """
            SELECT * FROM arkham_provenance_audit
            WHERE record_id = :record_id
            ORDER BY occurred_at DESC
            """,
            {"record_id": record_id}
        )

        return [self._row_to_audit(row) for row in rows]

    async def add_transformation(
        self,
        record_id: str,
        transformation_type: str,
        transformer: Optional[str] = None,
        input_hash: Optional[str] = None,
        output_hash: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Add a transformation to a record.

        Args:
            record_id: Record ID
            transformation_type: Type of transformation
            transformer: Who/what performed the transformation
            input_hash: Hash of input data
            output_hash: Hash of output data
            parameters: Transformation parameters

        Returns:
            Created transformation object
        """
        if not self._db:
            raise RuntimeError("Shard not initialized")

        import uuid
        import json
        from datetime import datetime

        transformation_id = str(uuid.uuid4())

        await self._db.execute(
            """
            INSERT INTO arkham_provenance_transformations
            (id, record_id, transformation_type, input_hash, output_hash, transformer, parameters)
            VALUES (:id, :record_id, :transformation_type, :input_hash, :output_hash, :transformer, :parameters)
            """,
            {
                "id": transformation_id,
                "record_id": record_id,
                "transformation_type": transformation_type,
                "input_hash": input_hash,
                "output_hash": output_hash,
                "transformer": transformer,
                "parameters": json.dumps(parameters or {}),
            }
        )

        # Log the transformation
        await self.log_access(record_id, transformer or "system", "transformation_added", {
            "transformation_id": transformation_id,
            "transformation_type": transformation_type
        })

        # Emit event
        if self._event_bus:
            await self._event_bus.publish("provenance.transformation.added", {
                "record_id": record_id,
                "transformation_id": transformation_id,
                "transformation_type": transformation_type
            })

        return {
            "id": transformation_id,
            "record_id": record_id,
            "transformation_type": transformation_type,
            "transformer": transformer,
            "transformed_at": datetime.utcnow().isoformat()
        }

    async def log_access(
        self,
        record_id: str,
        actor: str,
        action: str,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log access to a provenance record.

        Args:
            record_id: Record ID
            actor: Who performed the action
            action: Action performed
            details: Additional details
        """
        if not self._db:
            raise RuntimeError("Shard not initialized")

        import uuid
        import json

        audit_id = str(uuid.uuid4())

        await self._db.execute(
            """
            INSERT INTO arkham_provenance_audit
            (id, record_id, action, actor, details)
            VALUES (:id, :record_id, :action, :actor, :details)
            """,
            {
                "id": audit_id,
                "record_id": record_id,
                "action": action,
                "actor": actor,
                "details": json.dumps(details or {}),
            }
        )

    # --- Event Handlers ---

    async def _on_entity_created(self, event: Dict[str, Any]) -> None:
        """
        Handle entity creation events from any shard.

        Args:
            event: Event payload with entity details
        """
        # TODO: Implement automatic artifact tracking
        logger.debug(f"Tracking entity creation: {event}")
        pass

    async def _on_process_completed(self, event: Dict[str, Any]) -> None:
        """
        Handle process completion events from any shard.

        Args:
            event: Event payload with process details
        """
        # TODO: Implement automatic link creation
        logger.debug(f"Tracking process completion: {event}")
        pass

    async def _on_document_processed(self, event: Dict[str, Any]) -> None:
        """
        Handle document processing events.

        Args:
            event: Event payload with document details
        """
        # TODO: Implement document processing chain tracking
        logger.debug(f"Tracking document processing: {event}")
        pass

    # --- Public API for other shards ---

    async def create_chain(
        self,
        title: str,
        description: str = "",
        created_by: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Public method for other shards to create an evidence chain.

        Args:
            title: Chain title
            description: Chain description
            created_by: Creator identifier
            project_id: Associated project ID

        Returns:
            Chain object with ID and metadata
        """
        # TODO: Implement chain creation
        logger.info(f"Creating evidence chain: {title}")
        return {"id": "stub_chain_id", "title": title}

    async def add_link(
        self,
        chain_id: str,
        source_id: str,
        target_id: str,
        link_type: str,
        confidence: float = 1.0,
    ) -> Dict[str, Any]:
        """
        Public method to add a link to a chain.

        Args:
            chain_id: Chain ID
            source_id: Source artifact ID
            target_id: Target artifact ID
            link_type: Type of relationship
            confidence: Confidence level (0.0 to 1.0)

        Returns:
            Link object with ID and metadata
        """
        # TODO: Implement link addition
        logger.info(f"Adding link to chain {chain_id}: {source_id} -> {target_id}")
        return {"id": "stub_link_id", "chain_id": chain_id}

    async def get_lineage(
        self,
        artifact_id: str,
        direction: str = "both",
    ) -> Dict[str, Any]:
        """
        Public method to get artifact lineage.

        Args:
            artifact_id: Artifact ID to trace
            direction: Direction to trace (upstream, downstream, both)

        Returns:
            Lineage graph with nodes and edges
        """
        # TODO: Implement lineage retrieval
        logger.info(f"Getting lineage for artifact: {artifact_id}")
        return {"artifact_id": artifact_id, "nodes": [], "edges": []}

    async def verify_chain(self, chain_id: str) -> Dict[str, Any]:
        """
        Public method to verify chain integrity.

        Args:
            chain_id: Chain ID to verify

        Returns:
            Verification result with status and details
        """
        # TODO: Implement chain verification
        logger.info(f"Verifying chain: {chain_id}")
        return {"chain_id": chain_id, "verified": True, "issues": []}
