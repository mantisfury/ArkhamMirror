# ACH Shard - Analysis of Competing Hypotheses

An ArkhamFrame shard implementing the Analysis of Competing Hypotheses (ACH) intelligence analysis methodology. This shard serves as the **reference implementation** for SHATTERED shard standards.

## Overview

The ACH method helps intelligence analysts systematically evaluate multiple competing hypotheses by rating how consistent each piece of evidence is with each hypothesis. This approach reduces cognitive bias by focusing on disconfirming evidence rather than confirming evidence.

## Features

### Core ACH Functionality
- **Matrix Management**: Create and manage ACH matrices with hypotheses and evidence
- **Consistency Rating**: Rate evidence against hypotheses (++, +, N, -, --, N/A)
- **Automated Scoring**: Calculate hypothesis scores based on inconsistency counts
- **Diagnosticity Analysis**: Identify which evidence best differentiates hypotheses
- **Sensitivity Analysis**: Assess how uncertain evidence affects conclusions
- **Multi-Format Export**: Export matrices to JSON, CSV, HTML, and Markdown

### AI-Powered Features (requires LLM service)
- **Hypothesis Suggestions**: Generate hypotheses from a focus question
- **Evidence Suggestions**: Suggest diagnostic evidence to gather
- **Rating Suggestions**: AI-assisted rating of evidence against hypotheses
- **Devil's Advocate Mode**: Challenge leading hypotheses with counter-arguments
- **Analysis Insights**: Comprehensive AI analysis of matrix state
- **Milestone Suggestions**: Future indicators that would confirm/refute hypotheses
- **Evidence Extraction**: Extract evidence from document text

## Installation

```bash
pip install arkham-shard-ach
```

The shard will be auto-discovered by ArkhamFrame on startup.

## API Endpoints

All endpoints are prefixed with `/api/ach`.

### Matrix Management

- `POST /matrix` - Create new matrix
- `GET /matrix/{id}` - Get matrix by ID (full structured data)
- `PUT /matrix/{id}` - Update matrix
- `DELETE /matrix/{id}` - Delete matrix
- `GET /matrices` - List matrices (with optional filters)
- `GET /matrices/count` - Get count of active matrices (for badge)

### Hypothesis Management

- `POST /hypothesis` - Add hypothesis to matrix
- `DELETE /hypothesis/{matrix_id}/{hypothesis_id}` - Remove hypothesis

### Evidence Management

- `POST /evidence` - Add evidence to matrix
- `DELETE /evidence/{matrix_id}/{evidence_id}` - Remove evidence

### Rating and Scoring

- `PUT /rating` - Update evidence-hypothesis rating
- `POST /score` - Calculate/recalculate scores

### Analysis

- `POST /devils-advocate` - Generate devil's advocate challenge (basic)
- `GET /diagnosticity/{matrix_id}` - Get diagnosticity report
- `GET /sensitivity/{matrix_id}` - Get sensitivity analysis
- `GET /evidence-gaps/{matrix_id}` - Identify evidence gaps

### Export

- `GET /export/{matrix_id}?format=json|csv|html|markdown` - Export matrix

### AI Endpoints (require LLM service)

- `GET /ai/status` - Check AI availability
- `POST /ai/hypotheses` - Suggest hypotheses from focus question
- `POST /ai/evidence` - Suggest diagnostic evidence
- `POST /ai/ratings` - Suggest ratings for evidence
- `POST /ai/insights` - Get comprehensive analysis insights
- `POST /ai/milestones` - Suggest future indicators
- `POST /ai/devils-advocate` - Full structured devil's advocate challenge
- `POST /ai/extract-evidence` - Extract evidence from document text

## Usage Example

