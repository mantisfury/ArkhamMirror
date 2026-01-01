# Contradictions Shard Wiring Log

## Date: 2026-01-01

## Overview
Wired the Contradictions shard from in-memory/placeholder implementation to fully functional database-backed storage with real document fetching.

## Changes Made

### 1. shard.py

**Schema Creation**
- Added `SCHEMA_SQL` constant with complete database schema:
  - `arkham_contradictions.contradictions` table with all fields
  - `arkham_contradictions.chains` table for contradiction chains
  - Indexes on `doc_a_id`, `doc_b_id`, `status`, `chain_id`, `severity`, `contradiction_type`
- Added `_create_schema()` async method called during `initialize()`
- Schema uses TEXT for JSON fields (analyst_notes, tags, metadata, etc.)

**Database Integration**
- Added import of `set_db_service` from api module
- After initializing the API, now calls `set_db_service(self._db_service)` to provide database access to API endpoints

**Document Fetching**
- Added `_get_document_content()` method to fetch real document content
- Tries `arkham_frame.documents` table first
- Falls back to `arkham_parse.parse_results` for extracted text
- Used by `analyze_pair()` public method

**Async Updates**
- Converted `get_document_contradictions()` to async
- Converted `get_statistics()` to async
- Updated all storage method calls to use `await`

### 2. storage.py

**Complete Rewrite for Database Support**
- All CRUD methods now async with proper database queries
- Maintains in-memory fallback when database is unavailable

**Key Methods Updated:**

| Method | Changes |
|--------|---------|
| `create()` | INSERT with named parameters, JSON serialization for lists/dicts |
| `get()` | SELECT with :id parameter |
| `update()` | UPDATE with full field set |
| `delete()` | DELETE with existence check |
| `list_all()` | Dynamic WHERE clause, pagination with LIMIT/OFFSET |
| `get_by_document()` | Query by doc_a_id OR doc_b_id |
| `search()` | Multi-filter query with LIKE for text search |
| `get_statistics()` | Multiple COUNT queries for each enum value |

**Serialization Helpers:**
- `_row_to_contradiction()` - Deserializes database row to Contradiction object
- `_row_to_chain()` - Deserializes database row to ContradictionChain object
- JSON parsing for: `analyst_notes`, `related_contradictions`, `tags`, `metadata`, `contradiction_ids`
- ISO format parsing for datetime fields

**Chain Operations:**
- `create_chain()` - Creates chain record and updates contradiction.chain_id
- `get_chain()` - Fetches chain by ID
- `get_chain_contradictions()` - Fetches all contradictions in a chain
- `list_chains()` - Lists all chains

### 3. api.py

**Document Fetching**
- Added `_db` global variable for database service
- Added `set_db_service()` function to set database reference
- Added `_get_document_content()` async function:
  - Tries `arkham_frame.documents` table first
  - Falls back to `arkham_parse.parse_results`
  - Returns dict with `id`, `content`, `title` or None

**analyze_documents Endpoint**
- Now fetches real document content instead of placeholder
- Returns 404 if documents not found
- Logs document titles and content lengths

**All Endpoints Updated to Async Storage Calls:**
- `get_document_contradictions` - `await _storage.get_by_document()`
- `list_contradictions` - `await _storage.list_all()`
- `get_statistics` - `await _storage.get_statistics()`
- `detect_chains` - `await _storage.search()`, `await _storage.create_chain()`
- `list_chains` - `await _storage.list_chains()`
- `get_chain` - `await _storage.get_chain()`, `await _storage.get_chain_contradictions()`
- `get_contradiction` - `await _storage.get()`
- `update_status` - `await _storage.update_status()`, `await _storage.add_note()`
- `add_notes` - `await _storage.add_note()`
- `delete_contradiction` - `await _storage.delete()`

**New Endpoint**
- Added `GET /count` endpoint for navigation badge support

## Database Schema

