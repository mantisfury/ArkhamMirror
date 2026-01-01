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
            frame.app.state.claims_shard = self

        self._initialized = True
        logger.info(f"ClaimsShard initialized (v{self.version})")

    async def shutdown(self) -> None:
        """Clean shutdown of shard."""
        if self._events:
            await self._events.unsubscribe("parse.document.completed", self._on_document_processed)
            await self._events.unsubscribe("parse.entity.extracted", self._on_entity_created)

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

        # Subscribe to parse shard events for automatic claim extraction
        await self._events.subscribe("parse.document.completed", self._on_document_processed)
        await self._events.subscribe("parse.entity.extracted", self._on_entity_created)
        logger.info("Subscribed to parse.document.completed and parse.entity.extracted events")

    async def _on_document_processed(self, event: Dict[str, Any]) -> None:
        """
        Handle parse.document.completed event - extract claims from new documents.

        Event payload from parse shard:
            {
                "document_id": str,
                "entities": list,
                "chunks": int,
                "chunks_saved": int
            }
        """
        # EventBus wraps events: {"event_type": ..., "payload": {...}, "source": ...}
        payload = event.get("payload", event)  # Support both wrapped and unwrapped
        document_id = payload.get("document_id")

        if not document_id:
            logger.warning("parse.document.completed event missing document_id")
            return

        logger.info(f"Document processed, extracting claims: {document_id}")

        try:
            # Get document content from documents service
            content = None
            if hasattr(self.frame, "documents") and self.frame.documents:
                # Try to get document chunks for content
                chunks = await self.frame.documents.get_document_chunks(document_id)
                if chunks:
                    # Combine chunk content
                    texts = []
                    for chunk in chunks:
                        if hasattr(chunk, 'content'):
                            texts.append(chunk.content)
                        elif hasattr(chunk, 'text'):
                            texts.append(chunk.text)
                        elif isinstance(chunk, dict):
                            texts.append(chunk.get('content') or chunk.get('text', ''))
                    content = "\n".join(filter(None, texts))

            if not content:
                logger.warning(f"No content found for document {document_id}, skipping claim extraction")
                return

            # Extract claims using LLM if available, otherwise simple extraction
            if self._llm and hasattr(self._llm, 'is_available') and self._llm.is_available():
                claims = await self._extract_claims_llm(content, document_id)
            else:
                claims = await self._extract_claims_simple(content, document_id)

            # Store extracted claims
            for claim in claims:
                await self._store_claim(claim)

            logger.info(f"Extracted and stored {len(claims)} claims from document {document_id}")

            # Emit claims.extracted event
            if self._events and claims:
                await self._events.emit(
                    "claims.extracted",
                    {
                        "document_id": document_id,
                        "claim_count": len(claims),
                        "claim_ids": [c.id for c in claims],
                    },
                    source=self.name,
                )

        except Exception as e:
            logger.error(f"Claim extraction failed for document {document_id}: {e}", exc_info=True)

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

    # === Claim Extraction Methods ===

    async def _extract_claims_simple(self, text: str, document_id: Optional[str] = None) -> List[Claim]:
        """
        Simple claim extraction using sentence splitting.

        Fallback when LLM is not available. Splits text into sentences
        and creates claims from sentences that look like factual statements.

        Args:
            text: The text to extract claims from
            document_id: Optional source document ID

        Returns:
            List of extracted Claim objects
        """
        import re

        claims = []

        # Split into sentences (handles . ! ? but preserves abbreviations like "Dr." "Mr.")
        sentence_pattern = r'(?<=[.!?])\s+(?=[A-Z])'
        sentences = re.split(sentence_pattern, text)

        for sentence in sentences:
            sentence = sentence.strip()

            # Skip empty sentences
            if not sentence:
                continue

            # Skip very short sentences (less than 5 words)
            words = sentence.split()
            if len(words) < 5:
                continue

            # Skip questions
            if sentence.rstrip().endswith('?'):
                continue

            # Skip sentences that are likely headers or list items
            if sentence.startswith('-') or sentence.startswith('*') or sentence.startswith('#'):
                continue

            # Create claim
            claim_id = str(uuid4())
            now = datetime.utcnow()

            claim = Claim(
                id=claim_id,
                text=sentence[:1000],  # Limit claim length
                claim_type=ClaimType.FACTUAL,
                status=ClaimStatus.UNVERIFIED,
                confidence=0.5,  # Low confidence for simple extraction
                source_document_id=document_id,
                source_start_char=None,
                source_end_char=None,
                source_context=None,
                extracted_by=ExtractionMethod.RULE,
                extraction_model=None,
                entity_ids=[],
                evidence_count=0,
                supporting_count=0,
                refuting_count=0,
                created_at=now,
                updated_at=now,
                verified_at=None,
                metadata={"extraction_type": "simple_sentence_split"},
            )
            claims.append(claim)

            # Limit number of claims per document
            if len(claims) >= 100:
                logger.warning(f"Reached claim limit (100) for document {document_id}")
                break

        return claims

    async def _extract_claims_llm(self, text: str, document_id: Optional[str] = None) -> List[Claim]:
        """
        Extract claims using LLM.

        Uses the Frame's LLM service to identify factual claims with
        higher accuracy than simple extraction.

        Args:
            text: The text to extract claims from
            document_id: Optional source document ID

        Returns:
            List of extracted Claim objects
        """
        import json as json_module
        import re

        if not self._llm:
            logger.warning("LLM not available, falling back to simple extraction")
            return await self._extract_claims_simple(text, document_id)

        # Truncate text to avoid token limits
        max_text_length = 4000
        if len(text) > max_text_length:
            text = text[:max_text_length] + "..."

        system_prompt = """You are a claim extraction assistant. Your task is to identify factual claims from text.

A claim is a statement that can potentially be verified as true or false. Focus on:
- Factual statements (verifiable facts)
- Quantitative claims (numbers, statistics, dates)
- Attribution claims (statements attributed to someone)

Do NOT extract:
- Questions
- Opinions without factual basis
- Vague statements

Return a JSON array of claims. Each claim should have:
- text: The exact claim text (keep it concise, under 200 characters)
- type: One of "factual", "quantitative", "attribution", "opinion", "prediction"
- confidence: Your confidence this is a valid claim (0.0 to 1.0)"""

        prompt = f"""Extract factual claims from the following text.

Text:
{text}

Return ONLY a valid JSON array, no other text. Example format:
[{{"text": "The company was founded in 1995", "type": "factual", "confidence": 0.9}}]"""

        try:
            # Use LLM generate method
            response = await self._llm.generate(
                prompt,
                system_prompt=system_prompt,
                temperature=0.3
            )

            # Extract response text
            response_text = response.text if hasattr(response, 'text') else str(response)
            extraction_model = response.model if hasattr(response, 'model') else "unknown"

            # Parse JSON from response
            json_match = re.search(r'\[.*\]', response_text, re.DOTALL)
            if not json_match:
                logger.warning("LLM response did not contain JSON array, falling back to simple extraction")
                return await self._extract_claims_simple(text, document_id)

            claims_data = json_module.loads(json_match.group(0))

            claims = []
            now = datetime.utcnow()

            for item in claims_data:
                claim_text = item.get("text", "").strip()
                if not claim_text or len(claim_text) < 10:
                    continue

                # Map type string to ClaimType
                type_str = item.get("type", "factual").lower()
                type_mapping = {
                    "factual": ClaimType.FACTUAL,
                    "quantitative": ClaimType.QUANTITATIVE,
                    "attribution": ClaimType.ATTRIBUTION,
                    "opinion": ClaimType.OPINION,
                    "prediction": ClaimType.PREDICTION,
                }
                claim_type = type_mapping.get(type_str, ClaimType.FACTUAL)

                confidence = float(item.get("confidence", 0.8))
                confidence = max(0.0, min(1.0, confidence))  # Clamp to 0-1

                claim_id = str(uuid4())

                claim = Claim(
                    id=claim_id,
                    text=claim_text[:1000],
                    claim_type=claim_type,
                    status=ClaimStatus.UNVERIFIED,
                    confidence=confidence,
                    source_document_id=document_id,
                    source_start_char=None,
                    source_end_char=None,
                    source_context=None,
                    extracted_by=ExtractionMethod.LLM,
                    extraction_model=extraction_model,
                    entity_ids=[],
                    evidence_count=0,
                    supporting_count=0,
                    refuting_count=0,
                    created_at=now,
                    updated_at=now,
                    verified_at=None,
                    metadata={"extraction_type": "llm"},
                )
                claims.append(claim)

                # Limit claims
                if len(claims) >= 50:
                    break

            logger.info(f"LLM extracted {len(claims)} claims from document {document_id}")
            return claims

        except Exception as e:
            logger.error(f"LLM claim extraction failed: {e}", exc_info=True)
            return await self._extract_claims_simple(text, document_id)

    async def _store_claim(self, claim: Claim) -> None:
        """
        Store a claim in the database.

        Args:
            claim: The Claim object to store
        """
        if not self._db:
            logger.warning("Database not available, cannot store claim")
            return

        import json as json_module

        params = {
            "id": claim.id,
            "text": claim.text,
            "claim_type": claim.claim_type.value if isinstance(claim.claim_type, ClaimType) else claim.claim_type,
            "status": claim.status.value if isinstance(claim.status, ClaimStatus) else claim.status,
            "confidence": claim.confidence,
            "source_document_id": claim.source_document_id,
            "source_start_char": claim.source_start_char,
            "source_end_char": claim.source_end_char,
            "source_context": claim.source_context,
            "extracted_by": claim.extracted_by.value if isinstance(claim.extracted_by, ExtractionMethod) else claim.extracted_by,
            "extraction_model": claim.extraction_model,
            "entity_ids": json_module.dumps(claim.entity_ids),
            "evidence_count": claim.evidence_count,
            "supporting_count": claim.supporting_count,
            "refuting_count": claim.refuting_count,
            "created_at": claim.created_at.isoformat() if isinstance(claim.created_at, datetime) else claim.created_at,
            "updated_at": claim.updated_at.isoformat() if isinstance(claim.updated_at, datetime) else claim.updated_at,
            "verified_at": claim.verified_at.isoformat() if claim.verified_at else None,
            "metadata": json_module.dumps(claim.metadata),
        }

        await self._db.execute("""
            INSERT INTO arkham_claims (
                id, text, claim_type, status, confidence,
                source_document_id, source_start_char, source_end_char,
                source_context, extracted_by, extraction_model,
                entity_ids, evidence_count, supporting_count, refuting_count,
                created_at, updated_at, verified_at, metadata
            ) VALUES (
                :id, :text, :claim_type, :status, :confidence,
                :source_document_id, :source_start_char, :source_end_char,
                :source_context, :extracted_by, :extraction_model,
                :entity_ids, :evidence_count, :supporting_count, :refuting_count,
                :created_at, :updated_at, :verified_at, :metadata
            )
        """, params)

        logger.debug(f"Stored claim {claim.id}: {claim.text[:50]}...")

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
            "SELECT * FROM arkham_claims WHERE id = :claim_id",
            {"claim_id": claim_id},
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
        params: Dict[str, Any] = {}

        if filter:
            if filter.status:
                query += " AND status = :status"
                params["status"] = filter.status.value
            if filter.claim_type:
                query += " AND claim_type = :claim_type"
                params["claim_type"] = filter.claim_type.value
            if filter.document_id:
                query += " AND source_document_id = :document_id"
                params["document_id"] = filter.document_id
            if filter.min_confidence is not None:
                query += " AND confidence >= :min_confidence"
                params["min_confidence"] = filter.min_confidence
            if filter.max_confidence is not None:
                query += " AND confidence <= :max_confidence"
                params["max_confidence"] = filter.max_confidence
            if filter.extracted_by:
                query += " AND extracted_by = :extracted_by"
                params["extracted_by"] = filter.extracted_by.value
            if filter.has_evidence is not None:
                if filter.has_evidence:
                    query += " AND evidence_count > 0"
                else:
                    query += " AND evidence_count = 0"
            if filter.search_text:
                query += " AND text LIKE :search_text"
                params["search_text"] = f"%{filter.search_text}%"

        query += " ORDER BY created_at DESC LIMIT :limit OFFSET :offset"
        params["limit"] = limit
        params["offset"] = offset

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
            "SELECT * FROM arkham_claim_evidence WHERE claim_id = :claim_id ORDER BY added_at DESC",
            {"claim_id": claim_id},
        )
        return [self._row_to_evidence(row) for row in rows]

    async def extract_claims_from_text(
        self,
        text: str,
        document_id: Optional[str] = None,
        extraction_model: Optional[str] = None,
    ) -> ClaimExtractionResult:
        """
        Extract claims from text and store them.

        Uses LLM extraction if available, otherwise falls back to simple extraction.
        This is the public API method called by the /extract endpoint.

        Args:
            text: The text to extract claims from
            document_id: Optional source document ID
            extraction_model: Optional specific model to use

        Returns:
            ClaimExtractionResult with extracted claims and metadata
        """
        import time
        start_time = time.time()
        claims = []
        errors = []
        method = ExtractionMethod.RULE

        try:
            # Use LLM extraction if available
            if self._llm and hasattr(self._llm, 'is_available') and self._llm.is_available():
                claims = await self._extract_claims_llm(text, document_id)
                method = ExtractionMethod.LLM
            else:
                # Fall back to simple extraction
                claims = await self._extract_claims_simple(text, document_id)
                method = ExtractionMethod.RULE
                if not self._llm:
                    errors.append("LLM service not available, using simple extraction")

            # Store extracted claims and auto-link source document as evidence
            doc_title = None
            if document_id and self._db:
                # Fetch document filename for evidence reference (frame uses filename, not title)
                doc_row = await self._db.fetch_one(
                    "SELECT filename FROM arkham_frame.documents WHERE id = :doc_id",
                    {"doc_id": document_id},
                )
                if doc_row:
                    doc_title = doc_row.get("filename") or "Source Document"

            for claim in claims:
                await self._store_claim(claim)

                # Auto-link source document as evidence if we have a document_id
                if document_id:
                    await self.add_evidence(
                        claim_id=claim.id,
                        evidence_type=EvidenceType.DOCUMENT,
                        reference_id=document_id,
                        reference_title=doc_title,
                        relationship=EvidenceRelationship.SUPPORTS,
                        strength=EvidenceStrength.MODERATE,
                        excerpt=claim.source_context,
                        notes="Source document from which this claim was extracted",
                        added_by="extraction",
                    )

        except Exception as e:
            logger.error(f"Claim extraction failed: {e}", exc_info=True)
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
            extraction_method=method,
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
                "SELECT COUNT(*) as count FROM arkham_claims WHERE status = :status",
                {"status": status},
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
        params = {
            "id": claim.id,
            "text": claim.text,
            "claim_type": claim.claim_type.value,
            "status": claim.status.value,
            "confidence": claim.confidence,
            "source_document_id": claim.source_document_id,
            "source_start_char": claim.source_start_char,
            "source_end_char": claim.source_end_char,
            "source_context": claim.source_context,
            "extracted_by": claim.extracted_by.value,
            "extraction_model": claim.extraction_model,
            "entity_ids": json.dumps(claim.entity_ids),
            "evidence_count": claim.evidence_count,
            "supporting_count": claim.supporting_count,
            "refuting_count": claim.refuting_count,
            "created_at": claim.created_at.isoformat(),
            "updated_at": claim.updated_at.isoformat(),
            "verified_at": claim.verified_at.isoformat() if claim.verified_at else None,
            "metadata": json.dumps(claim.metadata),
        }

        if update:
            await self._db.execute("""
                UPDATE arkham_claims SET
                    text=:text, claim_type=:claim_type, status=:status, confidence=:confidence,
                    source_document_id=:source_document_id, source_start_char=:source_start_char, source_end_char=:source_end_char,
                    source_context=:source_context, extracted_by=:extracted_by, extraction_model=:extraction_model,
                    entity_ids=:entity_ids, evidence_count=:evidence_count, supporting_count=:supporting_count, refuting_count=:refuting_count,
                    created_at=:created_at, updated_at=:updated_at, verified_at=:verified_at, metadata=:metadata
                WHERE id=:id
            """, params)
        else:
            await self._db.execute("""
                INSERT INTO arkham_claims (
                    id, text, claim_type, status, confidence,
                    source_document_id, source_start_char, source_end_char,
                    source_context, extracted_by, extraction_model,
                    entity_ids, evidence_count, supporting_count, refuting_count,
                    created_at, updated_at, verified_at, metadata
                ) VALUES (:id, :text, :claim_type, :status, :confidence,
                    :source_document_id, :source_start_char, :source_end_char,
                    :source_context, :extracted_by, :extraction_model,
                    :entity_ids, :evidence_count, :supporting_count, :refuting_count,
                    :created_at, :updated_at, :verified_at, :metadata)
            """, params)

    async def _save_evidence(self, evidence: Evidence, update: bool = False) -> None:
        """Save evidence to the database."""
        if not self._db:
            return

        import json
        params = {
            "id": evidence.id,
            "claim_id": evidence.claim_id,
            "evidence_type": evidence.evidence_type.value,
            "reference_id": evidence.reference_id,
            "reference_title": evidence.reference_title,
            "relationship": evidence.relationship.value,
            "strength": evidence.strength.value,
            "excerpt": evidence.excerpt,
            "notes": evidence.notes,
            "added_by": evidence.added_by,
            "added_at": evidence.added_at.isoformat(),
            "metadata": json.dumps(evidence.metadata),
        }

        if update:
            await self._db.execute("""
                UPDATE arkham_claim_evidence SET
                    claim_id=:claim_id, evidence_type=:evidence_type, reference_id=:reference_id, reference_title=:reference_title,
                    relationship=:relationship, strength=:strength, excerpt=:excerpt, notes=:notes,
                    added_by=:added_by, added_at=:added_at, metadata=:metadata
                WHERE id=:id
            """, params)
        else:
            await self._db.execute("""
                INSERT INTO arkham_claim_evidence (
                    id, claim_id, evidence_type, reference_id, reference_title,
                    relationship, strength, excerpt, notes,
                    added_by, added_at, metadata
                ) VALUES (:id, :claim_id, :evidence_type, :reference_id, :reference_title,
                    :relationship, :strength, :excerpt, :notes,
                    :added_by, :added_at, :metadata)
            """, params)

    async def _update_claim_evidence_counts(self, claim_id: str) -> None:
        """Update evidence counts on a claim."""
        if not self._db:
            return

        total = await self._db.fetch_one(
            "SELECT COUNT(*) as count FROM arkham_claim_evidence WHERE claim_id = :claim_id",
            {"claim_id": claim_id},
        )
        supporting = await self._db.fetch_one(
            "SELECT COUNT(*) as count FROM arkham_claim_evidence WHERE claim_id = :claim_id AND relationship = 'supports'",
            {"claim_id": claim_id},
        )
        refuting = await self._db.fetch_one(
            "SELECT COUNT(*) as count FROM arkham_claim_evidence WHERE claim_id = :claim_id AND relationship = 'refutes'",
            {"claim_id": claim_id},
        )

        await self._db.execute("""
            UPDATE arkham_claims SET
                evidence_count = :evidence_count,
                supporting_count = :supporting_count,
                refuting_count = :refuting_count,
                updated_at = :updated_at
            WHERE id = :id
        """, {
            "evidence_count": total["count"] if total else 0,
            "supporting_count": supporting["count"] if supporting else 0,
            "refuting_count": refuting["count"] if refuting else 0,
            "updated_at": datetime.utcnow().isoformat(),
            "id": claim_id,
        })

    async def _link_claims_to_entity(self, entity_id: str, entity_name: str) -> None:
        """Link claims mentioning an entity to that entity."""
        if not self._db:
            return

        # Find claims mentioning this entity name
        claims = await self._db.fetch_all(
            "SELECT id, entity_ids FROM arkham_claims WHERE text LIKE :pattern",
            {"pattern": f"%{entity_name}%"},
        )

        import json
        for row in claims:
            entity_ids = json.loads(row["entity_ids"] or "[]")
            if entity_id not in entity_ids:
                entity_ids.append(entity_id)
                await self._db.execute(
                    "UPDATE arkham_claims SET entity_ids = :entity_ids WHERE id = :id",
                    {"entity_ids": json.dumps(entity_ids), "id": row["id"]},
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
