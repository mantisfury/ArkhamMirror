# Summary Shard

Auto-summarization of documents, collections, and analysis results using LLM.

## Overview

The Summary Shard provides comprehensive auto-summarization capabilities for the SHATTERED architecture. It can generate summaries of varying types and lengths, with LLM-powered generation and graceful degradation to extractive summarization when LLM is unavailable.

**Category**: Analysis
**Order**: 39
**Version**: 0.1.0
**Status**: Production-ready

## Features

### Core Capabilities

- **Multiple Summary Types**:
  - Brief: 1-2 sentence overview
  - Detailed: Comprehensive multi-paragraph summary
  - Executive: Key findings and recommendations
  - Bullet Points: Structured key points
  - Abstract: Academic-style abstract

- **Flexible Length Control**:
  - Very Short (~50 words)
  - Short (~100 words)
  - Medium (~250 words)
  - Long (~500 words)
  - Very Long (~1000 words)

- **Multi-Source Summarization**:
  - Single documents
  - Document collections
  - Entity-related documents
  - Projects
  - Claim sets
  - Timelines
  - Analysis results

- **Advanced Features**:
  - Focus areas (emphasize specific topics)
  - Topic exclusion
  - Key point extraction
  - Auto-generated titles
  - Quality metrics (confidence, completeness)
  - Batch processing
  - Event-driven auto-summarization

### LLM Integration

The shard integrates with the Frame's LLM service for AI-powered summarization:

- Uses LLM when available for high-quality abstractive summaries
- Gracefully degrades to extractive summarization when LLM unavailable
- Supports custom prompts and templates
- Configurable model parameters

### Graceful Degradation

When LLM service is unavailable:

- Automatically falls back to extractive summarization
- Uses sentence extraction heuristics
- Still provides key points and titles
- Lower confidence scores to indicate fallback mode
- All API endpoints remain functional

## Installation

```bash
cd packages/arkham-shard-summary
pip install -e .
```

The shard will be auto-discovered by the Frame on next startup.

## API Endpoints

### Health & Capabilities

```http
GET /api/summary/health
```

Returns service status and LLM availability.

```http
GET /api/summary/capabilities
```

Shows available features based on service availability.

```http
GET /api/summary/types
```

Lists available summary types with descriptions.

### Summary Management

```http
GET /api/summary/
```

List all summaries with pagination and filtering.

**Query Parameters**:
- `page` (default: 1): Page number
- `page_size` (default: 20, max: 100): Items per page
- `summary_type`: Filter by summary type
- `source_type`: Filter by source type
- `source_id`: Filter by source ID
- `status`: Filter by status
- `q`: Search in summary content

**Response**:
```json
{
  "items": [...],
  "total": 42,
  "page": 1,
  "page_size": 20
}
```

```http
POST /api/summary/
```

Generate a new summary.

**Request Body**:
```json
{
  "source_type": "document",
  "source_ids": ["doc-123"],
  "summary_type": "detailed",
  "target_length": "medium",
  "focus_areas": ["key findings", "methodology"],
  "exclude_topics": ["acknowledgments"],
  "include_key_points": true,
  "include_title": true,
  "tags": ["important"]
}
```

**Response**:
```json
{
  "summary_id": "sum-456",
  "status": "completed",
  "content": "The document discusses...",
  "key_points": ["Point 1", "Point 2"],
  "title": "Document Summary",
  "token_count": 250,
  "word_count": 200,
  "processing_time_ms": 1234.5,
  "confidence": 1.0
}
```

```http
GET /api/summary/{summary_id}
```

Get a specific summary by ID.

```http
DELETE /api/summary/{summary_id}
```

Delete a summary.

### Document Summaries

```http
GET /api/summary/document/{doc_id}
```

Get or generate summary for a specific document.

**Query Parameters**:
- `summary_type` (default: "detailed"): Type of summary
- `regenerate` (default: false): Force regeneration

**Behavior**:
- Returns existing summary if found
- Generates new summary if not found or `regenerate=true`

### Batch Processing

```http
POST /api/summary/batch
```

