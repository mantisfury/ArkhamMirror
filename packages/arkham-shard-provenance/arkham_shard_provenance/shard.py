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

        # Initialize API with shard instance (shard implements all managers)
        init_api(
            shard=self,
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

        # Chains table - groups of linked provenance records
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS arkham_provenance_chains (
                id TEXT PRIMARY KEY,
                project_id TEXT,
                title TEXT NOT NULL,
                description TEXT,
                chain_type TEXT DEFAULT 'evidence',
                status TEXT DEFAULT 'active',
                root_artifact_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_by TEXT,
                metadata JSONB DEFAULT '{}'
            )
        """)

        # Artifacts table - tracked items (documents, entities, claims, etc.)
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS arkham_provenance_artifacts (
                id TEXT PRIMARY KEY,
                artifact_type TEXT NOT NULL,
                entity_id TEXT NOT NULL,
                entity_table TEXT NOT NULL,
                title TEXT,
                hash TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata JSONB DEFAULT '{}'
            )
        """)

        # Links table - connections between artifacts in a chain
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS arkham_provenance_links (
                id TEXT PRIMARY KEY,
                chain_id TEXT NOT NULL,
                source_artifact_id TEXT NOT NULL,
                target_artifact_id TEXT NOT NULL,
                link_type TEXT NOT NULL,
                confidence REAL DEFAULT 1.0,
                verified INTEGER DEFAULT 0,
                verified_by TEXT,
                verified_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata JSONB DEFAULT '{}'
            )
        """)

        # Lineage cache - pre-computed paths for fast traversal
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS arkham_provenance_lineage (
                id TEXT PRIMARY KEY,
                artifact_id TEXT NOT NULL,
                ancestor_id TEXT NOT NULL,
                depth INTEGER NOT NULL,
                path TEXT NOT NULL,
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

        # Indexes for chains table
        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_provenance_chains_project
            ON arkham_provenance_chains(project_id)
        """)

        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_provenance_chains_status
            ON arkham_provenance_chains(status)
        """)

        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_provenance_chains_type
            ON arkham_provenance_chains(chain_type)
        """)

        # Indexes for artifacts table
        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_provenance_artifacts_type
            ON arkham_provenance_artifacts(artifact_type)
        """)

        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_provenance_artifacts_entity
            ON arkham_provenance_artifacts(entity_id)
        """)

        await self._db.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_provenance_artifacts_unique_entity
            ON arkham_provenance_artifacts(entity_id, entity_table)
        """)

        # Indexes for links table
        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_provenance_links_chain
            ON arkham_provenance_links(chain_id)
        """)

        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_provenance_links_source
            ON arkham_provenance_links(source_artifact_id)
        """)

        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_provenance_links_target
            ON arkham_provenance_links(target_artifact_id)
        """)

        # Indexes for lineage table
        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_provenance_lineage_artifact
            ON arkham_provenance_lineage(artifact_id)
        """)

        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_provenance_lineage_ancestor
            ON arkham_provenance_lineage(ancestor_id)
        """)

        # ===========================================
        # Multi-tenancy Migration
        # ===========================================
        await self._db.execute("""
            DO $$
            DECLARE
                tables_to_update TEXT[] := ARRAY[
                    'arkham_provenance_records',
                    'arkham_provenance_chains',
                    'arkham_provenance_artifacts',
                    'arkham_provenance_links',
                    'arkham_provenance_lineage',
                    'arkham_provenance_transformations',
                    'arkham_provenance_audit'
                ];
                tbl TEXT;
            BEGIN
                FOREACH tbl IN ARRAY tables_to_update LOOP
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_schema = 'public'
                        AND table_name = tbl
                        AND column_name = 'tenant_id'
                    ) THEN
                        EXECUTE format('ALTER TABLE %I ADD COLUMN tenant_id UUID', tbl);
                    END IF;
                END LOOP;
            END $$;
        """)

        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_provenance_records_tenant
            ON arkham_provenance_records(tenant_id)
        """)

        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_provenance_chains_tenant
            ON arkham_provenance_chains(tenant_id)
        """)

        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_provenance_artifacts_tenant
            ON arkham_provenance_artifacts(tenant_id)
        """)

        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_provenance_links_tenant
            ON arkham_provenance_links(tenant_id)
        """)

        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_provenance_lineage_tenant
            ON arkham_provenance_lineage(tenant_id)
        """)

        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_provenance_transformations_tenant
            ON arkham_provenance_transformations(tenant_id)
        """)

        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_provenance_audit_tenant
            ON arkham_provenance_audit(tenant_id)
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

    def _row_to_artifact(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """Convert database row to artifact object."""
        metadata = self._parse_jsonb(row.get("metadata"), {})

        return {
            "id": row["id"],
            "artifact_type": row["artifact_type"],
            "entity_id": row["entity_id"],
            "entity_table": row["entity_table"],
            "title": row.get("title"),
            "hash": row.get("hash"),
            "created_at": row.get("created_at").isoformat() if row.get("created_at") else None,
            "metadata": metadata,
        }

    def _row_to_chain(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """Convert database row to chain object."""
        metadata = self._parse_jsonb(row.get("metadata"), {})

        return {
            "id": row["id"],
            "project_id": row.get("project_id"),
            "title": row["title"],
            "description": row.get("description"),
            "chain_type": row.get("chain_type", "evidence"),
            "status": row.get("status", "active"),
            "root_artifact_id": row.get("root_artifact_id"),
            "created_at": row.get("created_at").isoformat() if row.get("created_at") else None,
            "updated_at": row.get("updated_at").isoformat() if row.get("updated_at") else None,
            "created_by": row.get("created_by"),
            "link_count": row.get("link_count", 0),
            "metadata": metadata,
        }

    def _row_to_link(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """Convert database row to link object."""
        metadata = self._parse_jsonb(row.get("metadata"), {})

        return {
            "id": row["id"],
            "chain_id": row["chain_id"],
            "source_artifact_id": row["source_artifact_id"],
            "target_artifact_id": row["target_artifact_id"],
            "link_type": row["link_type"],
            "confidence": row.get("confidence", 1.0),
            "verified": bool(row.get("verified", 0)),
            "verified_by": row.get("verified_by"),
            "verified_at": row.get("verified_at").isoformat() if row.get("verified_at") else None,
            "created_at": row.get("created_at").isoformat() if row.get("created_at") else None,
            "metadata": metadata,
            # Optional enrichment fields from JOINs
            "source_title": row.get("source_title"),
            "source_type": row.get("source_type"),
            "target_title": row.get("target_title"),
            "target_type": row.get("target_type"),
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

        where_clauses = []
        params: Dict[str, Any] = {}

        tenant_id = self.get_tenant_id_or_none()
        if tenant_id:
            where_clauses.append("tenant_id = :tenant_id")
            params["tenant_id"] = str(tenant_id)

        if entity_type:
            where_clauses.append("entity_type = :entity_type")
            params["entity_type"] = entity_type

        where_clause = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        query = f"SELECT * FROM arkham_provenance_records {where_clause} ORDER BY created_at DESC LIMIT :limit OFFSET :offset"
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

        tenant_id = self.get_tenant_id_or_none()
        if tenant_id:
            row = await self._db.fetch_one(
                "SELECT * FROM arkham_provenance_records WHERE id = :id AND tenant_id = :tenant_id",
                {"id": id, "tenant_id": str(tenant_id)}
            )
        else:
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

        tenant_id = self.get_tenant_id_or_none()
        if tenant_id:
            row = await self._db.fetch_one(
                """
                SELECT * FROM arkham_provenance_records
                WHERE entity_type = :entity_type AND entity_id = :entity_id AND tenant_id = :tenant_id
                """,
                {"entity_type": entity_type, "entity_id": entity_id, "tenant_id": str(tenant_id)}
            )
        else:
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

        tenant_id = self.get_tenant_id_or_none()
        if tenant_id:
            rows = await self._db.fetch_all(
                """
                SELECT * FROM arkham_provenance_transformations
                WHERE record_id = :record_id AND tenant_id = :tenant_id
                ORDER BY transformed_at DESC
                """,
                {"record_id": record_id, "tenant_id": str(tenant_id)}
            )
        else:
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

        tenant_id = self.get_tenant_id_or_none()
        if tenant_id:
            rows = await self._db.fetch_all(
                """
                SELECT * FROM arkham_provenance_audit
                WHERE record_id = :record_id AND tenant_id = :tenant_id
                ORDER BY occurred_at DESC
                """,
                {"record_id": record_id, "tenant_id": str(tenant_id)}
            )
        else:
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
        tenant_id = self.get_tenant_id_or_none()

        await self._db.execute(
            """
            INSERT INTO arkham_provenance_transformations
            (id, record_id, transformation_type, input_hash, output_hash, transformer, parameters, tenant_id)
            VALUES (:id, :record_id, :transformation_type, :input_hash, :output_hash, :transformer, :parameters, :tenant_id)
            """,
            {
                "id": transformation_id,
                "record_id": record_id,
                "transformation_type": transformation_type,
                "input_hash": input_hash,
                "output_hash": output_hash,
                "transformer": transformer,
                "parameters": json.dumps(parameters or {}),
                "tenant_id": str(tenant_id) if tenant_id else None,
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
        tenant_id = self.get_tenant_id_or_none()

        await self._db.execute(
            """
            INSERT INTO arkham_provenance_audit
            (id, record_id, action, actor, details, tenant_id)
            VALUES (:id, :record_id, :action, :actor, :details, :tenant_id)
            """,
            {
                "id": audit_id,
                "record_id": record_id,
                "action": action,
                "actor": actor,
                "details": json.dumps(details or {}),
                "tenant_id": str(tenant_id) if tenant_id else None,
            }
        )

    # --- Artifact CRUD Methods ---

    async def create_artifact(
        self,
        artifact_type: str,
        entity_id: str,
        entity_table: str,
        title: Optional[str] = None,
        content_hash: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Register an artifact for provenance tracking.

        Args:
            artifact_type: Type of artifact (document, entity, claim, chunk, etc.)
            entity_id: ID of the entity being tracked
            entity_table: Source table name (e.g., arkham_documents)
            title: Human-readable title
            content_hash: SHA-256 hash of content for integrity
            metadata: Additional metadata

        Returns:
            Created artifact object
        """
        if not self._db:
            raise RuntimeError("Shard not initialized")

        import uuid
        import json

        artifact_id = str(uuid.uuid4())
        tenant_id = self.get_tenant_id_or_none()

        # Check if artifact already exists for this entity
        if tenant_id:
            existing = await self._db.fetch_one(
                """
                SELECT id FROM arkham_provenance_artifacts
                WHERE entity_id = :entity_id AND entity_table = :entity_table AND tenant_id = :tenant_id
                """,
                {"entity_id": entity_id, "entity_table": entity_table, "tenant_id": str(tenant_id)}
            )
        else:
            existing = await self._db.fetch_one(
                """
                SELECT id FROM arkham_provenance_artifacts
                WHERE entity_id = :entity_id AND entity_table = :entity_table
                """,
                {"entity_id": entity_id, "entity_table": entity_table}
            )

        if existing:
            # Update existing artifact
            if tenant_id:
                await self._db.execute(
                    """
                    UPDATE arkham_provenance_artifacts
                    SET title = COALESCE(:title, title),
                        hash = COALESCE(:hash, hash),
                        metadata = metadata || :metadata
                    WHERE entity_id = :entity_id AND entity_table = :entity_table AND tenant_id = :tenant_id
                    """,
                    {
                        "title": title,
                        "hash": content_hash,
                        "metadata": json.dumps(metadata or {}),
                        "entity_id": entity_id,
                        "entity_table": entity_table,
                        "tenant_id": str(tenant_id),
                    }
                )
            else:
                await self._db.execute(
                    """
                    UPDATE arkham_provenance_artifacts
                    SET title = COALESCE(:title, title),
                        hash = COALESCE(:hash, hash),
                        metadata = metadata || :metadata
                    WHERE entity_id = :entity_id AND entity_table = :entity_table
                    """,
                    {
                        "title": title,
                        "hash": content_hash,
                        "metadata": json.dumps(metadata or {}),
                        "entity_id": entity_id,
                        "entity_table": entity_table,
                    }
                )
            artifact_id = existing["id"]
        else:
            # Insert new artifact
            await self._db.execute(
                """
                INSERT INTO arkham_provenance_artifacts
                (id, artifact_type, entity_id, entity_table, title, hash, metadata, tenant_id)
                VALUES (:id, :artifact_type, :entity_id, :entity_table, :title, :hash, :metadata, :tenant_id)
                """,
                {
                    "id": artifact_id,
                    "artifact_type": artifact_type,
                    "entity_id": entity_id,
                    "entity_table": entity_table,
                    "title": title,
                    "hash": content_hash,
                    "metadata": json.dumps(metadata or {}),
                    "tenant_id": str(tenant_id) if tenant_id else None,
                }
            )

            # Emit event for new artifact
            if self._event_bus:
                await self._event_bus.emit(
                    "provenance.artifact.created",
                    {"id": artifact_id, "type": artifact_type, "entity_id": entity_id},
                    source="provenance-shard"
                )

        # Fetch and return the artifact
        return await self.get_artifact(artifact_id)

    async def get_artifact(self, artifact_id: str) -> Optional[Dict[str, Any]]:
        """Get artifact by ID."""
        if not self._db:
            raise RuntimeError("Shard not initialized")

        tenant_id = self.get_tenant_id_or_none()
        if tenant_id:
            row = await self._db.fetch_one(
                "SELECT * FROM arkham_provenance_artifacts WHERE id = :id AND tenant_id = :tenant_id",
                {"id": artifact_id, "tenant_id": str(tenant_id)}
            )
        else:
            row = await self._db.fetch_one(
                "SELECT * FROM arkham_provenance_artifacts WHERE id = :id",
                {"id": artifact_id}
            )
        return self._row_to_artifact(row) if row else None

    async def get_artifact_by_entity(
        self,
        entity_id: str,
        entity_table: str
    ) -> Optional[Dict[str, Any]]:
        """Get artifact by the entity it tracks."""
        if not self._db:
            raise RuntimeError("Shard not initialized")

        tenant_id = self.get_tenant_id_or_none()
        if tenant_id:
            row = await self._db.fetch_one(
                """
                SELECT * FROM arkham_provenance_artifacts
                WHERE entity_id = :entity_id AND entity_table = :entity_table AND tenant_id = :tenant_id
                """,
                {"entity_id": entity_id, "entity_table": entity_table, "tenant_id": str(tenant_id)}
            )
        else:
            row = await self._db.fetch_one(
                """
                SELECT * FROM arkham_provenance_artifacts
                WHERE entity_id = :entity_id AND entity_table = :entity_table
                """,
                {"entity_id": entity_id, "entity_table": entity_table}
            )
        return self._row_to_artifact(row) if row else None

    async def list_artifacts(
        self,
        artifact_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """List artifacts with optional type filter."""
        if not self._db:
            raise RuntimeError("Shard not initialized")

        where_clauses = []
        params: Dict[str, Any] = {"limit": limit, "offset": offset}

        tenant_id = self.get_tenant_id_or_none()
        if tenant_id:
            where_clauses.append("tenant_id = :tenant_id")
            params["tenant_id"] = str(tenant_id)

        if artifact_type:
            where_clauses.append("artifact_type = :artifact_type")
            params["artifact_type"] = artifact_type

        where_clause = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        rows = await self._db.fetch_all(
            f"""
            SELECT * FROM arkham_provenance_artifacts
            {where_clause}
            ORDER BY created_at DESC
            LIMIT :limit OFFSET :offset
            """,
            params
        )

        return [self._row_to_artifact(row) for row in rows]

    async def count_artifacts(self) -> int:
        """Get total artifact count."""
        if not self._db:
            raise RuntimeError("Shard not initialized")

        tenant_id = self.get_tenant_id_or_none()
        tenant_filter = " WHERE tenant_id = :tenant_id" if tenant_id else ""
        params = {"tenant_id": str(tenant_id)} if tenant_id else {}

        result = await self._db.fetch_one(
            f"SELECT COUNT(*) as count FROM arkham_provenance_artifacts{tenant_filter}",
            params
        )
        return result["count"] if result else 0

    # --- Chain CRUD Methods ---

    async def create_chain_impl(
        self,
        title: str,
        description: Optional[str] = None,
        chain_type: str = "evidence",
        project_id: Optional[str] = None,
        root_artifact_id: Optional[str] = None,
        created_by: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a new provenance chain.

        Args:
            title: Chain title
            description: Chain description
            chain_type: Type (evidence, document, entity, claim, auto)
            project_id: Associated project ID
            root_artifact_id: Starting artifact for the chain
            created_by: Creator identifier
            metadata: Additional metadata

        Returns:
            Created chain object
        """
        if not self._db:
            raise RuntimeError("Shard not initialized")

        import uuid
        import json

        chain_id = str(uuid.uuid4())
        tenant_id = self.get_tenant_id_or_none()

        await self._db.execute(
            """
            INSERT INTO arkham_provenance_chains
            (id, title, description, chain_type, project_id, root_artifact_id, created_by, metadata, tenant_id)
            VALUES (:id, :title, :description, :chain_type, :project_id, :root_artifact_id, :created_by, :metadata, :tenant_id)
            """,
            {
                "id": chain_id,
                "title": title,
                "description": description,
                "chain_type": chain_type,
                "project_id": project_id,
                "root_artifact_id": root_artifact_id,
                "created_by": created_by,
                "metadata": json.dumps(metadata or {}),
                "tenant_id": str(tenant_id) if tenant_id else None,
            }
        )

        # Emit event
        if self._event_bus:
            await self._event_bus.emit(
                "provenance.chain.created",
                {"id": chain_id, "title": title, "type": chain_type},
                source="provenance-shard"
            )

        return await self.get_chain_impl(chain_id)

    async def get_chain_impl(self, chain_id: str) -> Optional[Dict[str, Any]]:
        """Get chain with link count."""
        if not self._db:
            raise RuntimeError("Shard not initialized")

        tenant_id = self.get_tenant_id_or_none()
        if tenant_id:
            row = await self._db.fetch_one(
                """
                SELECT c.*, COUNT(l.id) as link_count
                FROM arkham_provenance_chains c
                LEFT JOIN arkham_provenance_links l ON l.chain_id = c.id
                WHERE c.id = :id AND c.tenant_id = :tenant_id
                GROUP BY c.id
                """,
                {"id": chain_id, "tenant_id": str(tenant_id)}
            )
        else:
            row = await self._db.fetch_one(
                """
                SELECT c.*, COUNT(l.id) as link_count
                FROM arkham_provenance_chains c
                LEFT JOIN arkham_provenance_links l ON l.chain_id = c.id
                WHERE c.id = :id
                GROUP BY c.id
                """,
                {"id": chain_id}
            )
        return self._row_to_chain(row) if row else None

    async def list_chains(
        self,
        project_id: Optional[str] = None,
        chain_type: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """List chains with filters."""
        if not self._db:
            raise RuntimeError("Shard not initialized")

        conditions = []
        params: Dict[str, Any] = {"limit": limit, "offset": offset}

        tenant_id = self.get_tenant_id_or_none()
        if tenant_id:
            conditions.append("c.tenant_id = :tenant_id")
            params["tenant_id"] = str(tenant_id)

        if project_id:
            conditions.append("c.project_id = :project_id")
            params["project_id"] = project_id

        if chain_type:
            conditions.append("c.chain_type = :chain_type")
            params["chain_type"] = chain_type

        if status:
            conditions.append("c.status = :status")
            params["status"] = status

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        rows = await self._db.fetch_all(
            f"""
            SELECT c.*, COUNT(l.id) as link_count
            FROM arkham_provenance_chains c
            LEFT JOIN arkham_provenance_links l ON l.chain_id = c.id
            {where_clause}
            GROUP BY c.id
            ORDER BY c.created_at DESC
            LIMIT :limit OFFSET :offset
            """,
            params
        )

        return [self._row_to_chain(row) for row in rows]

    async def update_chain_impl(
        self,
        chain_id: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        status: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """Update chain properties."""
        if not self._db:
            raise RuntimeError("Shard not initialized")

        import json

        updates = ["updated_at = CURRENT_TIMESTAMP"]
        params: Dict[str, Any] = {"id": chain_id}

        tenant_id = self.get_tenant_id_or_none()
        tenant_filter = " AND tenant_id = :tenant_id" if tenant_id else ""
        if tenant_id:
            params["tenant_id"] = str(tenant_id)

        if title is not None:
            updates.append("title = :title")
            params["title"] = title

        if description is not None:
            updates.append("description = :description")
            params["description"] = description

        if status is not None:
            updates.append("status = :status")
            params["status"] = status

        if metadata is not None:
            updates.append("metadata = metadata || :metadata")
            params["metadata"] = json.dumps(metadata)

        await self._db.execute(
            f"""
            UPDATE arkham_provenance_chains
            SET {', '.join(updates)}
            WHERE id = :id{tenant_filter}
            """,
            params
        )

        chain = await self.get_chain_impl(chain_id)

        if chain and self._event_bus:
            await self._event_bus.emit(
                "provenance.chain.updated",
                {"id": chain_id, "status": status},
                source="provenance-shard"
            )

        return chain

    async def delete_chain_impl(self, chain_id: str) -> bool:
        """Delete a chain and its links."""
        if not self._db:
            raise RuntimeError("Shard not initialized")

        # Check if chain exists
        chain = await self.get_chain_impl(chain_id)
        if not chain:
            return False

        tenant_id = self.get_tenant_id_or_none()
        tenant_filter = " AND tenant_id = :tenant_id" if tenant_id else ""
        params: Dict[str, Any] = {"chain_id": chain_id}
        if tenant_id:
            params["tenant_id"] = str(tenant_id)

        # Delete chain (links are cascade deleted if using FK)
        await self._db.execute(
            f"DELETE FROM arkham_provenance_links WHERE chain_id = :chain_id{tenant_filter}",
            params
        )
        params_chain = {"id": chain_id}
        if tenant_id:
            params_chain["tenant_id"] = str(tenant_id)
        await self._db.execute(
            f"DELETE FROM arkham_provenance_chains WHERE id = :id{tenant_filter}",
            params_chain
        )

        if self._event_bus:
            await self._event_bus.emit(
                "provenance.chain.deleted",
                {"id": chain_id, "title": chain.get("title")},
                source="provenance-shard"
            )

        return True

    async def count_chains(self) -> int:
        """Get total chain count."""
        if not self._db:
            raise RuntimeError("Shard not initialized")

        tenant_id = self.get_tenant_id_or_none()
        tenant_filter = " WHERE tenant_id = :tenant_id" if tenant_id else ""
        params = {"tenant_id": str(tenant_id)} if tenant_id else {}

        result = await self._db.fetch_one(
            f"SELECT COUNT(*) as count FROM arkham_provenance_chains{tenant_filter}",
            params
        )
        return result["count"] if result else 0

    async def verify_chain_impl(
        self,
        chain_id: str,
        verified_by: Optional[str] = None
    ) -> Dict[str, Any]:
        """Verify all links in a chain and update status."""
        if not self._db:
            raise RuntimeError("Shard not initialized")

        tenant_id = self.get_tenant_id_or_none()
        tenant_filter = " AND tenant_id = :tenant_id" if tenant_id else ""
        params: Dict[str, Any] = {"chain_id": chain_id}
        if tenant_id:
            params["tenant_id"] = str(tenant_id)

        # Get all links
        links = await self._db.fetch_all(
            f"SELECT * FROM arkham_provenance_links WHERE chain_id = :chain_id{tenant_filter}",
            params
        )

        issues = []

        for link in links:
            # Check source artifact exists
            source = await self.get_artifact(link["source_artifact_id"])
            if not source:
                issues.append({
                    "link_id": link["id"],
                    "issue": "source_artifact_missing",
                    "artifact_id": link["source_artifact_id"]
                })

            # Check target artifact exists
            target = await self.get_artifact(link["target_artifact_id"])
            if not target:
                issues.append({
                    "link_id": link["id"],
                    "issue": "target_artifact_missing",
                    "artifact_id": link["target_artifact_id"]
                })

        verified = len(issues) == 0
        new_status = "verified" if verified else "disputed"

        # Update chain status
        await self.update_chain_impl(chain_id, status=new_status)

        # Mark all links as verified if no issues
        if verified and verified_by:
            verify_params: Dict[str, Any] = {"verified_by": verified_by, "chain_id": chain_id}
            if tenant_id:
                verify_params["tenant_id"] = str(tenant_id)
            await self._db.execute(
                f"""
                UPDATE arkham_provenance_links
                SET verified = 1, verified_by = :verified_by, verified_at = CURRENT_TIMESTAMP
                WHERE chain_id = :chain_id{tenant_filter}
                """,
                verify_params
            )

        if self._event_bus:
            await self._event_bus.emit(
                "provenance.chain.verified",
                {"id": chain_id, "verified": verified, "issue_count": len(issues)},
                source="provenance-shard"
            )

        return {
            "chain_id": chain_id,
            "verified": verified,
            "status": new_status,
            "issues": issues,
            "link_count": len(links)
        }

    # --- Link CRUD Methods ---

    async def add_link_impl(
        self,
        chain_id: str,
        source_artifact_id: str,
        target_artifact_id: str,
        link_type: str,
        confidence: float = 1.0,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Add a link between artifacts in a chain."""
        if not self._db:
            raise RuntimeError("Shard not initialized")

        import uuid
        import json

        # Validate artifacts exist
        source = await self.get_artifact(source_artifact_id)
        if not source:
            raise ValueError(f"Source artifact {source_artifact_id} not found")

        target = await self.get_artifact(target_artifact_id)
        if not target:
            raise ValueError(f"Target artifact {target_artifact_id} not found")

        link_id = str(uuid.uuid4())
        tenant_id = self.get_tenant_id_or_none()

        await self._db.execute(
            """
            INSERT INTO arkham_provenance_links
            (id, chain_id, source_artifact_id, target_artifact_id, link_type, confidence, metadata, tenant_id)
            VALUES (:id, :chain_id, :source_artifact_id, :target_artifact_id, :link_type, :confidence, :metadata, :tenant_id)
            """,
            {
                "id": link_id,
                "chain_id": chain_id,
                "source_artifact_id": source_artifact_id,
                "target_artifact_id": target_artifact_id,
                "link_type": link_type,
                "confidence": confidence,
                "metadata": json.dumps(metadata or {}),
                "tenant_id": str(tenant_id) if tenant_id else None,
            }
        )

        # Update lineage cache for target artifact
        await self._update_lineage_cache(target_artifact_id)

        if self._event_bus:
            await self._event_bus.emit(
                "provenance.link.added",
                {
                    "id": link_id,
                    "chain_id": chain_id,
                    "source": source_artifact_id,
                    "target": target_artifact_id,
                    "type": link_type
                },
                source="provenance-shard"
            )

        # Return the created link with artifact details
        if tenant_id:
            row = await self._db.fetch_one(
                """
                SELECT l.*,
                       sa.title as source_title, sa.artifact_type as source_type,
                       ta.title as target_title, ta.artifact_type as target_type
                FROM arkham_provenance_links l
                JOIN arkham_provenance_artifacts sa ON sa.id = l.source_artifact_id
                JOIN arkham_provenance_artifacts ta ON ta.id = l.target_artifact_id
                WHERE l.id = :id AND l.tenant_id = :tenant_id
                """,
                {"id": link_id, "tenant_id": str(tenant_id)}
            )
        else:
            row = await self._db.fetch_one(
                """
                SELECT l.*,
                       sa.title as source_title, sa.artifact_type as source_type,
                       ta.title as target_title, ta.artifact_type as target_type
                FROM arkham_provenance_links l
                JOIN arkham_provenance_artifacts sa ON sa.id = l.source_artifact_id
                JOIN arkham_provenance_artifacts ta ON ta.id = l.target_artifact_id
                WHERE l.id = :id
                """,
                {"id": link_id}
            )
        return self._row_to_link(row) if row else {"id": link_id, "chain_id": chain_id}

    async def get_chain_links(self, chain_id: str) -> List[Dict[str, Any]]:
        """Get all links in a chain with artifact details."""
        if not self._db:
            raise RuntimeError("Shard not initialized")

        tenant_id = self.get_tenant_id_or_none()
        if tenant_id:
            rows = await self._db.fetch_all(
                """
                SELECT l.*,
                       sa.title as source_title, sa.artifact_type as source_type,
                       ta.title as target_title, ta.artifact_type as target_type
                FROM arkham_provenance_links l
                JOIN arkham_provenance_artifacts sa ON sa.id = l.source_artifact_id
                JOIN arkham_provenance_artifacts ta ON ta.id = l.target_artifact_id
                WHERE l.chain_id = :chain_id AND l.tenant_id = :tenant_id
                ORDER BY l.created_at
                """,
                {"chain_id": chain_id, "tenant_id": str(tenant_id)}
            )
        else:
            rows = await self._db.fetch_all(
                """
                SELECT l.*,
                       sa.title as source_title, sa.artifact_type as source_type,
                       ta.title as target_title, ta.artifact_type as target_type
                FROM arkham_provenance_links l
                JOIN arkham_provenance_artifacts sa ON sa.id = l.source_artifact_id
                JOIN arkham_provenance_artifacts ta ON ta.id = l.target_artifact_id
                WHERE l.chain_id = :chain_id
                ORDER BY l.created_at
                """,
                {"chain_id": chain_id}
            )
        return [self._row_to_link(row) for row in rows]

    async def remove_link(self, link_id: str) -> bool:
        """Remove a link from a chain."""
        if not self._db:
            raise RuntimeError("Shard not initialized")

        tenant_id = self.get_tenant_id_or_none()
        tenant_filter = " AND tenant_id = :tenant_id" if tenant_id else ""
        params: Dict[str, Any] = {"id": link_id}
        if tenant_id:
            params["tenant_id"] = str(tenant_id)

        # Get link details for event
        link = await self._db.fetch_one(
            f"SELECT * FROM arkham_provenance_links WHERE id = :id{tenant_filter}",
            params
        )

        if not link:
            return False

        await self._db.execute(
            f"DELETE FROM arkham_provenance_links WHERE id = :id{tenant_filter}",
            params
        )

        # Update lineage cache for affected artifact
        await self._update_lineage_cache(link["target_artifact_id"])

        if self._event_bus:
            await self._event_bus.emit(
                "provenance.link.removed",
                {"id": link_id, "chain_id": link["chain_id"]},
                source="provenance-shard"
            )

        return True

    async def verify_link(
        self,
        link_id: str,
        verified_by: str,
        notes: str = ""
    ) -> Optional[Dict[str, Any]]:
        """Verify a specific link."""
        if not self._db:
            raise RuntimeError("Shard not initialized")

        import json

        tenant_id = self.get_tenant_id_or_none()
        tenant_filter = " AND tenant_id = :tenant_id" if tenant_id else ""
        params: Dict[str, Any] = {
            "verified_by": verified_by,
            "notes_metadata": json.dumps({"verification_notes": notes}) if notes else "{}",
            "id": link_id,
        }
        if tenant_id:
            params["tenant_id"] = str(tenant_id)

        await self._db.execute(
            f"""
            UPDATE arkham_provenance_links
            SET verified = 1,
                verified_by = :verified_by,
                verified_at = CURRENT_TIMESTAMP,
                metadata = metadata || :notes_metadata
            WHERE id = :id{tenant_filter}
            """,
            params
        )

        if tenant_id:
            row = await self._db.fetch_one(
                """
                SELECT l.*,
                       sa.title as source_title, sa.artifact_type as source_type,
                       ta.title as target_title, ta.artifact_type as target_type
                FROM arkham_provenance_links l
                JOIN arkham_provenance_artifacts sa ON sa.id = l.source_artifact_id
                JOIN arkham_provenance_artifacts ta ON ta.id = l.target_artifact_id
                WHERE l.id = :id AND l.tenant_id = :tenant_id
                """,
                {"id": link_id, "tenant_id": str(tenant_id)}
            )
        else:
            row = await self._db.fetch_one(
                """
                SELECT l.*,
                       sa.title as source_title, sa.artifact_type as source_type,
                       ta.title as target_title, ta.artifact_type as target_type
                FROM arkham_provenance_links l
                JOIN arkham_provenance_artifacts sa ON sa.id = l.source_artifact_id
                JOIN arkham_provenance_artifacts ta ON ta.id = l.target_artifact_id
                WHERE l.id = :id
                """,
                {"id": link_id}
            )

        if row and self._event_bus:
            await self._event_bus.emit(
                "provenance.link.verified",
                {"id": link_id, "verified_by": verified_by},
                source="provenance-shard"
            )

        return self._row_to_link(row) if row else None

    # --- Lineage Methods ---

    async def _update_lineage_cache(self, artifact_id: str) -> None:
        """Rebuild lineage cache for an artifact using BFS."""
        if not self._db:
            return

        import uuid
        import json

        tenant_id = self.get_tenant_id_or_none()
        tenant_filter = " AND tenant_id = :tenant_id" if tenant_id else ""
        params: Dict[str, Any] = {"artifact_id": artifact_id}
        if tenant_id:
            params["tenant_id"] = str(tenant_id)

        # Clear existing lineage for this artifact
        await self._db.execute(
            f"DELETE FROM arkham_provenance_lineage WHERE artifact_id = :artifact_id{tenant_filter}",
            params
        )

        # BFS to find all ancestors
        visited = set()
        queue = [(artifact_id, 0, [artifact_id])]  # (current_id, depth, path)

        while queue:
            current_id, depth, path = queue.pop(0)

            if current_id in visited:
                continue
            visited.add(current_id)

            # Find all sources (artifacts that link TO this one)
            source_params: Dict[str, Any] = {"target_id": current_id}
            if tenant_id:
                source_params["tenant_id"] = str(tenant_id)
            sources = await self._db.fetch_all(
                f"""
                SELECT DISTINCT source_artifact_id
                FROM arkham_provenance_links
                WHERE target_artifact_id = :target_id{tenant_filter}
                """,
                source_params
            )

            for row in sources:
                source_id = row["source_artifact_id"]
                new_path = [source_id] + path

                # Store lineage record
                lineage_id = str(uuid.uuid4())
                await self._db.execute(
                    """
                    INSERT INTO arkham_provenance_lineage
                    (id, artifact_id, ancestor_id, depth, path, tenant_id)
                    VALUES (:id, :artifact_id, :ancestor_id, :depth, :path, :tenant_id)
                    """,
                    {
                        "id": lineage_id,
                        "artifact_id": artifact_id,
                        "ancestor_id": source_id,
                        "depth": depth + 1,
                        "path": json.dumps(new_path),
                        "tenant_id": str(tenant_id) if tenant_id else None,
                    }
                )

                queue.append((source_id, depth + 1, new_path))

    async def get_lineage_impl(self, artifact_id: str) -> Dict[str, Any]:
        """Get full lineage graph for an artifact."""
        if not self._db:
            raise RuntimeError("Shard not initialized")

        import json

        tenant_id = self.get_tenant_id_or_none()
        tenant_filter = " AND l.tenant_id = :tenant_id" if tenant_id else ""

        # Get the artifact
        artifact = await self.get_artifact(artifact_id)
        if not artifact:
            return {"nodes": [], "edges": [], "root": None}

        # Get all ancestors from cache
        ancestor_params: Dict[str, Any] = {"artifact_id": artifact_id}
        if tenant_id:
            ancestor_params["tenant_id"] = str(tenant_id)
        ancestors = await self._db.fetch_all(
            f"""
            SELECT l.*, a.title, a.artifact_type, a.entity_id
            FROM arkham_provenance_lineage l
            JOIN arkham_provenance_artifacts a ON a.id = l.ancestor_id
            WHERE l.artifact_id = :artifact_id{tenant_filter}
            ORDER BY l.depth
            """,
            ancestor_params
        )

        # Get all descendants (artifacts that have this one as ancestor)
        descendant_params: Dict[str, Any] = {"artifact_id": artifact_id}
        if tenant_id:
            descendant_params["tenant_id"] = str(tenant_id)
        descendants = await self._db.fetch_all(
            f"""
            SELECT l.artifact_id, l.depth, a.title, a.artifact_type, a.entity_id
            FROM arkham_provenance_lineage l
            JOIN arkham_provenance_artifacts a ON a.id = l.artifact_id
            WHERE l.ancestor_id = :artifact_id{tenant_filter}
            ORDER BY l.depth
            """,
            descendant_params
        )

        # Build nodes
        nodes = [{
            "id": artifact_id,
            "title": artifact.get("title"),
            "type": artifact.get("artifact_type"),
            "is_focus": True,
            "depth": 0
        }]

        seen_ids = {artifact_id}

        for row in ancestors:
            if row["ancestor_id"] not in seen_ids:
                nodes.append({
                    "id": row["ancestor_id"],
                    "title": row["title"],
                    "type": row["artifact_type"],
                    "depth": -row["depth"]  # Negative for ancestors
                })
                seen_ids.add(row["ancestor_id"])

        for row in descendants:
            if row["artifact_id"] not in seen_ids:
                nodes.append({
                    "id": row["artifact_id"],
                    "title": row["title"],
                    "type": row["artifact_type"],
                    "depth": row["depth"]  # Positive for descendants
                })
                seen_ids.add(row["artifact_id"])

        # Get edges (links between all these artifacts)
        if len(seen_ids) > 0:
            # Build a query with placeholders
            id_list = list(seen_ids)
            placeholders = ", ".join([f":id_{i}" for i in range(len(id_list))])
            edge_params: Dict[str, Any] = {f"id_{i}": id_list[i] for i in range(len(id_list))}

            tenant_filter_edges = " AND tenant_id = :tenant_id" if tenant_id else ""
            if tenant_id:
                edge_params["tenant_id"] = str(tenant_id)

            edges_rows = await self._db.fetch_all(
                f"""
                SELECT id, source_artifact_id, target_artifact_id, link_type, confidence
                FROM arkham_provenance_links
                WHERE source_artifact_id IN ({placeholders}) AND target_artifact_id IN ({placeholders}){tenant_filter_edges}
                """,
                edge_params
            )

            edges = [{
                "id": e["id"],
                "source": e["source_artifact_id"],
                "target": e["target_artifact_id"],
                "link_type": e["link_type"],
                "confidence": e["confidence"]
            } for e in edges_rows]
        else:
            edges = []

        return {
            "nodes": nodes,
            "edges": edges,
            "root": artifact_id,
            "ancestor_count": len(ancestors),
            "descendant_count": len(descendants)
        }

    async def _get_or_create_default_chain(
        self,
        project_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get or create a default auto-tracking chain."""
        if not self._db:
            raise RuntimeError("Shard not initialized")

        chain_title = "Auto-tracked Provenance"
        tenant_id = self.get_tenant_id_or_none()
        tenant_filter = " AND tenant_id = :tenant_id" if tenant_id else ""

        # Check for existing
        if project_id:
            params: Dict[str, Any] = {"title": chain_title, "project_id": project_id}
            if tenant_id:
                params["tenant_id"] = str(tenant_id)
            existing = await self._db.fetch_one(
                f"""
                SELECT * FROM arkham_provenance_chains
                WHERE title = :title AND project_id = :project_id{tenant_filter}
                """,
                params
            )
        else:
            params_none: Dict[str, Any] = {"title": chain_title}
            if tenant_id:
                params_none["tenant_id"] = str(tenant_id)
            existing = await self._db.fetch_one(
                f"""
                SELECT * FROM arkham_provenance_chains
                WHERE title = :title AND project_id IS NULL{tenant_filter}
                """,
                params_none
            )

        if existing:
            return self._row_to_chain(existing)

        return await self.create_chain_impl(
            title=chain_title,
            description="Automatically tracked provenance links",
            chain_type="auto",
            project_id=project_id
        )

    # --- Helper Methods ---

    def _infer_artifact_type(self, table_name: str, event_type: str = "") -> str:
        """
        Infer artifact type from table name and event type.

        Args:
            table_name: Database table name (e.g., "arkham_documents", "qdrant_vectors")
            event_type: Event name (e.g., "embed.document.completed")

        Returns:
            Human-readable artifact type
        """
        # Table-based inference
        table_mapping = {
            "arkham_documents": "document",
            "arkham_document_chunks": "chunk",
            "arkham_document_pages": "page",
            "arkham_entities": "entity",
            "arkham_claims": "claim",
            "arkham_frame.entities": "entity",
            "arkham_frame.documents": "document",
            "qdrant_vectors": "embedding",
            "arkham_ach_matrices": "ach_matrix",
            "arkham_ach_hypotheses": "hypothesis",
            "arkham_ach_evidence": "evidence",
            "arkham_timeline_events": "timeline_event",
            "arkham_contradictions": "contradiction",
            "arkham_anomalies": "anomaly",
            "arkham_patterns": "pattern",
            "arkham_credibility_assessments": "credibility",
            "arkham_reports": "report",
            "arkham_letters": "letter",
            "arkham_packets": "packet",
        }

        # Check table mapping first
        if table_name in table_mapping:
            return table_mapping[table_name]

        # Partial match on table name
        for key, value in table_mapping.items():
            if key in table_name or table_name in key:
                return value

        # Event-based inference as fallback
        if event_type:
            event_lower = event_type.lower()
            if "embed" in event_lower or "vector" in event_lower:
                return "embedding"
            if "chunk" in event_lower:
                return "chunk"
            if "entity" in event_lower:
                return "entity"
            if "document" in event_lower:
                return "document"
            if "parse" in event_lower:
                return "chunk"

        # Final fallback - extract from table name
        if "chunk" in table_name.lower():
            return "chunk"
        if "vector" in table_name.lower() or "embed" in table_name.lower():
            return "embedding"
        if "entity" in table_name.lower():
            return "entity"
        if "document" in table_name.lower():
            return "document"

        return "artifact"

    def _generate_artifact_title(
        self,
        artifact_type: str,
        payload: Dict[str, Any],
        entity_id: str,
        index: int = 0,
    ) -> str:
        """
        Generate a meaningful title for an artifact.

        Args:
            artifact_type: Type of artifact (document, chunk, entity, etc.)
            payload: Event payload with context
            entity_id: Entity ID
            index: Index if part of a batch

        Returns:
            Human-readable title
        """
        # Try to get title from payload
        title = payload.get("title") or payload.get("name") or payload.get("filename")

        if title:
            if artifact_type == "document":
                return title
            return f"{artifact_type.title()}: {title[:50]}"

        # Try to get text content
        text = payload.get("text", "")
        if text:
            preview = text[:50].replace("\n", " ").strip()
            return f"{artifact_type.title()}: {preview}..."

        # Fallback with index
        parent_id = payload.get("document_id") or payload.get("parent_document_id") or ""
        if parent_id and index > 0:
            return f"{artifact_type.title()} #{index} from doc:{parent_id[:8]}"

        return f"{artifact_type.title()} {entity_id[:8]}"

    # --- Event Handlers ---

    async def _on_entity_created(self, event: Dict[str, Any]) -> None:
        """
        Handle entity creation events from any shard.

        Automatically creates an artifact record to track the entity.

        Args:
            event: Event payload with entity details
                - event_type: Event name (e.g., "documents.document.created")
                - payload: Contains id, title, and other entity data
                - source: Shard that emitted the event
        """
        try:
            payload = event.get("payload", {})
            event_type = event.get("event_type", "")
            source = event.get("source", "unknown")

            logger.info(f"[PROVENANCE] Received created event: {event_type} from {source}")

            # Skip our own events to prevent recursion
            if "provenance" in source.lower() or event_type.startswith("provenance."):
                return

            # Extract entity info from event
            entity_id = payload.get("id") or payload.get("entity_id") or payload.get("document_id")
            if not entity_id:
                logger.debug(f"No entity_id in event: {event_type}")
                return

            # Determine artifact type and table from event type
            # Event format: {shard}.{entity}.{action}
            parts = event_type.split(".")
            if len(parts) >= 2:
                shard_name = parts[0]
                entity_type_from_event = parts[1]
            else:
                shard_name = source.replace("-shard", "")
                entity_type_from_event = "unknown"

            # Map to table name based on entity type
            table_mapping = {
                "document": "arkham_documents",
                "entity": "arkham_entities",
                "claim": "arkham_claims",
                "chunk": "arkham_document_chunks",
                "matrix": "arkham_ach_matrices",
                "hypothesis": "arkham_ach_hypotheses",
                "evidence": "arkham_ach_evidence",
                "report": "arkham_reports",
                "letter": "arkham_letters",
                "packet": "arkham_packets",
                "project": "arkham_projects",
                "timeline": "arkham_timeline_events",
            }

            entity_table = table_mapping.get(entity_type_from_event, f"arkham_{shard_name}_{entity_type_from_event}s")

            # Use helper to get canonical artifact type
            artifact_type = self._infer_artifact_type(entity_table, event_type)

            # Generate meaningful title
            title = self._generate_artifact_title(artifact_type, payload, entity_id)

            artifact = await self.create_artifact(
                artifact_type=artifact_type,
                entity_id=entity_id,
                entity_table=entity_table,
                title=title,
                metadata={
                    "source_event": event_type,
                    "source_shard": source,
                    "created_from_event": True,
                }
            )

            logger.info(f"[PROVENANCE] Created artifact {artifact['id']} for {artifact_type}:{entity_id} from {event_type}")

        except Exception as e:
            logger.warning(f"Failed to track entity creation: {e}", exc_info=True)

    async def _on_process_completed(self, event: Dict[str, Any]) -> None:
        """
        Handle process completion events from any shard.

        Automatically creates links between source and output artifacts.
        Also creates a provenance record for the processing event.

        Args:
            event: Event payload with process details
                - event_type: Event name (e.g., "parse.document.completed")
                - payload: Contains source and output IDs
                - source: Shard that emitted the event
        """
        try:
            payload = event.get("payload", {})
            event_type = event.get("event_type", "")
            source = event.get("source", "unknown")

            logger.info(f"[PROVENANCE] Received completed event: {event_type} from {source}")
            logger.debug(f"[PROVENANCE] Payload: {payload}")

            # Skip our own events to prevent recursion
            if "provenance" in source.lower() or event_type.startswith("provenance."):
                return

            # Extract source ID (document being processed)
            source_id = payload.get("source_id") or payload.get("document_id") or payload.get("input_id")
            output_ids = payload.get("output_ids") or payload.get("chunk_ids") or []

            if not source_id:
                logger.debug(f"No source_id in completion event: {event_type}")
                return

            if isinstance(output_ids, str):
                output_ids = [output_ids]

            # Determine source table and type
            source_table = payload.get("source_table", "arkham_documents")
            source_type = "document" if "document" in source_table else "unknown"

            # Get or CREATE source artifact (don't just look it up)
            source_artifact = await self.get_artifact_by_entity(source_id, source_table)

            if not source_artifact:
                # Auto-create artifact for the source document
                logger.info(f"[PROVENANCE] Auto-creating artifact for {source_type}:{source_id}")
                source_artifact = await self.create_artifact(
                    artifact_type=source_type,
                    entity_id=source_id,
                    entity_table=source_table,
                    title=payload.get("title") or payload.get("filename") or f"Document {source_id[:8]}",
                    metadata={
                        "source_event": event_type,
                        "source_shard": source,
                        "auto_created": True,
                    }
                )
                logger.info(f"[PROVENANCE] Created artifact {source_artifact['id']} for {source_type}:{source_id}")

            # Record processing as a transformation/provenance record
            # Even if no output_ids, we still want to track that this document was processed
            import uuid
            import json
            from datetime import datetime

            record_id = str(uuid.uuid4())
            tenant_id = self.get_tenant_id_or_none()
            await self._db.execute(
                """
                INSERT INTO arkham_provenance_records
                (id, entity_type, entity_id, source_type, source_id, imported_by, metadata, tenant_id)
                VALUES (:id, :entity_type, :entity_id, :source_type, :source_id, :imported_by, :metadata, :tenant_id)
                ON CONFLICT (id) DO NOTHING
                """,
                {
                    "id": record_id,
                    "entity_type": source_type,
                    "entity_id": source_id,
                    "source_type": event_type.split(".")[0],  # e.g., "parse" from "parse.document.completed"
                    "source_id": source_id,
                    "imported_by": source,
                    "metadata": json.dumps({
                        "event": event_type,
                        "payload": payload,
                        "processed_at": datetime.utcnow().isoformat(),
                    }),
                    "tenant_id": str(tenant_id) if tenant_id else None,
                }
            )
            logger.info(f"[PROVENANCE] Created record {record_id} for {event_type} on {source_id}")

            # If there are output IDs, create links
            if output_ids:
                project_id = payload.get("project_id")
                chain = await self._get_or_create_default_chain(project_id)

                # Determine link type from event
                link_type = "derived_from"
                if "extract" in event_type:
                    link_type = "extracted_from"
                elif "embed" in event_type:
                    link_type = "generated_by"
                elif "parse" in event_type or "chunk" in event_type:
                    link_type = "derived_from"

                # Create links for each output
                output_table = payload.get("output_table", "arkham_document_chunks")

                # Determine output artifact type from table name and event
                output_type = self._infer_artifact_type(output_table, event_type)

                for idx, output_id in enumerate(output_ids):
                    output_artifact = await self.get_artifact_by_entity(output_id, output_table)

                    if not output_artifact:
                        # Generate meaningful title
                        doc_title = payload.get("title") or payload.get("filename") or source_id[:8]
                        output_title = f"{output_type.title()} #{idx + 1} from '{doc_title}'"

                        output_artifact = await self.create_artifact(
                            artifact_type=output_type,
                            entity_id=output_id,
                            entity_table=output_table,
                            title=output_title,
                            metadata={
                                "source_event": event_type,
                                "parent_document_id": source_id,
                                "index": idx,
                                "auto_created": True,
                            }
                        )

                    if output_artifact:
                        try:
                            await self.add_link_impl(
                                chain_id=chain["id"],
                                source_artifact_id=source_artifact["id"],
                                target_artifact_id=output_artifact["id"],
                                link_type=link_type,
                                confidence=1.0,
                                metadata={
                                    "source_event": event_type,
                                    "auto_linked": True,
                                }
                            )
                            logger.debug(f"Created auto-link: {source_artifact['id']} -> {output_artifact['id']}")
                        except Exception as e:
                            logger.warning(f"Failed to create link: {e}")

        except Exception as e:
            logger.warning(f"Failed to track process completion: {e}", exc_info=True)

    async def _on_document_processed(self, event: Dict[str, Any]) -> None:
        """
        Handle document processing events specifically.

        Creates comprehensive provenance chain for document processing.

        Args:
            event: Event payload with document details
        """
        try:
            payload = event.get("payload", {})
            event_type = event.get("event_type", "")

            document_id = payload.get("document_id") or payload.get("id")
            if not document_id:
                return

            # Create document artifact if not exists
            await self.create_artifact(
                artifact_type="document",
                entity_id=document_id,
                entity_table="arkham_documents",
                title=payload.get("title") or payload.get("filename"),
                metadata={
                    "processed_from_event": event_type,
                    "status": payload.get("status", "processed"),
                }
            )

            # Link to any extracted entities
            entity_ids = payload.get("entity_ids") or []
            claim_ids = payload.get("claim_ids") or []
            chunk_ids = payload.get("chunk_ids") or []

            if entity_ids or claim_ids or chunk_ids:
                # Forward to completion handler
                await self._on_process_completed({
                    "event_type": event_type,
                    "payload": {
                        "source_id": document_id,
                        "source_table": "arkham_documents",
                        "output_ids": entity_ids + claim_ids,
                        "output_table": "arkham_entities",
                        "chunk_ids": chunk_ids,
                        "project_id": payload.get("project_id"),
                    },
                    "source": "provenance-shard",
                })

            logger.debug(f"Tracked document processing: {document_id}")

        except Exception as e:
            logger.warning(f"Failed to track document processing: {e}")

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
        return await self.create_chain_impl(
            title=title,
            description=description,
            chain_type="evidence",
            project_id=project_id,
            created_by=created_by,
        )

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
        return await self.add_link_impl(
            chain_id=chain_id,
            source_artifact_id=source_id,
            target_artifact_id=target_id,
            link_type=link_type,
            confidence=confidence,
        )

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
        return await self.get_lineage_impl(artifact_id)

    async def verify_chain(self, chain_id: str) -> Dict[str, Any]:
        """
        Public method to verify chain integrity.

        Args:
            chain_id: Chain ID to verify

        Returns:
            Verification result with status and details
        """
        return await self.verify_chain_impl(chain_id)
