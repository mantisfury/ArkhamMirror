# arkham-shard-credibility

> Source credibility assessment with deception detection (MOM/POP/MOSES/EVE)

**Version:** 0.1.0
**Category:** Analysis
**Frame Requirement:** >=0.1.0

## Overview

The Credibility shard provides source reliability assessment and deception detection for SHATTERED. It implements traditional credibility scoring with weighted factors, plus intelligence tradecraft deception detection checklists (MOM, POP, MOSES, EVE).

### Key Capabilities

1. **Credibility Scoring** - Assess source reliability with weighted factors
2. **Source Assessment** - Track credibility across documents, entities, sources
3. **Deception Detection** - MOM/POP/MOSES/EVE checklists from intelligence tradecraft
4. **LLM Analysis** - AI-powered checklist completion
5. **History Tracking** - Track credibility changes over time

## Features

### Credibility Assessment
- Score sources 0-100 with confidence
- Multiple weighted factors
- Aggregate scores per source
- Assessment history and trends

### Credibility Levels
- `unreliable` (0-19) - Cannot be trusted
- `low` (20-39) - Limited reliability
- `medium` (40-59) - Moderate reliability
- `high` (60-79) - Generally reliable
- `verified` (80-100) - Highly reliable

### Source Types
- `document` - Document sources
- `entity` - Entity sources (persons, orgs)
- `claim` - Claim sources
- `external` - External sources

### Assessment Methods
- `manual` - Human assessment
- `automated` - Algorithm-based
- `llm` - LLM-assisted
- `hybrid` - Combined methods

### Standard Factors
- Source expertise
- Track record
- Corroboration
- Recency
- Bias indicators
- And more configurable factors

### Deception Detection Checklists

Intelligence tradecraft checklists for detecting deception:

#### MOM (Motive, Opportunity, Means)
Assesses whether a source has motive, opportunity, and means to deceive.

#### POP (Past Opposition Practices)
Reviews historical deception patterns and practices.

#### MOSES (Multiple, Orthogonal Sources)
Evaluates whether information comes from independent sources.

#### EVE (Evaluation of Evidence)
Examines evidence quality and potential manipulation.

### Deception Risk Levels
- `minimal` - Little evidence of deception
- `low` - Some minor indicators
- `moderate` - Notable concerns
- `high` - Strong deception indicators
- `critical` - High confidence of deception

## Installation

```bash
pip install -e packages/arkham-shard-credibility
```

The shard auto-registers via entry point on Frame startup.

## API Endpoints

### Health and Counts

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/credibility/health` | Health check |
| GET | `/api/credibility/count` | Total assessments count |
| GET | `/api/credibility/low/count` | Low credibility count (badge) |

### Assessment CRUD

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/credibility/` | List assessments |
| POST | `/api/credibility/` | Create assessment |
| GET | `/api/credibility/{id}` | Get assessment |
| PUT | `/api/credibility/{id}` | Update assessment |
| DELETE | `/api/credibility/{id}` | Delete assessment |

### By Level

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/credibility/level/{level}` | List by level |

### Source Analysis

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/credibility/source/{type}/{id}` | Get source credibility |
| GET | `/api/credibility/source/{type}/{id}/history` | Source history |
| POST | `/api/credibility/calculate` | Calculate credibility |

### Factors and Statistics

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/credibility/factors` | List standard factors |
| GET | `/api/credibility/stats` | Get statistics |
| GET | `/api/credibility/stats/by-source-type` | Stats by source type |

### Deception Detection

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/credibility/deception` | Create deception assessment |
| GET | `/api/credibility/deception` | List deception assessments |
| GET | `/api/credibility/deception/count` | Deception count |
| GET | `/api/credibility/deception/high-risk` | High risk sources |
| GET | `/api/credibility/deception/{id}` | Get deception assessment |
| PUT | `/api/credibility/deception/{id}` | Update assessment |
| DELETE | `/api/credibility/deception/{id}` | Delete assessment |

### Deception Checklists

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/credibility/deception/indicators/{type}` | Get checklist indicators |
| PUT | `/api/credibility/deception/{id}/checklist/{type}` | Update checklist |
| POST | `/api/credibility/deception/{id}/checklist/{type}/llm` | LLM analysis |
| POST | `/api/credibility/deception/{id}/recalculate` | Recalculate score |
| GET | `/api/credibility/deception/source/{type}/{id}` | Source deception history |

### AI Analysis

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/credibility/ai/junior-analyst` | AI analysis (streaming) |

## API Examples

### Create Credibility Assessment

```json
POST /api/credibility/
{
  "source_type": "document",
  "source_id": "doc_abc123",
  "score": 75,
  "confidence": 0.85,
  "factors": [
    {"factor_type": "expertise", "weight": 0.3, "score": 80, "notes": "Expert author"},
    {"factor_type": "corroboration", "weight": 0.25, "score": 70, "notes": "Multiple sources"},
    {"factor_type": "recency", "weight": 0.2, "score": 90, "notes": "Recent publication"}
  ],
  "assessed_by": "manual",
  "notes": "Generally reliable government report"
}
```

### Get Source Credibility