Generate summaries for multiple sources in batch.

**Request Body**:
```json
{
  "requests": [
    {
      "source_type": "document",
      "source_ids": ["doc-1"],
      "summary_type": "brief"
    },
    {
      "source_type": "document",
      "source_ids": ["doc-2"],
      "summary_type": "detailed"
    }
  ],
  "parallel": false,
  "stop_on_error": false
}
```

**Response**:
```json
{
  "total": 2,
  "successful": 2,
  "failed": 0,
  "summaries": [...],
  "errors": [],
  "total_processing_time_ms": 2500
}
```

### Statistics

```http
GET /api/summary/count
```

Get total summary count (for navigation badge).

```http
GET /api/summary/stats
```

Get aggregate statistics about all summaries.

**Response**:
```json
{
  "total_summaries": 42,
  "by_type": {
    "detailed": 20,
    "brief": 15,
    "executive": 7
  },
  "by_source_type": {
    "document": 30,
    "documents": 10,
    "project": 2
  },
  "by_status": {
    "completed": 40,
    "pending": 2
  },
  "avg_confidence": 0.95,
  "avg_word_count": 234.5,
  "avg_processing_time_ms": 1234.5,
  "generated_last_24h": 10
}
```

## Events

### Published Events

- `summary.summary.created`: New summary generated
- `summary.summary.updated`: Summary regenerated
- `summary.summary.deleted`: Summary removed
- `summary.batch.started`: Batch summarization started
- `summary.batch.completed`: Batch summarization finished
- `summary.batch.failed`: Batch summarization failed

**Event Payload Example**:
```python
{
  "summary_id": "sum-123",
  "source_type": "document",
  "source_ids": ["doc-456"],
  "summary_type": "detailed",
  "word_count": 250
}
```

### Subscribed Events

- `document.processed`: Auto-summarize newly processed documents
- `documents.document.created`: Auto-summarize newly created documents

## Usage Examples

### Python API

```python
from arkham_shard_summary import SummaryRequest, SummaryType, SourceType, SummaryLength

# Get shard instance from frame
summary_shard = frame.get_shard("summary")

# Generate a summary
request = SummaryRequest(
    source_type=SourceType.DOCUMENT,
    source_ids=["doc-123"],
    summary_type=SummaryType.DETAILED,
    target_length=SummaryLength.MEDIUM,
    focus_areas=["key findings"],
    include_key_points=True,
)

result = await summary_shard.generate_summary(request)
print(f"Summary: {result.content}")
print(f"Key Points: {result.key_points}")

# List summaries for a document
filter = SummaryFilter(
    source_type=SourceType.DOCUMENT,
    source_id="doc-123",
)
summaries = await summary_shard.list_summaries(filter)

# Batch summarization
batch_request = BatchSummaryRequest(
    requests=[request1, request2, request3],
    parallel=True,
)
batch_result = await summary_shard.generate_batch_summaries(batch_request)
print(f"Successful: {batch_result.successful}/{batch_result.total}")
```

### REST API

```bash
# Generate a brief summary
curl -X POST http://localhost:8100/api/summary/ \
  -H "Content-Type: application/json" \
  -d '{
    "source_type": "document",
    "source_ids": ["doc-123"],
    "summary_type": "brief",
    "target_length": "short"
  }'

# Get summary for a document
curl http://localhost:8100/api/summary/document/doc-123?summary_type=detailed

# List all detailed summaries
curl "http://localhost:8100/api/summary/?summary_type=detailed&page=1&page_size=20"

# Get statistics
curl http://localhost:8100/api/summary/stats
```

## Data Models

### Summary

Main summary object stored in the system.

