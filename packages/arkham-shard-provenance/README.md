# arkham-shard-provenance

> Evidence chain tracking and data lineage for legal and journalism analysis

**Version:** 0.1.0
**Category:** Analysis
**Frame Requirement:** >=0.1.0

## Overview

The Provenance shard tracks evidence chains and data lineage throughout the analysis workflow. It provides audit trails for legal and journalism use cases, tracks artifact transformations, maintains chain-of-custody documentation, and visualizes data lineage graphs.

### Key Capabilities

1. **Provenance Tracking** - Track source and origin of all data
2. **Evidence Chains** - Build and verify chains of evidence
3. **Audit Trail** - Complete audit log of all operations
4. **Lineage Visualization** - Visualize upstream/downstream dependencies
5. **Data Export** - Export provenance records and audit trails

## Features

### Evidence Chains
- Create chains linking evidence artifacts
- Track source-to-target relationships
- Confidence scoring for links
- Chain verification and integrity checks

### Chain Status
- `active` - Chain is active and in use
- `verified` - Chain has been verified
- `archived` - Chain is archived

### Link Types
- `derived_from` - Target derived from source
- `references` - Target references source
- `supports` - Target supports source
- `contradicts` - Target contradicts source
- `quotes` - Target quotes source
- `transforms` - Target is transformation of source

### Provenance Records
- Track entity origin and source
- Record import metadata
- Track transformations applied
- Maintain audit history

### Lineage Graphs
- Upstream dependency tracking
- Downstream impact analysis
- Graph visualization
- Configurable depth traversal

### Artifacts
- Track documents, entities, claims, and other objects
- Content hashing for integrity
- Entity-to-artifact mapping
- Type-based filtering

### Audit Trail
- All chain operations logged
- User attribution
- Timestamp tracking
- Exportable audit reports

## Installation

```bash
pip install -e packages/arkham-shard-provenance
```

The shard auto-registers via entry point on Frame startup.

## API Endpoints

### Health and Count

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/provenance/health` | Health check |
| GET | `/api/provenance/count` | Total counts (badge) |

### Evidence Chains

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/provenance/chains` | List chains |
| POST | `/api/provenance/chains` | Create chain |
| GET | `/api/provenance/chains/{id}` | Get chain |
| PUT | `/api/provenance/chains/{id}` | Update chain |
| DELETE | `/api/provenance/chains/{id}` | Delete chain |
| POST | `/api/provenance/chains/{id}/verify` | Verify chain integrity |

### Chain Links

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/provenance/chains/{id}/links` | List chain links |
| POST | `/api/provenance/chains/{id}/links` | Add link to chain |
| DELETE | `/api/provenance/links/{id}` | Remove link |
| PUT | `/api/provenance/links/{id}/verify` | Verify link |

### Lineage

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/provenance/lineage/{artifact_id}` | Get lineage graph |
| GET | `/api/provenance/lineage/{artifact_id}/upstream` | Get upstream artifacts |
| GET | `/api/provenance/lineage/{artifact_id}/downstream` | Get downstream artifacts |

### Artifacts

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/provenance/artifacts` | List artifacts |
| POST | `/api/provenance/artifacts` | Create artifact |
| GET | `/api/provenance/artifacts/{id}` | Get artifact |
| GET | `/api/provenance/artifacts/entity/{entity_id}` | Get by entity |

### Provenance Records

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/provenance/` | List records |
| GET | `/api/provenance/{id}` | Get record |
| GET | `/api/provenance/entity/{type}/{id}` | Get entity record |
| GET | `/api/provenance/{id}/transformations` | Get transformations |
| GET | `/api/provenance/{id}/audit` | Get audit trail |

### Audit

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/provenance/audit` | List audit records |
| GET | `/api/provenance/audit/{chain_id}` | Get chain audit trail |
| POST | `/api/provenance/audit/export` | Export audit trail |

### AI Analysis

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/provenance/ai/junior-analyst` | AI analysis (streaming) |

## API Examples

### Create Evidence Chain

```json
POST /api/provenance/chains
{
  "title": "Document Source Chain",
  "description": "Chain tracking source documents for investigation report",
  "project_id": "proj_123",
  "created_by": "analyst_john"
}
```

Response:
```json
{
  "id": "chain_abc123",
  "title": "Document Source Chain",
  "description": "Chain tracking source documents for investigation report",
  "chain_type": "evidence",
  "status": "active",
  "root_artifact_id": null,
  "created_at": "2024-12-15T10:30:00Z",
  "link_count": 0
}
```

### Add Link to Chain

```json
POST /api/provenance/chains/{chain_id}/links
{
  "source_artifact_id": "art_doc_original",
  "target_artifact_id": "art_doc_processed",
  "link_type": "derived_from",
  "confidence": 1.0,
  "metadata": {"transformation": "OCR extraction"}
}
```

### Verify Link

```json
PUT /api/provenance/links/{link_id}/verify
{
  "verified_by": "analyst_john",
  "notes": "Verified source document authenticity"
}
```