```bash
GET /api/credibility/source/document/doc_abc123
```

Response:
```json
{
  "source_type": "document",
  "source_id": "doc_abc123",
  "avg_score": 72.5,
  "assessment_count": 2,
  "latest_score": 75,
  "latest_confidence": 0.85,
  "latest_assessment_id": "assess_xyz",
  "latest_assessed_at": "2024-12-15T10:30:00Z",
  "level": "high"
}
```

### Calculate Credibility with LLM

```json
POST /api/credibility/calculate
{
  "source_type": "document",
  "source_id": "doc_abc123",
  "use_llm": true
}
```

### Create Deception Assessment

```json
POST /api/credibility/deception
{
  "source_type": "entity",
  "source_id": "ent_person_123",
  "source_name": "John Smith",
  "affects_credibility": true,
  "credibility_weight": 0.3
}
```

### Get Checklist Indicators

```bash
GET /api/credibility/deception/indicators/mom
```

Returns standard MOM checklist questions and guidance.

### Update Checklist with Answers

```json
PUT /api/credibility/deception/{id}/checklist/mom
{
  "indicators": [
    {
      "id": "mom_1",
      "checklist": "mom",
      "question": "Does the source have motive to deceive?",
      "answer": "Possible financial incentive identified",
      "strength": "moderate",
      "confidence": 0.7,
      "evidence_ids": ["ev_123"],
      "notes": "Recent business dealings suggest motive"
    }
  ],
  "summary": "Moderate motive indicators present"
}
```

### LLM-Assisted Checklist Analysis

```json
POST /api/credibility/deception/{id}/checklist/mom/llm
{
  "context": "Additional context about the source..."
}
```

### Get Statistics

```bash
GET /api/credibility/stats
```

Response:
```json
{
  "total_assessments": 450,
  "by_source_type": {"document": 300, "entity": 100, "external": 50},
  "by_level": {"unreliable": 20, "low": 80, "medium": 150, "high": 150, "verified": 50},
  "by_method": {"manual": 200, "automated": 150, "llm": 100},
  "avg_score": 58.5,
  "avg_confidence": 0.78,
  "unreliable_count": 20,
  "low_count": 80,
  "medium_count": 150,
  "high_count": 150,
  "verified_count": 50,
  "sources_assessed": 380,
  "avg_assessments_per_source": 1.18
}
```

## Events

### Published Events

| Event | Description |
|-------|-------------|
| `credibility.assessment.created` | New assessment created |
| `credibility.score.updated` | Score changed |
| `credibility.source.rated` | Source credibility rated |
| `credibility.factor.applied` | Factor applied |
| `credibility.analysis.completed` | Automated analysis finished |
| `credibility.threshold.breached` | Score crossed threshold |

### Subscribed Events

| Event | Handler |
|-------|---------|
| `document.processed` | Assess new documents |
| `claims.claim.verified` | Update source credibility |
| `claims.claim.disputed` | Downgrade source credibility |
| `contradictions.contradiction.detected` | Impact credibility |

## UI Routes

| Route | Description |
|-------|-------------|
| `/credibility` | All assessments |
| `/credibility/high` | High credibility sources |
| `/credibility/low` | Low credibility sources |
| `/credibility/sources` | Source analysis |

## Tech Stack

- **PostgreSQL 14+** - Single database for all persistence
- **pgvector extension** - Vector similarity search for semantic analysis
- **PostgreSQL job queue** - Background jobs using SKIP LOCKED pattern

## Dependencies

### Required Services
- **database** - Assessment storage (PostgreSQL)
- **events** - Event publishing

### Optional Services
- **llm** - AI-powered assessment
- **vectors** - Semantic analysis (pgvector)
- **workers** - Background jobs (PostgreSQL SKIP LOCKED)

## URL State

| Parameter | Description |
|-----------|-------------|
| `assessmentId` | Selected assessment |
| `sourceType` | Filter by source type |
| `sourceId` | Filter by source |
| `minScore` | Minimum score filter |

### Local Storage Keys
- `show_factors` - Factor detail expansion
- `sort_order` - List sort preference
- `score_threshold` - Display threshold

## Indicator Strength

| Strength | Description |
|----------|-------------|
| `none` | No indication |
| `weak` | Minor indicator |
| `moderate` | Notable indicator |
| `strong` | Strong indicator |
| `definitive` | Conclusive indicator |

## Scoring Methodology

### Credibility Score
Weighted average of factor scores:
- Each factor has weight (0-1) and score (0-100)
- Overall score = sum(factor_weight * factor_score) / sum(weights)
- Level determined by score thresholds

### Deception Score
Average of completed checklist scores:
- Each checklist calculates score from indicator strengths
- Overall score = average of completed checklist scores
- Risk level determined by score and indicator patterns

## Development

```bash
# Run tests
pytest packages/arkham-shard-credibility/tests/

# Type checking
mypy packages/arkham-shard-credibility/
```

## References

- Richards J. Heuer Jr., "Psychology of Intelligence Analysis"
- Intelligence Community tradecraft standards
- MICE (Money, Ideology, Compromise, Ego) framework

## License

MIT
