"""
Credibility Shard - Main Shard Implementation

Source credibility assessment and scoring for ArkhamFrame - evaluate
reliability of documents, entities, and sources for intelligence analysis.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from arkham_frame import ArkhamShard

from .models import (
    AssessmentMethod,
    CredibilityAssessment,
    CredibilityCalculation,
    CredibilityFactor,
    CredibilityFilter,
    CredibilityHistory,
    CredibilityLevel,
    CredibilityStatistics,
    FactorType,
    SourceCredibility,
    SourceType,
    STANDARD_FACTORS,
    # Deception detection models
    DeceptionAssessment,
    DeceptionChecklist,
    DeceptionChecklistType,
    DeceptionIndicator,
    DeceptionRisk,
    IndicatorStrength,
    create_empty_checklist,
    get_indicators_for_checklist,
)

logger = logging.getLogger(__name__)


class CredibilityShard(ArkhamShard):
    """
    Credibility Shard - Assess source credibility and reliability.

    This shard provides:
    - Credibility assessment for documents, entities, and other sources
    - Factor-based scoring with configurable weights
    - Manual, automated (LLM), and hybrid assessment methods
    - Source credibility tracking over time
    - Aggregate credibility scores across multiple assessments
    - Statistics and reporting
    """

    name = "credibility"
    version = "0.1.0"
    description = "Source credibility assessment and scoring for reliability evaluation"

    def __init__(self):
        super().__init__()  # Auto-loads manifest from shard.yaml
        self.frame = None
        self._db = None
        self._events = None
        self._llm = None
        self._vectors = None
        self._initialized = False

    async def initialize(self, frame) -> None:
        """Initialize shard with frame services."""
        self.frame = frame
        self._db = frame.database
        self._events = frame.events
        self._llm = getattr(frame, "llm", None)
        self._vectors = getattr(frame, "vectors", None)

        # Create database schema
        await self._create_schema()

        # Subscribe to events
        await self._subscribe_to_events()

        # Register self in app state for API access
        if hasattr(frame, "app") and frame.app:
            frame.app.state.credibility_shard = self

        self._initialized = True
        logger.info(f"CredibilityShard initialized (v{self.version})")

    async def shutdown(self) -> None:
        """Clean shutdown of shard."""
        if self._events:
            await self._events.unsubscribe("document.processed", self._on_document_processed)
            await self._events.unsubscribe("claims.claim.verified", self._on_claim_verified)
            await self._events.unsubscribe("claims.claim.disputed", self._on_claim_disputed)
            await self._events.unsubscribe("contradictions.contradiction.detected", self._on_contradiction_detected)

        self._initialized = False
        logger.info("CredibilityShard shutdown complete")

    def get_routes(self):
        """Return FastAPI router for this shard."""
        from .api import router
        return router

    # === Database Schema ===

    async def _create_schema(self) -> None:
        """Create database tables for credibility shard."""
        if not self._db:
            logger.warning("Database not available, skipping schema creation")
            return

        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS arkham_credibility_assessments (
                id TEXT PRIMARY KEY,
                source_type TEXT NOT NULL,
                source_id TEXT NOT NULL,
                score INTEGER NOT NULL,
                confidence REAL NOT NULL,

                factors TEXT DEFAULT '[]',

                assessed_by TEXT DEFAULT 'manual',
                assessor_id TEXT,
                notes TEXT,

                created_at TEXT,
                updated_at TEXT,

                metadata TEXT DEFAULT '{}'
            )
        """)

        # Create indexes for common queries
        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_credibility_source ON arkham_credibility_assessments(source_type, source_id)
        """)
        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_credibility_score ON arkham_credibility_assessments(score)
        """)
        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_credibility_method ON arkham_credibility_assessments(assessed_by)
        """)
        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_credibility_created ON arkham_credibility_assessments(created_at DESC)
        """)

        # Deception assessments table
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS arkham_deception_assessments (
                id TEXT PRIMARY KEY,
                source_type TEXT NOT NULL,
                source_id TEXT NOT NULL,
                source_name TEXT,

                -- Checklist data (JSON)
                mom_data TEXT DEFAULT '{}',
                pop_data TEXT DEFAULT '{}',
                moses_data TEXT DEFAULT '{}',
                eve_data TEXT DEFAULT '{}',

                -- Aggregate scores
                overall_score INTEGER DEFAULT 0,
                risk_level TEXT DEFAULT 'minimal',
                confidence REAL DEFAULT 0.0,

                -- Integration with main credibility
                linked_assessment_id TEXT,
                affects_credibility INTEGER DEFAULT 1,
                credibility_weight REAL DEFAULT 0.3,

                -- Metadata
                assessed_by TEXT DEFAULT 'manual',
                assessor_id TEXT,
                summary TEXT,
                red_flags TEXT DEFAULT '[]',

                -- Timestamps
                created_at TEXT,
                updated_at TEXT
            )
        """)

        # Create indexes for deception table
        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_deception_source ON arkham_deception_assessments(source_type, source_id)
        """)
        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_deception_score ON arkham_deception_assessments(overall_score DESC)
        """)
        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_deception_risk ON arkham_deception_assessments(risk_level)
        """)

        # ===========================================
        # Multi-tenancy Migration
        # ===========================================
        await self._db.execute("""
            DO $$
            DECLARE
                tables_to_update TEXT[] := ARRAY['arkham_credibility_assessments', 'arkham_deception_assessments'];
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
            CREATE INDEX IF NOT EXISTS idx_arkham_credibility_assessments_tenant
            ON arkham_credibility_assessments(tenant_id)
        """)

        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_arkham_deception_assessments_tenant
            ON arkham_deception_assessments(tenant_id)
        """)

        logger.debug("Credibility schema created/verified")

    # === Event Subscriptions ===

    async def _subscribe_to_events(self) -> None:
        """Subscribe to relevant events from other shards."""
        if not self._events:
            logger.warning("Events service not available")
            return

        await self._events.subscribe("document.processed", self._on_document_processed)
        await self._events.subscribe("claims.claim.verified", self._on_claim_verified)
        await self._events.subscribe("claims.claim.disputed", self._on_claim_disputed)
        await self._events.subscribe("contradictions.contradiction.detected", self._on_contradiction_detected)

    async def _on_document_processed(self, event: Dict[str, Any]) -> None:
        """Handle document.processed event - optionally assess new documents."""
        document_id = event.get("payload", {}).get("document_id")
        if not document_id:
            return

        logger.debug(f"Document processed, could assess credibility: {document_id}")
        # Could queue automated assessment if configured

    async def _on_claim_verified(self, event: Dict[str, Any]) -> None:
        """Handle claims.claim.verified event - boost source credibility."""
        payload = event.get("payload", {})
        claim_id = payload.get("claim_id")
        source_document_id = payload.get("source_document_id")

        if source_document_id:
            logger.info(f"Claim verified from document {source_document_id}, consider boosting credibility")
            # Could automatically adjust document credibility

    async def _on_claim_disputed(self, event: Dict[str, Any]) -> None:
        """Handle claims.claim.disputed event - reduce source credibility."""
        payload = event.get("payload", {})
        claim_id = payload.get("claim_id")
        source_document_id = payload.get("source_document_id")

        if source_document_id:
            logger.info(f"Claim disputed from document {source_document_id}, consider reducing credibility")
            # Could automatically adjust document credibility

    async def _on_contradiction_detected(self, event: Dict[str, Any]) -> None:
        """Handle contradictions.contradiction.detected event - impact source credibility."""
        payload = event.get("payload", {})
        document_ids = payload.get("document_ids", [])

        for doc_id in document_ids:
            logger.debug(f"Contradiction detected involving document {doc_id}, review credibility")

    # === Public API Methods ===

    async def create_assessment(
        self,
        source_type: SourceType,
        source_id: str,
        score: int,
        confidence: float,
        factors: Optional[List[CredibilityFactor]] = None,
        assessed_by: AssessmentMethod = AssessmentMethod.MANUAL,
        assessor_id: Optional[str] = None,
        notes: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> CredibilityAssessment:
        """Create a new credibility assessment."""
        # Validate score
        if not 0 <= score <= 100:
            raise ValueError(f"Score must be 0-100, got {score}")
        if not 0.0 <= confidence <= 1.0:
            raise ValueError(f"Confidence must be 0.0-1.0, got {confidence}")

        assessment_id = str(uuid4())
        now = datetime.utcnow()

        assessment = CredibilityAssessment(
            id=assessment_id,
            source_type=source_type,
            source_id=source_id,
            score=score,
            confidence=confidence,
            factors=factors or [],
            assessed_by=assessed_by,
            assessor_id=assessor_id,
            notes=notes,
            created_at=now,
            updated_at=now,
            metadata=metadata or {},
        )

        await self._save_assessment(assessment)

        # Emit events
        if self._events:
            await self._events.emit(
                "credibility.assessment.created",
                {
                    "assessment_id": assessment_id,
                    "source_type": source_type.value,
                    "source_id": source_id,
                    "score": score,
                    "level": assessment.level.value,
                },
                source=self.name,
            )

            await self._events.emit(
                "credibility.source.rated",
                {
                    "source_type": source_type.value,
                    "source_id": source_id,
                    "score": score,
                },
                source=self.name,
            )

            # Check for threshold breach
            if score <= 40:  # Low or unreliable
                await self._events.emit(
                    "credibility.threshold.breached",
                    {
                        "assessment_id": assessment_id,
                        "source_type": source_type.value,
                        "source_id": source_id,
                        "score": score,
                        "threshold": "low",
                    },
                    source=self.name,
                )

        return assessment

    async def get_assessment(self, assessment_id: str) -> Optional[CredibilityAssessment]:
        """Get an assessment by ID."""
        if not self._db:
            return None

        query = "SELECT * FROM arkham_credibility_assessments WHERE id = :id"
        params = {"id": assessment_id}
        tenant_id = self.get_tenant_id_or_none()
        if tenant_id:
            query += " AND tenant_id = :tenant_id"
            params["tenant_id"] = str(tenant_id)

        row = await self._db.fetch_one(query, params)
        return self._row_to_assessment(row) if row else None

    async def list_assessments(
        self,
        filter: Optional[CredibilityFilter] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[CredibilityAssessment]:
        """List assessments with optional filtering."""
        if not self._db:
            return []

        query = "SELECT * FROM arkham_credibility_assessments WHERE 1=1"
        params = {}

        tenant_id = self.get_tenant_id_or_none()
        if tenant_id:
            query += " AND tenant_id = :tenant_id"
            params["tenant_id"] = str(tenant_id)

        if filter:
            if filter.source_type:
                query += " AND source_type = :source_type"
                params["source_type"] = filter.source_type.value
            if filter.source_id:
                query += " AND source_id = :source_id"
                params["source_id"] = filter.source_id
            if filter.min_score is not None:
                query += " AND score >= :min_score"
                params["min_score"] = filter.min_score
            if filter.max_score is not None:
                query += " AND score <= :max_score"
                params["max_score"] = filter.max_score
            if filter.level:
                # Map level to score range
                level_ranges = {
                    CredibilityLevel.UNRELIABLE: (0, 20),
                    CredibilityLevel.LOW: (21, 40),
                    CredibilityLevel.MEDIUM: (41, 60),
                    CredibilityLevel.HIGH: (61, 80),
                    CredibilityLevel.VERIFIED: (81, 100),
                }
                min_s, max_s = level_ranges[filter.level]
                query += " AND score >= :level_min AND score <= :level_max"
                params["level_min"] = min_s
                params["level_max"] = max_s
            if filter.assessed_by:
                query += " AND assessed_by = :assessed_by"
                params["assessed_by"] = filter.assessed_by.value
            if filter.assessor_id:
                query += " AND assessor_id = :assessor_id"
                params["assessor_id"] = filter.assessor_id
            if filter.min_confidence is not None:
                query += " AND confidence >= :min_confidence"
                params["min_confidence"] = filter.min_confidence
            if filter.max_confidence is not None:
                query += " AND confidence <= :max_confidence"
                params["max_confidence"] = filter.max_confidence

        query += " ORDER BY created_at DESC LIMIT :limit OFFSET :offset"
        params["limit"] = limit
        params["offset"] = offset

        rows = await self._db.fetch_all(query, params)
        return [self._row_to_assessment(row) for row in rows]

    async def update_assessment(
        self,
        assessment_id: str,
        score: Optional[int] = None,
        confidence: Optional[float] = None,
        factors: Optional[List[CredibilityFactor]] = None,
        notes: Optional[str] = None,
    ) -> Optional[CredibilityAssessment]:
        """Update an existing assessment."""
        assessment = await self.get_assessment(assessment_id)
        if not assessment:
            return None

        old_score = assessment.score

        if score is not None:
            if not 0 <= score <= 100:
                raise ValueError(f"Score must be 0-100, got {score}")
            assessment.score = score

        if confidence is not None:
            if not 0.0 <= confidence <= 1.0:
                raise ValueError(f"Confidence must be 0.0-1.0, got {confidence}")
            assessment.confidence = confidence

        if factors is not None:
            assessment.factors = factors

        if notes is not None:
            assessment.notes = notes

        assessment.updated_at = datetime.utcnow()

        await self._save_assessment(assessment, update=True)

        # Emit event if score changed
        if self._events and score is not None and score != old_score:
            await self._events.emit(
                "credibility.score.updated",
                {
                    "assessment_id": assessment_id,
                    "source_type": assessment.source_type.value,
                    "source_id": assessment.source_id,
                    "old_score": old_score,
                    "new_score": score,
                },
                source=self.name,
            )

        return assessment

    async def delete_assessment(self, assessment_id: str) -> bool:
        """Delete an assessment."""
        if not self._db:
            return False

        query = "DELETE FROM arkham_credibility_assessments WHERE id = :id"
        params = {"id": assessment_id}
        tenant_id = self.get_tenant_id_or_none()
        if tenant_id:
            query += " AND tenant_id = :tenant_id"
            params["tenant_id"] = str(tenant_id)

        await self._db.execute(query, params)
        return True

    async def get_source_credibility(
        self,
        source_type: SourceType,
        source_id: str,
    ) -> Optional[SourceCredibility]:
        """Get aggregate credibility for a source."""
        if not self._db:
            return None

        # Get all assessments for this source
        query = """
            SELECT * FROM arkham_credibility_assessments
            WHERE source_type = :source_type AND source_id = :source_id
        """
        params = {"source_type": source_type.value, "source_id": source_id}
        tenant_id = self.get_tenant_id_or_none()
        if tenant_id:
            query += " AND tenant_id = :tenant_id"
            params["tenant_id"] = str(tenant_id)
        query += " ORDER BY created_at DESC"

        rows = await self._db.fetch_all(query, params)

        if not rows:
            return None

        # Calculate aggregate
        scores = [row["score"] for row in rows]
        avg_score = sum(scores) / len(scores)

        latest = rows[0]

        return SourceCredibility(
            source_type=source_type,
            source_id=source_id,
            avg_score=avg_score,
            assessment_count=len(rows),
            latest_score=latest["score"],
            latest_confidence=latest["confidence"],
            latest_assessment_id=latest["id"],
            latest_assessed_at=datetime.fromisoformat(latest["created_at"]),
        )

    async def get_source_history(
        self,
        source_type: SourceType,
        source_id: str,
    ) -> CredibilityHistory:
        """Get credibility history for a source."""
        assessments = await self.list_assessments(
            filter=CredibilityFilter(source_type=source_type, source_id=source_id),
            limit=1000,
        )

        if not assessments:
            return CredibilityHistory(
                source_type=source_type,
                source_id=source_id,
                assessments=[],
            )

        scores = [a.score for a in assessments]
        avg_score = sum(scores) / len(scores) if scores else 0.0

        # Determine trend
        if len(scores) >= 3:
            recent_avg = sum(scores[:3]) / 3
            older_avg = sum(scores[-3:]) / 3
            if recent_avg > older_avg + 10:
                trend = "improving"
            elif recent_avg < older_avg - 10:
                trend = "declining"
            else:
                # Check volatility
                variance = sum((s - avg_score) ** 2 for s in scores) / len(scores)
                trend = "volatile" if variance > 400 else "stable"
        else:
            trend = "stable"

        return CredibilityHistory(
            source_type=source_type,
            source_id=source_id,
            assessments=assessments,
            score_trend=trend,
            avg_score=avg_score,
            min_score=min(scores) if scores else 0,
            max_score=max(scores) if scores else 100,
        )

    async def calculate_credibility(
        self,
        source_type: SourceType,
        source_id: str,
        use_llm: bool = False,
    ) -> CredibilityCalculation:
        """Calculate credibility score for a source."""
        import time
        start_time = time.time()

        factors = []
        errors = []
        calculated_score = 50  # Default moderate score
        confidence = 0.5
        method = AssessmentMethod.AUTOMATED if use_llm else AssessmentMethod.MANUAL

        if use_llm and self._llm and self._llm.is_available():
            try:
                # LLM-based assessment
                prompt = f"""Assess the credibility of this source:
Type: {source_type.value}
ID: {source_id}

Evaluate the following factors (0-100 scale):
- Source Reliability: Track record of accuracy
- Evidence Quality: Quality of supporting evidence
- Bias Assessment: Political/ideological bias
- Expertise: Subject matter expertise
- Timeliness: Recency and relevance

Return as JSON with factors and overall score."""

                llm_response = await self._llm.generate(prompt)
                # Parse LLM response
                parsed = self._parse_llm_assessment(llm_response.text)
                factors = parsed.get("factors", [])
                calculated_score = parsed.get("score", 50)
                confidence = 0.8  # Higher confidence for LLM
            except Exception as e:
                logger.error(f"LLM assessment failed: {e}")
                errors.append(str(e))
                # Fall back to default factors
                factors = self._get_default_factors()
        else:
            # Use default factors
            factors = self._get_default_factors()

        # Calculate weighted score if factors provided
        if factors:
            total_weight = sum(f.weight for f in factors)
            if total_weight > 0:
                weighted_sum = sum(f.score * f.weight for f in factors)
                calculated_score = int(weighted_sum / total_weight)

        processing_time = (time.time() - start_time) * 1000

        # Emit event
        if self._events:
            await self._events.emit(
                "credibility.analysis.completed",
                {
                    "source_type": source_type.value,
                    "source_id": source_id,
                    "score": calculated_score,
                    "processing_time_ms": processing_time,
                },
                source=self.name,
            )

        return CredibilityCalculation(
            source_type=source_type,
            source_id=source_id,
            calculated_score=calculated_score,
            confidence=confidence,
            factors=factors,
            method=method,
            processing_time_ms=processing_time,
            errors=errors,
        )

    async def get_statistics(self) -> CredibilityStatistics:
        """Get statistics about credibility assessments."""
        if not self._db:
            return CredibilityStatistics()

        # Build tenant filter
        tenant_filter = ""
        tenant_params = {}
        tenant_id = self.get_tenant_id_or_none()
        if tenant_id:
            tenant_filter = " WHERE tenant_id = :tenant_id"
            tenant_params["tenant_id"] = str(tenant_id)

        # Total assessments
        total = await self._db.fetch_one(
            f"SELECT COUNT(*) as count FROM arkham_credibility_assessments{tenant_filter}",
            tenant_params,
        )
        total_assessments = total["count"] if total else 0

        # By source type
        type_rows = await self._db.fetch_all(
            f"SELECT source_type, COUNT(*) as count FROM arkham_credibility_assessments{tenant_filter} GROUP BY source_type",
            tenant_params,
        )
        by_source_type = {row["source_type"]: row["count"] for row in type_rows}

        # By level (calculate from score ranges)
        score_filter = tenant_filter if tenant_filter else " WHERE"
        score_and = " AND" if tenant_filter else ""

        unreliable = await self._db.fetch_one(
            f"SELECT COUNT(*) as count FROM arkham_credibility_assessments{score_filter}{score_and} score <= 20",
            tenant_params,
        )
        low = await self._db.fetch_one(
            f"SELECT COUNT(*) as count FROM arkham_credibility_assessments{score_filter}{score_and} score > 20 AND score <= 40",
            tenant_params,
        )
        medium = await self._db.fetch_one(
            f"SELECT COUNT(*) as count FROM arkham_credibility_assessments{score_filter}{score_and} score > 40 AND score <= 60",
            tenant_params,
        )
        high = await self._db.fetch_one(
            f"SELECT COUNT(*) as count FROM arkham_credibility_assessments{score_filter}{score_and} score > 60 AND score <= 80",
            tenant_params,
        )
        verified = await self._db.fetch_one(
            f"SELECT COUNT(*) as count FROM arkham_credibility_assessments{score_filter}{score_and} score > 80",
            tenant_params,
        )

        by_level = {
            "unreliable": unreliable["count"] if unreliable else 0,
            "low": low["count"] if low else 0,
            "medium": medium["count"] if medium else 0,
            "high": high["count"] if high else 0,
            "verified": verified["count"] if verified else 0,
        }

        # By method
        method_rows = await self._db.fetch_all(
            f"SELECT assessed_by, COUNT(*) as count FROM arkham_credibility_assessments{tenant_filter} GROUP BY assessed_by",
            tenant_params,
        )
        by_method = {row["assessed_by"]: row["count"] for row in method_rows}

        # Averages
        avg_score_row = await self._db.fetch_one(
            f"SELECT AVG(score) as avg FROM arkham_credibility_assessments{tenant_filter}",
            tenant_params,
        )
        avg_confidence_row = await self._db.fetch_one(
            f"SELECT AVG(confidence) as avg FROM arkham_credibility_assessments{tenant_filter}",
            tenant_params,
        )

        # Unique sources
        sources_row = await self._db.fetch_one(
            f"SELECT COUNT(DISTINCT source_type || ':' || source_id) as count FROM arkham_credibility_assessments{tenant_filter}",
            tenant_params,
        )
        sources_assessed = sources_row["count"] if sources_row else 0
        avg_per_source = total_assessments / sources_assessed if sources_assessed > 0 else 0.0

        return CredibilityStatistics(
            total_assessments=total_assessments,
            by_source_type=by_source_type,
            by_level=by_level,
            by_method=by_method,
            avg_score=avg_score_row["avg"] if avg_score_row and avg_score_row["avg"] else 0.0,
            avg_confidence=avg_confidence_row["avg"] if avg_confidence_row and avg_confidence_row["avg"] else 0.0,
            unreliable_count=by_level["unreliable"],
            low_count=by_level["low"],
            medium_count=by_level["medium"],
            high_count=by_level["high"],
            verified_count=by_level["verified"],
            sources_assessed=sources_assessed,
            avg_assessments_per_source=avg_per_source,
        )

    async def get_count(
        self,
        level: Optional[str] = None,
        source_type: Optional[str] = None,
    ) -> int:
        """Get count of assessments, optionally filtered."""
        if not self._db:
            return 0

        query = "SELECT COUNT(*) as count FROM arkham_credibility_assessments WHERE 1=1"
        params = {}

        tenant_id = self.get_tenant_id_or_none()
        if tenant_id:
            query += " AND tenant_id = :tenant_id"
            params["tenant_id"] = str(tenant_id)

        if level:
            level_ranges = {
                "unreliable": (0, 20),
                "low": (21, 40),
                "medium": (41, 60),
                "high": (61, 80),
                "verified": (81, 100),
            }
            if level in level_ranges:
                min_s, max_s = level_ranges[level]
                query += " AND score >= :min_score AND score <= :max_score"
                params["min_score"] = min_s
                params["max_score"] = max_s

        if source_type:
            query += " AND source_type = :source_type"
            params["source_type"] = source_type

        result = await self._db.fetch_one(query, params)
        return result["count"] if result else 0

    def get_standard_factors(self) -> List[Dict[str, Any]]:
        """Get list of standard credibility factors."""
        return [
            {
                "factor_type": f.factor_type,
                "default_weight": f.default_weight,
                "description": f.description,
                "scoring_guidance": f.scoring_guidance,
            }
            for f in STANDARD_FACTORS
        ]

    # === Private Helper Methods ===

    async def _save_assessment(self, assessment: CredibilityAssessment, update: bool = False) -> None:
        """Save an assessment to the database."""
        if not self._db:
            return

        import json

        # Serialize factors
        factors_json = json.dumps([
            {
                "factor_type": f.factor_type,
                "weight": f.weight,
                "score": f.score,
                "notes": f.notes,
            }
            for f in assessment.factors
        ])

        data = (
            assessment.id,
            assessment.source_type.value,
            assessment.source_id,
            assessment.score,
            assessment.confidence,
            factors_json,
            assessment.assessed_by.value,
            assessment.assessor_id,
            assessment.notes,
            assessment.created_at.isoformat(),
            assessment.updated_at.isoformat(),
            json.dumps(assessment.metadata),
        )

        if update:
            await self._db.execute("""
                UPDATE arkham_credibility_assessments SET
                    source_type=?, source_id=?, score=?, confidence=?,
                    factors=?, assessed_by=?, assessor_id=?, notes=?,
                    created_at=?, updated_at=?, metadata=?
                WHERE id=?
            """, data[1:] + (assessment.id,))
        else:
            await self._db.execute("""
                INSERT INTO arkham_credibility_assessments (
                    id, source_type, source_id, score, confidence,
                    factors, assessed_by, assessor_id, notes,
                    created_at, updated_at, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, data)

    def _row_to_assessment(self, row: Dict[str, Any]) -> CredibilityAssessment:
        """Convert database row to CredibilityAssessment object."""
        import json

        # Deserialize factors
        factors_data = json.loads(row.get("factors") or "[]")
        factors = [
            CredibilityFactor(
                factor_type=f.get("factor_type", ""),
                weight=f.get("weight", 0.0),
                score=f.get("score", 0),
                notes=f.get("notes"),
            )
            for f in factors_data
        ]

        return CredibilityAssessment(
            id=row["id"],
            source_type=SourceType(row["source_type"]),
            source_id=row["source_id"],
            score=row["score"],
            confidence=row["confidence"],
            factors=factors,
            assessed_by=AssessmentMethod(row["assessed_by"]),
            assessor_id=row["assessor_id"],
            notes=row["notes"],
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else datetime.utcnow(),
            updated_at=datetime.fromisoformat(row["updated_at"]) if row["updated_at"] else datetime.utcnow(),
            metadata=json.loads(row.get("metadata") or "{}"),
        )

    def _get_default_factors(self) -> List[CredibilityFactor]:
        """Get default credibility factors for calculation."""
        return [
            CredibilityFactor(
                factor_type=f.factor_type,
                weight=f.default_weight,
                score=50,  # Neutral default
                notes=f.description,
            )
            for f in STANDARD_FACTORS
        ]

    def _parse_llm_assessment(self, response: str) -> Dict[str, Any]:
        """Parse LLM credibility assessment response."""
        import json
        try:
            # Try to extract JSON from response
            start = response.find("{")
            end = response.rfind("}") + 1
            if start >= 0 and end > start:
                data = json.loads(response[start:end])

                # Convert to CredibilityFactor objects
                factors = []
                for f in data.get("factors", []):
                    factors.append(CredibilityFactor(
                        factor_type=f.get("type", "custom"),
                        weight=f.get("weight", 0.1),
                        score=f.get("score", 50),
                        notes=f.get("notes", ""),
                    ))

                return {
                    "score": data.get("score", 50),
                    "factors": factors,
                }
        except json.JSONDecodeError:
            logger.warning("Failed to parse LLM assessment response as JSON")

        return {"score": 50, "factors": []}

    async def _find_existing_credibility_assessment(
        self,
        source_type: SourceType,
        source_id: str,
    ) -> Optional[CredibilityAssessment]:
        """Find an existing credibility assessment for a source (most recent)."""
        if not self._db:
            return None

        query = """
            SELECT * FROM arkham_credibility_assessments
            WHERE source_type = :source_type AND source_id = :source_id
        """
        params = {"source_type": source_type.value, "source_id": source_id}

        tenant_id = self.get_tenant_id_or_none()
        if tenant_id:
            query += " AND tenant_id = :tenant_id"
            params["tenant_id"] = str(tenant_id)

        query += " ORDER BY created_at DESC LIMIT 1"

        row = await self._db.fetch_one(query, params)
        if row:
            return self._row_to_assessment(row)
        return None

    # =========================================================================
    # DECEPTION DETECTION (MOM/POP/MOSES/EVE) METHODS
    # =========================================================================

    async def create_deception_assessment(
        self,
        source_type: SourceType,
        source_id: str,
        source_name: Optional[str] = None,
        linked_assessment_id: Optional[str] = None,
        affects_credibility: bool = True,
        credibility_weight: float = 0.7,
    ) -> DeceptionAssessment:
        """Create a new deception detection assessment with empty checklists."""
        assessment_id = str(uuid4())
        now = datetime.utcnow()

        # Auto-link to existing credibility assessment if none provided
        if not linked_assessment_id and affects_credibility:
            existing = await self._find_existing_credibility_assessment(source_type, source_id)
            if existing:
                linked_assessment_id = existing.id
                logger.info(f"Auto-linked deception assessment to existing credibility {existing.id}")

        # Create empty checklists with standard indicators
        mom_checklist = create_empty_checklist(DeceptionChecklistType.MOM)
        pop_checklist = create_empty_checklist(DeceptionChecklistType.POP)
        moses_checklist = create_empty_checklist(DeceptionChecklistType.MOSES)
        eve_checklist = create_empty_checklist(DeceptionChecklistType.EVE)

        assessment = DeceptionAssessment(
            id=assessment_id,
            source_type=source_type,
            source_id=source_id,
            source_name=source_name,
            mom_checklist=mom_checklist,
            pop_checklist=pop_checklist,
            moses_checklist=moses_checklist,
            eve_checklist=eve_checklist,
            linked_assessment_id=linked_assessment_id,
            affects_credibility=affects_credibility,
            credibility_weight=credibility_weight,
            created_at=now,
            updated_at=now,
        )

        await self._save_deception_assessment(assessment)

        # Emit event
        if self._events:
            await self._events.emit(
                "credibility.deception.created",
                {
                    "assessment_id": assessment_id,
                    "source_type": source_type.value,
                    "source_id": source_id,
                },
                source=self.name,
            )

        return assessment

    async def get_deception_assessment(self, assessment_id: str) -> Optional[DeceptionAssessment]:
        """Get a deception assessment by ID."""
        if not self._db:
            return None

        query = "SELECT * FROM arkham_deception_assessments WHERE id = :id"
        params = {"id": assessment_id}
        tenant_id = self.get_tenant_id_or_none()
        if tenant_id:
            query += " AND tenant_id = :tenant_id"
            params["tenant_id"] = str(tenant_id)

        row = await self._db.fetch_one(query, params)
        return self._row_to_deception_assessment(row) if row else None

    async def list_deception_assessments(
        self,
        source_type: Optional[SourceType] = None,
        source_id: Optional[str] = None,
        min_score: Optional[int] = None,
        risk_level: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[DeceptionAssessment]:
        """List deception assessments with optional filtering."""
        if not self._db:
            return []

        query = "SELECT * FROM arkham_deception_assessments WHERE 1=1"
        params = {}

        tenant_id = self.get_tenant_id_or_none()
        if tenant_id:
            query += " AND tenant_id = :tenant_id"
            params["tenant_id"] = str(tenant_id)

        if source_type:
            query += " AND source_type = :source_type"
            params["source_type"] = source_type.value
        if source_id:
            query += " AND source_id = :source_id"
            params["source_id"] = source_id
        if min_score is not None:
            query += " AND overall_score >= :min_score"
            params["min_score"] = min_score
        if risk_level:
            query += " AND risk_level = :risk_level"
            params["risk_level"] = risk_level

        query += " ORDER BY created_at DESC LIMIT :limit OFFSET :offset"
        params["limit"] = limit
        params["offset"] = offset

        rows = await self._db.fetch_all(query, params)
        return [self._row_to_deception_assessment(row) for row in rows]

    async def update_deception_assessment(
        self,
        assessment_id: str,
        source_name: Optional[str] = None,
        summary: Optional[str] = None,
        red_flags: Optional[List[str]] = None,
        affects_credibility: Optional[bool] = None,
        credibility_weight: Optional[float] = None,
    ) -> Optional[DeceptionAssessment]:
        """Update a deception assessment metadata."""
        assessment = await self.get_deception_assessment(assessment_id)
        if not assessment:
            return None

        if source_name is not None:
            assessment.source_name = source_name
        if summary is not None:
            assessment.summary = summary
        if red_flags is not None:
            assessment.red_flags = red_flags
        if affects_credibility is not None:
            assessment.affects_credibility = affects_credibility
        if credibility_weight is not None:
            assessment.credibility_weight = credibility_weight

        assessment.updated_at = datetime.utcnow()

        await self._save_deception_assessment(assessment, update=True)
        return assessment

    async def delete_deception_assessment(self, assessment_id: str) -> bool:
        """Delete a deception assessment."""
        if not self._db:
            return False

        query = "DELETE FROM arkham_deception_assessments WHERE id = :id"
        params = {"id": assessment_id}
        tenant_id = self.get_tenant_id_or_none()
        if tenant_id:
            query += " AND tenant_id = :tenant_id"
            params["tenant_id"] = str(tenant_id)

        await self._db.execute(query, params)
        return True

    async def update_deception_checklist(
        self,
        assessment_id: str,
        checklist_type: DeceptionChecklistType,
        indicators: List[Any],  # List of DeceptionIndicatorModel from API
        summary: Optional[str] = None,
    ) -> Optional[DeceptionAssessment]:
        """Update a specific checklist within a deception assessment."""
        assessment = await self.get_deception_assessment(assessment_id)
        if not assessment:
            return None

        # Get the target checklist
        if checklist_type == DeceptionChecklistType.MOM:
            checklist = assessment.mom_checklist
        elif checklist_type == DeceptionChecklistType.POP:
            checklist = assessment.pop_checklist
        elif checklist_type == DeceptionChecklistType.MOSES:
            checklist = assessment.moses_checklist
        elif checklist_type == DeceptionChecklistType.EVE:
            checklist = assessment.eve_checklist
        else:
            return None

        if not checklist:
            checklist = create_empty_checklist(checklist_type)

        # Update indicators
        indicator_map = {ind.id: ind for ind in checklist.indicators}
        for ind_data in indicators:
            ind_id = ind_data.id if hasattr(ind_data, 'id') else ind_data.get('id')
            if ind_id in indicator_map:
                existing = indicator_map[ind_id]
                existing.answer = ind_data.answer if hasattr(ind_data, 'answer') else ind_data.get('answer')
                existing.strength = IndicatorStrength(ind_data.strength if hasattr(ind_data, 'strength') else ind_data.get('strength', 'none'))
                existing.confidence = ind_data.confidence if hasattr(ind_data, 'confidence') else ind_data.get('confidence', 0.0)
                existing.evidence_ids = ind_data.evidence_ids if hasattr(ind_data, 'evidence_ids') else ind_data.get('evidence_ids', [])
                existing.notes = ind_data.notes if hasattr(ind_data, 'notes') else ind_data.get('notes')

        # Calculate checklist score
        checklist.overall_score = checklist.calculate_score()
        checklist.risk_level = self._score_to_risk_level(checklist.overall_score)
        checklist.summary = summary
        checklist.completed_at = datetime.utcnow()

        # Store updated checklist
        if checklist_type == DeceptionChecklistType.MOM:
            assessment.mom_checklist = checklist
        elif checklist_type == DeceptionChecklistType.POP:
            assessment.pop_checklist = checklist
        elif checklist_type == DeceptionChecklistType.MOSES:
            assessment.moses_checklist = checklist
        elif checklist_type == DeceptionChecklistType.EVE:
            assessment.eve_checklist = checklist

        # Recalculate overall score
        assessment.overall_score = assessment.calculate_overall_score()
        assessment.risk_level = assessment.get_risk_level(assessment.overall_score)
        assessment.updated_at = datetime.utcnow()

        await self._save_deception_assessment(assessment, update=True)

        # Emit event
        if self._events:
            await self._events.emit(
                "credibility.deception.checklist.updated",
                {
                    "assessment_id": assessment_id,
                    "checklist_type": checklist_type.value,
                    "score": checklist.overall_score,
                    "overall_score": assessment.overall_score,
                },
                source=self.name,
            )

        # Sync deception score to credibility if enabled
        if assessment.affects_credibility:
            await self._sync_deception_to_credibility(assessment)

        return assessment

    async def recalculate_deception_score(self, assessment_id: str) -> Optional[DeceptionAssessment]:
        """Recalculate overall deception score from completed checklists."""
        assessment = await self.get_deception_assessment(assessment_id)
        if not assessment:
            return None

        # Recalculate each checklist score
        for checklist in [assessment.mom_checklist, assessment.pop_checklist,
                          assessment.moses_checklist, assessment.eve_checklist]:
            if checklist:
                checklist.overall_score = checklist.calculate_score()
                checklist.risk_level = self._score_to_risk_level(checklist.overall_score)

        # Recalculate overall
        assessment.overall_score = assessment.calculate_overall_score()
        assessment.risk_level = assessment.get_risk_level(assessment.overall_score)

        # Calculate confidence based on completed checklists
        assessment.confidence = assessment.completed_checklists / 4.0

        assessment.updated_at = datetime.utcnow()
        await self._save_deception_assessment(assessment, update=True)

        # Sync deception score to credibility if enabled
        if assessment.affects_credibility:
            await self._sync_deception_to_credibility(assessment)

        return assessment

    async def get_deception_count(
        self,
        risk_level: Optional[str] = None,
        min_score: Optional[int] = None,
    ) -> int:
        """Get count of deception assessments."""
        if not self._db:
            return 0

        query = "SELECT COUNT(*) as count FROM arkham_deception_assessments WHERE 1=1"
        params = {}

        tenant_id = self.get_tenant_id_or_none()
        if tenant_id:
            query += " AND tenant_id = :tenant_id"
            params["tenant_id"] = str(tenant_id)

        if risk_level:
            query += " AND risk_level = :risk_level"
            params["risk_level"] = risk_level
        if min_score is not None:
            query += " AND overall_score >= :min_score"
            params["min_score"] = min_score

        result = await self._db.fetch_one(query, params)
        return result["count"] if result else 0

    async def analyze_checklist_with_llm(
        self,
        assessment_id: str,
        checklist_type: DeceptionChecklistType,
        context: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Use LLM to analyze and populate a checklist."""
        import time
        start_time = time.time()

        assessment = await self.get_deception_assessment(assessment_id)
        if not assessment:
            return None

        if not self._llm or not self._llm.is_available():
            logger.warning("LLM service not available for deception analysis")
            return None

        # Get indicators for this checklist type
        indicators = get_indicators_for_checklist(checklist_type)

        # Build prompt
        checklist_guidance = {
            DeceptionChecklistType.MOM: "MOM Analysis (Motive, Opportunity, Means): Focus on whether the source has incentive, access, and capability to deceive.",
            DeceptionChecklistType.POP: "POP Analysis (Past Opposition Practices): Focus on historical deception patterns by this source or organization.",
            DeceptionChecklistType.MOSES: "MOSES Analysis (Manipulability of Sources): Focus on whether the source could be manipulated or is an unwitting conduit.",
            DeceptionChecklistType.EVE: "EVE Analysis (Evaluation of Evidence): Focus on the evidence quality, consistency, and signs of fabrication.",
        }

        questions_formatted = "\n".join([
            f"- ID: {ind.id}\n  Question: {ind.question}\n  Guidance: {ind.guidance}"
            for ind in indicators
        ])

        prompt = f"""You are an intelligence analyst specializing in deception detection.

Analyze the following source for deception risk using the {checklist_type.value.upper()} framework.

## Source Information
- Type: {assessment.source_type.value}
- ID: {assessment.source_id}
- Name: {assessment.source_name or 'Unknown'}

## {checklist_guidance.get(checklist_type, '')}

## Context
{context or 'No additional context provided.'}

## Questions to Assess

{questions_formatted}

For each question, provide an assessment using the EXACT indicator ID shown above.

## Output Format (JSON)
IMPORTANT: Use the exact indicator IDs from the questions above (e.g., "{indicators[0].id if indicators else 'id_example'}").
{{
  "indicators": [
    {{
      "id": "<exact ID from the question>",
      "answer": "Your assessment of the question",
      "strength": "none|weak|moderate|strong|conclusive",
      "confidence": 0.5,
      "reasoning": "Brief explanation"
    }}
  ],
  "overall_assessment": "Summary of deception risk based on this checklist",
  "checklist_score": 0-100,
  "key_concerns": ["concern1", "concern2"]
}}
"""

        try:
            llm_response = await self._llm.generate(prompt)
            parsed = self._parse_llm_deception_response(llm_response.text, checklist_type, indicators)

            processing_time = (time.time() - start_time) * 1000

            # Save the analyzed checklist to the assessment
            analyzed_checklist = parsed["checklist"]
            await self.update_deception_checklist(
                assessment_id=assessment_id,
                checklist_type=checklist_type,
                indicators=analyzed_checklist.indicators,
                summary=analyzed_checklist.summary,
            )

            return {
                "checklist": analyzed_checklist,
                "reasoning": parsed.get("reasoning", ""),
                "confidence": parsed.get("confidence", 0.7),
                "processing_time_ms": processing_time,
            }

        except Exception as e:
            logger.error(f"LLM deception analysis failed: {e}")
            return None

    # === Private Deception Helper Methods ===

    def _score_to_risk_level(self, score: int) -> str:
        """Convert score to risk level string."""
        if score <= 20:
            return "minimal"
        elif score <= 40:
            return "low"
        elif score <= 60:
            return "moderate"
        elif score <= 80:
            return "high"
        else:
            return "critical"

    async def _sync_deception_to_credibility(self, deception: DeceptionAssessment) -> None:
        """
        Sync deception assessment score to linked credibility assessment.

        Deception score (0-100) indicates likelihood of deception:
        - 0 = no deception indicators
        - 100 = strong deception indicators

        Credibility score is inverted: high deception = low credibility
        The deception score is weighted by credibility_weight (default 0.7).
        """
        if not deception.affects_credibility:
            return

        # Only sync if there's meaningful data (at least one checklist completed)
        if deception.completed_checklists == 0:
            logger.debug(f"Skipping credibility sync - no checklists completed for {deception.id}")
            return

        # Convert deception score to credibility impact
        # Deception score of 100 (high deception) = credibility of 0 (unreliable)
        # Deception score of 0 (no deception) = credibility of 100 (verified)
        deception_credibility = 100 - deception.overall_score

        # Create credibility factors from completed checklists
        # Use the same weights as the deception assessment calculation
        checklist_weights = {
            "MOM Analysis": 0.35,    # MOM most heavily weighted
            "EVE Analysis": 0.25,    # Evidence evaluation second
            "MOSES Analysis": 0.25,  # Manipulability third
            "POP Analysis": 0.15,    # Past practices least (often unknown)
        }
        factors = []

        for checklist, name in [
            (deception.mom_checklist, "MOM Analysis"),
            (deception.pop_checklist, "POP Analysis"),
            (deception.moses_checklist, "MOSES Analysis"),
            (deception.eve_checklist, "EVE Analysis"),
        ]:
            if checklist and checklist.completed_at:
                # Invert the checklist score (high deception indicator = low credibility)
                checklist_credibility = 100 - checklist.overall_score
                factors.append(CredibilityFactor(
                    factor_type=f"deception_{name.lower().replace(' ', '_')}",
                    weight=checklist_weights[name],
                    score=checklist_credibility,
                    notes=f"{name}: {checklist.risk_level} risk ({checklist.overall_score}% deception indicators)",
                ))

        if not factors:
            return

        # Calculate weighted score from factors
        total_weight = sum(f.weight for f in factors)
        if total_weight > 0:
            final_score = int(sum(f.score * f.weight for f in factors) / total_weight)
        else:
            final_score = deception_credibility

        # SEVERITY OVERRIDE: High deception scores force low credibility
        # This ensures that conclusive/strong deception evidence dramatically impacts credibility
        # regardless of how other factors might average out
        if deception.overall_score >= 80:  # Critical risk
            # Conclusive deception: cap credibility at 15 (Unreliable)
            final_score = min(final_score, 15)
            logger.info(f"Deception severity override: critical risk ({deception.overall_score}%) "
                       f"capped credibility at {final_score}")
        elif deception.overall_score >= 60:  # High risk
            # Strong deception: cap credibility at 30 (Low)
            final_score = min(final_score, 30)
            logger.info(f"Deception severity override: high risk ({deception.overall_score}%) "
                       f"capped credibility at {final_score}")
        elif deception.overall_score >= 40:  # Moderate risk
            # Moderate deception: cap credibility at 50 (Medium)
            final_score = min(final_score, 50)
            logger.info(f"Deception severity override: moderate risk ({deception.overall_score}%) "
                       f"capped credibility at {final_score}")

        # Confidence based on how many checklists were completed
        confidence = deception.confidence if deception.confidence > 0 else 0.5

        try:
            # Check if linked assessment exists
            if deception.linked_assessment_id:
                existing = await self.get_assessment(deception.linked_assessment_id)
                if existing:
                    # Update existing assessment
                    await self.update_assessment(
                        assessment_id=deception.linked_assessment_id,
                        score=final_score,
                        confidence=confidence,
                        factors=factors,
                        notes=f"Auto-updated from deception assessment {deception.id}. "
                              f"Deception risk: {deception.risk_level} ({deception.overall_score}%)",
                    )
                    logger.info(f"Updated credibility assessment {deception.linked_assessment_id} "
                               f"from deception {deception.id}: score={final_score}")
                    return

            # Create new credibility assessment
            assessment = await self.create_assessment(
                source_type=deception.source_type,
                source_id=deception.source_id,
                score=final_score,
                confidence=confidence,
                factors=factors,
                assessed_by=AssessmentMethod.AUTOMATED,
                notes=f"Auto-generated from deception assessment {deception.id}. "
                      f"Deception risk: {deception.risk_level} ({deception.overall_score}%)",
            )

            # Link the new assessment back to deception
            deception.linked_assessment_id = assessment.id
            await self._save_deception_assessment(deception, update=True)

            logger.info(f"Created credibility assessment {assessment.id} "
                       f"from deception {deception.id}: score={final_score}")

        except Exception as e:
            logger.error(f"Failed to sync deception to credibility: {e}")

    async def _save_deception_assessment(self, assessment: DeceptionAssessment, update: bool = False) -> None:
        """Save a deception assessment to the database."""
        if not self._db:
            return

        import json

        data = {
            "id": assessment.id,
            "source_type": assessment.source_type.value,
            "source_id": assessment.source_id,
            "source_name": assessment.source_name,
            "mom_data": json.dumps(assessment.mom_checklist.to_dict()) if assessment.mom_checklist else "{}",
            "pop_data": json.dumps(assessment.pop_checklist.to_dict()) if assessment.pop_checklist else "{}",
            "moses_data": json.dumps(assessment.moses_checklist.to_dict()) if assessment.moses_checklist else "{}",
            "eve_data": json.dumps(assessment.eve_checklist.to_dict()) if assessment.eve_checklist else "{}",
            "overall_score": assessment.overall_score,
            "risk_level": assessment.risk_level.value if isinstance(assessment.risk_level, DeceptionRisk) else assessment.risk_level,
            "confidence": assessment.confidence,
            "linked_assessment_id": assessment.linked_assessment_id,
            "affects_credibility": 1 if assessment.affects_credibility else 0,
            "credibility_weight": assessment.credibility_weight,
            "assessed_by": assessment.assessed_by.value,
            "assessor_id": assessment.assessor_id,
            "summary": assessment.summary,
            "red_flags": json.dumps(assessment.red_flags),
            "created_at": assessment.created_at.isoformat(),
            "updated_at": assessment.updated_at.isoformat(),
        }

        if update:
            await self._db.execute("""
                UPDATE arkham_deception_assessments SET
                    source_type=:source_type, source_id=:source_id, source_name=:source_name,
                    mom_data=:mom_data, pop_data=:pop_data, moses_data=:moses_data, eve_data=:eve_data,
                    overall_score=:overall_score, risk_level=:risk_level, confidence=:confidence,
                    linked_assessment_id=:linked_assessment_id, affects_credibility=:affects_credibility,
                    credibility_weight=:credibility_weight, assessed_by=:assessed_by, assessor_id=:assessor_id,
                    summary=:summary, red_flags=:red_flags, created_at=:created_at, updated_at=:updated_at
                WHERE id=:id
            """, data)
        else:
            await self._db.execute("""
                INSERT INTO arkham_deception_assessments (
                    id, source_type, source_id, source_name,
                    mom_data, pop_data, moses_data, eve_data,
                    overall_score, risk_level, confidence,
                    linked_assessment_id, affects_credibility, credibility_weight,
                    assessed_by, assessor_id, summary, red_flags,
                    created_at, updated_at
                ) VALUES (:id, :source_type, :source_id, :source_name,
                    :mom_data, :pop_data, :moses_data, :eve_data,
                    :overall_score, :risk_level, :confidence,
                    :linked_assessment_id, :affects_credibility, :credibility_weight,
                    :assessed_by, :assessor_id, :summary, :red_flags,
                    :created_at, :updated_at)
            """, data)

    def _row_to_deception_assessment(self, row: Dict[str, Any]) -> DeceptionAssessment:
        """Convert database row to DeceptionAssessment object."""
        import json

        def parse_checklist(data_str: str, checklist_type: DeceptionChecklistType) -> Optional[DeceptionChecklist]:
            if not data_str or data_str == "{}":
                return create_empty_checklist(checklist_type)

            try:
                data = json.loads(data_str)
                if not data.get("indicators"):
                    return create_empty_checklist(checklist_type)

                indicators = [
                    DeceptionIndicator(
                        id=ind.get("id", ""),
                        checklist=DeceptionChecklistType(ind.get("checklist", checklist_type.value)),
                        question=ind.get("question", ""),
                        answer=ind.get("answer"),
                        strength=IndicatorStrength(ind.get("strength", "none")),
                        confidence=ind.get("confidence", 0.0),
                        evidence_ids=ind.get("evidence_ids", []),
                        notes=ind.get("notes"),
                    )
                    for ind in data.get("indicators", [])
                ]

                completed_at = None
                if data.get("completed_at"):
                    try:
                        completed_at = datetime.fromisoformat(data["completed_at"])
                    except (ValueError, TypeError):
                        pass

                return DeceptionChecklist(
                    checklist_type=checklist_type,
                    indicators=indicators,
                    overall_score=data.get("overall_score", 0),
                    risk_level=data.get("risk_level", "minimal"),
                    summary=data.get("summary"),
                    completed_at=completed_at,
                )
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                logger.warning(f"Failed to parse checklist data: {e}")
                return create_empty_checklist(checklist_type)

        risk_level_str = row.get("risk_level", "minimal")
        try:
            risk_level = DeceptionRisk(risk_level_str)
        except ValueError:
            risk_level = DeceptionRisk.MINIMAL

        return DeceptionAssessment(
            id=row["id"],
            source_type=SourceType(row["source_type"]),
            source_id=row["source_id"],
            source_name=row.get("source_name"),
            mom_checklist=parse_checklist(row.get("mom_data", "{}"), DeceptionChecklistType.MOM),
            pop_checklist=parse_checklist(row.get("pop_data", "{}"), DeceptionChecklistType.POP),
            moses_checklist=parse_checklist(row.get("moses_data", "{}"), DeceptionChecklistType.MOSES),
            eve_checklist=parse_checklist(row.get("eve_data", "{}"), DeceptionChecklistType.EVE),
            overall_score=row.get("overall_score", 0),
            risk_level=risk_level,
            confidence=row.get("confidence", 0.0),
            linked_assessment_id=row.get("linked_assessment_id"),
            affects_credibility=bool(row.get("affects_credibility", 1)),
            credibility_weight=row.get("credibility_weight", 0.7),
            assessed_by=AssessmentMethod(row.get("assessed_by", "manual")),
            assessor_id=row.get("assessor_id"),
            summary=row.get("summary"),
            red_flags=json.loads(row.get("red_flags", "[]")),
            created_at=datetime.fromisoformat(row["created_at"]) if row.get("created_at") else datetime.utcnow(),
            updated_at=datetime.fromisoformat(row["updated_at"]) if row.get("updated_at") else datetime.utcnow(),
        )

    def _parse_llm_deception_response(
        self,
        response: str,
        checklist_type: DeceptionChecklistType,
        standard_indicators: List[Any],
    ) -> Dict[str, Any]:
        """Parse LLM deception analysis response."""
        import json

        logger.info(f"Parsing LLM response for {checklist_type.value}: {response[:500]}...")

        try:
            # Try to extract JSON from response
            start = response.find("{")
            end = response.rfind("}") + 1
            if start >= 0 and end > start:
                json_str = response[start:end]
                logger.info(f"Extracted JSON: {json_str[:300]}...")
                data = json.loads(json_str)
                logger.info(f"Parsed data keys: {list(data.keys())}, indicators count: {len(data.get('indicators', []))}")

                # Build indicators from response
                indicators = []
                response_indicators = {ind.get("id"): ind for ind in data.get("indicators", [])}

                for std_ind in standard_indicators:
                    resp_ind = response_indicators.get(std_ind.id, {})

                    strength_str = resp_ind.get("strength", "none").lower()
                    try:
                        strength = IndicatorStrength(strength_str)
                    except ValueError:
                        strength = IndicatorStrength.NONE

                    indicators.append(DeceptionIndicator(
                        id=std_ind.id,
                        checklist=checklist_type,
                        question=std_ind.question,
                        answer=resp_ind.get("answer"),
                        strength=strength,
                        confidence=resp_ind.get("confidence", 0.5),
                        notes=resp_ind.get("reasoning"),
                    ))

                checklist = DeceptionChecklist(
                    checklist_type=checklist_type,
                    indicators=indicators,
                    overall_score=data.get("checklist_score", 0),
                    risk_level=self._score_to_risk_level(data.get("checklist_score", 0)),
                    summary=data.get("overall_assessment"),
                    completed_at=datetime.utcnow(),
                )

                return {
                    "checklist": checklist,
                    "reasoning": data.get("overall_assessment", ""),
                    "confidence": 0.7,
                    "key_concerns": data.get("key_concerns", []),
                }

        except json.JSONDecodeError:
            logger.warning("Failed to parse LLM deception response as JSON")

        # Return empty checklist on failure
        return {
            "checklist": create_empty_checklist(checklist_type),
            "reasoning": "Failed to parse LLM response",
            "confidence": 0.0,
        }
