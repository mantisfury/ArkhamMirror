# Credibility Shard

**Production-ready source credibility assessment and scoring for ArkhamFrame**

## Overview

The Credibility Shard provides comprehensive source credibility assessment capabilities for the SHATTERED intelligence analysis platform. It evaluates the reliability and trustworthiness of documents, entities, websites, publications, and other sources using configurable scoring factors and optional AI-powered analysis.

## Purpose

Source credibility is fundamental to intelligence analysis. This shard enables:

- **Credibility Scoring**: Assign 0-100 scores to sources with confidence metrics
- **Factor-Based Assessment**: Evaluate sources across multiple credibility dimensions
- **Source Type Support**: Assess documents, entities, websites, publications, people, organizations
- **Assessment Methods**: Manual, automated (LLM), and hybrid approaches
- **Historical Tracking**: Track credibility changes over time
- **Threshold Alerts**: Notifications when credibility crosses thresholds

## Features

### Core Capabilities

- **Multi-Source Assessment**: Evaluate diverse source types (documents, entities, websites, etc.)
- **Factor-Based Scoring**: Configurable credibility factors with weights
- **0-100 Scoring Scale**: UNRELIABLE (0-20), LOW (21-40), MEDIUM (41-60), HIGH (61-80), VERIFIED (81-100)
- **Confidence Tracking**: Separate confidence scores for assessment reliability
- **Method Tracking**: Manual, automated (LLM), or hybrid assessment methods
- **Source History**: Track all assessments for a given source over time
- **Score Aggregation**: Combine multiple assessments into aggregate scores

### AI-Powered Assessment (Optional)

When LLM service is available:
- Automated credibility factor extraction
- Natural language assessment reasoning
- Bias detection and analysis
- Cross-source consistency checking

### Event Integration

**Publishes**:
- `credibility.assessment.created` - New assessment created
- `credibility.score.updated` - Score changed
- `credibility.source.rated` - Source received new rating
- `credibility.factor.applied` - Credibility factor applied
- `credibility.analysis.completed` - Automated analysis finished
- `credibility.threshold.breached` - Score crossed threshold

**Subscribes**:
- `document.processed` - Assess newly processed documents
- `claims.claim.verified` - Boost source credibility from verified claims
- `claims.claim.disputed` - Reduce source credibility from disputed claims
- `contradictions.contradiction.detected` - Impact credibility of involved sources

## Installation

```bash
cd packages/arkham-shard-credibility
pip install -e .
```

The shard will be auto-discovered by ArkhamFrame on next startup.

## API Endpoints

### Core Endpoints

- `GET /api/credibility/health` - Health check
- `GET /api/credibility/count` - Get assessment count (badge)
- `GET /api/credibility/` - List assessments (with filtering)
- `POST /api/credibility/` - Create assessment
- `GET /api/credibility/{id}` - Get assessment by ID
- `PUT /api/credibility/{id}` - Update assessment
- `DELETE /api/credibility/{id}` - Delete assessment

### Source Endpoints

- `GET /api/credibility/source/{source_type}/{source_id}` - Get source score
- `POST /api/credibility/calculate` - Calculate score for source
- `GET /api/credibility/source/{source_type}/{source_id}/history` - Get source history

### Factor Endpoints

- `GET /api/credibility/factors` - List available credibility factors
- `POST /api/credibility/factors` - Create custom factor
- `GET /api/credibility/factors/apply` - Apply factors to assessment

### Statistics

- `GET /api/credibility/stats` - Get credibility statistics
- `GET /api/credibility/stats/by-source-type` - Statistics by source type
- `GET /api/credibility/low/count` - Count low-credibility sources (for badge)

## Credibility Factors

### Standard Factors

The shard includes these standard credibility factors:

**Source Reliability** (weight: 0.25)
- Track record of accuracy
- History of corrections/retractions
- Peer recognition

**Evidence Quality** (weight: 0.20)
- Primary vs. secondary sources
- Documentation completeness
- Verifiability

**Bias Assessment** (weight: 0.15)
- Political/ideological bias
- Financial conflicts of interest
- Objectivity indicators

**Expertise** (weight: 0.15)
- Subject matter expertise
- Professional credentials
- Domain authority

**Timeliness** (weight: 0.10)
- Recency of information
- Update frequency
- Temporal relevance

**Independence** (weight: 0.10)
- Editorial independence
- Funding transparency
- Organizational autonomy

**Transparency** (weight: 0.05)
- Source disclosure
- Methodology transparency
- Correction policies

### Custom Factors

Create domain-specific factors via API:

```python
POST /api/credibility/factors
{
  "factor_type": "academic_rigor",
  "weight": 0.20,
  "description": "Peer review and citation metrics"
}
```

## Data Models

### CredibilityAssessment