### Get Lineage Graph

```bash
GET /api/provenance/lineage/{artifact_id}?direction=both&max_depth=5
```

Response:
```json
{
  "nodes": [
    {
      "id": "art_123",
      "title": "Original Document",
      "type": "document",
      "is_focus": true,
      "depth": 0
    },
    {
      "id": "art_456",
      "title": "Processed Text",
      "type": "document",
      "is_focus": false,
      "depth": 1
    }
  ],
  "edges": [
    {
      "id": "link_abc",
      "source": "art_123",
      "target": "art_456",
      "link_type": "derived_from",
      "confidence": 1.0
    }
  ],
  "root": "art_123",
  "ancestor_count": 0,
  "descendant_count": 1
}
```

### Create Artifact

```json
POST /api/provenance/artifacts
{
  "artifact_type": "document",
  "entity_id": "doc_abc123",
  "entity_table": "arkham_documents.documents",
  "title": "Investigation Report v1",
  "hash": "sha256:abc123...",
  "metadata": {"version": 1}
}
```

### Verify Chain Integrity

```bash
POST /api/provenance/chains/{chain_id}/verify?verified_by=analyst_john
```

Response:
```json
{
  "chain_id": "chain_abc123",
  "is_valid": true,
  "issues": [],
  "link_count": 5,
  "verified_links": 5,
  "broken_links": 0,
  "verified_at": "2024-12-15T11:00:00Z",
  "verified_by": "analyst_john"
}
```

### List Chains with Filtering

```bash
GET /api/provenance/chains?page=1&page_size=20&project_id=proj_123&status=active
```

### Get Entity Provenance

```bash
GET /api/provenance/entity/document/doc_abc123
```

Response:
```json
{
  "id": "prov_xyz",
  "entity_type": "document",
  "entity_id": "doc_abc123",
  "source_type": "upload",
  "source_url": "file://original.pdf",
  "imported_at": "2024-12-15T09:00:00Z",
  "imported_by": "analyst_john",
  "metadata": {"original_filename": "report.pdf"}
}
```

### Get Transformation History

```bash
GET /api/provenance/{record_id}/transformations
```

Response:
```json
[
  {
    "id": "trans_1",
    "record_id": "prov_xyz",
    "transformation_type": "ocr",
    "input_hash": "sha256:aaa...",
    "output_hash": "sha256:bbb...",
    "transformed_at": "2024-12-15T09:15:00Z",
    "transformer": "paddleocr",
    "parameters": {"language": "en"}
  }
]
```

### Export Audit Trail

```bash
POST /api/provenance/audit/export?chain_id=chain_abc&format=json
```

## Events

### Published Events

| Event | Description |
|-------|-------------|
| `provenance.chain.created` | Chain created |
| `provenance.chain.updated` | Chain updated |
| `provenance.chain.deleted` | Chain deleted |
| `provenance.link.added` | Link added to chain |
| `provenance.link.removed` | Link removed |
| `provenance.link.verified` | Link verified |
| `provenance.audit.generated` | Audit report generated |
| `provenance.export.completed` | Export completed |

### Subscribed Events

| Event | Handler |
|-------|---------|
| `*.*.created` | Track all creation events |
| `*.*.completed` | Track all completion events |
| `document.processed` | Track document processing chain |

## UI Routes

| Route | Description |
|-------|-------------|
| `/provenance` | Main provenance view |
| `/provenance/chains` | Evidence chains |
| `/provenance/audit` | Audit trail |
| `/provenance/lineage` | Data lineage |

## Tech Stack

- **PostgreSQL 14+** - Single database for all persistence
- **PostgreSQL job queue** - Background jobs using SKIP LOCKED pattern

## Dependencies

### Required Services
- **database** - Chain and lineage persistence (PostgreSQL)
- **events** - Track all creation/completion events

### Optional Services
- **storage** - For audit report exports

## URL State

| Parameter | Description |
|-----------|-------------|
| `chainId` | Active evidence chain ID |
| `artifactId` | Selected artifact ID |
| `tab` | Active tab (chain, lineage, audit) |
| `view` | View mode (tree, graph, list) |

### Local Storage Keys
- `graph_layout` - Graph layout preference
- `show_metadata` - Metadata visibility
- `expand_level` - Tree expansion level

## Use Cases

### Legal Discovery
- Track document chain of custody
- Verify evidence integrity
- Generate audit reports for court

### Journalism
- Source attribution tracking
- Verification chain documentation
- Fact-checking provenance

### Intelligence Analysis
- Track analysis derivations
- Document source reliability
- Maintain analytical trail

## Lineage Direction

| Direction | Description |
|-----------|-------------|
| `upstream` | Trace sources and origins |
| `downstream` | Trace derivatives and impacts |
| `both` | Trace in both directions |

## Development

```bash
# Run tests
pytest packages/arkham-shard-provenance/tests/

# Type checking
mypy packages/arkham-shard-provenance/
```

## License

MIT
