"""
Claims Shard - Main Shard Implementation

Claim extraction and tracking for ArkhamFrame - foundation for
contradiction detection and fact-checking.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from arkham_frame import ArkhamShard

from .models import (
    Claim,
    ClaimExtractionResult,
    ClaimFilter,
    ClaimMatch,
    ClaimMergeResult,
    ClaimStatistics,
    ClaimStatus,
    ClaimType,
    Evidence,
    EvidenceRelationship,
    EvidenceStrength,
    EvidenceType,
    ExtractionMethod,
)

logger = logging.getLogger(__name__)


class ClaimsShard(ArkhamShard):
    """
    Claims Shard - Extracts and tracks factual claims from documents.

    This shard provides:
    - Claim extraction from text and documents
    - Evidence linking and management
    - Claim status workflow (unverified → verified/disputed)
    - Similarity detection for claim deduplication
    - Statistics and reporting
    """

    name = "claims"
    version = "0.1.0"
    description = "Claim extraction and tracking for contradiction detection and fact-checking"

    def __init__(self):
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

        self._initialized = True
        logger.info(f"ClaimsShard initialized (v{self.version})")

    async def shutdown(self) -> None:
        """Clean shutdown of shard."""
        if self._events:
            await self._events.unsubscribe("document.processed", self._on_document_processed)
            await self._events.unsubscribe("entity.created", self._on_entity_created)
            await self._events.unsubscribe("entity.updated", self._on_entity_updated)

        self._initialized = False
        logger.info("ClaimsShard shutdown complete")

    def get_routes(self):
        """Return FastAPI router for this shard."""
        from .api import router
        return router

    # === Database Schema ===

    async def _create_schema(self) -> None:
        """Create database tables for claims shard."""
        if not self._db:
            logger.warning("Database not available, skipping schema creation")
            return

        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS arkham_claims (
                id TEXT PRIMARY KEY,
                text TEXT NOT NULL,
                claim_type TEXT DEFAULT 'factual',
                status TEXT DEFAULT 'unverified',
                confidence REAL DEFAULT 1.0,

                source_document_id TEXT,
                source_start_char INTEGER,
                source_end_char INTEGER,
                source_context TEXT,

                extracted_by TEXT DEFAULT 'manual',
                extraction_model TEXT,

                entity_ids TEXT DEFAULT '[]',
                evidence_count INTEGER DEFAULT 0,
                supporting_count INTEGER DEFAULT 0,
                refuting_count INTEGER DEFAULT 0,

                created_at TEXT,
                updated_at TEXT,
                verified_at TEXT,

                metadata TEXT DEFAULT '{}'
            )
        """)

        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS arkham_claim_evidence (
                id TEXT PRIMARY KEY,
                claim_id TEXT NOT NULL,
                evidence_type TEXT NOT NULL,
                reference_id TEXT NOT NULL,
                reference_title TEXT,

                relationship TEXT DEFAULT 'supports',
                strength TEXT DEFAULT 'moderate',

                excerpt TEXT,
                notes TEXT,

                added_by TEXT DEFAULT 'system',
                added_at TEXT,
                metadata TEXT DEFAULT '{}',

                FOREIGN KEY (claim_id) REFERENCES arkham_claims(id)
            )
        """)

        # Create indexes for common queries
        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_claims_status ON arkham_claims(status)
        """)
        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_claims_document ON arkham_claims(source_document_id)
        """)
        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_claims_type ON arkham_claims(claim_type)
        """)
        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_evidence_claim ON arkham_claim_evidence(claim_id)
        """)

        logger.debug("Claims schema created/verified")

    # === Event Subscriptions ===

    async def _subscribe_to_events(self) -> None:
        """Subscribe to relevant events from other shards."""
        if not self._events:
            logger.warning("Events service not available")
            return

        await self._events.subscribe("document.processed", self._on_document_processed)
        await self._events.subscribe("entity.created", self._on_entity_created)
        await self._events.subscribe("entity.updated", self._on_entity_updated)

    async def _on_document_processed(self, event: Dict[str, Any]) -> None:
        """Handle document.processed event - extract claims from new documents."""
        document_id = event.get("payload", {}).get("document_id")
        if not document_id:
            return

        logger.info(f"Document processed, queuing claim extraction: {document_id}")
        # Queue extraction job via workers if available
        if hasattr(self.frame, "workers"):
            await self.frame.workers.enqueue(
                pool="extraction",
                job_id=f"claims-extract-{document_id}",
                payload={"document_id": document_id, "action": "extract_claims"},
            )

    async def _on_entity_created(self, event: Dict[str, Any]) -> None:
        """Handle entity.created event - link claims to new entities."""
        entity_id = event.get("payload", {}).get("entity_id")
        entity_name = event.get("payload", {}).get("name")
        if entity_id and entity_name:
            await self._link_claims_to_entity(entity_id, entity_name)

    async def _on_entity_updated(self, event: Dict[str, Any]) -> None:
        """Handle entity.updated event - update claim-entity links."""
        entity_id = event.get("payload", {}).get("entity_id")
        if entity_id:
            logger.debug(f"Entity updated, reviewing claim links: {entity_id}")

    # === Public API Methods ===

    async def create_claim(
        self,
        text: str,
        claim_type: ClaimType = ClaimType.FACTUAL,
        source_document_id: Optional[str] = None,
        source_start_char: Optional[int] = None,
        source_end_char: Optional[int] = None,
        source_context: Optional[str] = None,
        extracted_by: ExtractionMethod = ExtractionMethod.MANUAL,
        extraction_model: Optional[str] = None,
        confidence: float = 1.0,
        entity_ids: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Claim:
        """Create a new claim."""
        claim_id = str(uuid4())
        now = datetime.utcnow()

        claim = Claim(
            id=claim_id,
            text=text,
            claim_type=claim_type,
            status=ClaimStatus.UNVERIFIED,
            confidence=confidence,
            source_document_id=source_document_id,
            source_start_char=source_start_char,
            source_end_char=source_end_char,
            source_context=source_context,
            extracted_by=extracted_by,
            extraction_model=extraction_model,
            entity_ids=entity_ids or [],
            created_at=now,
            updated_at=now,
            metadata=metadata or {},
        )

        await self._save_claim(claim)

        # Emit event
        if self._events:
            await self._events.emit(
                "claims.claim.created",
                {
                    "claim_id": claim_id,
                    "text": text[:200],
                    "claim_type": claim_type.value,
                    "source_document_id": source_document_id,
                },
                source=self.name,
            )

        return claim

    async def get_claim(self, claim_id: str) -> Optional[Claim]:
        """Get a claim by ID."""
        if not self._db:
            return None

        row = await self._db.fetch_one(
            "SELECT * FROM arkham_claims WHERE id = ?",
            [claim_id],
        )
        return self._row_to_claim(row) if row else None

    async def list_claims(
        self,
        filter: Optional[ClaimFilter] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Claim]:
        """List claims with optional filtering."""
        if not self._db:
            return []

        query = "SELECT * FROM arkham_claims WHERE 1=1"
        params = []

        if filter:
            if filter.status:
                query += " AND status = ?"
                params.append(filter.status.value)
            if filter.claim_type:
                query += " AND claim_type = ?"
                params.append(filter.claim_type.value)
            if filter.document_id:
                query += " AND source_document_id = ?"
                params.append(filter.document_id)
            if filter.min_confidence is not None:
                query += " AND confidence >= ?"
                params.append(filter.min_confidence)
            if filter.max_confidence is not None:
                query += " AND confidence <= ?"
                params.append(filter.max_confidence)
            if filter.extracted_by:
                query += " AND extracted_by = ?"
                params.append(filter.extracted_by.value)
            if filter.has_evidence is not None:
                if filter.has_evidence:
                    query += " AND evidence_count > 0"
                else:
                    query += " AND evidence_count = 0"
            if filter.search_text:
                query += " AND text LIKE ?"
                params.append(f"%{filter.search_text}%")

        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = await self._db.fetch_all(query, params)
        return [self._row_to_claim(row) for row in rows]

    async def update_claim_status(
        self,
        claim_id: str,
        status: ClaimStatus,
        notes: Optional[str] = None,
    ) -> Optional[Claim]:
        """Update the status of a claim."""
        claim = await self.get_claim(claim_id)
        if not claim:
            return None

        old_status = claim.status
        claim.status = status
        claim.updated_at = datetime.utcnow()

        if status == ClaimStatus.VERIFIED:
            claim.verified_at = datetime.utcnow()

        await self._save_claim(claim, update=True)

        # Emit event
        if self._events:
            await self._events.emit(
                "claims.claim.status_changed",
                {
                    "claim_id": claim_id,
                    "old_status": old_status.value,
                    "new_status": status.value,
                    "notes": notes,
                },
                source=self.name,
            )

        return claim

    async def add_evidence(
        self,
        claim_id: str,
        evidence_type: EvidenceType,
        reference_id: str,
        relationship: EvidenceRelationship = EvidenceRelationship.SUPPORTS,
        strength: EvidenceStrength = EvidenceStrength.MODERATE,
        reference_title: Optional[str] = None,
        excerpt: Optional[str] = None,
        notes: Optional[str] = None,
        added_by: str = "system",
    ) -> Evidence:
        """Add evidence to a claim."""
        evidence_id = str(uuid4())
        now = datetime.utcnow()

        evidence = Evidence(
            id=evidence_id,
            claim_id=claim_id,
            evidence_type=evidence_type,
            reference_id=reference_id,
            reference_title=reference_title,
            relationship=relationship,
            strength=strength,
            excerpt=excerpt,
            notes=notes,
            added_by=added_by,
            added_at=now,
        )

        await self._save_evidence(evidence)
        await self._update_claim_evidence_counts(claim_id)

        # Emit event
        if self._events:
            await self._events.emit(
                "claims.evidence.linked",
                {
                    "claim_id": claim_id,
                    "evidence_id": evidence_id,
                    "evidence_type": evidence_type.value,
                    "relationship": relationship.value,
                },
                source=self.name,
            )

        return evidence

    async def get_claim_evidence(self, claim_id: str) -> List[Evidence]:
        """Get all evidence for a claim."""
        if not self._db:
            return []

        rows = await self._db.fetch_all(
            "SELECT * FROM arkham_claim_evidence WHERE claim_id = ? ORDER BY added_at DESC",
            [claim_id],
        )
        return [self._row_to_evidence(row) for row in rows]

    async def extract_claims_from_text(
        self,
        text: str,
        document_id: Optional[str] = None,
        extraction_model: Optional[str] = None,
    ) -> ClaimExtractionResult:
        """Extract claims from text using LLM."""
        import time
        start_time = time.time()
        claims = []
        errors = []

        if not self._llm or not self._llm.is_available():
            errors.append("LLM service not available")
            return ClaimExtractionResult(
                claims=[],
                source_document_id=document_id,
                extraction_method=ExtractionMethod.LLM,
                extraction_model=extraction_model,
                total_extracted=0,
                processing_time_ms=(time.time() - start_time) * 1000,
                errors=errors,
            )

        try:
            # LLM prompt for claim extraction
            prompt = f"""Extract factual claims from the following text.