```python
{
  "id": str,
  "source_type": SourceType,  # DOCUMENT, ENTITY, WEBSITE, etc.
  "source_id": str,
  "score": int,  # 0-100
  "confidence": float,  # 0.0-1.0
  "factors": [CredibilityFactor],
  "assessed_by": AssessmentMethod,  # MANUAL, AUTOMATED, HYBRID
  "assessor_id": str,
  "notes": str,
  "metadata": dict,
  "created_at": datetime,
  "updated_at": datetime
}
```

### CredibilityFactor

```python
{
  "factor_type": str,
  "weight": float,  # 0.0-1.0
  "score": int,  # 0-100
  "notes": str
}
```

### SourceType Enum

- `DOCUMENT` - Document credibility
- `ENTITY` - Entity reliability
- `WEBSITE` - Website trustworthiness
- `PUBLICATION` - Publication reputation
- `PERSON` - Individual credibility
- `ORGANIZATION` - Organizational reliability

### AssessmentMethod Enum

- `MANUAL` - Human analyst assessment
- `AUTOMATED` - LLM-generated assessment
- `HYBRID` - Combined human + AI assessment

## Usage Examples

### Create Manual Assessment

```python
POST /api/credibility/
{
  "source_type": "DOCUMENT",
  "source_id": "doc-123",
  "score": 75,
  "confidence": 0.9,
  "factors": [
    {
      "factor_type": "source_reliability",
      "weight": 0.25,
      "score": 80,
      "notes": "Well-established publication"
    },
    {
      "factor_type": "evidence_quality",
      "weight": 0.20,
      "score": 70,
      "notes": "Primary source with citations"
    }
  ],
  "assessed_by": "MANUAL",
  "assessor_id": "analyst-1",
  "notes": "Reputable source with strong track record"
}
```

### Get Source Credibility

```python
GET /api/credibility/source/DOCUMENT/doc-123
# Returns aggregate score and all assessments
```

### Calculate Automated Assessment

```python
POST /api/credibility/calculate
{
  "source_type": "WEBSITE",
  "source_id": "site-456",
  "use_llm": true  # Optional: use LLM for analysis
}
# Returns calculated credibility score
```

### Filter Low-Credibility Sources

```python
GET /api/credibility/?max_score=40
# Returns all assessments with score <= 40
```

## Database Schema

### arkham_credibility.assessments

- `id` - Assessment UUID
- `source_type` - Type of source (enum)
- `source_id` - Reference to source
- `score` - Credibility score (0-100)
- `confidence` - Assessment confidence (0-1)
- `factors` - JSON array of factors
- `assessed_by` - Assessment method (enum)
- `assessor_id` - Who/what performed assessment
- `notes` - Assessment notes
- `metadata` - Additional metadata (JSON)
- `created_at` - Timestamp
- `updated_at` - Timestamp

### Indexes

- `idx_assessments_source` - (source_type, source_id)
- `idx_assessments_score` - (score)
- `idx_assessments_method` - (assessed_by)
- `idx_assessments_created` - (created_at DESC)

## Integration Points

### With Claims Shard

- Verified claims boost source credibility
- Disputed claims reduce source credibility
- Aggregate claim verification rates inform credibility

### With Contradictions Shard

- Contradictions detected reduce credibility of involved sources
- Pattern of contradictions indicates unreliable source

### With Documents Shard

- Document credibility assessments available in document viewer
- Bulk document assessment via worker queues

### With Entities Shard

- Entity credibility assessments for people and organizations
- Entity network credibility propagation

## Configuration

### Score Thresholds

Configure in Frame settings:

```yaml
credibility:
  thresholds:
    unreliable: 20
    low: 40
    medium: 60
    high: 80
    verified: 100
  alert_on_breach: true
  default_confidence: 0.7
```

### Factor Weights

Default weights can be customized per deployment.

## Development

### Run Tests

```bash
pytest tests/
```

### Test Coverage

```bash
pytest --cov=arkham_shard_credibility tests/
```

## Architecture Compliance

This shard fully complies with:
- **shard_manifest_schema_prod.md** v1.0
- **CLAUDE.md** project guidelines
- **ArkhamFrame** v0.1.0+ requirements

### Compliance Checklist

- [x] Valid manifest structure
- [x] Correct navigation category (Analysis) and order (33)
- [x] Event naming: `{shard}.{entity}.{action}`
- [x] Empty `dependencies.shards: []`
- [x] Standard capability names
- [x] Database schema: `arkham_credibility`
- [x] FastAPI router with `/api/credibility` prefix
- [x] Health and count endpoints
- [x] Pydantic models for all data
- [x] Async/await throughout
- [x] Proper error handling
- [x] Full test coverage

## License

Part of the SHATTERED intelligence analysis platform.

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 0.1.0 | 2025-12-26 | Initial production release |

---

*Credibility Shard - Production v0.1.0*
*Part of ArkhamFrame Shard Ecosystem*
