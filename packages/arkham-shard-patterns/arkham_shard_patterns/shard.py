"""
Patterns Shard - Main Shard Implementation

Cross-document pattern detection - identifies recurring themes,
behaviors, and relationships across the document corpus.

Key features:
- Automatic pattern detection across documents
- Recurring theme analysis
- Behavioral pattern identification
- Temporal pattern detection
- Entity correlation analysis (Pearson/Spearman)
- Pattern evidence linking

Pattern matching uses graceful degradation:
1. Keyword matching (always available)
2. Regex matching (always available)
3. Vector similarity (if vectors service available)
"""

import json
import logging
import re
from collections import Counter
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from arkham_frame import ArkhamShard

from .models import (
    Correlation,
    CorrelationRequest,
    CorrelationResult,
    DetectionMethod,
    Pattern,
    PatternAnalysisRequest,
    PatternAnalysisResult,
    PatternCriteria,
    PatternFilter,
    PatternMatch,
    PatternMatchCreate,
    PatternStatistics,
    PatternStatus,
    PatternType,
    SourceType,
)

logger = logging.getLogger(__name__)


class PatternsShard(ArkhamShard):
    """
    Patterns Shard - Cross-document pattern detection.

    This shard provides:
    - Automatic pattern detection across documents
    - Recurring theme analysis
    - Behavioral pattern identification
    - Temporal pattern detection
    - Entity correlation analysis
    - Pattern evidence linking
    """

    name = "patterns"
    version = "0.1.0"
    description = "Cross-document pattern detection and recurring theme analysis"

    def __init__(self):
        super().__init__()  # Auto-loads manifest from shard.yaml
        self.frame = None
        self._db = None
        self._events = None
        self._llm = None
        self._vectors = None
        self._workers = None
        self._initialized = False

    async def initialize(self, frame) -> None:
        """Initialize shard with frame services."""
        self.frame = frame
        self._db = frame.database
        self._events = frame.events
        self._llm = getattr(frame, "llm", None)
        self._vectors = getattr(frame, "vectors", None)
        self._workers = getattr(frame, "workers", None)

        # Create database schema
        await self._create_schema()

        # Subscribe to events
        await self._subscribe_to_events()

        # Register self in app state for API access
        if hasattr(frame, "app") and frame.app:
            frame.app.state.patterns_shard = self

        self._initialized = True
        logger.info(f"PatternsShard initialized (v{self.version})")

    async def shutdown(self) -> None:
        """Clean shutdown of shard."""
        if self._events:
            await self._events.unsubscribe("document.processed", self._on_document_processed)
            await self._events.unsubscribe("entity.created", self._on_entity_created)
            await self._events.unsubscribe("claims.claim.created", self._on_claim_created)
            await self._events.unsubscribe("timeline.event.created", self._on_timeline_event)

        self._initialized = False
        logger.info("PatternsShard shutdown complete")

    def get_routes(self):
        """Return FastAPI router for this shard."""
        from .api import router
        return router

    # === Database Schema ===

    async def _create_schema(self) -> None:
        """Create database tables for patterns shard."""
        if not self._db:
            logger.warning("Database not available, skipping schema creation")
            return

        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS arkham_patterns (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                pattern_type TEXT DEFAULT 'recurring_theme',
                status TEXT DEFAULT 'detected',
                confidence REAL DEFAULT 0.5,

                match_count INTEGER DEFAULT 0,
                document_count INTEGER DEFAULT 0,
                entity_count INTEGER DEFAULT 0,

                first_detected TEXT,
                last_matched TEXT,

                detection_method TEXT DEFAULT 'manual',
                detection_model TEXT,

                criteria TEXT DEFAULT '{}',

                created_at TEXT,
                updated_at TEXT,
                created_by TEXT DEFAULT 'system',

                metadata TEXT DEFAULT '{}'
            )
        """)

        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS arkham_pattern_matches (
                id TEXT PRIMARY KEY,
                pattern_id TEXT NOT NULL,

                source_type TEXT NOT NULL,
                source_id TEXT NOT NULL,
                source_title TEXT,

                match_score REAL DEFAULT 1.0,
                excerpt TEXT,
                context TEXT,

                start_char INTEGER,
                end_char INTEGER,

                matched_at TEXT,
                matched_by TEXT DEFAULT 'system',

                metadata TEXT DEFAULT '{}',

                FOREIGN KEY (pattern_id) REFERENCES arkham_patterns(id)
            )
        """)

        # Create indexes
        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_patterns_type ON arkham_patterns(pattern_type)
        """)
        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_patterns_status ON arkham_patterns(status)
        """)
        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_pattern_matches_pattern ON arkham_pattern_matches(pattern_id)
        """)
        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_pattern_matches_source ON arkham_pattern_matches(source_type, source_id)
        """)

        # ===========================================
        # Multi-tenancy Migration
        # ===========================================
        await self._db.execute("""
            DO $$
            DECLARE
                tables_to_update TEXT[] := ARRAY['arkham_patterns', 'arkham_pattern_matches'];
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
            CREATE INDEX IF NOT EXISTS idx_arkham_patterns_tenant
            ON arkham_patterns(tenant_id)
        """)

        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_arkham_pattern_matches_tenant
            ON arkham_pattern_matches(tenant_id)
        """)

        logger.debug("Patterns schema created/verified")

    # === Event Subscriptions ===

    async def _subscribe_to_events(self) -> None:
        """Subscribe to relevant events from other shards."""
        if not self._events:
            logger.warning("Events service not available")
            return

        await self._events.subscribe("document.processed", self._on_document_processed)
        await self._events.subscribe("entity.created", self._on_entity_created)
        await self._events.subscribe("claims.claim.created", self._on_claim_created)
        await self._events.subscribe("timeline.event.created", self._on_timeline_event)

    async def _on_document_processed(self, event: Dict[str, Any]) -> None:
        """Handle document.processed event - check for pattern matches."""
        document_id = event.get("payload", {}).get("document_id")
        if not document_id:
            return

        logger.debug(f"Document processed, checking patterns: {document_id}")
        # Queue pattern matching job if workers available
        if self._workers:
            await self._workers.enqueue(
                pool="cpu-light",
                job_id=f"patterns-match-{document_id}",
                payload={"document_id": document_id, "action": "match_patterns"},
            )

    async def _on_entity_created(self, event: Dict[str, Any]) -> None:
        """Handle entity.created event - check for pattern matches."""
        entity_id = event.get("payload", {}).get("entity_id")
        if entity_id:
            await self._check_source_against_patterns(SourceType.ENTITY, entity_id)

    async def _on_claim_created(self, event: Dict[str, Any]) -> None:
        """Handle claims.claim.created event - check for pattern matches."""
        claim_id = event.get("payload", {}).get("claim_id")
        if claim_id:
            await self._check_source_against_patterns(SourceType.CLAIM, claim_id)

    async def _on_timeline_event(self, event: Dict[str, Any]) -> None:
        """Handle timeline.event.created event - check for pattern matches."""
        event_id = event.get("payload", {}).get("event_id")
        if event_id:
            await self._check_source_against_patterns(SourceType.EVENT, event_id)

    # === Public API Methods ===

    async def create_pattern(
        self,
        name: str,
        description: str,
        pattern_type: PatternType = PatternType.RECURRING_THEME,
        criteria: Optional[PatternCriteria] = None,
        confidence: float = 0.5,
        detection_method: DetectionMethod = DetectionMethod.MANUAL,
        detection_model: Optional[str] = None,
        created_by: str = "system",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Pattern:
        """Create a new pattern."""
        pattern_id = str(uuid4())
        now = datetime.utcnow()

        pattern = Pattern(
            id=pattern_id,
            name=name,
            description=description,
            pattern_type=pattern_type,
            status=PatternStatus.DETECTED,
            confidence=confidence,
            first_detected=now,
            detection_method=detection_method,
            detection_model=detection_model,
            criteria=criteria or PatternCriteria(),
            created_at=now,
            updated_at=now,
            created_by=created_by,
            metadata=metadata or {},
        )

        await self._save_pattern(pattern)

        # Emit event
        if self._events:
            await self._events.emit(
                "patterns.pattern.detected",
                {
                    "pattern_id": pattern_id,
                    "name": name,
                    "pattern_type": pattern_type.value,
                    "detection_method": detection_method.value,
                },
                source=self.name,
            )

        return pattern

    async def get_pattern(self, pattern_id: str) -> Optional[Pattern]:
        """Get a pattern by ID."""
        if not self._db:
            return None

        query = "SELECT * FROM arkham_patterns WHERE id = :pattern_id"
        params = {"pattern_id": pattern_id}
        tenant_id = self.get_tenant_id_or_none()
        if tenant_id:
            query += " AND tenant_id = :tenant_id"
            params["tenant_id"] = str(tenant_id)

        row = await self._db.fetch_one(query, params)
        return self._row_to_pattern(row) if row else None

    async def list_patterns(
        self,
        filter: Optional[PatternFilter] = None,
        limit: int = 50,
        offset: int = 0,
        sort: str = "created_at",
        order: str = "desc",
    ) -> List[Pattern]:
        """List patterns with optional filtering."""
        if not self._db:
            return []

        query = "SELECT * FROM arkham_patterns WHERE 1=1"
        params: Dict[str, Any] = {}

        tenant_id = self.get_tenant_id_or_none()
        if tenant_id:
            query += " AND tenant_id = :tenant_id"
            params["tenant_id"] = str(tenant_id)

        if filter:
            if filter.pattern_type:
                query += " AND pattern_type = :pattern_type"
                params["pattern_type"] = filter.pattern_type.value
            if filter.status:
                query += " AND status = :status"
                params["status"] = filter.status.value
            if filter.min_confidence is not None:
                query += " AND confidence >= :min_confidence"
                params["min_confidence"] = filter.min_confidence
            if filter.max_confidence is not None:
                query += " AND confidence <= :max_confidence"
                params["max_confidence"] = filter.max_confidence
            if filter.min_matches is not None:
                query += " AND match_count >= :min_matches"
                params["min_matches"] = filter.min_matches
            if filter.detection_method:
                query += " AND detection_method = :detection_method"
                params["detection_method"] = filter.detection_method.value
            if filter.search_text:
                query += " AND (name LIKE :search_text OR description LIKE :search_text)"
                params["search_text"] = f"%{filter.search_text}%"
            if filter.created_after:
                query += " AND created_at >= :created_after"
                params["created_after"] = filter.created_after.isoformat()
            if filter.created_before:
                query += " AND created_at <= :created_before"
                params["created_before"] = filter.created_before.isoformat()

        # Validate sort column
        valid_sorts = ["created_at", "updated_at", "name", "confidence", "match_count"]
        if sort not in valid_sorts:
            sort = "created_at"
        order_dir = "DESC" if order.lower() == "desc" else "ASC"

        query += f" ORDER BY {sort} {order_dir} LIMIT :limit OFFSET :offset"
        params["limit"] = limit
        params["offset"] = offset

        rows = await self._db.fetch_all(query, params)
        return [self._row_to_pattern(row) for row in rows]

    async def update_pattern(
        self,
        pattern_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        criteria: Optional[PatternCriteria] = None,
        confidence: Optional[float] = None,
        status: Optional[PatternStatus] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Pattern]:
        """Update a pattern."""
        pattern = await self.get_pattern(pattern_id)
        if not pattern:
            return None

        if name is not None:
            pattern.name = name
        if description is not None:
            pattern.description = description
        if criteria is not None:
            pattern.criteria = criteria
        if confidence is not None:
            pattern.confidence = confidence
        if status is not None:
            pattern.status = status
        if metadata is not None:
            pattern.metadata = metadata

        pattern.updated_at = datetime.utcnow()
        await self._save_pattern(pattern, update=True)

        # Emit event
        if self._events:
            await self._events.emit(
                "patterns.pattern.updated",
                {
                    "pattern_id": pattern_id,
                    "name": pattern.name,
                },
                source=self.name,
            )

        return pattern

    async def delete_pattern(self, pattern_id: str) -> bool:
        """Delete a pattern and its matches."""
        if not self._db:
            return False

        # Delete matches first
        await self._db.execute(
            "DELETE FROM arkham_pattern_matches WHERE pattern_id = :pattern_id",
            {"pattern_id": pattern_id},
        )

        # Delete pattern
        await self._db.execute(
            "DELETE FROM arkham_patterns WHERE id = :id",
            {"id": pattern_id},
        )

        return True

    async def confirm_pattern(self, pattern_id: str, notes: Optional[str] = None) -> Optional[Pattern]:
        """Confirm a pattern as valid."""
        pattern = await self.update_pattern(pattern_id, status=PatternStatus.CONFIRMED)

        if pattern and self._events:
            await self._events.emit(
                "patterns.pattern.confirmed",
                {
                    "pattern_id": pattern_id,
                    "name": pattern.name,
                    "notes": notes,
                },
                source=self.name,
            )

        return pattern

    async def dismiss_pattern(self, pattern_id: str, notes: Optional[str] = None) -> Optional[Pattern]:
        """Dismiss a pattern as noise/false positive."""
        pattern = await self.update_pattern(pattern_id, status=PatternStatus.DISMISSED)

        if pattern and self._events:
            await self._events.emit(
                "patterns.pattern.dismissed",
                {
                    "pattern_id": pattern_id,
                    "name": pattern.name,
                    "notes": notes,
                },
                source=self.name,
            )

        return pattern

    # === Pattern Match Methods ===

    async def add_match(
        self,
        pattern_id: str,
        match: PatternMatchCreate,
    ) -> PatternMatch:
        """Add a match to a pattern."""
        match_id = str(uuid4())
        now = datetime.utcnow()

        pattern_match = PatternMatch(
            id=match_id,
            pattern_id=pattern_id,
            source_type=match.source_type,
            source_id=match.source_id,
            source_title=match.source_title,
            match_score=match.match_score,
            excerpt=match.excerpt,
            context=match.context,
            start_char=match.start_char,
            end_char=match.end_char,
            matched_at=now,
            matched_by="system",
            metadata=match.metadata or {},
        )

        await self._save_match(pattern_match)
        await self._update_pattern_counts(pattern_id)

        # Emit event
        if self._events:
            await self._events.emit(
                "patterns.match.added",
                {
                    "pattern_id": pattern_id,
                    "match_id": match_id,
                    "source_type": match.source_type.value,
                    "source_id": match.source_id,
                },
                source=self.name,
            )

        return pattern_match

    async def get_pattern_matches(
        self,
        pattern_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> List[PatternMatch]:
        """Get all matches for a pattern."""
        if not self._db:
            return []

        query = """SELECT * FROM arkham_pattern_matches
               WHERE pattern_id = :pattern_id"""
        params = {"pattern_id": pattern_id, "limit": limit, "offset": offset}

        tenant_id = self.get_tenant_id_or_none()
        if tenant_id:
            query += " AND tenant_id = :tenant_id"
            params["tenant_id"] = str(tenant_id)

        query += " ORDER BY matched_at DESC LIMIT :limit OFFSET :offset"

        rows = await self._db.fetch_all(query, params)
        return [self._row_to_match(row) for row in rows]

    async def remove_match(self, pattern_id: str, match_id: str) -> bool:
        """Remove a match from a pattern."""
        if not self._db:
            return False

        await self._db.execute(
            "DELETE FROM arkham_pattern_matches WHERE id = :id AND pattern_id = :pattern_id",
            {"id": match_id, "pattern_id": pattern_id},
        )
        await self._update_pattern_counts(pattern_id)
        return True

    # === Analysis Methods ===

    async def analyze_documents(
        self,
        request: PatternAnalysisRequest,
        project_id: str | None = None,
    ) -> PatternAnalysisResult:
        """Analyze documents for patterns."""
        import time
        start_time = time.time()
        patterns_detected = []
        matches_found = []
        errors = []

        # Emit start event
        if self._events:
            await self._events.emit(
                "patterns.analysis.started",
                {
                    "document_ids": request.document_ids,
                    "pattern_types": [t.value for t in (request.pattern_types or [])],
                },
                source=self.name,
            )

        try:
            # Get text to analyze
            text = request.text or ""
            if request.document_ids and self._db:
                for doc_id in request.document_ids:
                    # Fetch document content from chunks (same as anomalies shard)
                    doc_content = await self._fetch_document_content(doc_id, project_id=project_id)
                    if doc_content:
                        text += "\n\n" + doc_content

            if not text:
                errors.append("No text to analyze")
            else:
                # LLM-based pattern detection
                if self._llm and self._llm.is_available():
                    llm_patterns = await self._detect_patterns_llm(
                        text,
                        request.pattern_types,
                        request.min_confidence,
                    )
                    patterns_detected.extend(llm_patterns)
                else:
                    # Fallback to keyword-based detection
                    keyword_patterns = await self._detect_patterns_keywords(
                        text,
                        request.min_confidence,
                    )
                    patterns_detected.extend(keyword_patterns)

                # Match against existing patterns
                existing_patterns = await self.list_patterns(limit=100)
                for pattern in existing_patterns:
                    match_result = await self._match_pattern_against_text(pattern, text)
                    if match_result:
                        matches_found.append(match_result)

        except Exception as e:
            logger.error(f"Pattern analysis failed: {e}")
            errors.append(str(e))

        processing_time = (time.time() - start_time) * 1000

        # Emit completion event
        if self._events:
            await self._events.emit(
                "patterns.analysis.completed",
                {
                    "patterns_detected": len(patterns_detected),
                    "matches_found": len(matches_found),
                    "processing_time_ms": processing_time,
                },
                source=self.name,
            )

        return PatternAnalysisResult(
            patterns_detected=patterns_detected,
            matches_found=matches_found,
            documents_analyzed=len(request.document_ids or []),
            processing_time_ms=processing_time,
            errors=errors,
        )

    async def find_correlations(
        self,
        request: CorrelationRequest,
    ) -> CorrelationResult:
        """
        Find correlations between entities using statistical methods.

        Uses Pearson correlation for continuous co-occurrence patterns
        and Spearman for ranked correlations.
        """
        import time
        import math
        start_time = time.time()
        correlations = []

        if not self._db:
            return CorrelationResult(
                correlations=[],
                entities_analyzed=len(request.entity_ids),
                processing_time_ms=(time.time() - start_time) * 1000,
            )

        # Build entity-document occurrence matrix
        entity_docs: Dict[str, set] = {}
        all_docs: set = set()

        for entity_id in request.entity_ids:
            # Query for documents containing this entity
            # Check entity mentions table if it exists
            rows = await self._db.fetch_all(
                """SELECT DISTINCT document_id FROM arkham_entity_mentions
                   WHERE entity_id = :entity_id
                   UNION
                   SELECT DISTINCT source_id as document_id FROM arkham_pattern_matches
                   WHERE source_type = 'entity' AND source_id = :entity_id""",
                {"entity_id": entity_id}
            )

            doc_ids = {row["document_id"] for row in rows if row.get("document_id")}

            # Fallback: check if entity has document references in metadata
            if not doc_ids:
                entity_row = await self._db.fetch_one(
                    "SELECT metadata FROM arkham_entities WHERE id = :id",
                    {"id": entity_id}
                )
                if entity_row:
                    metadata = json.loads(entity_row.get("metadata", "{}"))
                    doc_refs = metadata.get("document_ids", [])
                    doc_ids = set(doc_refs)

            entity_docs[entity_id] = doc_ids
            all_docs.update(doc_ids)

        # Convert to binary occurrence vectors for correlation calculation
        doc_list = list(all_docs)
        if len(doc_list) < 2:
            # Not enough documents to calculate correlation
            for i, entity1 in enumerate(request.entity_ids):
                for entity2 in request.entity_ids[i + 1:]:
                    docs1 = entity_docs.get(entity1, set())
                    docs2 = entity_docs.get(entity2, set())
                    common = docs1 & docs2

                    if len(common) >= request.min_occurrences:
                        correlations.append(Correlation(
                            entity_id_1=entity1,
                            entity_id_2=entity2,
                            correlation_score=1.0 if common else 0.0,
                            co_occurrence_count=len(common),
                            document_ids=list(common),
                            correlation_type="co_occurrence",
                            description=f"Found in {len(common)} common documents",
                        ))

            return CorrelationResult(
                correlations=correlations,
                entities_analyzed=len(request.entity_ids),
                processing_time_ms=(time.time() - start_time) * 1000,
            )

        # Build occurrence vectors
        entity_vectors: Dict[str, List[int]] = {}
        for entity_id in request.entity_ids:
            entity_vectors[entity_id] = [
                1 if doc_id in entity_docs.get(entity_id, set()) else 0
                for doc_id in doc_list
            ]

        # Calculate Pearson correlation for each pair
        for i, entity1 in enumerate(request.entity_ids):
            for entity2 in request.entity_ids[i + 1:]:
                vec1 = entity_vectors.get(entity1, [])
                vec2 = entity_vectors.get(entity2, [])

                if not vec1 or not vec2:
                    continue

                # Calculate co-occurrence
                common_docs = entity_docs.get(entity1, set()) & entity_docs.get(entity2, set())
                co_occurrence_count = len(common_docs)

                # Skip if below minimum occurrences
                if co_occurrence_count < request.min_occurrences:
                    continue

                # Calculate Pearson correlation coefficient
                correlation_score = self._calculate_pearson(vec1, vec2)

                # Determine correlation type and description
                if correlation_score >= 0.7:
                    corr_type = "strong_positive"
                    desc = f"Strong positive correlation (r={correlation_score:.2f})"
                elif correlation_score >= 0.4:
                    corr_type = "moderate_positive"
                    desc = f"Moderate positive correlation (r={correlation_score:.2f})"
                elif correlation_score <= -0.7:
                    corr_type = "strong_negative"
                    desc = f"Strong negative correlation (r={correlation_score:.2f})"
                elif correlation_score <= -0.4:
                    corr_type = "moderate_negative"
                    desc = f"Moderate negative correlation (r={correlation_score:.2f})"
                else:
                    corr_type = "weak"
                    desc = f"Weak correlation (r={correlation_score:.2f})"

                correlations.append(Correlation(
                    entity_id_1=entity1,
                    entity_id_2=entity2,
                    correlation_score=correlation_score,
                    co_occurrence_count=co_occurrence_count,
                    document_ids=list(common_docs)[:20],  # Limit to 20 doc IDs
                    correlation_type=corr_type,
                    description=f"{desc}, co-occurred in {co_occurrence_count} documents",
                ))

        # Sort by absolute correlation score (strongest correlations first)
        correlations.sort(key=lambda c: abs(c.correlation_score), reverse=True)

        processing_time = (time.time() - start_time) * 1000

        return CorrelationResult(
            correlations=correlations,
            entities_analyzed=len(request.entity_ids),
            processing_time_ms=processing_time,
        )

    def _calculate_pearson(self, x: List[int], y: List[int]) -> float:
        """
        Calculate Pearson correlation coefficient between two vectors.

        Returns a value between -1 (perfect negative correlation)
        and 1 (perfect positive correlation).
        """
        import math

        n = len(x)
        if n != len(y) or n == 0:
            return 0.0

        # Calculate means
        mean_x = sum(x) / n
        mean_y = sum(y) / n

        # Calculate standard deviations and covariance
        sum_xy = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n))
        sum_x2 = sum((x[i] - mean_x) ** 2 for i in range(n))
        sum_y2 = sum((y[i] - mean_y) ** 2 for i in range(n))

        # Avoid division by zero
        if sum_x2 == 0 or sum_y2 == 0:
            return 0.0

        # Pearson correlation
        r = sum_xy / math.sqrt(sum_x2 * sum_y2)

        # Clamp to [-1, 1] to handle floating point errors
        return max(-1.0, min(1.0, r))

    def _calculate_spearman(self, x: List[int], y: List[int]) -> float:
        """
        Calculate Spearman rank correlation coefficient.

        Converts values to ranks and applies Pearson correlation.
        """
        def rank(values: List[int]) -> List[float]:
            """Convert values to ranks (1-based, handle ties with average)."""
            sorted_indices = sorted(range(len(values)), key=lambda i: values[i])
            ranks = [0.0] * len(values)

            i = 0
            while i < len(sorted_indices):
                j = i
                # Find ties
                while j < len(sorted_indices) - 1 and values[sorted_indices[j]] == values[sorted_indices[j + 1]]:
                    j += 1
                # Assign average rank to ties
                avg_rank = (i + j) / 2 + 1
                for k in range(i, j + 1):
                    ranks[sorted_indices[k]] = avg_rank
                i = j + 1

            return ranks

        ranks_x = rank(x)
        ranks_y = rank(y)

        # Spearman is Pearson on ranks
        return self._calculate_pearson(
            [int(r) for r in ranks_x],
            [int(r) for r in ranks_y]
        )

    async def get_statistics(self) -> PatternStatistics:
        """Get statistics about patterns in the system."""
        if not self._db:
            return PatternStatistics()

        # Build tenant filter
        tenant_filter = ""
        params: Dict[str, Any] = {}
        tenant_id = self.get_tenant_id_or_none()
        if tenant_id:
            tenant_filter = " WHERE tenant_id = :tenant_id"
            params["tenant_id"] = str(tenant_id)

        # Total patterns
        total = await self._db.fetch_one(
            f"SELECT COUNT(*) as count FROM arkham_patterns{tenant_filter}",
            params
        )
        total_patterns = total["count"] if total else 0

        # By type
        type_rows = await self._db.fetch_all(
            f"SELECT pattern_type, COUNT(*) as count FROM arkham_patterns{tenant_filter} GROUP BY pattern_type",
            params
        )
        by_type = {row["pattern_type"]: row["count"] for row in type_rows}

        # By status
        status_rows = await self._db.fetch_all(
            f"SELECT status, COUNT(*) as count FROM arkham_patterns{tenant_filter} GROUP BY status",
            params
        )
        by_status = {row["status"]: row["count"] for row in status_rows}

        # By detection method
        method_rows = await self._db.fetch_all(
            f"SELECT detection_method, COUNT(*) as count FROM arkham_patterns{tenant_filter} GROUP BY detection_method",
            params
        )
        by_method = {row["detection_method"]: row["count"] for row in method_rows}

        # Total matches
        matches = await self._db.fetch_one(
            f"SELECT COUNT(*) as count FROM arkham_pattern_matches{tenant_filter}",
            params
        )
        total_matches = matches["count"] if matches else 0

        # Averages
        avg_conf = await self._db.fetch_one(
            f"SELECT AVG(confidence) as avg FROM arkham_patterns{tenant_filter}",
            params
        )
        avg_matches = await self._db.fetch_one(
            f"SELECT AVG(match_count) as avg FROM arkham_patterns{tenant_filter}",
            params
        )

        return PatternStatistics(
            total_patterns=total_patterns,
            by_type=by_type,
            by_status=by_status,
            by_detection_method=by_method,
            total_matches=total_matches,
            avg_confidence=avg_conf["avg"] if avg_conf and avg_conf["avg"] else 0.0,
            avg_matches_per_pattern=avg_matches["avg"] if avg_matches and avg_matches["avg"] else 0.0,
            patterns_confirmed=by_status.get("confirmed", 0),
            patterns_dismissed=by_status.get("dismissed", 0),
            patterns_pending_review=by_status.get("detected", 0),
        )

    async def get_count(self, status: Optional[str] = None) -> int:
        """Get count of patterns, optionally filtered by status."""
        if not self._db:
            return 0

        query = "SELECT COUNT(*) as count FROM arkham_patterns WHERE 1=1"
        params: Dict[str, Any] = {}

        tenant_id = self.get_tenant_id_or_none()
        if tenant_id:
            query += " AND tenant_id = :tenant_id"
            params["tenant_id"] = str(tenant_id)

        if status:
            query += " AND status = :status"
            params["status"] = status

        result = await self._db.fetch_one(query, params)
        return result["count"] if result else 0

    async def get_match_count(self, pattern_id: str) -> int:
        """Get count of matches for a pattern."""
        if not self._db:
            return 0

        query = "SELECT COUNT(*) as count FROM arkham_pattern_matches WHERE pattern_id = :pattern_id"
        params = {"pattern_id": pattern_id}

        tenant_id = self.get_tenant_id_or_none()
        if tenant_id:
            query += " AND tenant_id = :tenant_id"
            params["tenant_id"] = str(tenant_id)

        result = await self._db.fetch_one(query, params)
        return result["count"] if result else 0

    # === Private Helper Methods ===

    async def _save_pattern(self, pattern: Pattern, update: bool = False) -> None:
        """Save a pattern to the database."""
        if not self._db:
            return

        criteria_json = pattern.criteria.model_dump_json() if pattern.criteria else "{}"
        metadata_json = json.dumps(pattern.metadata)

        params = {
            "id": pattern.id,
            "name": pattern.name,
            "description": pattern.description,
            "pattern_type": pattern.pattern_type.value if isinstance(pattern.pattern_type, PatternType) else pattern.pattern_type,
            "status": pattern.status.value if isinstance(pattern.status, PatternStatus) else pattern.status,
            "confidence": pattern.confidence,
            "match_count": pattern.match_count,
            "document_count": pattern.document_count,
            "entity_count": pattern.entity_count,
            "first_detected": pattern.first_detected.isoformat() if pattern.first_detected else None,
            "last_matched": pattern.last_matched.isoformat() if pattern.last_matched else None,
            "detection_method": pattern.detection_method.value if isinstance(pattern.detection_method, DetectionMethod) else pattern.detection_method,
            "detection_model": pattern.detection_model,
            "criteria": criteria_json,
            "created_at": pattern.created_at.isoformat(),
            "updated_at": pattern.updated_at.isoformat(),
            "created_by": pattern.created_by,
            "metadata": metadata_json,
        }

        if update:
            await self._db.execute("""
                UPDATE arkham_patterns SET
                    name=:name, description=:description, pattern_type=:pattern_type, status=:status, confidence=:confidence,
                    match_count=:match_count, document_count=:document_count, entity_count=:entity_count,
                    first_detected=:first_detected, last_matched=:last_matched,
                    detection_method=:detection_method, detection_model=:detection_model, criteria=:criteria,
                    created_at=:created_at, updated_at=:updated_at, created_by=:created_by, metadata=:metadata
                WHERE id=:id
            """, params)
        else:
            await self._db.execute("""
                INSERT INTO arkham_patterns (
                    id, name, description, pattern_type, status, confidence,
                    match_count, document_count, entity_count,
                    first_detected, last_matched,
                    detection_method, detection_model, criteria,
                    created_at, updated_at, created_by, metadata
                ) VALUES (:id, :name, :description, :pattern_type, :status, :confidence,
                    :match_count, :document_count, :entity_count,
                    :first_detected, :last_matched,
                    :detection_method, :detection_model, :criteria,
                    :created_at, :updated_at, :created_by, :metadata)
            """, params)

    async def _save_match(self, match: PatternMatch) -> None:
        """Save a match to the database."""
        if not self._db:
            return

        params = {
            "id": match.id,
            "pattern_id": match.pattern_id,
            "source_type": match.source_type.value if isinstance(match.source_type, SourceType) else match.source_type,
            "source_id": match.source_id,
            "source_title": match.source_title,
            "match_score": match.match_score,
            "excerpt": match.excerpt,
            "context": match.context,
            "start_char": match.start_char,
            "end_char": match.end_char,
            "matched_at": match.matched_at.isoformat(),
            "matched_by": match.matched_by,
            "metadata": json.dumps(match.metadata),
        }

        await self._db.execute("""
            INSERT INTO arkham_pattern_matches (
                id, pattern_id, source_type, source_id, source_title,
                match_score, excerpt, context, start_char, end_char,
                matched_at, matched_by, metadata
            ) VALUES (:id, :pattern_id, :source_type, :source_id, :source_title,
                :match_score, :excerpt, :context, :start_char, :end_char,
                :matched_at, :matched_by, :metadata)
        """, params)

    async def _update_pattern_counts(self, pattern_id: str) -> None:
        """Update match counts on a pattern."""
        if not self._db:
            return

        total = await self._db.fetch_one(
            "SELECT COUNT(*) as count FROM arkham_pattern_matches WHERE pattern_id = :pattern_id",
            {"pattern_id": pattern_id},
        )

        doc_count = await self._db.fetch_one(
            """SELECT COUNT(DISTINCT source_id) as count
               FROM arkham_pattern_matches
               WHERE pattern_id = :pattern_id AND source_type = 'document'""",
            {"pattern_id": pattern_id},
        )

        entity_count = await self._db.fetch_one(
            """SELECT COUNT(DISTINCT source_id) as count
               FROM arkham_pattern_matches
               WHERE pattern_id = :pattern_id AND source_type = 'entity'""",
            {"pattern_id": pattern_id},
        )

        await self._db.execute("""
            UPDATE arkham_patterns SET
                match_count = :match_count,
                document_count = :document_count,
                entity_count = :entity_count,
                last_matched = :last_matched,
                updated_at = :updated_at
            WHERE id = :id
        """, {
            "match_count": total["count"] if total else 0,
            "document_count": doc_count["count"] if doc_count else 0,
            "entity_count": entity_count["count"] if entity_count else 0,
            "last_matched": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "id": pattern_id,
        })

    async def _check_source_against_patterns(
        self,
        source_type: SourceType,
        source_id: str,
        content: Optional[str] = None,
    ) -> List[PatternMatch]:
        """
        Check a source against all active patterns.

        Args:
            source_type: Type of source (document, entity, claim, etc.)
            source_id: ID of the source
            content: Optional pre-fetched content (avoids double-fetch)

        Returns:
            List of matches created
        """
        matches_created = []

        # Get all confirmed patterns (active patterns that should be matched)
        patterns = await self.list_patterns(
            filter=PatternFilter(status=PatternStatus.CONFIRMED),
            limit=100,
        )

        # Also check detected patterns with high confidence
        detected_patterns = await self.list_patterns(
            filter=PatternFilter(status=PatternStatus.DETECTED, min_confidence=0.7),
            limit=50,
        )
        patterns.extend(detected_patterns)

        # Get source title for match metadata
        _, title = await self._fetch_source_content(source_type, source_id)

        for pattern in patterns:
            # Check if source matches pattern criteria
            matches, score, excerpt = await self._source_matches_pattern(
                source_type, source_id, pattern
            )

            if matches and score >= 0.5:
                # Check for duplicate match
                existing = await self._db.fetch_one(
                    """SELECT id FROM arkham_pattern_matches
                       WHERE pattern_id = :pattern_id
                       AND source_type = :source_type
                       AND source_id = :source_id""",
                    {
                        "pattern_id": pattern.id,
                        "source_type": source_type.value,
                        "source_id": source_id,
                    }
                ) if self._db else None

                if not existing:
                    match = await self.add_match(
                        pattern.id,
                        PatternMatchCreate(
                            source_type=source_type,
                            source_id=source_id,
                            source_title=title,
                            match_score=score,
                            excerpt=excerpt,
                        ),
                    )
                    matches_created.append(match)

        return matches_created

    async def _source_matches_pattern(
        self,
        source_type: SourceType,
        source_id: str,
        pattern: Pattern,
    ) -> Tuple[bool, float, Optional[str]]:
        """
        Check if a source matches a pattern's criteria.

        Uses graceful degradation:
        1. Keyword matching (always available)
        2. Regex matching (always available)
        3. Vector similarity (if vectors service available)

        Returns:
            Tuple of (matches, score, excerpt)
        """
        # Fetch source content
        content, title = await self._fetch_source_content(source_type, source_id)
        if not content:
            return False, 0.0, None

        content_lower = content.lower()
        criteria = pattern.criteria
        match_scores = []
        excerpt = None

        # 1. Keyword matching (always available)
        if criteria.keywords:
            keyword_matches = 0
            for keyword in criteria.keywords:
                if keyword.lower() in content_lower:
                    keyword_matches += 1
                    # Capture excerpt around first match
                    if not excerpt:
                        idx = content_lower.find(keyword.lower())
                        start = max(0, idx - 50)
                        end = min(len(content), idx + len(keyword) + 50)
                        excerpt = content[start:end]

            if keyword_matches > 0:
                keyword_score = keyword_matches / len(criteria.keywords)
                match_scores.append(keyword_score)

        # 2. Regex matching (always available)
        if criteria.regex_patterns:
            regex_matches = 0
            for regex_pattern in criteria.regex_patterns:
                try:
                    match = re.search(regex_pattern, content, re.IGNORECASE)
                    if match:
                        regex_matches += 1
                        if not excerpt:
                            start = max(0, match.start() - 50)
                            end = min(len(content), match.end() + 50)
                            excerpt = content[start:end]
                except re.error:
                    logger.warning(f"Invalid regex pattern: {regex_pattern}")

            if regex_matches > 0:
                regex_score = regex_matches / len(criteria.regex_patterns)
                match_scores.append(regex_score)

        # 3. Vector similarity (if vectors service available)
        if self._vectors and criteria.keywords:
            try:
                # Create query from pattern keywords/description
                query_text = " ".join(criteria.keywords) + " " + (pattern.description or "")

                # Search for similar content
                results = await self._vectors.search(
                    collection="documents",
                    query=query_text,
                    limit=5,
                    filter={"source_id": source_id} if source_type == SourceType.DOCUMENT else None
                )

                if results and len(results) > 0:
                    # Use highest similarity score
                    best_similarity = max(r.get("score", 0) for r in results)
                    if best_similarity >= criteria.similarity_threshold:
                        match_scores.append(best_similarity)

            except Exception as e:
                logger.debug(f"Vector similarity check failed (graceful degradation): {e}")

        # Check minimum occurrences for keyword patterns
        if criteria.keywords and criteria.min_occurrences > 1:
            total_occurrences = sum(
                content_lower.count(kw.lower()) for kw in criteria.keywords
            )
            if total_occurrences < criteria.min_occurrences:
                return False, 0.0, None

        # Calculate final score
        if not match_scores:
            return False, 0.0, None

        final_score = sum(match_scores) / len(match_scores)
        matches = final_score >= 0.5  # Match if average score >= 50%

        return matches, final_score, excerpt

    async def _fetch_source_content(
        self,
        source_type: SourceType,
        source_id: str,
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Fetch content from a source for pattern matching.

        Uses graceful degradation - tries multiple approaches:
        1. Direct Frame shard access (if available)
        2. Database query (if schema known)
        3. Returns None if content unavailable

        Returns:
            Tuple of (content, title)
        """
        content = None
        title = None

        try:
            if source_type == SourceType.DOCUMENT:
                # Try documents shard
                documents_shard = self.frame.shards.get("documents")
                if documents_shard and hasattr(documents_shard, "get"):
                    doc = await documents_shard.get(source_id)
                    if doc:
                        content = getattr(doc, "content", None) or getattr(doc, "text", None)
                        title = getattr(doc, "name", None) or getattr(doc, "title", None)

                # Fallback: direct DB query using correct schema
                if not content and self._db:
                    # Get title from documents table
                    doc_row = await self._db.fetch_one(
                        "SELECT filename FROM arkham_frame.documents WHERE id = :id",
                        {"id": source_id}
                    )
                    if doc_row:
                        title = doc_row.get("filename")

                    # Get content from chunks table
                    chunk_rows = await self._db.fetch_all(
                        """SELECT text FROM arkham_frame.chunks
                           WHERE document_id = :id
                           ORDER BY chunk_index""",
                        {"id": source_id}
                    )
                    if chunk_rows:
                        content = "\n".join(row.get("text", "") for row in chunk_rows if row.get("text"))

            elif source_type == SourceType.ENTITY:
                # Try entities shard
                entities_shard = self.frame.shards.get("entities")
                if entities_shard and hasattr(entities_shard, "get"):
                    entity = await entities_shard.get(source_id)
                    if entity:
                        title = getattr(entity, "name", None)
                        # Build content from entity properties
                        props = getattr(entity, "properties", {}) or {}
                        content = f"{title} " + " ".join(str(v) for v in props.values())

                # Fallback: direct DB query
                if not content and self._db:
                    row = await self._db.fetch_one(
                        "SELECT name, properties FROM arkham_entities WHERE id = :id",
                        {"id": source_id}
                    )
                    if row:
                        title = row.get("name")
                        props = json.loads(row.get("properties", "{}"))
                        content = f"{title} " + " ".join(str(v) for v in props.values())

            elif source_type == SourceType.CLAIM:
                # Try claims shard
                claims_shard = self.frame.shards.get("claims")
                if claims_shard and hasattr(claims_shard, "get"):
                    claim = await claims_shard.get(source_id)
                    if claim:
                        content = getattr(claim, "text", None) or getattr(claim, "content", None)
                        title = content[:50] + "..." if content and len(content) > 50 else content

                # Fallback: direct DB query
                if not content and self._db:
                    row = await self._db.fetch_one(
                        "SELECT text, claim_text FROM arkham_claims WHERE id = :id",
                        {"id": source_id}
                    )
                    if row:
                        content = row.get("text") or row.get("claim_text")
                        title = content[:50] + "..." if content and len(content) > 50 else content

            elif source_type == SourceType.EVENT:
                # Try timeline shard
                timeline_shard = self.frame.shards.get("timeline")
                if timeline_shard and hasattr(timeline_shard, "get_event"):
                    event = await timeline_shard.get_event(source_id)
                    if event:
                        title = getattr(event, "title", None) or getattr(event, "description", None)
                        content = f"{title} {getattr(event, 'description', '')}"

                # Fallback: direct DB query
                if not content and self._db:
                    row = await self._db.fetch_one(
                        "SELECT title, description FROM arkham_timeline_events WHERE id = :id",
                        {"id": source_id}
                    )
                    if row:
                        title = row.get("title") or row.get("description")
                        content = f"{title} {row.get('description', '')}"

            elif source_type == SourceType.CHUNK:
                # Direct DB query for chunks using correct schema
                if self._db:
                    row = await self._db.fetch_one(
                        "SELECT text, document_id FROM arkham_frame.chunks WHERE id = :id",
                        {"id": source_id}
                    )
                    if row:
                        content = row.get("text")
                        title = f"Chunk from {row.get('document_id', 'unknown')}"

        except Exception as e:
            logger.debug(f"Failed to fetch source content for {source_type}:{source_id}: {e}")

        return content, title

    async def _fetch_document_content(self, doc_id: str, project_id: str | None = None) -> Optional[str]:
        """
        Fetch document content from the database.

        Content is stored in arkham_frame.chunks table, joined from document.
        """
        if not self._db:
            return None

        try:
            # Get content from chunks table (where text is stored), project-scoped if provided
            if project_id:
                chunk_rows = await self._db.fetch_all(
                    """SELECT c.text FROM arkham_frame.chunks c
                       INNER JOIN arkham_frame.documents d ON d.id = c.document_id
                       WHERE c.document_id = :doc_id AND d.project_id = :project_id
                       ORDER BY c.chunk_index""",
                    {"doc_id": doc_id, "project_id": str(project_id)},
                )
            else:
                chunk_rows = await self._db.fetch_all(
                    """SELECT text FROM arkham_frame.chunks
                       WHERE document_id = :doc_id
                       ORDER BY chunk_index""",
                    {"doc_id": doc_id},
                )

            if chunk_rows:
                # Combine all chunks
                text = "\n".join(row.get("text", "") for row in chunk_rows if row.get("text"))
                return text

            # Fallback: try content column if it exists
            if project_id:
                doc_row = await self._db.fetch_one(
                    """SELECT content FROM arkham_frame.documents
                       WHERE id = :doc_id AND project_id = :project_id""",
                    {"doc_id": doc_id, "project_id": str(project_id)},
                )
            else:
                doc_row = await self._db.fetch_one(
                    """SELECT content FROM arkham_frame.documents WHERE id = :doc_id""",
                    {"doc_id": doc_id},
                )
            if doc_row and doc_row.get("content"):
                return doc_row.get("content")

            return None

        except Exception as e:
            logger.debug(f"Failed to fetch document content for {doc_id}: {e}")
            return None

    async def _detect_patterns_llm(
        self,
        text: str,
        pattern_types: Optional[List[PatternType]],
        min_confidence: float,
    ) -> List[Pattern]:
        """
        Detect patterns using LLM with structured output.

        Uses chain-of-thought reasoning and structured JSON output.
        """
        if not self._llm:
            return []

        # Limit text to prevent context overflow
        text_sample = text[:12000] if len(text) > 12000 else text
        text_preview = text[:500] + "..." if len(text) > 500 else text

        # Build type descriptions for the prompt
        type_descriptions = {
            PatternType.RECURRING_THEME: "Themes, topics, or subjects that appear multiple times across the text",
            PatternType.BEHAVIORAL: "Consistent actions, behaviors, or patterns of conduct by entities",
            PatternType.TEMPORAL: "Time-based patterns like cycles, sequences, or scheduling patterns",
            PatternType.CORRELATION: "Statistical relationships or associations between entities",
            PatternType.LINGUISTIC: "Language patterns, writing styles, or phraseological similarities",
            PatternType.STRUCTURAL: "Document structure patterns, formatting, or organization",
            PatternType.CUSTOM: "Other patterns not fitting the above categories",
        }

        types_to_check = pattern_types or list(PatternType)
        types_str = "\n".join(f"- {t.value}: {type_descriptions.get(t, t.value)}" for t in types_to_check)

        prompt = f"""You are an intelligence analyst identifying patterns in text.

## Task
Analyze the following text and identify significant patterns. For each pattern:
1. Think step-by-step about what makes it a pattern
2. Consider the evidence supporting it
3. Assign a confidence score based on evidence strength

## Pattern Types to Look For
{types_str}

## Text to Analyze
{text_sample}

## Output Format
Return a JSON array of patterns. Each pattern should have:
- "name": Brief descriptive name (3-6 words)
- "description": What the pattern represents and why it matters
- "type": One of [{', '.join(f'"{t.value}"' for t in types_to_check)}]
- "confidence": Float 0.0-1.0 based on evidence strength
- "keywords": Array of key terms that identify this pattern
- "evidence": Array of excerpts/quotes supporting this pattern
- "reasoning": Brief explanation of why this is a pattern

## Guidelines
- Only report patterns with confidence >= {min_confidence}
- Focus on patterns that appear multiple times or have strong evidence
- Be specific rather than generic
- Limit to 5-10 most significant patterns

## Response
Return ONLY the JSON array, no other text:
```json
[
  {{
    "name": "Pattern Name",
    "description": "What this pattern means",
    "type": "recurring_theme",
    "confidence": 0.8,
    "keywords": ["keyword1", "keyword2"],
    "evidence": ["quote 1", "quote 2"],
    "reasoning": "Why this is a pattern"
  }}
]
```"""

        try:
            llm_response = await self._llm.generate(prompt)
            # Extract text from LLMResponse object
            response_text = llm_response.text if hasattr(llm_response, 'text') else str(llm_response)
            patterns_data = self._parse_llm_patterns(response_text)

            patterns = []
            for data in patterns_data:
                conf = data.get("confidence", 0)
                if conf < min_confidence:
                    continue

                # Extract keywords for pattern criteria
                keywords = data.get("keywords", [])
                if not keywords and data.get("name"):
                    # Generate keywords from name if not provided
                    keywords = [w.lower() for w in data["name"].split() if len(w) > 3]

                # Map type string to enum
                pattern_type_str = data.get("type", "recurring_theme")
                try:
                    pattern_type = PatternType(pattern_type_str)
                except ValueError:
                    pattern_type = PatternType.RECURRING_THEME

                # Create pattern with criteria
                criteria = PatternCriteria(
                    keywords=keywords[:10],  # Limit keywords
                    min_occurrences=2,
                )

                # Build description including reasoning
                description = data.get("description", "")
                reasoning = data.get("reasoning", "")
                if reasoning and reasoning not in description:
                    description = f"{description}\n\nReasoning: {reasoning}"

                pattern = await self.create_pattern(
                    name=data.get("name", "Unnamed Pattern")[:100],
                    description=description[:500],
                    pattern_type=pattern_type,
                    criteria=criteria,
                    confidence=min(1.0, max(0.0, conf)),
                    detection_method=DetectionMethod.LLM,
                    detection_model=getattr(self._llm, "model", None),
                    metadata={
                        "evidence": data.get("evidence", [])[:5],
                        "llm_response": True,
                    },
                )
                patterns.append(pattern)

            logger.info(f"LLM detected {len(patterns)} patterns")
            return patterns

        except Exception as e:
            logger.error(f"LLM pattern detection failed: {e}")
            import traceback
            traceback.print_exc()
            return []

    async def _detect_patterns_keywords(
        self,
        text: str,
        min_confidence: float,
    ) -> List[Pattern]:
        """Detect patterns using keyword analysis."""
        # Simple keyword frequency analysis
        patterns = []
        words = text.lower().split()
        word_counts = {}

        for word in words:
            if len(word) > 4:  # Skip short words
                word_counts[word] = word_counts.get(word, 0) + 1

        # Find repeated phrases
        for word, count in word_counts.items():
            if count >= 5:  # Appears at least 5 times
                confidence = min(count / 20, 1.0)  # Scale to 0-1
                if confidence >= min_confidence:
                    pattern = await self.create_pattern(
                        name=f"Recurring: {word}",
                        description=f"The term '{word}' appears {count} times",
                        pattern_type=PatternType.RECURRING_THEME,
                        confidence=confidence,
                        detection_method=DetectionMethod.AUTOMATED,
                        criteria=PatternCriteria(keywords=[word], min_occurrences=count),
                    )
                    patterns.append(pattern)

        return patterns[:10]  # Limit to top 10

    async def _match_pattern_against_text(
        self,
        pattern: Pattern,
        text: str,
    ) -> Optional[PatternMatch]:
        """Check if text matches a pattern."""
        text_lower = text.lower()

        # Check keywords
        if pattern.criteria.keywords:
            for keyword in pattern.criteria.keywords:
                if keyword.lower() in text_lower:
                    # Find excerpt
                    idx = text_lower.find(keyword.lower())
                    start = max(0, idx - 100)
                    end = min(len(text), idx + len(keyword) + 100)
                    excerpt = text[start:end]

                    return PatternMatch(
                        id=str(uuid4()),
                        pattern_id=pattern.id,
                        source_type=SourceType.DOCUMENT,
                        source_id="text",
                        match_score=0.8,
                        excerpt=excerpt,
                        start_char=idx,
                        end_char=idx + len(keyword),
                        matched_at=datetime.utcnow(),
                    )

        return None

    def _row_to_pattern(self, row: Dict[str, Any]) -> Pattern:
        """Convert database row to Pattern object."""
        criteria_data = json.loads(row["criteria"] or "{}")
        return Pattern(
            id=row["id"],
            name=row["name"],
            description=row["description"] or "",
            pattern_type=PatternType(row["pattern_type"]),
            status=PatternStatus(row["status"]),
            confidence=row["confidence"],
            match_count=row["match_count"],
            document_count=row["document_count"],
            entity_count=row["entity_count"],
            first_detected=datetime.fromisoformat(row["first_detected"]) if row["first_detected"] else datetime.utcnow(),
            last_matched=datetime.fromisoformat(row["last_matched"]) if row["last_matched"] else None,
            detection_method=DetectionMethod(row["detection_method"]),
            detection_model=row["detection_model"],
            criteria=PatternCriteria(**criteria_data),
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else datetime.utcnow(),
            updated_at=datetime.fromisoformat(row["updated_at"]) if row["updated_at"] else datetime.utcnow(),
            created_by=row["created_by"],
            metadata=json.loads(row["metadata"] or "{}"),
        )

    def _row_to_match(self, row: Dict[str, Any]) -> PatternMatch:
        """Convert database row to PatternMatch object."""
        return PatternMatch(
            id=row["id"],
            pattern_id=row["pattern_id"],
            source_type=SourceType(row["source_type"]),
            source_id=row["source_id"],
            source_title=row["source_title"],
            match_score=row["match_score"],
            excerpt=row["excerpt"],
            context=row["context"],
            start_char=row["start_char"],
            end_char=row["end_char"],
            matched_at=datetime.fromisoformat(row["matched_at"]) if row["matched_at"] else datetime.utcnow(),
            matched_by=row["matched_by"],
            metadata=json.loads(row["metadata"] or "{}"),
        )

    def _parse_llm_patterns(self, response: str) -> List[Dict[str, Any]]:
        """
        Parse LLM pattern detection response.

        Handles various response formats:
        - Direct JSON array
        - JSON wrapped in markdown code blocks
        - JSON with explanatory text before/after
        """
        if not response:
            return []

        # Clean up response
        text = response.strip()

        # Try to find JSON array in various formats
        patterns = []

        # 1. Try direct JSON parsing first
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError:
            pass

        # 2. Look for JSON in markdown code blocks
        code_block_patterns = [
            r'```json\s*\n?(.*?)\n?```',
            r'```\s*\n?(.*?)\n?```',
        ]
        for pattern in code_block_patterns:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                try:
                    parsed = json.loads(match.group(1).strip())
                    if isinstance(parsed, list):
                        return parsed
                except json.JSONDecodeError:
                    pass

        # 3. Find JSON array by brackets
        start = text.find("[")
        end = text.rfind("]")
        if start >= 0 and end > start:
            try:
                parsed = json.loads(text[start:end + 1])
                if isinstance(parsed, list):
                    return parsed
            except json.JSONDecodeError:
                # Try to fix common JSON issues
                json_text = text[start:end + 1]
                # Fix trailing commas
                json_text = re.sub(r',\s*}', '}', json_text)
                json_text = re.sub(r',\s*]', ']', json_text)
                try:
                    parsed = json.loads(json_text)
                    if isinstance(parsed, list):
                        return parsed
                except json.JSONDecodeError:
                    pass

        # 4. Try to extract individual JSON objects
        object_pattern = r'\{[^{}]*\}'
        matches = re.findall(object_pattern, text)
        for match in matches:
            try:
                obj = json.loads(match)
                if isinstance(obj, dict) and ("name" in obj or "type" in obj):
                    patterns.append(obj)
            except json.JSONDecodeError:
                pass

        if patterns:
            return patterns

        logger.warning(f"Failed to parse LLM patterns response: {text[:200]}...")
        return []
