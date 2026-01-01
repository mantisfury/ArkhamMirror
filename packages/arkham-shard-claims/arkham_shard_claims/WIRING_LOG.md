# Claims Shard - Wiring Log

## Date: 2026-01-01

## Summary

Wired the Claims shard to be fully functional by implementing event handlers and extraction logic.

## Changes Made

### 1. Event Subscriptions (shard.py)

**Location**: `_subscribe_to_events()` method (lines 172-181)

**Changes**:
- Updated event subscriptions from incorrect event names to correct ones:
  - `document.processed` -> `parse.document.completed`
  - `entity.created` -> `parse.entity.extracted`
- Removed subscription to `entity.updated` (not needed)
- Added logging when subscriptions are registered

**Shutdown** (lines 80-87):
- Updated `shutdown()` method to unsubscribe from the correct event names

### 2. Document Processing Handler (shard.py)

**Location**: `_on_document_processed()` method (lines 182-251)

**Changes**:
- Complete rewrite of the handler to:
  - Extract payload correctly from wrapped events (EventBus format)
  - Fetch document chunks from the documents service
  - Combine chunk content for claim extraction
  - Call LLM extraction if available, otherwise simple extraction
  - Store extracted claims in database
  - Emit `claims.extracted` event on success
  - Proper error handling and logging

### 3. Simple Claim Extraction (shard.py)

**Location**: `_extract_claims_simple()` method (lines 268-342)

**Implementation**:
- New method for fallback claim extraction when LLM is not available
- Uses sentence splitting with regex pattern that preserves abbreviations
- Filters out:
  - Empty sentences
  - Short sentences (less than 5 words)
  - Questions
  - Headers and list items
- Creates Claim objects with:
  - `ClaimType.FACTUAL` type
  - `ClaimStatus.UNVERIFIED` status
  - `ExtractionMethod.RULE` extraction method
  - 0.5 confidence (low for simple extraction)
- Limits to 100 claims per document

### 4. LLM Claim Extraction (shard.py)

**Location**: `_extract_claims_llm()` method (lines 344-471)

**Implementation**:
- New method for LLM-based claim extraction
- Uses structured prompts with system and user messages
- Truncates input text to 4000 characters to avoid token limits
- Parses JSON response from LLM
- Maps claim types: factual, quantitative, attribution, opinion, prediction
- Falls back to simple extraction on error
- Limits to 50 claims per extraction
- Stores extraction model name in metadata

### 5. Claim Storage (shard.py)

**Location**: `_store_claim()` method (lines 473-524)

**Implementation**:
- New method to insert claims into database
- Uses named parameters (`:param_name` syntax) as required
- Properly serializes:
  - Enum values to strings
  - Lists/dicts to JSON strings
  - Datetime objects to ISO format strings
- Handles all claim fields from the database schema

### 6. Extract API Endpoint (shard.py)

**Location**: `extract_claims_from_text()` method (lines 734-802)

**Changes**:
- Refactored to use new `_extract_claims_llm()` and `_extract_claims_simple()` methods
- Added proper fallback logic when LLM is unavailable
- Stores extracted claims in database
- Returns correct extraction method in result
- Removed broken `self._llm.complete()` call

## Database Patterns Used

All database operations use named parameters as required:

```python
# Named parameter syntax
await self._db.execute(
    "INSERT INTO arkham_claims (...) VALUES (:id, :text, ...)",
    {"id": claim_id, "text": text, ...}
)

# JSONB fields serialized with json.dumps()
params["entity_ids"] = json.dumps(entity_ids_list)
params["metadata"] = json.dumps(metadata_dict)
```

## Event Flow

```
1. Parse shard processes document
   -> emits parse.document.completed event

2. Claims shard receives event
   -> _on_document_processed() handler triggered

3. Handler fetches document chunks
   -> Combines chunk content

4. Extraction runs (LLM or simple)
   -> Creates Claim objects

5. Claims stored in database
   -> _store_claim() for each claim

6. Success event emitted
   -> claims.extracted event
```

## Testing Notes

### Syntax Verification

All modified files pass Python syntax check:

```bash
python -m py_compile packages/arkham-shard-claims/arkham_shard_claims/shard.py
python -m py_compile packages/arkham-shard-claims/arkham_shard_claims/api.py
python -m py_compile packages/arkham-shard-claims/arkham_shard_claims/models.py
```

### Integration Testing

To test the full flow:

1. Start the frame: `python -m uvicorn arkham_frame.main:app --host 127.0.0.1 --port 8100`
2. Upload a document via the ingest shard
3. Wait for parse shard to process (check logs for `parse.document.completed`)
4. Check claims shard logs for extraction messages
5. Query claims via API: `GET /api/claims/`
6. Verify claims appear in the UI

### Manual Extraction Test

```bash
curl -X POST http://127.0.0.1:8100/api/claims/extract \
  -H "Content-Type: application/json" \
  -d '{"text": "The company was founded in 1995. It has 500 employees. Revenue grew by 20% last year."}'
```

## Known Limitations

1. **Text Truncation**: LLM extraction truncates text to 4000 characters
2. **Claim Limits**: Maximum 100 claims (simple) or 50 claims (LLM) per document
3. **No Position Tracking**: `source_start_char` and `source_end_char` are not populated
4. **Entity Linking**: Only links entities when `parse.entity.extracted` event includes entity text

## Files Modified

- `arkham_shard_claims/shard.py` - Main implementation changes
- `arkham_shard_claims/WIRING_LOG.md` - This documentation file (new)

## Files NOT Modified

- `arkham_shard_claims/api.py` - Already correctly wired
- `arkham_shard_claims/models.py` - No changes needed
- `shard.yaml` - No changes needed
- `pyproject.toml` - No changes needed
