# Claims Shard

**Version:** 0.1.0
**Category:** Analysis
**Frame Requirement:** >=0.1.0

Claim extraction and tracking shard for ArkhamFrame. Identifies factual assertions from documents for verification, evidence linking, and fact-checking workflows.

## Overview

The Claims shard is a foundational analysis component that:

1. **Extracts Claims** - Identifies factual assertions from document text
2. **Tracks Verification** - Manages claim verification status and evidence
3. **Links Evidence** - Connects claims to supporting or refuting documents
4. **Detects Duplicates** - Finds and merges similar claims across documents
5. **Enables Fact-Checking** - Provides foundation for contradiction detection

## Key Features

### Claim Extraction
- Manual claim creation
- LLM-powered automatic extraction (when LLM service available)
- Background batch extraction (when workers service available)
- Confidence scoring for extracted claims

### Claim Classification
- **Status Types:**
  - `unverified` - Newly extracted, not yet reviewed
  - `verified` - Confirmed with supporting evidence
  - `disputed` - Contradicted by other evidence
  - `retracted` - Claim withdrawn/corrected
  - `uncertain` - Evidence is inconclusive

- **Claim Types:**
  - `factual` - Verifiable statement of fact
  - `opinion` - Subjective statement
  - `prediction` - Future-oriented claim
  - `quantitative` - Numerical/statistical claim
  - `attribution` - Quote or attributed statement

### Evidence Linking
- Link multiple evidence items to a claim
- Evidence can support or refute
- Track evidence strength (strong/moderate/weak)
- Evidence from documents, entities, or external sources

### Claim Matching
- Semantic similarity matching (when vectors service available)
- Find related claims across documents
- Merge duplicate claims with provenance tracking

## Dependencies

### Required Frame Services
- **database** - Stores claims, evidence links, and metadata
- **events** - Publishes claim lifecycle events

### Optional Frame Services
- **llm** - Enables AI-powered claim extraction
- **vectors** - Enables semantic claim matching and similarity search
- **workers** - Enables background batch extraction

## Events

### Published Events

| Event | Description |
|-------|-------------|
| `claims.claim.extracted` | New claim extracted from document |
| `claims.claim.verified` | Claim verification status changed |
| `claims.claim.disputed` | Claim marked as disputed |
| `claims.claim.merged` | Duplicate claims merged |
| `claims.evidence.linked` | Evidence linked to claim |
| `claims.evidence.unlinked` | Evidence removed from claim |
| `claims.extraction.started` | Batch extraction job started |
| `claims.extraction.completed` | Batch extraction job finished |

### Subscribed Events

| Event | Handler |
|-------|---------|
| `document.processed` | Auto-extract claims from new documents |
| `parse.entity.created` | Link claims to extracted entities |
| `contradictions.contradiction.detected` | Mark claims as disputed |

## API Endpoints

### Claims CRUD

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/claims/items` | List claims with pagination |
| GET | `/api/claims/items/{id}` | Get claim details |
| POST | `/api/claims/items` | Create manual claim |
| PATCH | `/api/claims/items/{id}` | Update claim |
| DELETE | `/api/claims/items/{id}` | Delete claim |

### Claim Status

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/claims/{id}/verify` | Mark claim as verified |
| POST | `/api/claims/{id}/dispute` | Mark claim as disputed |
| POST | `/api/claims/{id}/retract` | Mark claim as retracted |

### Evidence Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/claims/{id}/evidence` | Get evidence for claim |
| POST | `/api/claims/{id}/evidence` | Link evidence to claim |
| DELETE | `/api/claims/{id}/evidence/{eid}` | Unlink evidence |

### Extraction

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/claims/extract` | Extract claims from text |
| POST | `/api/claims/extract/document/{id}` | Extract from document |
| POST | `/api/claims/extract/batch` | Batch extraction job |

### Search & Discovery

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/claims/search` | Search claims |
| GET | `/api/claims/similar/{id}` | Find similar claims |
| POST | `/api/claims/merge` | Merge duplicate claims |

