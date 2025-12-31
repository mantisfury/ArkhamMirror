# Claims Shard - Wiring Plan

## Current State Summary

The Claims shard has database schema creation and API structure, but **endpoints return empty data** because claims are not being extracted from documents. The shard needs integration with the parse shard or LLM-based extraction.

### What Exists
- **Backend**:
  - Complete shard structure in `shard.py` (899 lines)
  - Full API endpoints in `api.py` (604 lines)
  - Database schema creation (`arkham_claims`, `arkham_claim_evidence`)
  - Complete models in `models.py` (203 lines)

- **Frontend**:
  - Complete UI in `ClaimsPage.tsx` with filtering and search
  - Status workflow (unverified → verified/disputed/uncertain)
  - Evidence linking interface

### What's Missing

1. **Claim Extraction**: No mechanism to extract claims from documents
2. **Event Subscription**: Event handlers are stubbed out
3. **LLM Integration**: Extraction endpoint exists but needs real LLM calls
4. **Evidence Linking**: API exists but needs document/entity integration

## Specific Missing Pieces

### Backend Files to Modify

#### 1. `arkham_shard_claims/shard.py`
**Lines 83-85**: Uncomment and implement event subscriptions

**Current**:
```python
if self._events:
    await self._events.unsubscribe("document.processed", self._on_document_processed)
    await self._events.unsubscribe("entity.created", self._on_entity_created)
    await self._events.unsubscribe("entity.updated", self._on_entity_updated)
```

