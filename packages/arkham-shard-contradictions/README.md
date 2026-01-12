# arkham-shard-contradictions

> Contradiction detection engine for multi-document analysis

**Version:** 0.1.0
**Category:** Analysis
**Frame Requirement:** >=0.1.0

## Overview

The Contradictions shard detects conflicting claims between documents. It extracts claims from documents, finds semantically similar claim pairs, and verifies contradictions using LLM analysis. Supports chain detection for identifying linked contradictions across multiple documents.

### Key Capabilities

1. **Multi-Document Analysis** - Compare documents for contradictions
2. **Claim Extraction** - Extract factual claims from text
3. **Semantic Matching** - Find similar claims via vector embeddings
4. **LLM Verification** - AI-powered contradiction confirmation
5. **Chain Detection** - Find linked contradictions across documents
6. **AI Analysis** - AI Junior Analyst for contradiction interpretation

## Features

### Contradiction Detection
- Pairwise document comparison
- Batch analysis of multiple pairs
- LLM-powered claim extraction
- Simple heuristic extraction fallback
- Configurable similarity threshold

### Contradiction Types
- `direct` - Direct factual contradiction
- `temporal` - Timeline inconsistency
- `quantitative` - Numeric disagreement
- `causal` - Cause/effect conflict
- `attributive` - Attribution conflict

### Contradiction Status
- `detected` - Newly detected
- `investigating` - Under review
- `confirmed` - Verified contradiction
- `dismissed` - False positive

### Severity Levels
- `critical` - Major factual conflict
- `high` - Significant contradiction
- `medium` - Notable inconsistency
- `low` - Minor discrepancy

### Chain Detection
Finds linked contradictions:
- A contradicts B, B contradicts C
- Builds contradiction networks
- Assigns chain severity

### Analyst Workflow
- Review detected contradictions
- Update status with notes
- Bulk status updates
- Chain visualization

## Installation

```bash
pip install -e packages/arkham-shard-contradictions
```

The shard auto-registers via entry point on Frame startup.

## API Endpoints

### Analysis

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/contradictions/analyze` | Analyze two documents |
| POST | `/api/contradictions/batch` | Batch analyze pairs |
| POST | `/api/contradictions/claims` | Extract claims from text |

### Listing and Filtering

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/contradictions/list` | List all contradictions |
| GET | `/api/contradictions/document/{id}` | Get by document |
| GET | `/api/contradictions/count` | Total count |
| GET | `/api/contradictions/pending/count` | Pending count (badge) |
| GET | `/api/contradictions/stats` | Statistics |

### Contradiction Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/contradictions/{id}` | Get details |
| PUT | `/api/contradictions/{id}/status` | Update status |
| POST | `/api/contradictions/{id}/notes` | Add notes |
| DELETE | `/api/contradictions/{id}` | Delete |
| POST | `/api/contradictions/bulk-status` | Bulk status update |

### Chains

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/contradictions/detect-chains` | Detect chains |
| GET | `/api/contradictions/chains` | List chains |
| GET | `/api/contradictions/chains/{id}` | Get chain details |

### AI Analysis

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/contradictions/ai/junior-analyst` | AI analysis (streaming) |

## API Examples

### Analyze Two Documents

```json
POST /api/contradictions/analyze
{
  "doc_a_id": "doc_report_q1",
  "doc_b_id": "doc_report_q2",
  "threshold": 0.75,
  "use_llm": true
}
```

Response:
```json
{
  "doc_a_id": "doc_report_q1",
  "doc_b_id": "doc_report_q2",
  "contradictions": [
    {
      "id": "contra_123",
      "doc_a_id": "doc_report_q1",
      "doc_b_id": "doc_report_q2",
      "claim_a": "Revenue increased by 15% in Q1",
      "claim_b": "Revenue declined by 3% in the first quarter",
      "contradiction_type": "quantitative",
      "severity": "high",
      "status": "detected",
      "explanation": "Direct contradiction on Q1 revenue change",
      "confidence_score": 0.92
    }
  ],
  "count": 1
}
```

