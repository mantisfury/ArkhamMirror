# arkham-shard-claims

> Claim extraction and verification tracking for fact-checking workflows

**Version:** 0.1.0
**Category:** Analysis
**Frame Requirement:** >=0.1.0

## Overview

The Claims shard extracts and tracks factual assertions from documents for verification and analysis. It provides the foundation for contradiction detection and fact-checking workflows, with LLM-powered claim extraction and evidence linking.

### Key Capabilities

1. **Claim Extraction** - Extract factual claims from text using LLM
2. **Verification Tracking** - Track claim status (unverified, verified, disputed)
3. **Evidence Linking** - Link supporting and refuting evidence to claims
4. **Claim Matching** - Find similar/duplicate claims
5. **AI Analysis** - AI Junior Analyst for claim analysis

## Features

### Claim Extraction
- LLM-powered extraction from raw text
- Extract from documents by ID
- Track extraction method and model
- Confidence scoring

### Claim Types
- `factual` - Verifiable factual statements
- `opinion` - Opinions or subjective statements
- `prediction` - Future predictions
- `quote` - Direct quotations
- `statistic` - Statistical claims

### Claim Status
- `unverified` - Not yet verified
- `verified` - Confirmed as accurate
- `disputed` - Conflicting evidence exists
- `false` - Confirmed as false
- `retracted` - Withdrawn or deleted

### Evidence Management
- Link evidence to claims
- Track relationship (supports/refutes)
- Evidence strength levels
- Multiple evidence types

### Evidence Types
- `document` - From document corpus
- `external` - External sources
- `expert` - Expert testimony
- `data` - Statistical data
- `testimony` - Witness statements

### Evidence Relationships
- `supports` - Evidence supports claim
- `refutes` - Evidence contradicts claim
- `neutral` - Neither supports nor refutes

### Evidence Strength
- `strong` - Compelling evidence
- `moderate` - Reasonably convincing
- `weak` - Limited support

## Installation

```bash
pip install -e packages/arkham-shard-claims
```

The shard auto-registers via entry point on Frame startup.

## API Endpoints

### Count

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/claims/count` | Total claims count (badge) |

### Claim CRUD

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/claims/` | List claims with filtering |
| POST | `/api/claims/` | Create claim manually |
| GET | `/api/claims/{id}` | Get claim details |
| PATCH | `/api/claims/{id}/status` | Update claim status |
| DELETE | `/api/claims/{id}` | Delete (retract) claim |

### Status Filtered Lists

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/claims/status/unverified` | List unverified claims |
| GET | `/api/claims/status/verified` | List verified claims |
| GET | `/api/claims/status/disputed` | List disputed claims |

### Evidence

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/claims/{id}/evidence` | Get claim evidence |
| POST | `/api/claims/{id}/evidence` | Add evidence |
| POST | `/api/claims/backfill-evidence` | Backfill source evidence |

### Extraction

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/claims/extract` | Extract from text |
| POST | `/api/claims/extract-from-document/{id}` | Extract from document |

### Similarity and Merging

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/claims/{id}/similar` | Find similar claims |
| POST | `/api/claims/{id}/merge` | Merge duplicate claims |

### By Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/claims/by-document/{id}` | Claims from document |
| GET | `/api/claims/by-entity/{id}` | Claims about entity |

### Statistics

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/claims/stats/overview` | Comprehensive statistics |

### AI Analysis

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/claims/ai/junior-analyst` | AI analysis (streaming) |

## API Examples

### Extract Claims from Text

```json
POST /api/claims/extract
{
  "text": "The company reported revenue of $5.2 billion in Q4 2024. CEO John Smith stated that growth exceeded expectations.",
  "document_id": "doc_123",
  "extraction_model": null
}
```

Response:
```json
{
  "claims": [
    {
      "id": "claim_abc",
      "text": "The company reported revenue of $5.2 billion in Q4 2024",
      "claim_type": "statistic",
      "status": "unverified",
      "confidence": 0.92,
      "source_document_id": "doc_123",
      "entity_ids": ["ent_company"],
      "evidence_count": 0
    }
  ],
  "extraction_method": "llm",
  "total_extracted": 2,
  "processing_time_ms": 1523.5,
  "errors": []
}
```

