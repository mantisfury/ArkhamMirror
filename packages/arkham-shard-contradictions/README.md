# ArkhamFrame Contradictions Shard

Multi-document contradiction detection for investigative journalism.

## Overview

The Contradictions Shard provides sophisticated multi-stage analysis to detect contradictions between documents:

1. **Claim Extraction**: Extracts factual claims from document text
2. **Semantic Matching**: Uses embeddings to find similar claims across documents
3. **LLM Verification**: Verifies if similar claims actually contradict
4. **Severity Scoring**: Classifies contradictions by severity and type

## Features

### Detection Strategies

- **Direct Contradiction**: "X happened" vs "X did not happen"
- **Temporal Contradiction**: Different dates/times for same event
- **Numeric Contradiction**: Different figures or amounts
- **Entity Contradiction**: Different people/places attributed
- **Logical Contradiction**: Logically incompatible statements
- **Contextual Contradiction**: Contradictory in specific context

### Analyst Workflow

- Confirm detected contradictions
- Dismiss false positives
- Add investigative notes
- Track status (detected → investigating → confirmed/dismissed)

### Chain Detection

Automatically detects contradiction chains where:
- Document A contradicts Document B
- Document B contradicts Document C
- Creates linked chain of related contradictions

## Installation

```bash
pip install arkham-shard-contradictions
```

## API Endpoints

### Analyze Documents

```http
POST /api/contradictions/analyze
{
  "doc_a_id": "doc1",
  "doc_b_id": "doc2",
  "threshold": 0.7,
  "use_llm": true
}
```

### Get Document Contradictions

```http
GET /api/contradictions/document/{doc_id}?include_chains=false
```

### List Contradictions

```http
GET /api/contradictions/list?page=1&page_size=50&status=detected&severity=high
```

### Update Status

```http
PUT /api/contradictions/{id}/status
{
  "status": "confirmed",
  "notes": "Verified against original sources",
  "analyst_id": "analyst_1"
}
```

### Add Notes

```http
POST /api/contradictions/{id}/notes
{
  "notes": "Follow up needed with source X",
  "analyst_id": "analyst_1"
}
```

### Extract Claims

```http
POST /api/contradictions/claims
{
  "text": "Document text to analyze...",
  "document_id": "doc1",
  "use_llm": true
}
```

### Get Statistics

```http
GET /api/contradictions/stats
```

### Detect Chains

```http
POST /api/contradictions/detect-chains
```

### List Chains

```http
GET /api/contradictions/chains
```

## Dependencies

### Required Frame Services
- **database** - DatabaseService for storing contradictions (schema: arkham_contradictions)
- **events** - EventBus for pub/sub communication
- **vectors** - VectorService for semantic similarity matching

### Optional Frame Services
- **llm** - LLMService for enhanced contradiction verification (falls back to heuristic detection)

## Events

### Published Events

- `contradictions.contradiction.detected` - New contradiction detected
- `contradictions.contradiction.confirmed` - Analyst confirmed contradiction
- `contradictions.contradiction.dismissed` - Analyst dismissed false positive
- `contradictions.chain.detected` - Contradiction chain detected
- `contradictions.status.updated` - Status changed

### Subscribed Events

- `document.ingested` - Triggers background analysis against existing documents
- `document.updated` - May trigger re-analysis if content changed
- `llm.analysis.completed` - Processes LLM verification results

## Usage Example

```python
from arkham_frame import ArkhamFrame

# Initialize Frame
frame = ArkhamFrame()
await frame.initialize()

# Get contradictions shard
contradictions = frame.get_shard("contradictions")

# Analyze two documents
results = await contradictions.analyze_pair(
    doc_a_id="witness_statement_1",
    doc_b_id="witness_statement_2",
    threshold=0.7,
    use_llm=True
)

# Get statistics
stats = contradictions.get_statistics()
print(f"Total contradictions: {stats['total_contradictions']}")
print(f"High severity: {stats['by_severity']['high']}")

# Detect chains
chains = await contradictions.detect_chains()
print(f"Found {len(chains)} contradiction chains")
```

## Detection Process

### Stage 1: Claim Extraction

Extracts factual claims from documents using:
- Simple sentence splitting (fast, no dependencies)
- LLM-based extraction (more accurate, requires LLM service)

### Stage 2: Semantic Matching

Finds similar claim pairs using:
- Embedding-based cosine similarity (requires embedding service)
- Keyword overlap (fallback method)

Configurable similarity threshold (default: 0.7)

### Stage 3: Verification

Verifies contradictions using:
- LLM analysis (most accurate, requires LLM service)
- Heuristic patterns (fast, no dependencies):
  - Negation detection ("did" vs "did not")
  - Numeric differences (different amounts)
  - Temporal conflicts (different dates)

### Stage 4: Severity Scoring

Classifies by severity:
- **High**: Direct contradictions, clear negations
- **Medium**: Numeric/temporal contradictions
- **Low**: Contextual contradictions, ambiguous cases

## Dependencies

- `arkham-frame>=0.1.0`
- `pydantic>=2.0.0`
- `numpy>=1.24.0`

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black .

# Type check
mypy .
```

## License

See LICENSE file in repository root.
