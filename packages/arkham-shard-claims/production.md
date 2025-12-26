# Claims Shard - Production Readiness

> Production status documentation for arkham-shard-claims

---

## Production Status: READY

| Criteria | Status | Notes |
|----------|--------|-------|
| Manifest Compliance | PASS | shard.yaml follows shard_manifest_schema_prod.md v1.0 |
| Package Structure | PASS | Standard shard structure with all required files |
| Entry Point | PASS | `arkham_shard_claims:ClaimsShard` registered |
| Test Coverage | PASS | Unit tests for models, shard, and API |
| Documentation | PASS | README.md with full API documentation |
| Error Handling | PASS | Graceful degradation when services unavailable |

---

## File Inventory

| File | Purpose | Lines |
|------|---------|-------|
| `pyproject.toml` | Package configuration | 30 |
| `shard.yaml` | Production manifest v1.0 | 85 |
| `README.md` | User documentation | ~280 |
| `production.md` | This file | ~150 |
| `arkham_shard_claims/__init__.py` | Module exports | 10 |
| `arkham_shard_claims/models.py` | Data models | 204 |
| `arkham_shard_claims/shard.py` | Shard implementation | 640 |
| `arkham_shard_claims/api.py` | FastAPI routes | 480 |
| `tests/__init__.py` | Test package | 3 |
| `tests/test_models.py` | Model tests | ~300 |
| `tests/test_shard.py` | Shard tests | ~450 |
| `tests/test_api.py` | API tests | ~500 |

**Total:** ~3,100 lines

---

## Manifest Compliance

### Required Fields
- [x] `name`: claims
- [x] `version`: 0.1.0 (semver)
- [x] `description`: Present
- [x] `entry_point`: arkham_shard_claims:ClaimsShard
- [x] `api_prefix`: /api/claims
- [x] `requires_frame`: >=0.1.0

### Navigation
- [x] `category`: Analysis (valid category)
- [x] `order`: 31 (within 30-39 Analysis range)
- [x] `icon`: Quote (valid Lucide icon)
- [x] `label`: Claims
- [x] `route`: /claims (unique)
- [x] `badge_endpoint`: /api/claims/unverified/count
- [x] `sub_routes`: 4 defined (all, unverified, verified, disputed)

### Dependencies
- [x] `services`: database, events (valid Frame services)
- [x] `optional`: llm, vectors, workers (valid optional services)
- [x] `shards`: [] (empty as required)

### Events
- [x] `publishes`: 8 events (correct {shard}.{entity}.{action} format)
- [x] `subscribes`: 3 events (valid patterns)

### Capabilities
- [x] 5 capabilities declared (valid registry names)

---

## Service Dependencies

| Service | Type | Usage |
|---------|------|-------|
| `database` | Required | Stores claims and evidence in arkham_claims, arkham_claim_evidence tables |
| `events` | Required | Publishes claim events, subscribes to document/entity events |
| `llm` | Optional | Powers AI-driven claim extraction from text |
| `vectors` | Optional | Enables semantic similarity search for claim matching |
| `workers` | Optional | Background job processing for batch extraction |

### Graceful Degradation

When optional services are unavailable:
- **LLM unavailable**: `extract_claims_from_text` returns empty result with error message
- **Vectors unavailable**: `find_similar_claims` falls back to Jaccard similarity
- **Workers unavailable**: `_on_document_processed` logs warning, no job queued

---

## Database Schema

### arkham_claims
```sql
CREATE TABLE arkham_claims (
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
);

-- Indexes
CREATE INDEX idx_claims_status ON arkham_claims(status);
CREATE INDEX idx_claims_document ON arkham_claims(source_document_id);
CREATE INDEX idx_claims_type ON arkham_claims(claim_type);
```

### arkham_claim_evidence
```sql
CREATE TABLE arkham_claim_evidence (
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
);

CREATE INDEX idx_evidence_claim ON arkham_claim_evidence(claim_id);
```

---

## API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/claims/count` | Badge count |
| GET | `/api/claims/` | List claims with filters |
| POST | `/api/claims/` | Create claim |
| GET | `/api/claims/{id}` | Get single claim |
| PATCH | `/api/claims/{id}/status` | Update status |
| DELETE | `/api/claims/{id}` | Delete (retract) claim |
| GET | `/api/claims/{id}/evidence` | Get claim evidence |
| POST | `/api/claims/{id}/evidence` | Add evidence |
| POST | `/api/claims/extract` | Extract claims from text |
| POST | `/api/claims/{id}/similar` | Find similar claims |
| POST | `/api/claims/{id}/merge` | Merge duplicate claims |
| GET | `/api/claims/stats/overview` | Statistics |
| GET | `/api/claims/status/unverified` | List unverified |
| GET | `/api/claims/status/verified` | List verified |
| GET | `/api/claims/status/disputed` | List disputed |
| GET | `/api/claims/by-document/{id}` | Claims by document |
| GET | `/api/claims/by-entity/{id}` | Claims by entity |

---

## Test Coverage

### test_models.py (~300 lines)
- All 7 enums tested for values and count
- All 8 dataclasses tested for creation and defaults
- Edge cases for optional fields

### test_shard.py (~450 lines)
- Shard metadata verification
- Initialization and shutdown
- Database schema creation
- Event subscriptions
- CRUD operations (create, get, list, update)
- Evidence management
- Claim extraction
- Similarity detection
- Claim merging
- Statistics retrieval
- Helper methods

### test_api.py (~500 lines)
- All 17 endpoints tested
- Success and error cases
- Validation errors (422)
- Not found cases (404)
- Query parameter handling
- Request/response model validation

---

## Event Contracts

### Published Events

| Event | Payload |
|-------|---------|
| `claims.claim.extracted` | `{claim_id, text, claim_type, source_document_id}` |
| `claims.claim.verified` | `{claim_id, old_status, new_status}` |
| `claims.claim.disputed` | `{claim_id, old_status, new_status}` |
| `claims.claim.merged` | `{primary_claim_id, merged_claim_ids, evidence_transferred}` |
| `claims.evidence.linked` | `{claim_id, evidence_id, evidence_type, relationship}` |
| `claims.evidence.unlinked` | `{claim_id, evidence_id}` |
| `claims.extraction.started` | `{document_id, job_id}` |
| `claims.extraction.completed` | `{document_id, claims_extracted, processing_time_ms}` |

### Subscribed Events

| Event | Handler |
|-------|---------|
| `document.processed` | Queue claim extraction job |
| `entity.created` | Link claims mentioning entity |
| `entity.updated` | Update claim-entity links |

---

## Known Limitations

1. **LLM Extraction**: Requires external LLM service; no built-in extraction
2. **Vector Similarity**: Falls back to simple Jaccard similarity without vector service
3. **Batch Size**: No explicit limit on extraction batch size
4. **Merge Rollback**: Claim merges are not reversible

---

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 0.1.0 | 2024-12-25 | Initial production release |

---

*Production readiness verified: 2024-12-25*