### Create Manual Claim

```json
POST /api/claims/
{
  "text": "The meeting occurred on March 15, 2024",
  "claim_type": "factual",
  "source_document_id": "doc_456",
  "confidence": 1.0,
  "entity_ids": []
}
```

### Update Claim Status

```json
PATCH /api/claims/{claim_id}/status
{
  "status": "verified",
  "notes": "Confirmed via official records"
}
```

### Add Evidence

```json
POST /api/claims/{claim_id}/evidence
{
  "evidence_type": "document",
  "reference_id": "doc_789",
  "relationship": "supports",
  "strength": "strong",
  "reference_title": "Official Report",
  "excerpt": "Revenue for Q4 was $5.2 billion...",
  "notes": "Primary source confirmation"
}
```

### Find Similar Claims

```json
POST /api/claims/{claim_id}/similar
{
  "threshold": 0.8,
  "limit": 10
}
```

### Get Statistics

```bash
GET /api/claims/stats/overview
```

Response:
```json
{
  "total_claims": 1250,
  "by_status": {"unverified": 800, "verified": 350, "disputed": 100},
  "by_type": {"factual": 900, "statistic": 200, "quote": 150},
  "by_extraction_method": {"llm": 1100, "manual": 150},
  "total_evidence": 3200,
  "evidence_supporting": 2800,
  "evidence_refuting": 400,
  "claims_with_evidence": 950,
  "claims_without_evidence": 300,
  "avg_confidence": 0.87,
  "avg_evidence_per_claim": 2.56
}
```

## Events

### Published Events

| Event | Description |
|-------|-------------|
| `claims.claim.extracted` | New claim extracted |
| `claims.claim.verified` | Claim status changed |
| `claims.claim.disputed` | Claim marked disputed |
| `claims.claim.merged` | Duplicate claims merged |
| `claims.evidence.linked` | Evidence added |
| `claims.evidence.unlinked` | Evidence removed |
| `claims.extraction.started` | Batch extraction started |
| `claims.extraction.completed` | Batch extraction finished |

### Subscribed Events

| Event | Handler |
|-------|---------|
| `document.processed` | Auto-extract claims from new documents |
| `parse.entity.created` | Link claims to extracted entities |
| `contradictions.contradiction.detected` | Mark claims as disputed |

## UI Routes

| Route | Description |
|-------|-------------|
| `/claims` | All claims list |
| `/claims/unverified` | Unverified claims |
| `/claims/verified` | Verified claims |
| `/claims/disputed` | Disputed claims |

## Tech Stack

- **PostgreSQL 14+** - Single database for all persistence
- **pgvector extension** - Vector similarity search for claim matching
- **PostgreSQL job queue** - Background jobs using SKIP LOCKED pattern

## Dependencies

### Required Services
- **database** - Claim and evidence storage (PostgreSQL)
- **events** - Event publishing

### Optional Services
- **llm** - AI-powered claim extraction
- **vectors** - Semantic similarity for matching (pgvector)
- **workers** - Background extraction jobs (PostgreSQL SKIP LOCKED)

## URL State

| Parameter | Description |
|-----------|-------------|
| `claimId` | Selected claim |
| `documentId` | Filter by document |
| `status` | Filter by status |
| `view` | Display mode |

### Local Storage Keys
- `show_evidence` - Evidence panel expansion
- `sort_order` - Claim list sort preference
- `confidence_threshold` - Minimum confidence filter

## Extraction Methods

| Method | Description |
|--------|-------------|
| `llm` | LLM-powered extraction |
| `manual` | User-created claims |
| `imported` | Imported from external source |
| `rule_based` | Pattern matching extraction |

## Development

```bash
# Run tests
pytest packages/arkham-shard-claims/tests/

# Type checking
mypy packages/arkham-shard-claims/
```

## License

MIT