### Statistics

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/claims/count` | Badge endpoint |
| GET | `/api/claims/unverified/count` | Unverified count |
| GET | `/api/claims/stats` | Claim statistics |

## Data Models

### Claim
```python
@dataclass
class Claim:
    id: str
    text: str                    # The claim text
    claim_type: ClaimType        # factual, opinion, etc.
    status: ClaimStatus          # unverified, verified, etc.
    confidence: float            # Extraction confidence (0-1)
    source_document_id: str      # Document claim was extracted from
    source_start_char: int       # Position in source document
    source_end_char: int
    extracted_by: str            # "manual", "llm", "rule"
    entities: List[str]          # Linked entity IDs
    created_at: datetime
    updated_at: datetime
    metadata: Dict[str, Any]
```

### Evidence
```python
@dataclass
class Evidence:
    id: str
    claim_id: str
    evidence_type: EvidenceType  # document, entity, external
    reference_id: str            # ID of evidence source
    relationship: str            # "supports" or "refutes"
    strength: str                # strong, moderate, weak
    notes: str                   # Analyst notes
    added_by: str
    added_at: datetime
```

## Database Schema

The shard uses PostgreSQL schema `arkham_claims`:

```sql
CREATE SCHEMA IF NOT EXISTS arkham_claims;

-- Main claims table
CREATE TABLE arkham_claims.claims (
    id UUID PRIMARY KEY,
    text TEXT NOT NULL,
    claim_type VARCHAR(50),
    status VARCHAR(50) DEFAULT 'unverified',
    confidence FLOAT,
    source_document_id UUID,
    source_start_char INTEGER,
    source_end_char INTEGER,
    extracted_by VARCHAR(50),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Evidence links
CREATE TABLE arkham_claims.evidence (
    id UUID PRIMARY KEY,
    claim_id UUID REFERENCES arkham_claims.claims(id),
    evidence_type VARCHAR(50),
    reference_id UUID,
    relationship VARCHAR(20),
    strength VARCHAR(20),
    notes TEXT,
    added_by VARCHAR(100),
    added_at TIMESTAMPTZ DEFAULT NOW()
);

-- Claim-entity links
CREATE TABLE arkham_claims.claim_entities (
    claim_id UUID REFERENCES arkham_claims.claims(id),
    entity_id UUID,
    PRIMARY KEY (claim_id, entity_id)
);

-- Indexes
CREATE INDEX idx_claims_status ON arkham_claims.claims(status);
CREATE INDEX idx_claims_document ON arkham_claims.claims(source_document_id);
CREATE INDEX idx_claims_type ON arkham_claims.claims(claim_type);
CREATE INDEX idx_evidence_claim ON arkham_claims.evidence(claim_id);
```

## Installation

```bash
cd packages/arkham-shard-claims
pip install -e .
```

The shard will be auto-discovered by ArkhamFrame on startup.

## Use Cases

### Investigative Journalism
- Extract factual claims from source documents
- Track verification status across investigation
- Link supporting evidence for each claim
- Export verified claims for publication

### Legal Research
- Identify factual assertions in legal documents
- Track evidence supporting each claim
- Detect contradictory statements
- Export claim chains with provenance

### Academic Research
- Extract hypotheses and claims from papers
- Track supporting/refuting evidence
- Identify claim patterns across literature

## Integration with Other Shards

### Contradictions Shard
- Claims are the foundation for contradiction detection
- Contradictions shard compares claims semantically
- Disputed status set when contradiction detected

### Provenance Shard
- Tracks claim extraction lineage
- Records evidence linking history
- Maintains audit trail for legal use

### Timeline Shard
- Claims with temporal references
- Track when claims were made
- Detect temporal inconsistencies

## Configuration

The shard respects these Frame configurations:

```yaml
# In frame config
claims:
  auto_extract: true              # Auto-extract on document.processed
  min_confidence: 0.7             # Minimum extraction confidence
  max_claims_per_document: 100    # Limit per document
  llm_extraction_model: null      # LLM model for extraction
```

## License

Part of the SHATTERED architecture, licensed under MIT.