For each claim, provide:
- The exact claim text
- The type (factual, opinion, prediction, quantitative, attribution)
- Confidence score (0.0-1.0)
- Start and end character positions

Text:
{text}

Return claims as JSON array."""

            response = await self._llm.complete(prompt, model=extraction_model)

            # Parse LLM response and create claims
            extracted_data = self._parse_extraction_response(response)

            for item in extracted_data:
                claim = await self.create_claim(
                    text=item.get("text", ""),
                    claim_type=ClaimType(item.get("type", "factual")),
                    source_document_id=document_id,
                    source_start_char=item.get("start_char"),
                    source_end_char=item.get("end_char"),
                    extracted_by=ExtractionMethod.LLM,
                    extraction_model=extraction_model,
                    confidence=item.get("confidence", 0.8),
                )
                claims.append(claim)

        except Exception as e:
            logger.error(f"Claim extraction failed: {e}")
            errors.append(str(e))

        processing_time = (time.time() - start_time) * 1000

        # Emit event
        if self._events and claims:
            await self._events.emit(
                "claims.extraction.completed",
                {
                    "document_id": document_id,
                    "claims_extracted": len(claims),
                    "processing_time_ms": processing_time,
                },
                source=self.name,
            )

        return ClaimExtractionResult(
            claims=claims,
            source_document_id=document_id,
            extraction_method=ExtractionMethod.LLM,
            extraction_model=extraction_model,
            total_extracted=len(claims),
            processing_time_ms=processing_time,
            errors=errors,
        )

    async def find_similar_claims(
        self,
        claim_id: str,
        threshold: float = 0.8,
        limit: int = 10,
    ) -> List[ClaimMatch]:
        """Find claims similar to the given claim."""
        claim = await self.get_claim(claim_id)
        if not claim:
            return []

        matches = []

        # Use vector similarity if available
        if self._vectors and self._vectors.is_available():
            similar = await self._vectors.search(
                collection="claims",
                query=claim.text,
                limit=limit + 1,  # +1 to exclude self
            )
            for item in similar:
                if item["id"] != claim_id and item["score"] >= threshold:
                    matches.append(ClaimMatch(
                        claim_id=claim_id,
                        matched_claim_id=item["id"],
                        similarity_score=item["score"],
                        match_type="semantic",
                        suggested_action="review" if item["score"] < 0.95 else "merge",
                    ))
        else:
            # Fallback to simple text matching
            all_claims = await self.list_claims(limit=1000)
            for other in all_claims:
                if other.id != claim_id:
                    score = self._simple_similarity(claim.text, other.text)
                    if score >= threshold:
                        matches.append(ClaimMatch(
                            claim_id=claim_id,
                            matched_claim_id=other.id,
                            similarity_score=score,
                            match_type="fuzzy",
                            suggested_action="review",
                        ))

        return sorted(matches, key=lambda m: m.similarity_score, reverse=True)[:limit]

    async def merge_claims(
        self,
        primary_claim_id: str,
        claim_ids_to_merge: List[str],
    ) -> ClaimMergeResult:
        """Merge duplicate claims into a primary claim."""
        evidence_transferred = 0
        entities_merged = set()

        for claim_id in claim_ids_to_merge:
            if claim_id == primary_claim_id:
                continue

            # Transfer evidence
            evidence = await self.get_claim_evidence(claim_id)
            for ev in evidence:
                ev.claim_id = primary_claim_id
                await self._save_evidence(ev, update=True)
                evidence_transferred += 1

            # Collect entity links
            claim = await self.get_claim(claim_id)
            if claim:
                entities_merged.update(claim.entity_ids)

            # Mark claim as merged (retracted)
            await self.update_claim_status(
                claim_id,
                ClaimStatus.RETRACTED,
                notes=f"Merged into {primary_claim_id}",
            )

        # Update primary claim with merged entities
        primary = await self.get_claim(primary_claim_id)
        if primary:
            primary.entity_ids = list(set(primary.entity_ids) | entities_merged)
            await self._save_claim(primary, update=True)

        await self._update_claim_evidence_counts(primary_claim_id)

        # Emit event
        if self._events:
            await self._events.emit(
                "claims.claims.merged",
                {
                    "primary_claim_id": primary_claim_id,
                    "merged_claim_ids": claim_ids_to_merge,
                    "evidence_transferred": evidence_transferred,
                },
                source=self.name,
            )

        return ClaimMergeResult(
            primary_claim_id=primary_claim_id,
            merged_claim_ids=claim_ids_to_merge,
            evidence_transferred=evidence_transferred,
            entities_merged=len(entities_merged),
        )

    async def get_statistics(self) -> ClaimStatistics:
        """Get statistics about claims in the system."""
        if not self._db:
            return ClaimStatistics()

        # Total claims
        total = await self._db.fetch_one(
            "SELECT COUNT(*) as count FROM arkham_claims"
        )
        total_claims = total["count"] if total else 0

        # By status
        status_rows = await self._db.fetch_all(
            "SELECT status, COUNT(*) as count FROM arkham_claims GROUP BY status"
        )
        by_status = {row["status"]: row["count"] for row in status_rows}

        # By type
        type_rows = await self._db.fetch_all(
            "SELECT claim_type, COUNT(*) as count FROM arkham_claims GROUP BY claim_type"
        )
        by_type = {row["claim_type"]: row["count"] for row in type_rows}

        # By extraction method
        method_rows = await self._db.fetch_all(
            "SELECT extracted_by, COUNT(*) as count FROM arkham_claims GROUP BY extracted_by"
        )
        by_method = {row["extracted_by"]: row["count"] for row in method_rows}

        # Evidence stats
        evidence_total = await self._db.fetch_one(
            "SELECT COUNT(*) as count FROM arkham_claim_evidence"
        )
        total_evidence = evidence_total["count"] if evidence_total else 0

        supporting = await self._db.fetch_one(
            "SELECT COUNT(*) as count FROM arkham_claim_evidence WHERE relationship = 'supports'"
        )
        refuting = await self._db.fetch_one(
            "SELECT COUNT(*) as count FROM arkham_claim_evidence WHERE relationship = 'refutes'"
        )

        with_evidence = await self._db.fetch_one(
            "SELECT COUNT(*) as count FROM arkham_claims WHERE evidence_count > 0"
        )

        # Averages
        avg_conf = await self._db.fetch_one(
            "SELECT AVG(confidence) as avg FROM arkham_claims"
        )
        avg_ev = await self._db.fetch_one(
            "SELECT AVG(evidence_count) as avg FROM arkham_claims"
        )

        return ClaimStatistics(
            total_claims=total_claims,
            by_status=by_status,
            by_type=by_type,
            by_extraction_method=by_method,
            total_evidence=total_evidence,
            evidence_supporting=supporting["count"] if supporting else 0,
            evidence_refuting=refuting["count"] if refuting else 0,
            claims_with_evidence=with_evidence["count"] if with_evidence else 0,
            claims_without_evidence=total_claims - (with_evidence["count"] if with_evidence else 0),
            avg_confidence=avg_conf["avg"] if avg_conf and avg_conf["avg"] else 0.0,
            avg_evidence_per_claim=avg_ev["avg"] if avg_ev and avg_ev["avg"] else 0.0,
        )

    async def get_count(self, status: Optional[str] = None) -> int:
        """Get count of claims, optionally filtered by status."""
        if not self._db:
            return 0

        if status:
            result = await self._db.fetch_one(
                "SELECT COUNT(*) as count FROM arkham_claims WHERE status = ?",
                [status],
            )
        else:
            result = await self._db.fetch_one(
                "SELECT COUNT(*) as count FROM arkham_claims"
            )

        return result["count"] if result else 0

    # === Private Helper Methods ===

    async def _save_claim(self, claim: Claim, update: bool = False) -> None:
        """Save a claim to the database."""
        if not self._db:
            return

        import json
        data = (
            claim.id,
            claim.text,
            claim.claim_type.value,
            claim.status.value,
            claim.confidence,
            claim.source_document_id,
            claim.source_start_char,
            claim.source_end_char,
            claim.source_context,
            claim.extracted_by.value,
            claim.extraction_model,
            json.dumps(claim.entity_ids),
            claim.evidence_count,
            claim.supporting_count,
            claim.refuting_count,
            claim.created_at.isoformat(),
            claim.updated_at.isoformat(),
            claim.verified_at.isoformat() if claim.verified_at else None,
            json.dumps(claim.metadata),
        )

        if update:
            await self._db.execute("""
                UPDATE arkham_claims SET
                    text=?, claim_type=?, status=?, confidence=?,
                    source_document_id=?, source_start_char=?, source_end_char=?,
                    source_context=?, extracted_by=?, extraction_model=?,
                    entity_ids=?, evidence_count=?, supporting_count=?, refuting_count=?,
                    created_at=?, updated_at=?, verified_at=?, metadata=?
                WHERE id=?
            """, data[1:] + (claim.id,))
        else:
            await self._db.execute("""
                INSERT INTO arkham_claims (
                    id, text, claim_type, status, confidence,
                    source_document_id, source_start_char, source_end_char,
                    source_context, extracted_by, extraction_model,
                    entity_ids, evidence_count, supporting_count, refuting_count,
                    created_at, updated_at, verified_at, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, data)

    async def _save_evidence(self, evidence: Evidence, update: bool = False) -> None:
        """Save evidence to the database."""
        if not self._db:
            return

        import json
        data = (
            evidence.id,
            evidence.claim_id,
            evidence.evidence_type.value,
            evidence.reference_id,
            evidence.reference_title,
            evidence.relationship.value,
            evidence.strength.value,
            evidence.excerpt,
            evidence.notes,
            evidence.added_by,
            evidence.added_at.isoformat(),
            json.dumps(evidence.metadata),
        )

        if update:
            await self._db.execute("""
                UPDATE arkham_claim_evidence SET
                    claim_id=?, evidence_type=?, reference_id=?, reference_title=?,
                    relationship=?, strength=?, excerpt=?, notes=?,
                    added_by=?, added_at=?, metadata=?
                WHERE id=?
            """, data[1:] + (evidence.id,))
        else:
            await self._db.execute("""
                INSERT INTO arkham_claim_evidence (
                    id, claim_id, evidence_type, reference_id, reference_title,
                    relationship, strength, excerpt, notes,
                    added_by, added_at, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, data)

    async def _update_claim_evidence_counts(self, claim_id: str) -> None:
        """Update evidence counts on a claim."""
        if not self._db:
            return

        total = await self._db.fetch_one(
            "SELECT COUNT(*) as count FROM arkham_claim_evidence WHERE claim_id = ?",
            [claim_id],
        )
        supporting = await self._db.fetch_one(
            "SELECT COUNT(*) as count FROM arkham_claim_evidence WHERE claim_id = ? AND relationship = 'supports'",
            [claim_id],
        )
        refuting = await self._db.fetch_one(
            "SELECT COUNT(*) as count FROM arkham_claim_evidence WHERE claim_id = ? AND relationship = 'refutes'",
            [claim_id],
        )

        await self._db.execute("""
            UPDATE arkham_claims SET
                evidence_count = ?,
                supporting_count = ?,
                refuting_count = ?,
                updated_at = ?
            WHERE id = ?
        """, [
            total["count"] if total else 0,
            supporting["count"] if supporting else 0,
            refuting["count"] if refuting else 0,
            datetime.utcnow().isoformat(),
            claim_id,
        ])

    async def _link_claims_to_entity(self, entity_id: str, entity_name: str) -> None:
        """Link claims mentioning an entity to that entity."""
        if not self._db:
            return

        # Find claims mentioning this entity name
        claims = await self._db.fetch_all(
            "SELECT id, entity_ids FROM arkham_claims WHERE text LIKE ?",
            [f"%{entity_name}%"],
        )

        import json
        for row in claims:
            entity_ids = json.loads(row["entity_ids"] or "[]")
            if entity_id not in entity_ids:
                entity_ids.append(entity_id)
                await self._db.execute(
                    "UPDATE arkham_claims SET entity_ids = ? WHERE id = ?",
                    [json.dumps(entity_ids), row["id"]],
                )

    def _row_to_claim(self, row: Dict[str, Any]) -> Claim:
        """Convert database row to Claim object."""
        import json
        return Claim(
            id=row["id"],
            text=row["text"],
            claim_type=ClaimType(row["claim_type"]),
            status=ClaimStatus(row["status"]),
            confidence=row["confidence"],
            source_document_id=row["source_document_id"],
            source_start_char=row["source_start_char"],
            source_end_char=row["source_end_char"],
            source_context=row["source_context"],
            extracted_by=ExtractionMethod(row["extracted_by"]),
            extraction_model=row["extraction_model"],
            entity_ids=json.loads(row["entity_ids"] or "[]"),
            evidence_count=row["evidence_count"],
            supporting_count=row["supporting_count"],
            refuting_count=row["refuting_count"],
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else datetime.utcnow(),
            updated_at=datetime.fromisoformat(row["updated_at"]) if row["updated_at"] else datetime.utcnow(),
            verified_at=datetime.fromisoformat(row["verified_at"]) if row["verified_at"] else None,
            metadata=json.loads(row["metadata"] or "{}"),
        )

    def _row_to_evidence(self, row: Dict[str, Any]) -> Evidence:
        """Convert database row to Evidence object."""
        import json
        return Evidence(
            id=row["id"],
            claim_id=row["claim_id"],
            evidence_type=EvidenceType(row["evidence_type"]),
            reference_id=row["reference_id"],
            reference_title=row["reference_title"],
            relationship=EvidenceRelationship(row["relationship"]),
            strength=EvidenceStrength(row["strength"]),
            excerpt=row["excerpt"],
            notes=row["notes"],
            added_by=row["added_by"],
            added_at=datetime.fromisoformat(row["added_at"]) if row["added_at"] else datetime.utcnow(),
            metadata=json.loads(row["metadata"] or "{}"),
        )

    def _parse_extraction_response(self, response: str) -> List[Dict[str, Any]]:
        """Parse LLM extraction response into structured data."""
        import json
        try:
            # Try to extract JSON from response
            start = response.find("[")
            end = response.rfind("]") + 1
            if start >= 0 and end > start:
                return json.loads(response[start:end])
        except json.JSONDecodeError:
            logger.warning("Failed to parse LLM extraction response as JSON")
        return []

    def _simple_similarity(self, text1: str, text2: str) -> float:
        """Calculate simple similarity between two texts."""
        # Jaccard similarity on words
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        if not words1 or not words2:
            return 0.0
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        return intersection / union if union > 0 else 0.0
