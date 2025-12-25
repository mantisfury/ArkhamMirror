# ACH Shard Implementation Summary

**Date:** 2025-12-24
**Package:** arkham-shard-ach v0.1.0
**Location:** `packages/arkham-shard-ach/`

## Overview

Complete implementation of the Analysis of Competing Hypotheses (ACH) shard for SHATTERED architecture. This shard serves as the **reference implementation** for shard standards, demonstrating proper manifest v5 format, Frame integration, and LLM-powered analysis features.

The ACH method is a structured intelligence analysis technique for evaluating multiple competing hypotheses against evidence, focusing on disconfirming rather than confirming evidence.

## Package Structure

```
arkham-shard-ach/
├── pyproject.toml              # Package metadata, entry points
├── shard.yaml                  # Manifest v5 format (reference implementation)
├── README.md                   # User documentation
├── IMPLEMENTATION_SUMMARY.md   # This file
├── INTEGRATION_GUIDE.md        # Integration instructions
├── test_basic.py               # Smoke tests
├── arkham_shard_ach/
│   ├── __init__.py             # Package exports (ACHShard, ACHLLMIntegration)
│   ├── shard.py                # ACHShard class (~328 lines)
│   ├── api.py                  # FastAPI router (~1021 lines)
│   ├── models.py               # Data models (~239 lines)
│   ├── matrix.py               # Matrix operations (~338 lines)
│   ├── scoring.py              # Scoring algorithms (~260 lines)
│   ├── evidence.py             # Evidence management (~327 lines)
│   ├── export.py               # Export formats (~370 lines)
│   └── llm.py                  # LLM integration (~944 lines)
```

**Total:** ~3,827 lines across 12 files

## Core Components

### 1. Data Models (`models.py`)

**Enumerations:**
- `ConsistencyRating` - Evidence ratings (++, +, N, -, --, N/A) with score properties
- `EvidenceType` - Evidence categories (fact, testimony, document, physical, circumstantial, inference)
- `MatrixStatus` - Matrix lifecycle states (draft, active, completed, archived)

**Data Classes:**
- `Hypothesis` - Column in ACH matrix (id, title, description, column_index, is_lead)
- `Evidence` - Row in ACH matrix (id, description, source, credibility, relevance, document_ids)
- `Rating` - Cell in ACH matrix (evidence vs hypothesis with reasoning and confidence)
- `HypothesisScore` - Calculated scores (inconsistency_count, weighted_score, normalized_score, rank)
- `ACHMatrix` - Complete matrix container with helper methods (get_hypothesis, get_evidence, get_rating, leading_hypothesis)
- `DevilsAdvocateChallenge` - LLM-generated critique with structured fields
- `MatrixExport` - Export container

### 2. Matrix Manager (`matrix.py`)

In-memory matrix storage and CRUD operations:
- Create/read/update/delete matrices
- Add/remove hypotheses with column reindexing
- Add/remove evidence with row reindexing
- Set/update ratings between evidence and hypotheses
- `get_matrix_data()` - Full structured API response format

### 3. Scoring Engine (`scoring.py`)

ACH scoring methodology implementation:
- **Primary:** Count inconsistencies (- and --) per hypothesis
- **Secondary:** Calculate weighted consistency scores (by credibility, relevance, confidence)
- **Ranking:** Lower inconsistency count = better rank (marks `is_lead` flag)
- **Diagnosticity Analysis:** Identify high-variance evidence that differentiates hypotheses
- **Sensitivity Analysis:** Test impact of removing low-credibility evidence on rankings

### 4. Evidence Analyzer (`evidence.py`)

Evidence quality and gap analysis:
- Quality assessment based on credibility and relevance (high/medium/low)
- Gap identification:
  - Under-evidenced hypotheses (< 3 substantive ratings)
  - Missing evidence types
  - Unrated evidence items
  - High proportion of low-quality evidence
- Evidence comparison between items (agreements/disagreements)
- Rule-based suggestion generation

### 5. Exporter (`export.py`)