**Replace** (in `_subscribe_to_events` method, add before shutdown):
```python
async def _subscribe_to_events(self) -> None:
    """Subscribe to events from other shards."""
    if not self._events:
        return

    # Subscribe to document processing events
    await self._events.subscribe("parse.document.completed", self._on_document_processed)
    await self._events.subscribe("entities.entity.extracted", self._on_entity_extracted)

    logger.info("Subscribed to document and entity events")

async def _on_document_processed(self, event: dict) -> None:
    """
    Handle document processing completion.

    Automatically extract claims from newly processed documents.

    Event payload:
        {
            "document_id": str,
            "content": str,
            "filename": str
        }
    """
    document_id = event.get("document_id")
    content = event.get("content") or event.get("extracted_text")

    if not document_id or not content:
        logger.warning(f"Document event missing required fields: {event.keys()}")
        return

    logger.info(f"Auto-extracting claims from document {document_id}")

    try:
        # Extract claims using LLM if available, otherwise simple extraction
        if self._llm:
            claims = await self._extract_claims_llm(content, document_id)
        else:
            claims = await self._extract_claims_simple(content, document_id)

        # Store extracted claims
        for claim in claims:
            await self._store_claim(claim)

        logger.info(f"Extracted {len(claims)} claims from document {document_id}")

        # Emit event
        if self._events:
            await self._events.emit(
                "claims.extracted",
                {
                    "document_id": document_id,
                    "claim_count": len(claims),
                    "claim_ids": [c.id for c in claims],
                },
                source="claims-shard",
            )

    except Exception as e:
        logger.error(f"Claim extraction failed for {document_id}: {e}", exc_info=True)

async def _on_entity_extracted(self, event: dict) -> None:
    """
    Handle entity extraction.

    Link entities to claims that mention them.
    """
    entity_id = event.get("entity_id")
    entity_text = event.get("text")
    document_id = event.get("document_id")

    if not entity_id or not entity_text or not document_id:
        return

    # Find claims from this document that mention this entity
    claims = await self._db.fetch_all("""
        SELECT id, text FROM arkham_claims
        WHERE source_document_id = ?
    """, [document_id])

    for claim_row in claims:
        claim_text = claim_row["text"].lower()
        if entity_text.lower() in claim_text:
            # Link entity to claim
            claim_id = claim_row["id"]
            entity_ids = await self._db.fetch_one(
                "SELECT entity_ids FROM arkham_claims WHERE id = ?", [claim_id]
            )
            current_ids = json.loads(entity_ids["entity_ids"]) if entity_ids["entity_ids"] else []

            if entity_id not in current_ids:
                current_ids.append(entity_id)
                await self._db.execute(
                    "UPDATE arkham_claims SET entity_ids = ? WHERE id = ?",
                    [json.dumps(current_ids), claim_id]
                )
                logger.debug(f"Linked entity {entity_id} to claim {claim_id}")

async def _extract_claims_simple(self, text: str, document_id: str) -> list[Claim]:
    """
    Simple claim extraction using sentence splitting.

    Fallback when LLM is not available.
    """
    import re
    import uuid
    from datetime import datetime

    # Split into sentences
    sentences = re.split(r'[.!?]+', text)
    claims = []

    for i, sentence in enumerate(sentences):
        sentence = sentence.strip()

        # Skip very short sentences
        if len(sentence.split()) < 5:
            continue

        # Skip questions
        if sentence.endswith('?'):
            continue

        claim_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()

        claim = Claim(
            id=claim_id,
            text=sentence,
            claim_type=ClaimType.FACTUAL,
            status=ClaimStatus.UNVERIFIED,
            confidence=0.5,  # Low confidence for simple extraction
            source_document_id=document_id,
            source_start_char=None,
            source_end_char=None,
            source_context=None,
            extracted_by=ExtractionMethod.PATTERN.value,
            extraction_model=None,
            entity_ids=[],
            evidence_count=0,
            supporting_count=0,
            refuting_count=0,
            created_at=now,
            updated_at=now,
            verified_at=None,
            metadata={},
        )
        claims.append(claim)

    return claims

async def _extract_claims_llm(self, text: str, document_id: str) -> list[Claim]:
    """
    Extract claims using LLM.

    Uses the Frame's LLM service to identify factual claims.
    """
    import uuid
    from datetime import datetime

    if not self._llm:
        return await self._extract_claims_simple(text, document_id)

    prompt = f"""Extract factual claims from the following text.

For each claim:
1. Extract the exact claim text
2. Classify it as: factual, opinion, prediction, or attribution
3. Rate your confidence (0.0 to 1.0)

Return JSON array: [{{"text": "claim text", "type": "factual", "confidence": 0.9}}]

Text:
{text[:2000]}  # Limit to avoid token overflow

Return only valid JSON, no explanations."""

    try:
        response = await self._llm.generate(prompt)
        response_text = response.get("text", "")

        # Parse JSON response
        import json
        import re

        # Extract JSON array from response
        json_match = re.search(r'\[.*\]', response_text, re.DOTALL)
        if not json_match:
            logger.warning("LLM response did not contain JSON array, falling back to simple extraction")
            return await self._extract_claims_simple(text, document_id)

        claims_data = json.loads(json_match.group(0))

        claims = []
        now = datetime.utcnow().isoformat()

        for claim_data in claims_data:
            claim_text = claim_data.get("text", "").strip()
            if not claim_text:
                continue

            claim_type_str = claim_data.get("type", "factual").lower()
            try:
                claim_type = ClaimType[claim_type_str.upper()]
            except KeyError:
                claim_type = ClaimType.FACTUAL

            claim_id = str(uuid.uuid4())

            claim = Claim(
                id=claim_id,
                text=claim_text,
                claim_type=claim_type,
                status=ClaimStatus.UNVERIFIED,
                confidence=claim_data.get("confidence", 0.8),
                source_document_id=document_id,
                source_start_char=None,
                source_end_char=None,
                source_context=None,
                extracted_by=ExtractionMethod.LLM.value,
                extraction_model=response.get("model", "unknown"),
                entity_ids=[],
                evidence_count=0,
                supporting_count=0,
                refuting_count=0,
                created_at=now,
                updated_at=now,
                verified_at=None,
                metadata={},
            )
            claims.append(claim)

        return claims

    except Exception as e:
        logger.error(f"LLM claim extraction failed: {e}", exc_info=True)
        return await self._extract_claims_simple(text, document_id)

async def _store_claim(self, claim: Claim) -> None:
    """Store a claim in the database."""
    if not self._db:
        return

    await self._db.execute("""
        INSERT INTO arkham_claims (
            id, text, claim_type, status, confidence,
            source_document_id, source_start_char, source_end_char, source_context,
            extracted_by, extraction_model,
            entity_ids, evidence_count, supporting_count, refuting_count,
            created_at, updated_at, verified_at, metadata
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, [
        claim.id,
        claim.text,
        claim.claim_type.value if isinstance(claim.claim_type, ClaimType) else claim.claim_type,
        claim.status.value if isinstance(claim.status, ClaimStatus) else claim.status,
        claim.confidence,
        claim.source_document_id,
        claim.source_start_char,
        claim.source_end_char,
        claim.source_context,
        claim.extracted_by,
        claim.extraction_model,
        json.dumps(claim.entity_ids),
        claim.evidence_count,
        claim.supporting_count,
        claim.refuting_count,
        claim.created_at,
        claim.updated_at,
        claim.verified_at,
        json.dumps(claim.metadata),
    ])
```