**Fields**:
- `id`: Unique identifier
- `summary_type`: Type of summary (brief, detailed, executive, etc.)
- `status`: Status (pending, generating, completed, failed, stale)
- `source_type`: Type of source (document, documents, entity, etc.)
- `source_ids`: IDs of source items
- `content`: The summary text
- `key_points`: Extracted key points
- `title`: Auto-generated title
- `model_used`: LLM model used (or "extractive")
- `token_count`: Approximate token count
- `word_count`: Word count
- `target_length`: Target length (very_short, short, medium, long, very_long)
- `confidence`: Confidence in summary (0-1)
- `completeness`: Coverage of source (0-1)
- `focus_areas`: Specific topics focused on
- `exclude_topics`: Topics excluded
- `processing_time_ms`: Time to generate
- `created_at`, `updated_at`: Timestamps
- `metadata`: Additional metadata
- `tags`: User-defined tags

### SummaryType Enum

- `BRIEF`: Short 1-2 sentence summary
- `DETAILED`: Comprehensive multi-paragraph summary
- `EXECUTIVE`: Executive summary with key findings
- `BULLET_POINTS`: Key points as bullet list
- `ABSTRACT`: Academic-style abstract

### SourceType Enum

- `DOCUMENT`: Single document
- `DOCUMENTS`: Collection of documents
- `ENTITY`: Entity with related documents
- `PROJECT`: Entire project
- `CLAIM_SET`: Set of related claims
- `TIMELINE`: Timeline of events
- `ANALYSIS`: Analysis result (ACH, etc.)

### SummaryLength Enum

- `VERY_SHORT`: ~50 words
- `SHORT`: ~100 words
- `MEDIUM`: ~250 words
- `LONG`: ~500 words
- `VERY_LONG`: ~1000 words

## Configuration

The shard supports configuration through environment variables or Frame config:

```yaml
# config.yaml
summary:
  auto_summarize: true          # Auto-summarize new documents
  default_type: detailed         # Default summary type
  default_length: medium         # Default target length
  batch_size: 10                 # Batch processing size
  enable_cache: true             # Cache generated summaries
```

## Dependencies

### Required Services

- `database`: Stores summaries and metadata
- `events`: Event publishing and subscription

### Optional Services

- `llm`: LLM service for AI-powered summarization (highly recommended)
- `workers`: Background job processing for batch operations

### Shard Dependencies

**None** - This shard has no dependencies on other shards, following the SHATTERED architecture principle.

## Performance

### Typical Processing Times

- Brief summary (LLM): ~500-1000ms
- Detailed summary (LLM): ~1500-3000ms
- Extractive summary: ~100-300ms
- Batch processing: Parallel for speed

### Optimization Tips

1. Use appropriate summary type and length
2. Enable batch processing for multiple summaries
3. Use extractive mode when speed > quality
4. Cache summaries and regenerate only when source changes
5. Use focus areas to reduce processing scope

## Troubleshooting

### LLM Service Unavailable

**Symptom**: Summaries are shorter and lower confidence

**Solution**: The shard automatically falls back to extractive summarization. Check:
- LLM service is running
- LLM model is loaded
- Frame LLM service configuration

### Poor Summary Quality

**Symptom**: Summary doesn't capture key points

**Solutions**:
- Use `focus_areas` to emphasize important topics
- Try different summary types
- Increase target length
- Verify LLM service is available (extractive mode has lower quality)

### Batch Processing Slow

**Symptom**: Batch operations take too long

**Solutions**:
- Enable parallel processing in batch request
- Use workers service for background processing
- Reduce batch size
- Use brief summaries instead of detailed

## Development

### Running Tests

```bash
cd packages/arkham-shard-summary
pytest tests/
```

### Test Coverage

- Unit tests for models
- Shard initialization tests
- API endpoint tests
- LLM integration tests (with mocks)
- Graceful degradation tests

## Compliance

This shard is fully compliant with:
- Shard Manifest Schema Production v1.0
- ArkhamFrame v0.1.0 interface
- Event naming conventions
- Navigation category standards

## License

Part of the SHATTERED project.

## See Also

- [Shard Manifest Schema](../../../docs/shard_manifest_schema_prod.md)
- [New Shards Plan](../../../docs/new_shards_plan.md)
- [ArkhamFrame Documentation](../../arkham-frame/README.md)
- [Claims Shard](../arkham-shard-claims/README.md) - Can summarize claim sets
- [Reports Shard](../arkham-shard-reports/README.md) - Uses summaries in reports