### Batch Analysis

```json
POST /api/contradictions/batch
{
  "document_pairs": [
    ["doc_a", "doc_b"],
    ["doc_a", "doc_c"],
    ["doc_b", "doc_c"]
  ],
  "threshold": 0.75,
  "use_llm": true
}
```

### Extract Claims from Text

```json
POST /api/contradictions/claims
{
  "text": "The company reported revenue of $5.2 billion. Profits increased by 12%.",
  "document_id": "doc_123",
  "use_llm": true
}
```

### Update Status

```json
PUT /api/contradictions/{id}/status
{
  "status": "confirmed",
  "analyst_id": "analyst_john",
  "notes": "Verified contradiction between Q1 and Q2 reports"
}
```

### Bulk Status Update

```json
POST /api/contradictions/bulk-status
{
  "contradiction_ids": ["contra_1", "contra_2", "contra_3"],
  "status": "dismissed",
  "analyst_id": "analyst_john",
  "notes": "Batch dismissed - different reporting periods"
}
```

### Detect Chains

```bash
POST /api/contradictions/detect-chains
```

Response:
```json
{
  "chains_detected": 2,
  "chains": [
    {
      "id": "chain_abc",
      "contradiction_count": 3,
      "contradictions": ["contra_1", "contra_2", "contra_3"]
    }
  ]
}
```

### Get Statistics

```bash
GET /api/contradictions/stats
```

Response:
```json
{
  "total_contradictions": 45,
  "by_status": {"detected": 20, "confirmed": 15, "dismissed": 10},
  "by_severity": {"critical": 5, "high": 15, "medium": 15, "low": 10},
  "by_type": {"direct": 20, "temporal": 10, "quantitative": 15},
  "chain_count": 3
}
```

## Events

### Published Events

| Event | Description |
|-------|-------------|
| `contradictions.detected` | Contradictions found |
| `contradictions.confirmed` | Contradiction confirmed |
| `contradictions.dismissed` | Contradiction dismissed |
| `contradictions.chain_detected` | Chain detected |
| `contradictions.status_updated` | Status changed |
| `contradictions.bulk_status_updated` | Bulk update |

### Subscribed Events

| Event | Handler |
|-------|---------|
| `documents.document.created` | Auto-analyze new docs |
| `documents.document.updated` | Re-analyze updated docs |
| `embed.document.completed` | Analyze after embedding |

## UI Routes

| Route | Description |
|-------|-------------|
| `/contradictions` | Contradictions list |

## Tech Stack

- **PostgreSQL 14+** - Single database for all persistence
- **pgvector extension** - Vector similarity search for claim matching
- **PostgreSQL job queue** - Background jobs using SKIP LOCKED pattern

## Dependencies

### Required Services
- **database** - Contradiction storage (PostgreSQL)
- **events** - Event publishing
- **vectors** - Semantic similarity matching (pgvector)

### Optional Services
- **llm** - AI-powered extraction and verification

## URL State

| Parameter | Description |
|-----------|-------------|
| `status` | Filter by status |
| `severity` | Filter by severity |
| `documentId` | Filter by document |

## Detection Process

1. **Claim Extraction**: Extract factual claims from both documents
   - LLM extraction (more accurate, slower)
   - Simple heuristic extraction (fast fallback)

2. **Semantic Matching**: Find similar claim pairs
   - Embed claims using pgvector
   - Filter by similarity threshold

3. **Contradiction Verification**: Verify each potential contradiction
   - LLM analysis of claim pair
   - Classify contradiction type
   - Assign severity and confidence

4. **Storage**: Persist detected contradictions
   - Link to source documents
   - Track for analyst review

## Development

```bash
# Run tests
pytest packages/arkham-shard-contradictions/tests/

# Type checking
mypy packages/arkham-shard-contradictions/
```

## License

MIT