```python
import httpx

async with httpx.AsyncClient(base_url="http://localhost:8100") as client:
    # Create matrix
    response = await client.post("/api/ach/matrix", json={
        "title": "Stolen Documents Analysis",
        "description": "Who stole the classified documents?",
    })
    matrix_id = response.json()["matrix_id"]

    # Get AI-suggested hypotheses
    ai_hyp = await client.post("/api/ach/ai/hypotheses", json={
        "focus_question": "Who stole the classified documents?",
        "context": "Documents went missing from secure facility",
    })

    # Add hypotheses (from AI or manually)
    await client.post("/api/ach/hypothesis", json={
        "matrix_id": matrix_id,
        "title": "Insider Threat",
        "description": "Documents stolen by employee with access",
    })

    await client.post("/api/ach/hypothesis", json={
        "matrix_id": matrix_id,
        "title": "External Breach",
        "description": "Hackers gained remote access",
    })

    # Add evidence
    e1 = await client.post("/api/ach/evidence", json={
        "matrix_id": matrix_id,
        "description": "Security logs show access during business hours",
        "source": "Security audit report",
        "evidence_type": "document",
        "credibility": 0.9,
        "relevance": 0.9,
    })
    evidence_id = e1.json()["evidence_id"]

    # Get AI-suggested ratings
    ratings = await client.post("/api/ach/ai/ratings", json={
        "matrix_id": matrix_id,
        "evidence_id": evidence_id,
    })

    # Apply ratings (from AI or manually)
    await client.put("/api/ach/rating", json={
        "matrix_id": matrix_id,
        "evidence_id": evidence_id,
        "hypothesis_id": hypothesis_id,
        "rating": "++",
        "reasoning": "Business hours access strongly supports insider threat",
    })

    # Calculate scores
    scores = await client.post(f"/api/ach/score?matrix_id={matrix_id}")
    print(scores.json())

    # Get AI analysis insights
    insights = await client.post("/api/ach/ai/insights", json={
        "matrix_id": matrix_id,
    })
    print(insights.json()["insights"])

    # Export report
    export = await client.get(f"/api/ach/export/{matrix_id}?format=html")
```

## Consistency Ratings

| Rating | Label | Description |
|--------|-------|-------------|
| `++` | Highly Consistent | Evidence strongly supports hypothesis |
| `+` | Consistent | Evidence supports hypothesis |
| `N` | Neutral | Evidence neither supports nor refutes |
| `-` | Inconsistent | Evidence refutes hypothesis |
| `--` | Highly Inconsistent | Evidence strongly refutes hypothesis |
| `N/A` | Not Applicable | Evidence not relevant to hypothesis |

## Evidence Types

- `fact` - Established facts
- `testimony` - Witness statements
- `document` - Documentary evidence
- `physical` - Physical evidence
- `circumstantial` - Circumstantial evidence
- `inference` - Logical inferences

## Scoring Methodology

The ACH method focuses on **disconfirming evidence**:

1. Count inconsistencies (- and --) for each hypothesis
2. Calculate weighted consistency score (using evidence credibility and relevance)
3. Rank hypotheses by inconsistency count (lower = better)

The hypothesis with the **fewest inconsistencies** is typically the best supported.

## Shell UI

The shard includes custom UI pages in the Shell:
- **Matrix List** - View and filter all matrices
- **New Matrix Wizard** - Step-by-step matrix creation with AI assistance
- **Matrix Editor** - Full matrix editing with ratings grid

## Dependencies

```toml
dependencies = [
    "arkham-frame>=0.1.0",
    "pydantic>=2.0.0",
]
```

Optional:
- LLM service (from frame) - Enables AI-powered features

## Events

The shard publishes these events via the Frame EventBus:

| Event | Payload |
|-------|---------|
| `ach.matrix.created` | `{matrix_id, title, created_by}` |
| `ach.matrix.updated` | `{matrix_id, title}` |
| `ach.matrix.deleted` | `{matrix_id}` |
| `ach.hypothesis.added` | `{matrix_id, hypothesis_id, title}` |
| `ach.hypothesis.removed` | `{matrix_id, hypothesis_id}` |
| `ach.evidence.added` | `{matrix_id, evidence_id, description}` |
| `ach.evidence.removed` | `{matrix_id, evidence_id}` |
| `ach.rating.updated` | `{matrix_id, evidence_id, hypothesis_id, rating}` |
| `ach.score.calculated` | `{matrix_id, hypothesis_count}` |

## Production Compliance

This shard is compliant with `shard_manifest_schema_prod.md` and serves as the **reference implementation** for all SHATTERED shards.

See [production.md](production.md) for the compliance audit report.

## Documentation

- [production.md](production.md) - Production compliance report
- [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md) - Technical implementation details
- [INTEGRATION_GUIDE.md](INTEGRATION_GUIDE.md) - How to integrate with this shard
- [CLAUDE.md](../../CLAUDE.md) - Project-wide shard standards

## References

- Richards J. Heuer Jr., "Psychology of Intelligence Analysis"
- CIA Center for the Study of Intelligence

## License

Part of the SHATTERED project.