Multi-format matrix export:
- **JSON** - Full structured data with metadata
- **CSV** - Spreadsheet-compatible tabular format with scores section
- **HTML** - Rich formatted table with color-coded ratings and CSS styling
- **Markdown** - Documentation-friendly format with tables

### 6. LLM Integration (`llm.py`)

Comprehensive AI-powered analysis features:

**Response Models:**
- `HypothesisSuggestion` - Suggested hypothesis from LLM
- `EvidenceSuggestion` - Suggested evidence with type
- `RatingSuggestion` - Suggested rating with explanation
- `Challenge` - Devil's advocate challenge structure
- `MilestoneSuggestion` - Future indicator suggestion
- `AnalysisInsights` - Comprehensive analysis output

**System Prompts:** Specialized prompts for hypotheses, evidence, ratings, devil's advocate, insights, and milestones

**Core Methods:**
- `suggest_hypotheses()` - Generate 3-5 hypotheses from focus question
- `suggest_evidence()` - Generate diagnostic evidence suggestions
- `suggest_ratings()` - Rate evidence against all hypotheses with explanations
- `challenge_hypotheses()` / `generate_full_challenge()` - Devil's advocate mode
- `get_analysis_insights()` - Comprehensive matrix analysis
- `suggest_milestones()` - Future indicators for each hypothesis
- `extract_evidence_from_text()` - Extract evidence from document text

**Parsing:** Robust parsing of LLM responses (numbered lists, JSON, structured text)

### 7. API Router (`api.py`)

**28 FastAPI endpoints** (prefix: `/api/ach`):

**Matrix Management:**
- `POST /matrix` - Create matrix
- `GET /matrix/{id}` - Retrieve matrix (full structured data)
- `PUT /matrix/{id}` - Update matrix (title, description, status, notes)
- `DELETE /matrix/{id}` - Delete matrix
- `GET /matrices` - List with filters (project_id, status)
- `GET /matrices/count` - Active matrix count (for navigation badge)

**Hypothesis Management:**
- `POST /hypothesis` - Add hypothesis
- `DELETE /hypothesis/{matrix_id}/{hypothesis_id}` - Remove

**Evidence Management:**
- `POST /evidence` - Add evidence (with document_ids linking)
- `DELETE /evidence/{matrix_id}/{evidence_id}` - Remove

**Rating & Scoring:**
- `PUT /rating` - Update rating (with reasoning, confidence)
- `POST /score` - Calculate scores

**Analysis:**
- `POST /devils-advocate` - Basic LLM challenge
- `GET /diagnosticity/{id}` - Diagnosticity report
- `GET /sensitivity/{id}` - Sensitivity analysis
- `GET /evidence-gaps/{id}` - Gap analysis

**Export:**
- `GET /export/{id}?format=json|csv|html|markdown` - Export matrix

**AI-Powered Endpoints** (require LLM service):
- `GET /ai/status` - Check AI feature availability
- `POST /ai/hypotheses` - Suggest hypotheses
- `POST /ai/evidence` - Suggest diagnostic evidence
- `POST /ai/ratings` - Suggest ratings for evidence
- `POST /ai/insights` - Get comprehensive analysis insights
- `POST /ai/milestones` - Suggest future indicators
- `POST /ai/devils-advocate` - Full structured devil's advocate challenge
- `POST /ai/extract-evidence` - Extract evidence from document text

### 8. Shard Class (`shard.py`)

Implements `ArkhamShard` interface with manifest v5 loading:

**Manifest Loading:**
- `load_manifest_from_yaml()` - Full v5 manifest parsing
- Parses: navigation, dependencies, events, state, UI config
- Fallback to minimal manifest if YAML fails

**Initialization:**
- Creates MatrixManager, ACHScorer, EvidenceAnalyzer, MatrixExporter
- Gets Frame services (events, llm)
- Initializes `ACHLLMIntegration` if LLM available
- Calls `init_api()` to wire up dependencies

