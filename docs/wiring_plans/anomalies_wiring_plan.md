# Anomalies Shard - Wiring Plan

## Current State Summary

The Anomalies shard has a complete backend API structure and frontend UI, but uses **in-memory storage** instead of proper database persistence. The shard will lose all data on restart.

### What Exists
- **Backend**:
  - Complete detector logic in `detector.py` (411 lines) - statistical anomaly detection
  - Full API endpoints in `api.py` (505 lines) - all CRUD operations defined
  - In-memory storage in `storage.py` (346 lines) - NOT persisted to database
  - Complete models in `models.py` (205 lines)

- **Frontend**:
  - Complete API client in `api.ts` (142 lines)
  - UI components: `AnomaliesPage.tsx`, `AnomalyDetail.tsx`
  - Type definitions in `types.ts`

### What's Missing

1. **Database Persistence**: Storage is in-memory only (`self.anomalies: dict[str, Anomaly] = {}`)
2. **Schema Creation**: No database tables are created in shard initialization
3. **Real Detection**: Detection endpoints return placeholder data (e.g., `anomalies_detected=0, job_id="job-123"`)

## Specific Missing Pieces

### Backend Files to Modify

#### 1. `arkham_shard_anomalies/shard.py`
**Location**: `async def initialize(self, frame) -> None` (around line 50)

**Add**:
```python
# Create database schema
await self._create_schema()
```

**Add new method**:
```python
async def _create_schema(self) -> None:
    """Create database tables for anomalies."""
    if not self._db:
        return

    await self._db.execute("""
        CREATE TABLE IF NOT EXISTS arkham_anomalies (
            id TEXT PRIMARY KEY,
            doc_id TEXT NOT NULL,
            project_id TEXT,
            anomaly_type TEXT NOT NULL,
            severity TEXT NOT NULL,
            status TEXT DEFAULT 'detected',
            score REAL NOT NULL,

            title TEXT NOT NULL,
            description TEXT,
            evidence TEXT,

            metadata TEXT DEFAULT '{}',

            detected_at TEXT,
            reviewed_at TEXT,
            reviewed_by TEXT,
            notes TEXT,

            created_at TEXT,
            updated_at TEXT
        )
    """)

    await self._db.execute("""
        CREATE INDEX IF NOT EXISTS idx_anomalies_doc_id
        ON arkham_anomalies(doc_id)
    """)

    await self._db.execute("""
        CREATE INDEX IF NOT EXISTS idx_anomalies_type
        ON arkham_anomalies(anomaly_type)
    """)

    await self._db.execute("""
        CREATE INDEX IF NOT EXISTS idx_anomalies_status
        ON arkham_anomalies(status)
    """)

    # Create analyst notes table
    await self._db.execute("""
        CREATE TABLE IF NOT EXISTS arkham_anomaly_notes (
            id TEXT PRIMARY KEY,
            anomaly_id TEXT NOT NULL,
            content TEXT NOT NULL,
            author TEXT NOT NULL,
            created_at TEXT,
            FOREIGN KEY (anomaly_id) REFERENCES arkham_anomalies(id)
        )
    """)

    logger.info("Anomalies schema created")
```

#### 2. `arkham_shard_anomalies/storage.py`
**Replace entire file** - convert from in-memory to database storage

**Key changes**:
- Replace `self.anomalies: dict[str, Anomaly] = {}` with database queries
- Update `create_anomaly()` to use `INSERT` statements
- Update `get_anomaly()` to use `SELECT` statements
- Update `list_anomalies()` to build dynamic SQL with filters
- Update `update_anomaly()` to use `UPDATE` statements
- Update `delete_anomaly()` to use `DELETE` statements

