# arkham-shard-ach

> Analysis of Competing Hypotheses with AI-powered analysis, premortem, and scenario planning

**Version:** 0.1.0
**Category:** Analysis
**Frame Requirement:** >=0.1.0

## Overview

The ACH shard implements Analysis of Competing Hypotheses, a structured analytic technique used in intelligence analysis. It provides matrix-based evaluation of hypotheses against evidence, enhanced with AI-powered features including devil's advocate challenges, premortem analysis, corpus-based evidence extraction, and cone of plausibility scenario planning.

### Key Capabilities

1. **Matrix Management** - Create and manage ACH matrices with hypotheses and evidence
2. **Consistency Scoring** - Calculate hypothesis scores based on evidence ratings
3. **AI Analysis** - LLM-powered hypothesis suggestions, evidence extraction, and insights
4. **Premortem Analysis** - Failure mode identification for hypotheses
5. **Scenario Planning** - Cone of plausibility with branching futures
6. **Corpus Search** - Extract evidence from document corpus via vector search
7. **Export** - Export to JSON, CSV, HTML, PDF, Markdown

## Features

### Matrix Management
- Create, update, delete matrices
- Add/remove hypotheses and evidence
- Rate evidence consistency against hypotheses
- Track matrix status (active, archived, completed)
- Link documents to matrices for corpus search scope

### Consistency Ratings

| Rating | Symbol | Description |
|--------|--------|-------------|
| `++` | Strongly Consistent | Evidence strongly supports hypothesis |
| `+` | Consistent | Evidence supports hypothesis |
| `N` | Neutral | Evidence neither supports nor contradicts |
| `-` | Inconsistent | Evidence contradicts hypothesis |
| `--` | Strongly Inconsistent | Evidence strongly contradicts hypothesis |
| `NA` | Not Applicable | Evidence not relevant to hypothesis |

### Evidence Types
- `fact` - Verified factual information
- `document` - From document corpus
- `testimony` - Witness statements
- `circumstantial` - Indirect evidence
- `assumption` - Working assumptions

### AI-Powered Features

#### Hypothesis Suggestions
Generate new hypotheses based on focus question and context.

#### Evidence Suggestions
Suggest diagnostic evidence that distinguishes between hypotheses.

#### Rating Suggestions
AI-generated consistency ratings with explanations.

#### Devil's Advocate
Challenge the leading hypothesis with counter-arguments.

#### Analysis Insights
Comprehensive analysis including:
- Leading hypothesis assessment
- Key distinguishing evidence
- Evidence gaps
- Cognitive bias warnings
- Recommendations

#### Milestone Suggestions
Generate observable future indicators for hypotheses.

### Premortem Analysis
Assumes a hypothesis is WRONG and identifies:
- Failure modes with likelihood
- Early warning indicators
- Mitigation actions
- Key risks
- Convert failure modes to new hypotheses or milestones

### Cone of Plausibility (Scenarios)
Generate branching scenario trees showing possible futures:
- Multiple depth levels
- Probability assignments
- Key drivers and trigger conditions
- Status tracking (active, occurred, ruled_out)
- Convert scenarios to hypotheses

### Corpus Search
Search document corpus for evidence:
- Vector similarity search
- LLM classification of relevance
- Duplicate detection
- Accept extracted evidence into matrix
- Auto-rate evidence by relevance

## Installation

```bash
pip install -e packages/arkham-shard-ach
```

The shard auto-registers via entry point on Frame startup.

## API Endpoints

### Matrix CRUD

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/ach/matrix` | Create matrix |
| GET | `/api/ach/matrix/{id}` | Get matrix |
| PUT | `/api/ach/matrix/{id}` | Update matrix |
| DELETE | `/api/ach/matrix/{id}` | Delete matrix |
| GET | `/api/ach/matrices` | List matrices |
| GET | `/api/ach/matrices/count` | Matrix count (badge) |

### Linked Documents

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/ach/matrix/{id}/documents` | Get linked documents |
| POST | `/api/ach/matrix/{id}/documents` | Link documents |
| DELETE | `/api/ach/matrix/{id}/documents/{doc_id}` | Unlink document |