**Public API Methods:**
- `create_matrix()` - For other shards
- `get_matrix()` - For other shards
- `calculate_scores()` - For other shards
- `export_matrix()` - For other shards

## Manifest v5 (Reference Implementation)

```yaml
name: ach
version: 0.1.0
description: Analysis of Competing Hypotheses matrix for intelligence analysis
entry_point: arkham_shard_ach:ACHShard
api_prefix: /api/ach
requires_frame: ">=0.1.0"

navigation:
  category: Analysis
  order: 30
  icon: Scale
  label: ACH Analysis
  route: /ach
  badge_endpoint: /api/ach/matrices/count
  badge_type: count
  sub_routes:
    - id: matrices
      label: All Matrices
      route: /ach/matrices
      icon: List
    - id: new
      label: New Analysis
      route: /ach/new
      icon: Plus

dependencies:
  services: [database, events]
  optional: [llm]
  shards: []  # No shard dependencies

capabilities:
  - hypothesis_management
  - evidence_management
  - consistency_scoring
  - devils_advocate
  - matrix_export

events:
  publishes:
    - ach.matrix.created
    - ach.matrix.updated
    - ach.matrix.deleted
    - ach.hypothesis.added
    - ach.hypothesis.removed
    - ach.evidence.added
    - ach.evidence.removed
    - ach.rating.updated
    - ach.score.calculated
  subscribes:
    - llm.analysis.completed

state:
  strategy: url
  url_params: [matrixId, tab, view]

ui:
  has_custom_ui: true
```

## Event-Driven Architecture

Publishes 9 event types via Frame EventBus:
- `ach.matrix.created` - {matrix_id, title, created_by}
- `ach.matrix.updated` - {matrix_id, title}
- `ach.matrix.deleted` - {matrix_id}
- `ach.hypothesis.added` - {matrix_id, hypothesis_id, title}
- `ach.hypothesis.removed` - {matrix_id, hypothesis_id}
- `ach.evidence.added` - {matrix_id, evidence_id, description}
- `ach.evidence.removed` - {matrix_id, evidence_id}
- `ach.rating.updated` - {matrix_id, evidence_id, hypothesis_id, rating}
- `ach.score.calculated` - {matrix_id, hypothesis_count}

All events include `source="ach-shard"`.

## Shell Integration

The shard provides pages in `packages/arkham-shard-shell/src/pages/ach/`:
- `ACHListPage.tsx` - Matrix listing
- `ACHNewPage.tsx` - New matrix creation wizard
- `ACHPage.tsx` - Matrix detail/editing
- `api.ts` - API client functions
- `types.ts` - TypeScript types
- `components/` - Reusable ACH components (StepIndicator, GuidancePanel, AIDialogs, etc.)

## Testing

`test_basic.py` validates:
- Matrix creation
- Hypothesis and evidence addition
- Rating assignment
- Score calculation (correctly ranks by inconsistency)
- Export to all 4 formats

## Dependencies

```toml
dependencies = [
    "arkham-frame>=0.1.0",
    "pydantic>=2.0.0",
]
```

## Compliance with Shard Standards

- Implements `ArkhamShard` ABC from `arkham_frame.shard_interface`
- Uses manifest v5 format with all optional sections
- Depends only on Frame services (no other shard imports)
- EventBus uses `emit()` method
- Router prefix matches manifest `api_prefix`
- Public API methods for inter-shard communication
- Graceful degradation when optional services unavailable

## Future Enhancements

1. **Database Persistence** - Currently in-memory only
2. **Document Linking** - Deep integration with ingest shard
3. **Visualization** - Interactive matrix editor improvements
4. **Collaboration** - Multi-user with conflict resolution
5. **Statistical Analysis** - Bayesian updating, confidence intervals

## Status

**COMPLETE** - Reference implementation for SHATTERED shard standards

The ACH shard demonstrates:
- Full manifest v5 compliance
- Comprehensive LLM integration
- Event-driven architecture
- Shell UI integration
- Export capabilities
- Public API for other shards
