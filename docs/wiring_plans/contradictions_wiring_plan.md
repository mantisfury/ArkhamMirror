# Contradictions Shard - Wiring Plan

## Current State Summary

The Contradictions shard has complete backend detection logic and frontend UI, but uses **in-memory storage** and has **placeholder document fetching**. The shard cannot actually analyze real documents.

### What Exists
- **Backend**:
  - Complete detector logic in `detector.py` (536 lines) - claim extraction and contradiction detection
  - Full API endpoints in `api.py` (484 lines) - all CRUD operations defined
  - In-memory storage in `storage.py` (469 lines) - NOT persisted to database
  - Complete models in `models.py` (197 lines)
  - Chain detection logic for transitive contradictions

- **Frontend**:
  - Complete API client in `api.ts` (180 lines)
  - UI components: `ContradictionsPage.tsx`, `ContradictionDetail.tsx`
  - Type definitions in `types.ts`

### What's Missing

1. **Database Persistence**: Storage is in-memory only
2. **Schema Creation**: No database tables are created
3. **Document Content Fetching**: Uses placeholder text (`doc_a_text = f"Document {request.doc_a_id} content"`)
4. **LLM Integration**: Claim extraction and verification need real LLM calls

## Specific Missing Pieces

### Backend Files to Modify

#### 1. `arkham_shard_contradictions/shard.py`
**Location**: `async def initialize(self, frame) -> None` (around line 65)

**Add**:
```python
# Create database schema
await self._create_schema()

# Get document service for content fetching
self._doc_service = frame.get_service("documents")
if not self._doc_service:
    logger.warning("Document service not available - will use placeholder content")
```

**Add new method**:
```python
async def _create_schema(self) -> None:
    """Create database tables for contradictions."""
    if not self._db:
        return

    await self._db.execute("""
        CREATE TABLE IF NOT EXISTS arkham_contradictions (
            id TEXT PRIMARY KEY,
            doc_a_id TEXT NOT NULL,
            doc_b_id TEXT NOT NULL,
            claim_a TEXT NOT NULL,
            claim_b TEXT NOT NULL,

            contradiction_type TEXT NOT NULL,
            severity TEXT NOT NULL,
            status TEXT DEFAULT 'detected',

            explanation TEXT,
            confidence_score REAL DEFAULT 1.0,

            analyst_notes TEXT DEFAULT '[]',
            chain_id TEXT,

            created_at TEXT,
            updated_at TEXT,
            reviewed_at TEXT,
            reviewed_by TEXT
        )
    """)

    await self._db.execute("""
        CREATE INDEX IF NOT EXISTS idx_contradictions_doc_a
        ON arkham_contradictions(doc_a_id)
    """)

    await self._db.execute("""
        CREATE INDEX IF NOT EXISTS idx_contradictions_doc_b
        ON arkham_contradictions(doc_b_id)
    """)

    await self._db.execute("""
        CREATE INDEX IF NOT EXISTS idx_contradictions_status
        ON arkham_contradictions(status)
    """)

    await self._db.execute("""
        CREATE INDEX IF NOT EXISTS idx_contradictions_chain
        ON arkham_contradictions(chain_id)
    """)

    # Create chains table
    await self._db.execute("""
        CREATE TABLE IF NOT EXISTS arkham_contradiction_chains (
            id TEXT PRIMARY KEY,
            description TEXT,
            severity TEXT NOT NULL,
            contradiction_count INTEGER DEFAULT 0,
            created_at TEXT,
            updated_at TEXT
        )
    """)

    logger.info("Contradictions schema created")
```

#### 2. `arkham_shard_contradictions/storage.py`
**Replace entire file** - convert from in-memory to database storage

**Key changes**:
- Replace `self.contradictions: dict[str, Contradiction] = {}` with database queries
- Update all CRUD methods to use SQL
- Add helper methods for serialization
- Handle JSON arrays for `analyst_notes`

**Example**:
```python
class ContradictionStorage:
    def __init__(self, db):
        self.db = db

    async def create(self, contradiction: Contradiction) -> Contradiction:
        await self.db.execute("""
            INSERT INTO arkham_contradictions (
                id, doc_a_id, doc_b_id, claim_a, claim_b,
                contradiction_type, severity, status,
                explanation, confidence_score,
                analyst_notes, chain_id,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            contradiction.id,
            contradiction.doc_a_id,
            contradiction.doc_b_id,
            contradiction.claim_a,
            contradiction.claim_b,
            contradiction.contradiction_type.value,
            contradiction.severity.value,
            contradiction.status.value,
            contradiction.explanation,
            contradiction.confidence_score,
            json.dumps(contradiction.analyst_notes),
            contradiction.chain_id,
            contradiction.created_at.isoformat(),
            contradiction.updated_at.isoformat(),
        ])
        return contradiction

    async def list_contradictions(self, page, page_size, status, severity, type_filter):
        # Build WHERE clause dynamically
        conditions = []
        params = []

        if status:
            conditions.append("status = ?")
            params.append(status.value)
        if severity:
            conditions.append("severity = ?")
            params.append(severity.value)
        if type_filter:
            conditions.append("contradiction_type = ?")
            params.append(type_filter.value)

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        # Get total count
        count_result = await self.db.fetch_one(
            f"SELECT COUNT(*) as count FROM arkham_contradictions WHERE {where_clause}",
            params
        )
        total = count_result["count"]

        # Get paginated results
        offset = (page - 1) * page_size
        rows = await self.db.fetch_all(f"""
            SELECT * FROM arkham_contradictions
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """, params + [page_size, offset])

        contradictions = [self._row_to_contradiction(row) for row in rows]
        return contradictions, total

    def _row_to_contradiction(self, row) -> Contradiction:
        return Contradiction(
            id=row["id"],
            doc_a_id=row["doc_a_id"],
            doc_b_id=row["doc_b_id"],
            claim_a=row["claim_a"],
            claim_b=row["claim_b"],
            contradiction_type=ContradictionType(row["contradiction_type"]),
            severity=Severity(row["severity"]),
            status=ContradictionStatus(row["status"]),
            explanation=row["explanation"],
            confidence_score=row["confidence_score"],
            analyst_notes=json.loads(row["analyst_notes"]),
            chain_id=row["chain_id"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            reviewed_at=datetime.fromisoformat(row["reviewed_at"]) if row["reviewed_at"] else None,
            reviewed_by=row["reviewed_by"],
        )
```