#### 2. `arkham_shard_claims/api.py`
**Lines 200-250**: Verify manual extraction endpoint

The `/extract` endpoint should use the LLM extraction logic:

**Add/Verify**:
```python
@router.post("/extract")
async def extract_claims_from_text(request: Request, extraction: ExtractionRequest):
    """
    Manually extract claims from text.

    Useful for testing or extracting from non-document sources.
    """
    shard = get_shard(request)

    if not shard:
        raise HTTPException(status_code=503, detail="Claims shard not available")

    start_time = time.time()

    try:
        # Extract claims
        if shard._llm:
            claims = await shard._extract_claims_llm(extraction.text, extraction.document_id)
        else:
            claims = await shard._extract_claims_simple(extraction.text, extraction.document_id)

        # Store claims
        for claim in claims:
            await shard._store_claim(claim)

        duration_ms = (time.time() - start_time) * 1000

        return ExtractionResponse(
            claims=[claim_to_response(claim) for claim in claims],
            source_document_id=extraction.document_id,
            extraction_method=ExtractionMethod.LLM.value if shard._llm else ExtractionMethod.PATTERN.value,
            extraction_model=extraction.extraction_model,
            total_extracted=len(claims),
            processing_time_ms=duration_ms,
            errors=[],
        )

    except Exception as e:
        logger.error(f"Claim extraction failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Extraction failed: {str(e)}")

def claim_to_response(claim: Claim) -> ClaimResponse:
    """Convert Claim model to ClaimResponse."""
    return ClaimResponse(
        id=claim.id,
        text=claim.text,
        claim_type=claim.claim_type.value if isinstance(claim.claim_type, ClaimType) else claim.claim_type,
        status=claim.status.value if isinstance(claim.status, ClaimStatus) else claim.status,
        confidence=claim.confidence,
        source_document_id=claim.source_document_id,
        source_start_char=claim.source_start_char,
        source_end_char=claim.source_end_char,
        source_context=claim.source_context,
        extracted_by=claim.extracted_by,
        extraction_model=claim.extraction_model,
        entity_ids=claim.entity_ids,
        evidence_count=claim.evidence_count,
        supporting_count=claim.supporting_count,
        refuting_count=claim.refuting_count,
        created_at=claim.created_at,
        updated_at=claim.updated_at,
        verified_at=claim.verified_at,
        metadata=claim.metadata,
    )
```

### Frontend Changes

**None required** - frontend is already complete and will work once backend returns data.

## Implementation Steps

### Step 1: Implement Event Handlers (LARGE)
**Files**: `arkham_shard_claims/shard.py`
- Implement `_subscribe_to_events()`
- Implement `_on_document_processed()` handler
- Implement `_on_entity_extracted()` handler
- Implement `_extract_claims_simple()` method
- Implement `_extract_claims_llm()` method
- Implement `_store_claim()` method

**Estimated time**: 2.5 hours

### Step 2: Wire Up Manual Extraction Endpoint (SMALL)
**Files**: `arkham_shard_claims/api.py`
- Implement `/extract` endpoint to call shard methods
- Add `claim_to_response()` helper

**Estimated time**: 30 minutes

### Step 3: Test Integration (MEDIUM)
**Testing**:
- Upload document via ingest
- Verify parse shard processes it
- Verify claims shard extracts claims automatically
- Check claims appear in database and UI
- Test manual extraction via API
- Test status workflow (mark as verified/disputed)
- Test entity linking

**Estimated time**: 1 hour

## Overall Complexity: MEDIUM-LARGE

**Total estimated time**: 4 hours

**Dependencies**:
- Parse shard must emit `parse.document.completed` events with content
- Frame LLM service (for quality extraction, optional)
- Frame database service (already available)
- Frame event bus (already available)
- Entities shard (for entity linking, optional)

**Risk areas**:
- LLM prompt engineering for claim extraction quality
- Simple extraction (fallback) may produce low-quality claims
- Parse shard may not be emitting document completion events yet
- Entity linking requires exact text matching (case sensitivity)
- Large documents may exceed LLM context limits (need chunking)
