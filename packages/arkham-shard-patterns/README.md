# Arkham Shard: Patterns

Cross-document pattern detection shard for ArkhamFrame - identifies recurring themes, behaviors, and relationships across the document corpus.

## Overview

The Patterns shard provides automated and manual pattern detection across documents, entities, and timeline events. It identifies recurring themes, behavioral patterns, temporal correlations, and relationships that span multiple sources.

## Features

- **Pattern Detection**: Automatically detect patterns across documents
- **Recurring Theme Analysis**: Identify themes that appear repeatedly
- **Behavioral Pattern Detection**: Find consistent behaviors of entities
- **Temporal Pattern Analysis**: Detect time-based patterns and cycles
- **Correlation Detection**: Find correlations between entities and events
- **Evidence Linking**: Link pattern matches to source documents
- **LLM-Powered Analysis**: Optional AI-assisted pattern recognition
- **Vector Similarity**: Semantic pattern matching when vectors available

## Installation

```bash
cd packages/arkham-shard-patterns
pip install -e .
```

## API Endpoints

### Health & Status

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/patterns/health` | GET | Health check |
| `/api/patterns/count` | GET | Get pattern count (for badge) |
| `/api/patterns/stats` | GET | Get pattern statistics |
| `/api/patterns/capabilities` | GET | Check available capabilities |

### Patterns CRUD

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/patterns/` | GET | List patterns with filters |
| `/api/patterns/` | POST | Create/report a pattern |
| `/api/patterns/{id}` | GET | Get pattern by ID |
| `/api/patterns/{id}` | PUT | Update pattern |
| `/api/patterns/{id}` | DELETE | Delete pattern |
| `/api/patterns/{id}/confirm` | POST | Confirm pattern |
| `/api/patterns/{id}/dismiss` | POST | Dismiss pattern |

### Pattern Matches

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/patterns/{id}/matches` | GET | Get matches for pattern |
| `/api/patterns/{id}/matches` | POST | Add match to pattern |
| `/api/patterns/{id}/matches/{match_id}` | DELETE | Remove match |

### Analysis

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/patterns/analyze` | POST | Run pattern analysis on documents |
| `/api/patterns/detect` | POST | Detect patterns in text |
| `/api/patterns/correlate` | POST | Find correlations between entities |

## Pattern Types

| Type | Description |
|------|-------------|
| `recurring_theme` | Theme appearing in multiple documents |
| `behavioral` | Consistent behavior of an entity |
| `temporal` | Time-based pattern (cycles, sequences) |
| `correlation` | Statistical correlation between entities |
| `linguistic` | Language/style pattern |
| `structural` | Document structure pattern |
| `custom` | User-defined pattern |

## Pattern Status

| Status | Description |
|--------|-------------|
| `detected` | Automatically detected, pending review |
| `confirmed` | Manually confirmed as valid |
| `dismissed` | Dismissed as noise/false positive |
| `archived` | No longer active but preserved |

## Events

### Published Events

| Event | Description |
|-------|-------------|
| `patterns.pattern.detected` | New pattern detected |
| `patterns.pattern.updated` | Pattern updated with new evidence |
| `patterns.pattern.confirmed` | Pattern manually confirmed |
| `patterns.pattern.dismissed` | Pattern dismissed |
| `patterns.match.added` | New match added to pattern |
| `patterns.analysis.started` | Analysis job started |
| `patterns.analysis.completed` | Analysis job completed |

### Subscribed Events

| Event | Description |
|-------|-------------|
| `document.processed` | Scan new documents for patterns |
| `entity.created` | Check entities against patterns |
| `claims.claim.created` | Check claims for pattern matches |
| `timeline.event.created` | Check timeline events for patterns |

## Models

### Pattern

```python
Pattern(
    id: str,
    name: str,
    description: str,
    pattern_type: PatternType,
    status: PatternStatus,
    confidence: float,  # 0.0-1.0
    match_count: int,
    first_detected: datetime,
    last_matched: datetime,
    detection_method: DetectionMethod,
    criteria: Dict,  # Pattern matching criteria
    metadata: Dict
)
```

### PatternMatch

```python
PatternMatch(
    id: str,
    pattern_id: str,
    source_type: SourceType,  # document, entity, claim, event
    source_id: str,
    match_score: float,
    excerpt: str,
    context: str,
    matched_at: datetime,
    metadata: Dict
)
```

## Usage Examples

### Create a Pattern

```python
from arkham_shard_patterns import PatternsShard

pattern = await shard.create_pattern(
    name="Financial Discrepancy Pattern",
    description="Recurring discrepancies in financial reporting",
    pattern_type=PatternType.RECURRING_THEME,
    criteria={
        "keywords": ["discrepancy", "adjustment", "restatement"],
        "entity_types": ["organization", "amount"],
        "min_occurrences": 3
    }
)
```

### Analyze Documents for Patterns

```python
result = await shard.analyze_documents(
    document_ids=["doc1", "doc2", "doc3"],
    pattern_types=[PatternType.RECURRING_THEME, PatternType.BEHAVIORAL]
)
print(f"Found {len(result.patterns_detected)} patterns")
```

### Find Correlations

```python
correlations = await shard.find_correlations(
    entity_ids=["entity1", "entity2"],
    time_window_days=90
)
```

## Dependencies

### Required Services
- `database` - Pattern and match persistence
- `events` - Event publishing/subscription

### Optional Services
- `llm` - AI-powered pattern analysis
- `vectors` - Semantic similarity matching
- `workers` - Background analysis jobs

## Configuration

The shard respects system settings for:
- Minimum confidence threshold for pattern detection
- Maximum patterns to return in listings
- Background analysis batch size
- LLM model selection for analysis

## License

Part of the SHATTERED project.