### Hypotheses and Evidence

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/ach/hypothesis` | Add hypothesis |
| DELETE | `/api/ach/hypothesis/{matrix_id}/{id}` | Remove hypothesis |
| GET | `/api/ach/hypotheses` | List all hypotheses |
| POST | `/api/ach/evidence` | Add evidence |
| DELETE | `/api/ach/evidence/{matrix_id}/{id}` | Remove evidence |
| GET | `/api/ach/evidence` | List all evidence |
| PUT | `/api/ach/rating` | Update rating |

### Scoring and Analysis

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/ach/score` | Calculate scores |
| GET | `/api/ach/diagnosticity/{id}` | Diagnosticity report |
| GET | `/api/ach/sensitivity/{id}` | Sensitivity analysis |
| GET | `/api/ach/evidence-gaps/{id}` | Evidence gaps |
| POST | `/api/ach/devils-advocate` | Devil's advocate challenge |

### Export

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/ach/export/{id}?format=json` | Export matrix |

### AI Features

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/ach/ai/status` | AI availability |
| POST | `/api/ach/ai/hypotheses` | Suggest hypotheses |
| POST | `/api/ach/ai/evidence` | Suggest evidence |
| POST | `/api/ach/ai/ratings` | Suggest ratings |
| POST | `/api/ach/ai/insights` | Analysis insights |
| POST | `/api/ach/ai/milestones` | Suggest milestones |
| POST | `/api/ach/ai/devils-advocate` | Full devil's advocate |
| POST | `/api/ach/ai/extract-evidence` | Extract from text |
| POST | `/api/ach/ai/junior-analyst` | AI Junior Analyst (streaming) |

### Corpus Search

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/ach/ai/corpus/status` | Corpus availability |
| POST | `/api/ach/ai/corpus-search` | Search for hypothesis |
| POST | `/api/ach/ai/corpus-search-all` | Search all hypotheses |
| POST | `/api/ach/ai/accept-corpus-evidence` | Accept evidence |

### Premortem

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/ach/ai/premortem` | Run premortem |
| GET | `/api/ach/matrix/{id}/premortems` | List premortems |
| GET | `/api/ach/premortem/{id}` | Get premortem |
| DELETE | `/api/ach/premortem/{id}` | Delete premortem |
| POST | `/api/ach/premortem/convert` | Convert failure mode |

### Scenarios (Cone of Plausibility)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/ach/ai/scenarios` | Generate scenario tree |
| GET | `/api/ach/matrix/{id}/scenarios` | List scenario trees |
| GET | `/api/ach/scenarios/{id}` | Get scenario tree |
| DELETE | `/api/ach/scenarios/{id}` | Delete tree |
| POST | `/api/ach/scenarios/branch` | Add branches |
| PUT | `/api/ach/scenarios/{tree_id}/nodes/{node_id}` | Update node |
| POST | `/api/ach/scenarios/convert` | Convert to hypothesis |

## API Examples

### Create Matrix

```json
POST /api/ach/matrix
{
  "title": "Source Attribution Analysis",
  "description": "Determining the origin of the intelligence leak",
  "project_id": "proj_123"
}
```

### Add Hypothesis

```json
POST /api/ach/hypothesis
{
  "matrix_id": "matrix_abc",
  "title": "Insider Threat",
  "description": "The leak originated from an internal employee"
}
```

### Add Evidence and Rate

```json
POST /api/ach/evidence
{
  "matrix_id": "matrix_abc",
  "description": "Access logs show employee A accessed the files",
  "source": "IT Security Report",
  "evidence_type": "fact",
  "credibility": 0.9,
  "relevance": 0.8
}

PUT /api/ach/rating
{
  "matrix_id": "matrix_abc",
  "evidence_id": "ev_123",
  "hypothesis_id": "hyp_456",
  "rating": "++",
  "reasoning": "Direct evidence of access",
  "confidence": 0.9
}
```