**Example**:
```python
class AnomalyStore:
    def __init__(self, db):
        self.db = db

    async def create_anomaly(self, anomaly: Anomaly) -> Anomaly:
        await self.db.execute("""
            INSERT INTO arkham_anomalies (
                id, doc_id, project_id, anomaly_type, severity,
                status, score, title, description, evidence,
                metadata, detected_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            anomaly.id, anomaly.doc_id, anomaly.project_id,
            anomaly.anomaly_type.value, anomaly.severity.value,
            anomaly.status.value, anomaly.score,
            anomaly.title, anomaly.description,
            json.dumps(anomaly.evidence) if anomaly.evidence else None,
            json.dumps(anomaly.metadata),
            anomaly.detected_at.isoformat(),
            anomaly.created_at.isoformat(),
            anomaly.updated_at.isoformat(),
        ])
        return anomaly

    async def list_anomalies(self, offset, limit, anomaly_type, status, severity, doc_id, project_id):
        # Build WHERE clause dynamically
        conditions = []
        params = []

        if anomaly_type:
            conditions.append("anomaly_type = ?")
            params.append(anomaly_type.value)
        if status:
            conditions.append("status = ?")
            params.append(status.value)
        if severity:
            conditions.append("severity = ?")
            params.append(severity.value)
        if doc_id:
            conditions.append("doc_id = ?")
            params.append(doc_id)
        if project_id:
            conditions.append("project_id = ?")
            params.append(project_id)

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        # Get total count
        count_result = await self.db.fetch_one(
            f"SELECT COUNT(*) as count FROM arkham_anomalies WHERE {where_clause}",
            params
        )
        total = count_result["count"]

        # Get paginated results
        rows = await self.db.fetch_all(f"""
            SELECT * FROM arkham_anomalies
            WHERE {where_clause}
            ORDER BY detected_at DESC
            LIMIT ? OFFSET ?
        """, params + [limit, offset])

        anomalies = [self._row_to_anomaly(row) for row in rows]
        return anomalies, total
```

#### 3. `arkham_shard_anomalies/api.py`
**Lines 103-136**: Replace stub detection logic

**Current** (line 126):
```python
return DetectResponse(
    anomalies_detected=0,
    duration_ms=duration_ms,
    job_id="job-123",  # Would be a real job ID
)
```

**Replace with**:
```python
# Run detection
anomalies = await _detector.detect_all(
    doc_ids=request.doc_ids,
    project_id=request.project_id,
    config=request.config or DetectionConfig(),
)

# Store detected anomalies
for anomaly in anomalies:
    await _store.create_anomaly(anomaly)

# Emit completion event
if _event_bus:
    await _event_bus.emit(
        "anomalies.detection_completed",
        {
            "project_id": request.project_id,
            "anomalies_detected": len(anomalies),
            "doc_ids": request.doc_ids,
        },
        source="anomalies-shard",
    )

return DetectResponse(
    anomalies_detected=len(anomalies),
    duration_ms=duration_ms,
    job_id=None,
)
```

### No Frontend Changes Needed

The frontend is already correctly implemented and will work once the backend returns real data.

## Implementation Steps

### Step 1: Add Database Schema (MEDIUM)
**Files**: `arkham_shard_anomalies/shard.py`
- Add `_create_schema()` method
- Call it from `initialize()`
- Add import for `json` module

**Estimated time**: 30 minutes

### Step 2: Convert Storage to Database (LARGE)
**Files**: `arkham_shard_anomalies/storage.py`
- Replace in-memory dictionaries with database queries
- Implement all CRUD methods with SQL
- Add helper methods for serialization (`_row_to_anomaly`, `_anomaly_to_row`)
- Handle JSON serialization for metadata and evidence fields

**Estimated time**: 2 hours

### Step 3: Wire Up Detection Logic (MEDIUM)
**Files**: `arkham_shard_anomalies/api.py`, `arkham_shard_anomalies/detector.py`
- Replace stub responses in `/detect` endpoint
- Ensure detector can fetch document embeddings from Frame
- Store detected anomalies to database
- Emit proper events

**Estimated time**: 1 hour

### Step 4: Test End-to-End (SMALL)
**Testing**:
- Start frame and verify schema creation
- Trigger anomaly detection via API
- Verify anomalies are persisted to database
- Check frontend displays detected anomalies
- Test filtering and pagination

**Estimated time**: 30 minutes

## Overall Complexity: MEDIUM-LARGE

**Total estimated time**: 4 hours

**Dependencies**:
- Frame database service (already available)
- Frame vectors service (for embedding-based detection)
- Document content from frame (for text analysis)

**Risk areas**:
- Detector needs access to document embeddings - may require integration with embed shard
- Statistical detection requires document metadata - may need documents shard integration
- Performance of full-corpus detection on large datasets