#### 3. `arkham_shard_contradictions/api.py`
**Lines 84-87**: Replace placeholder document fetching

**Current**:
```python
# TODO: Fetch actual document content from Frame
# For now, this is a placeholder
doc_a_text = f"Document {request.doc_a_id} content"
doc_b_text = f"Document {request.doc_b_id} content"
```

**Replace with**:
```python
# Fetch document content from Frame
doc_a = await _get_document_content(request.doc_a_id)
doc_b = await _get_document_content(request.doc_b_id)

if not doc_a or not doc_b:
    raise HTTPException(
        status_code=404,
        detail=f"Document not found: {request.doc_a_id if not doc_a else request.doc_b_id}"
    )

doc_a_text = doc_a["content"]
doc_b_text = doc_b["content"]
```

**Add helper function** (at module level, after `init_api`):
```python
async def _get_document_content(doc_id: str) -> dict | None:
    """Fetch document content from Frame services."""
    if not _db:
        return None

    # Try to get from documents table
    result = await _db.fetch_one(
        "SELECT content, title FROM arkham_documents WHERE id = ?",
        [doc_id]
    )

    if result:
        return {
            "id": doc_id,
            "content": result["content"],
            "title": result["title"],
        }

    # Fallback: try parse shard's extracted text
    result = await _db.fetch_one(
        "SELECT extracted_text, filename FROM arkham_parse WHERE document_id = ?",
        [doc_id]
    )

    if result:
        return {
            "id": doc_id,
            "content": result["extracted_text"],
            "title": result["filename"],
        }

    return None
```

#### 4. `arkham_shard_contradictions/detector.py`
**Lines 94-100**: Ensure LLM claim extraction works

**Check**: The `extract_claims_llm` method already has proper structure. Just verify LLM service integration in `shard.py`:

```python
# In shard.py initialize()
self._llm_service = frame.get_service("llm")
if not self._llm_service:
    logger.warning("LLM service not available - claim extraction will be basic")
```

### No Frontend Changes Needed

The frontend is already correctly implemented and will work once the backend returns real data.

## Implementation Steps

### Step 1: Add Database Schema (MEDIUM)
**Files**: `arkham_shard_contradictions/shard.py`
- Add `_create_schema()` method for contradictions and chains tables
- Call it from `initialize()`
- Get document service reference

**Estimated time**: 30 minutes

### Step 2: Convert Storage to Database (LARGE)
**Files**: `arkham_shard_contradictions/storage.py`
- Replace in-memory dictionaries with database queries
- Implement all CRUD methods with SQL
- Add serialization helpers
- Handle chain storage

**Estimated time**: 2 hours

### Step 3: Wire Up Document Fetching (MEDIUM)
**Files**: `arkham_shard_contradictions/api.py`
- Add `_get_document_content()` helper function
- Replace placeholder text with real document fetching
- Handle missing documents gracefully

**Estimated time**: 45 minutes

### Step 4: Verify LLM Integration (SMALL)
**Files**: `arkham_shard_contradictions/shard.py`, `detector.py`
- Ensure LLM service is passed to detector
- Verify claim extraction calls work
- Test contradiction verification

**Estimated time**: 30 minutes

### Step 5: Test End-to-End (SMALL)
**Testing**:
- Start frame and verify schema creation
- Upload two documents via ingest
- Trigger contradiction analysis via API
- Verify contradictions are detected and persisted
- Check frontend displays contradictions
- Test chain detection

**Estimated time**: 45 minutes

## Overall Complexity: MEDIUM-LARGE

**Total estimated time**: 4.5 hours

**Dependencies**:
- Frame database service (already available)
- Frame LLM service (for claim extraction and verification)
- Documents shard or parse shard (for document content)
- Embeddings for semantic similarity (vectors service)

**Risk areas**:
- Document content may be in different schemas (documents vs parse shard)
- LLM prompts may need tuning for quality claim extraction
- Semantic similarity requires embeddings - may be slow for large documents
- Chain detection algorithm may be computationally expensive