### Corpus Search for Evidence

```json
POST /api/ach/ai/corpus-search
{
  "matrix_id": "matrix_abc",
  "hypothesis_id": "hyp_456",
  "chunk_limit": 30,
  "min_similarity": 0.5
}
```

### Run Premortem

```json
POST /api/ach/ai/premortem
{
  "matrix_id": "matrix_abc",
  "hypothesis_id": "hyp_456"
}
```

Response includes failure modes, early warning indicators, and mitigation actions.

### Generate Scenario Tree

```json
POST /api/ach/ai/scenarios
{
  "matrix_id": "matrix_abc",
  "title": "Possible Outcomes",
  "situation_summary": "Current evidence points to...",
  "max_depth": 2
}
```

## Events

### Published Events

| Event | Description |
|-------|-------------|
| `ach.matrix.created` | Matrix created |
| `ach.matrix.updated` | Matrix updated |
| `ach.matrix.deleted` | Matrix deleted |
| `ach.hypothesis.added` | Hypothesis added |
| `ach.hypothesis.removed` | Hypothesis removed |
| `ach.evidence.added` | Evidence added |
| `ach.evidence.removed` | Evidence removed |
| `ach.rating.updated` | Rating changed |
| `ach.analysis.completed` | Analysis finished |
| `ach.premortem.created` | Premortem generated |
| `ach.premortem.deleted` | Premortem deleted |
| `ach.scenario_tree.created` | Scenarios generated |
| `ach.scenario_tree.updated` | Scenarios updated |
| `ach.scenario_tree.deleted` | Scenarios deleted |
| `ach.scenario.converted` | Scenario to hypothesis |

### Subscribed Events

| Event | Handler |
|-------|---------|
| `llm.analysis.completed` | Process LLM results |
| `document.processed` | Link processed documents |

## UI Routes

| Route | Description |
|-------|-------------|
| `/ach` | ACH main page |
| `/ach/matrices` | All matrices list |
| `/ach/new` | Create new analysis |
| `/ach/scenarios` | Scenario planning |

## Tech Stack

- **PostgreSQL 14+** - Single database for all persistence
- **pgvector extension** - Vector similarity search for corpus evidence
- **PostgreSQL job queue** - Background jobs using SKIP LOCKED pattern

## Dependencies

### Required Services
- **database** - Matrix, evidence, premortem persistence (PostgreSQL)
- **events** - Event publishing

### Optional Services
- **llm** - AI-powered analysis, suggestions, premortem
- **vectors** - Corpus evidence search (pgvector)

## URL State

| Parameter | Description |
|-----------|-------------|
| `matrixId` | Active matrix ID |
| `hypothesisId` | Selected hypothesis |
| `tab` | Active tab (matrix, evidence, analysis) |
| `view` | View mode (grid, list, summary) |

### Local Storage Keys
- `matrix_zoom` - Zoom level preference
- `show_tooltips` - Tooltip visibility

## Export Formats

| Format | Content Type | Description |
|--------|--------------|-------------|
| `json` | application/json | Full matrix data |
| `csv` | text/csv | Evidence and ratings table |
| `html` | text/html | Formatted HTML report |
| `pdf` | application/pdf | Professional PDF report |
| `markdown` | text/markdown | Markdown document |

## Scoring Methodology

The ACH scoring algorithm:
1. Counts inconsistencies per hypothesis
2. Weights by evidence credibility and relevance
3. Normalizes scores to 0-1 range
4. Ranks hypotheses (lowest inconsistency = highest rank)

The leading hypothesis has the **fewest inconsistencies** with the evidence, not the most consistencies.

## Development

```bash
# Run tests
pytest packages/arkham-shard-ach/tests/

# Type checking
mypy packages/arkham-shard-ach/
```

## References

- Heuer, R.J. (1999). Psychology of Intelligence Analysis
- CIA Tradecraft Primer: Structured Analytic Techniques

## License

MIT
