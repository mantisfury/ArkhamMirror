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

        row = await self._db.fetch_one(
            "SELECT * FROM arkham_credibility_assessments WHERE id = ?",
            [assessment_id],
        )
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
        params = []

        if filter:
            if filter.source_type:
                query += " AND source_type = ?"
                params.append(filter.source_type.value)
            if filter.source_id:
                query += " AND source_id = ?"
                params.append(filter.source_id)
            if filter.min_score is not None:
                query += " AND score >= ?"
                params.append(filter.min_score)
            if filter.max_score is not None:
                query += " AND score <= ?"
                params.append(filter.max_score)
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
                query += " AND score >= ? AND score <= ?"
                params.extend([min_s, max_s])
            if filter.assessed_by:
                query += " AND assessed_by = ?"
                params.append(filter.assessed_by.value)
            if filter.assessor_id:
                query += " AND assessor_id = ?"
                params.append(filter.assessor_id)
            if filter.min_confidence is not None:
                query += " AND confidence >= ?"
                params.append(filter.min_confidence)
            if filter.max_confidence is not None:
                query += " AND confidence <= ?"
                params.append(filter.max_confidence)

        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

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

        await self._db.execute(
            "DELETE FROM arkham_credibility_assessments WHERE id = ?",
            [assessment_id],
        )
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
        rows = await self._db.fetch_all(
            """
            SELECT * FROM arkham_credibility_assessments
            WHERE source_type = ? AND source_id = ?
            ORDER BY created_at DESC
            """,
            [source_type.value, source_id],
        )

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

                response = await self._llm.complete(prompt)
                # Parse LLM response
                parsed = self._parse_llm_assessment(response)
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

        # Total assessments
        total = await self._db.fetch_one(
            "SELECT COUNT(*) as count FROM arkham_credibility_assessments"
        )
        total_assessments = total["count"] if total else 0

        # By source type
        type_rows = await self._db.fetch_all(
            "SELECT source_type, COUNT(*) as count FROM arkham_credibility_assessments GROUP BY source_type"
        )
        by_source_type = {row["source_type"]: row["count"] for row in type_rows}

        # By level (calculate from score ranges)
        unreliable = await self._db.fetch_one(
            "SELECT COUNT(*) as count FROM arkham_credibility_assessments WHERE score <= 20"
        )
        low = await self._db.fetch_one(
            "SELECT COUNT(*) as count FROM arkham_credibility_assessments WHERE score > 20 AND score <= 40"
        )
        medium = await self._db.fetch_one(
            "SELECT COUNT(*) as count FROM arkham_credibility_assessments WHERE score > 40 AND score <= 60"
        )
        high = await self._db.fetch_one(
            "SELECT COUNT(*) as count FROM arkham_credibility_assessments WHERE score > 60 AND score <= 80"
        )
        verified = await self._db.fetch_one(
            "SELECT COUNT(*) as count FROM arkham_credibility_assessments WHERE score > 80"
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
            "SELECT assessed_by, COUNT(*) as count FROM arkham_credibility_assessments GROUP BY assessed_by"
        )
        by_method = {row["assessed_by"]: row["count"] for row in method_rows}

        # Averages
        avg_score_row = await self._db.fetch_one(
            "SELECT AVG(score) as avg FROM arkham_credibility_assessments"
        )
        avg_confidence_row = await self._db.fetch_one(
            "SELECT AVG(confidence) as avg FROM arkham_credibility_assessments"
        )

        # Unique sources
        sources_row = await self._db.fetch_one(
            "SELECT COUNT(DISTINCT source_type || ':' || source_id) as count FROM arkham_credibility_assessments"
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
        params = []

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
                query += " AND score >= ? AND score <= ?"
                params.extend([min_s, max_s])

        if source_type:
            query += " AND source_type = ?"
            params.append(source_type)

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