```sql
-- Schema
CREATE SCHEMA IF NOT EXISTS arkham_contradictions;

-- Contradictions Table
CREATE TABLE IF NOT EXISTS arkham_contradictions.contradictions (
    id TEXT PRIMARY KEY,
    doc_a_id TEXT NOT NULL,
    doc_b_id TEXT NOT NULL,
    claim_a TEXT NOT NULL,
    claim_b TEXT NOT NULL,
    claim_a_location TEXT DEFAULT '',
    claim_b_location TEXT DEFAULT '',
    contradiction_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    status TEXT DEFAULT 'detected',
    explanation TEXT DEFAULT '',
    confidence_score REAL DEFAULT 1.0,
    detected_by TEXT DEFAULT 'system',
    analyst_notes TEXT DEFAULT '[]',
    chain_id TEXT,
    related_contradictions TEXT DEFAULT '[]',
    tags TEXT DEFAULT '[]',
    metadata TEXT DEFAULT '{}',
    confirmed_by TEXT,
    confirmed_at TEXT,
    created_at TEXT,
    updated_at TEXT
);

-- Chains Table
CREATE TABLE IF NOT EXISTS arkham_contradictions.chains (
    id TEXT PRIMARY KEY,
    contradiction_ids TEXT DEFAULT '[]',
    description TEXT DEFAULT '',
    severity TEXT NOT NULL,
    created_at TEXT,
    updated_at TEXT
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_contradictions_doc_a ON arkham_contradictions.contradictions(doc_a_id);
CREATE INDEX IF NOT EXISTS idx_contradictions_doc_b ON arkham_contradictions.contradictions(doc_b_id);
CREATE INDEX IF NOT EXISTS idx_contradictions_status ON arkham_contradictions.contradictions(status);
CREATE INDEX IF NOT EXISTS idx_contradictions_chain ON arkham_contradictions.contradictions(chain_id);
CREATE INDEX IF NOT EXISTS idx_contradictions_severity ON arkham_contradictions.contradictions(severity);
CREATE INDEX IF NOT EXISTS idx_contradictions_type ON arkham_contradictions.contradictions(contradiction_type);
```

## Testing Notes

### Syntax Verification
All modified files pass Python syntax verification:
```bash
python -m py_compile shard.py    # OK
python -m py_compile storage.py  # OK
python -m py_compile api.py      # OK
```

### Integration Testing Checklist
- [ ] Start Frame and verify schema creation in database
- [ ] Ingest two documents with overlapping content
- [ ] Call POST /api/contradictions/analyze with document IDs
- [ ] Verify contradictions are stored in database
- [ ] Test GET /api/contradictions/list pagination
- [ ] Test status updates and note additions
- [ ] Test chain detection
- [ ] Verify event emission on contradiction detection

### Fallback Behavior
When database is unavailable:
- Storage falls back to in-memory dictionaries
- Document fetching returns None (analysis fails gracefully with 404)
- Warning logged about missing database service

## Known Limitations

1. **Document Sources**: Currently checks `arkham_frame.documents` and `arkham_parse.parse_results`. May need to expand to other document storage locations.

2. **Large Document Handling**: No chunking implemented - entire document content is passed to claim extraction. May need optimization for very large documents.

3. **Batch Analysis**: Batch endpoint processes pairs sequentially. Could be parallelized for better performance.

## API Endpoints Summary

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/contradictions/analyze | Analyze two documents for contradictions |
| POST | /api/contradictions/batch | Batch analyze multiple document pairs |
| GET | /api/contradictions/document/{doc_id} | Get contradictions for a document |
| GET | /api/contradictions/list | List contradictions with pagination |
| POST | /api/contradictions/claims | Extract claims from text |
| GET | /api/contradictions/stats | Get contradiction statistics |
| POST | /api/contradictions/detect-chains | Detect contradiction chains |
| GET | /api/contradictions/chains | List all chains |
| GET | /api/contradictions/chains/{chain_id} | Get chain details |
| GET | /api/contradictions/{id} | Get contradiction by ID |
| PUT | /api/contradictions/{id}/status | Update status |
| POST | /api/contradictions/{id}/notes | Add analyst notes |
| DELETE | /api/contradictions/{id} | Delete contradiction |
| GET | /api/contradictions/count | Get total count (for badge) |
