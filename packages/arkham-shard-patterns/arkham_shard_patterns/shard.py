"""
Patterns Shard - Main Shard Implementation

Cross-document pattern detection - identifies recurring themes,
behaviors, and relationships across the document corpus.
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
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

        row = await self._db.fetch_one(
            "SELECT * FROM arkham_patterns WHERE id = ?",
            [pattern_id],
        )
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
        params = []

        if filter:
            if filter.pattern_type:
                query += " AND pattern_type = ?"
                params.append(filter.pattern_type.value)
            if filter.status:
                query += " AND status = ?"
                params.append(filter.status.value)
            if filter.min_confidence is not None:
                query += " AND confidence >= ?"
                params.append(filter.min_confidence)
            if filter.max_confidence is not None:
                query += " AND confidence <= ?"
                params.append(filter.max_confidence)
            if filter.min_matches is not None:
                query += " AND match_count >= ?"
                params.append(filter.min_matches)
            if filter.detection_method:
                query += " AND detection_method = ?"
                params.append(filter.detection_method.value)
            if filter.search_text:
                query += " AND (name LIKE ? OR description LIKE ?)"
                params.extend([f"%{filter.search_text}%", f"%{filter.search_text}%"])
            if filter.created_after:
                query += " AND created_at >= ?"
                params.append(filter.created_after.isoformat())
            if filter.created_before:
                query += " AND created_at <= ?"
                params.append(filter.created_before.isoformat())

        # Validate sort column
        valid_sorts = ["created_at", "updated_at", "name", "confidence", "match_count"]
        if sort not in valid_sorts:
            sort = "created_at"
        order_dir = "DESC" if order.lower() == "desc" else "ASC"

        query += f" ORDER BY {sort} {order_dir} LIMIT ? OFFSET ?"
        params.extend([limit, offset])

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
            "DELETE FROM arkham_pattern_matches WHERE pattern_id = ?",
            [pattern_id],
        )

        # Delete pattern
        await self._db.execute(
            "DELETE FROM arkham_patterns WHERE id = ?",
            [pattern_id],
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

        rows = await self._db.fetch_all(
            """SELECT * FROM arkham_pattern_matches
               WHERE pattern_id = ?
               ORDER BY matched_at DESC
               LIMIT ? OFFSET ?""",
            [pattern_id, limit, offset],
        )
        return [self._row_to_match(row) for row in rows]

    async def remove_match(self, pattern_id: str, match_id: str) -> bool:
        """Remove a match from a pattern."""
        if not self._db:
            return False

        await self._db.execute(
            "DELETE FROM arkham_pattern_matches WHERE id = ? AND pattern_id = ?",
            [match_id, pattern_id],
        )
        await self._update_pattern_counts(pattern_id)
        return True

    # === Analysis Methods ===

    async def analyze_documents(
        self,
        request: PatternAnalysisRequest,
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
            if request.document_ids and hasattr(self.frame, "documents"):
                for doc_id in request.document_ids:
                    doc = await self.frame.documents.get(doc_id)
                    if doc and hasattr(doc, "content"):
                        text += "\n\n" + doc.content

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
        """Find correlations between entities."""
        import time
        start_time = time.time()
        correlations = []

        if not self._db:
            return CorrelationResult(
                correlations=[],
                entities_analyzed=len(request.entity_ids),
                processing_time_ms=(time.time() - start_time) * 1000,
            )

        # Find co-occurrences in documents
        entity_pairs = []
        for i, entity1 in enumerate(request.entity_ids):
            for entity2 in request.entity_ids[i + 1:]:
                entity_pairs.append((entity1, entity2))

        for entity1, entity2 in entity_pairs:
            # Query for co-occurrence (simplified - would need document-entity links)
            # This is a placeholder - actual implementation depends on data model
            correlation = Correlation(
                entity_id_1=entity1,
                entity_id_2=entity2,
                correlation_score=0.5,  # Placeholder
                co_occurrence_count=0,
                document_ids=[],
                correlation_type="co_occurrence",
                description=f"Co-occurrence analysis between {entity1} and {entity2}",
            )
            correlations.append(correlation)

        processing_time = (time.time() - start_time) * 1000

        return CorrelationResult(
            correlations=correlations,
            entities_analyzed=len(request.entity_ids),
            processing_time_ms=processing_time,
        )

    async def get_statistics(self) -> PatternStatistics:
        """Get statistics about patterns in the system."""
        if not self._db:
            return PatternStatistics()

        # Total patterns
        total = await self._db.fetch_one(
            "SELECT COUNT(*) as count FROM arkham_patterns"
        )
        total_patterns = total["count"] if total else 0

        # By type
        type_rows = await self._db.fetch_all(
            "SELECT pattern_type, COUNT(*) as count FROM arkham_patterns GROUP BY pattern_type"
        )
        by_type = {row["pattern_type"]: row["count"] for row in type_rows}

        # By status
        status_rows = await self._db.fetch_all(
            "SELECT status, COUNT(*) as count FROM arkham_patterns GROUP BY status"
        )
        by_status = {row["status"]: row["count"] for row in status_rows}

        # By detection method
        method_rows = await self._db.fetch_all(
            "SELECT detection_method, COUNT(*) as count FROM arkham_patterns GROUP BY detection_method"
        )
        by_method = {row["detection_method"]: row["count"] for row in method_rows}

        # Total matches
        matches = await self._db.fetch_one(
            "SELECT COUNT(*) as count FROM arkham_pattern_matches"
        )
        total_matches = matches["count"] if matches else 0

        # Averages
        avg_conf = await self._db.fetch_one(
            "SELECT AVG(confidence) as avg FROM arkham_patterns"
        )
        avg_matches = await self._db.fetch_one(
            "SELECT AVG(match_count) as avg FROM arkham_patterns"
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

        if status:
            result = await self._db.fetch_one(
                "SELECT COUNT(*) as count FROM arkham_patterns WHERE status = ?",
                [status],
            )
        else:
            result = await self._db.fetch_one(
                "SELECT COUNT(*) as count FROM arkham_patterns"
            )

        return result["count"] if result else 0

    async def get_match_count(self, pattern_id: str) -> int:
        """Get count of matches for a pattern."""
        if not self._db:
            return 0

        result = await self._db.fetch_one(
            "SELECT COUNT(*) as count FROM arkham_pattern_matches WHERE pattern_id = ?",
            [pattern_id],
        )
        return result["count"] if result else 0

    # === Private Helper Methods ===

    async def _save_pattern(self, pattern: Pattern, update: bool = False) -> None:
        """Save a pattern to the database."""
        if not self._db:
            return

        criteria_json = pattern.criteria.model_dump_json() if pattern.criteria else "{}"
        metadata_json = json.dumps(pattern.metadata)

        data = (
            pattern.id,
            pattern.name,
            pattern.description,
            pattern.pattern_type.value if isinstance(pattern.pattern_type, PatternType) else pattern.pattern_type,
            pattern.status.value if isinstance(pattern.status, PatternStatus) else pattern.status,
            pattern.confidence,
            pattern.match_count,
            pattern.document_count,
            pattern.entity_count,
            pattern.first_detected.isoformat() if pattern.first_detected else None,
            pattern.last_matched.isoformat() if pattern.last_matched else None,
            pattern.detection_method.value if isinstance(pattern.detection_method, DetectionMethod) else pattern.detection_method,
            pattern.detection_model,
            criteria_json,
            pattern.created_at.isoformat(),
            pattern.updated_at.isoformat(),
            pattern.created_by,
            metadata_json,
        )

        if update:
            await self._db.execute("""
                UPDATE arkham_patterns SET
                    name=?, description=?, pattern_type=?, status=?, confidence=?,
                    match_count=?, document_count=?, entity_count=?,
                    first_detected=?, last_matched=?,
                    detection_method=?, detection_model=?, criteria=?,
                    created_at=?, updated_at=?, created_by=?, metadata=?
                WHERE id=?
            """, data[1:] + (pattern.id,))
        else:
            await self._db.execute("""
                INSERT INTO arkham_patterns (
                    id, name, description, pattern_type, status, confidence,
                    match_count, document_count, entity_count,
                    first_detected, last_matched,
                    detection_method, detection_model, criteria,
                    created_at, updated_at, created_by, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, data)

    async def _save_match(self, match: PatternMatch) -> None:
        """Save a match to the database."""
        if not self._db:
            return

        data = (
            match.id,
            match.pattern_id,
            match.source_type.value if isinstance(match.source_type, SourceType) else match.source_type,
            match.source_id,
            match.source_title,
            match.match_score,
            match.excerpt,
            match.context,
            match.start_char,
            match.end_char,
            match.matched_at.isoformat(),
            match.matched_by,
            json.dumps(match.metadata),
        )

        await self._db.execute("""
            INSERT INTO arkham_pattern_matches (
                id, pattern_id, source_type, source_id, source_title,
                match_score, excerpt, context, start_char, end_char,
                matched_at, matched_by, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, data)

    async def _update_pattern_counts(self, pattern_id: str) -> None:
        """Update match counts on a pattern."""
        if not self._db:
            return

        total = await self._db.fetch_one(
            "SELECT COUNT(*) as count FROM arkham_pattern_matches WHERE pattern_id = ?",
            [pattern_id],
        )

        doc_count = await self._db.fetch_one(
            """SELECT COUNT(DISTINCT source_id) as count
               FROM arkham_pattern_matches
               WHERE pattern_id = ? AND source_type = 'document'""",
            [pattern_id],
        )

        entity_count = await self._db.fetch_one(
            """SELECT COUNT(DISTINCT source_id) as count
               FROM arkham_pattern_matches
               WHERE pattern_id = ? AND source_type = 'entity'""",
            [pattern_id],
        )

        await self._db.execute("""
            UPDATE arkham_patterns SET
                match_count = ?,
                document_count = ?,
                entity_count = ?,
                last_matched = ?,
                updated_at = ?
            WHERE id = ?
        """, [
            total["count"] if total else 0,
            doc_count["count"] if doc_count else 0,
            entity_count["count"] if entity_count else 0,
            datetime.utcnow().isoformat(),
            datetime.utcnow().isoformat(),
            pattern_id,
        ])

    async def _check_source_against_patterns(self, source_type: SourceType, source_id: str) -> None:
        """Check a source against all active patterns."""
        # Get all confirmed patterns
        patterns = await self.list_patterns(
            filter=PatternFilter(status=PatternStatus.CONFIRMED),
            limit=100,
        )

        for pattern in patterns:
            # Check if source matches pattern criteria
            if await self._source_matches_pattern(source_type, source_id, pattern):
                await self.add_match(
                    pattern.id,
                    PatternMatchCreate(
                        source_type=source_type,
                        source_id=source_id,
                        match_score=0.8,
                    ),
                )

    async def _source_matches_pattern(
        self,
        source_type: SourceType,
        source_id: str,
        pattern: Pattern,
    ) -> bool:
        """Check if a source matches a pattern's criteria."""
        # This is a simplified implementation
        # Real implementation would fetch source content and check against criteria
        return False  # Placeholder

    async def _detect_patterns_llm(
        self,
        text: str,
        pattern_types: Optional[List[PatternType]],
        min_confidence: float,
    ) -> List[Pattern]:
        """Detect patterns using LLM."""
        if not self._llm:
            return []

        try:
            types_str = ", ".join(t.value for t in (pattern_types or list(PatternType)))
            prompt = f"""Analyze the following text and identify patterns.
Look for these pattern types: {types_str}

For each pattern found, provide:
- Name (brief descriptive name)
- Description (what the pattern represents)
- Type (one of: {types_str})
- Confidence (0.0-1.0)
- Evidence (excerpts from the text)

Text:
{text[:10000]}

Return patterns as JSON array with minimum confidence {min_confidence}."""

            response = await self._llm.complete(prompt)
            patterns_data = self._parse_llm_patterns(response)

            patterns = []
            for data in patterns_data:
                if data.get("confidence", 0) >= min_confidence:
                    pattern = await self.create_pattern(
                        name=data.get("name", "Unnamed Pattern"),
                        description=data.get("description", ""),
                        pattern_type=PatternType(data.get("type", "recurring_theme")),
                        confidence=data.get("confidence", 0.5),
                        detection_method=DetectionMethod.LLM,
                    )
                    patterns.append(pattern)

            return patterns

        except Exception as e:
            logger.error(f"LLM pattern detection failed: {e}")
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
        """Parse LLM pattern detection response."""
        try:
            start = response.find("[")
            end = response.rfind("]") + 1
            if start >= 0 and end > start:
                return json.loads(response[start:end])
        except json.JSONDecodeError:
            logger.warning("Failed to parse LLM patterns response")
        return []
