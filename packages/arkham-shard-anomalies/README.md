# Anomalies Shard

**Anomaly and outlier detection for ArkhamFrame**

Detects anomalies and outliers across multiple dimensions to help analysts identify unusual documents, patterns, and red flags in their corpus.

## Features

### Detection Strategies

1. **Content Anomalies** - Embedding-based outlier detection
   - Documents semantically distant from corpus centroid
   - Configurable distance thresholds
   - Z-score based severity levels

2. **Statistical Anomalies** - Text pattern analysis
   - Unusual word counts
   - Unusual sentence lengths
   - Unusual word frequency distributions
   - Character/word ratio anomalies

3. **Metadata Anomalies** - File property analysis
   - Unusual file sizes
   - Unexpected creation dates
   - Missing expected metadata fields

4. **Temporal Anomalies** - Time reference detection
   - Documents with unexpected date references
   - Temporal outliers in corpus timeline

5. **Structural Anomalies** - Document structure analysis
   - Unusual formatting patterns
   - Unexpected section structures

6. **Red Flags** - Sensitive content detection
   - Money patterns (amounts, currencies)
   - Date patterns (multiple formats)
   - Name patterns (capitalized names)
   - Sensitive keywords (confidential, secret, etc.)

### Analyst Workflow

- **Triage**: Review detected anomalies
- **Status management**: Confirm, dismiss, or mark as false positive
- **Note taking**: Add context and reasoning
- **Pattern detection**: Find recurring anomaly patterns
- **Statistics**: Track detection quality and trends

## Installation

```bash
pip install -e .
```

## Usage

### Via API

```python
import httpx

# Detect anomalies in documents
response = httpx.post("http://localhost:8000/api/anomalies/detect", json={
    "project_id": "proj-123",
    "doc_ids": [],  # Empty = all docs
    "config": {
        "z_score_threshold": 3.0,
        "detect_content": true,
        "detect_red_flags": true
    }
})

# List detected anomalies
response = httpx.get("http://localhost:8000/api/anomalies/list", params={
    "limit": 20,
    "status": "detected",
    "severity": "high"
})

# Update anomaly status
response = httpx.put("http://localhost:8000/api/anomalies/{id}/status", json={
    "status": "confirmed",
    "notes": "Legitimate anomaly - requires investigation",
    "reviewed_by": "analyst-1"
})

# Get statistics
response = httpx.get("http://localhost:8000/api/anomalies/stats")
```

### Via Shard Interface

```python
# Get the shard from Frame
anomalies_shard = frame.get_shard("anomalies")

# Check a specific document
anomalies = await anomalies_shard.check_document(
    doc_id="doc-123",
    text="Document content...",
    metadata={"file_size": 12345, "created_at": "2024-01-01"}
)

# Get anomalies for a document
anomalies = await anomalies_shard.get_anomalies_for_document("doc-123")

# Get statistics
stats = await anomalies_shard.get_statistics()
```

## API Endpoints

### Detection

- `POST /api/anomalies/detect` - Run anomaly detection on corpus
- `POST /api/anomalies/document/{doc_id}` - Check specific document

### Retrieval

- `GET /api/anomalies/list` - List anomalies (paginated, filtered)
- `GET /api/anomalies/{id}` - Get specific anomaly
- `GET /api/anomalies/outliers` - Get statistical outliers

### Management

- `PUT /api/anomalies/{id}/status` - Update status
- `POST /api/anomalies/{id}/notes` - Add analyst note

### Analysis

- `POST /api/anomalies/patterns` - Detect anomaly patterns
- `GET /api/anomalies/stats` - Get statistics

## Configuration

### Detection Config

```python
{
    "z_score_threshold": 3.0,          # Standard deviations for outlier
    "min_cluster_distance": 0.7,       # Cosine distance threshold

    # Detection toggles
    "detect_content": true,
    "detect_metadata": true,
    "detect_temporal": true,
    "detect_structural": true,
    "detect_statistical": true,
    "detect_red_flags": true,

    # Red flag patterns
    "money_patterns": true,
    "date_patterns": true,
    "name_patterns": true,
    "sensitive_keywords": true,

    # Processing
    "batch_size": 100,
    "min_confidence": 0.5
}
```

## Dependencies

### Required Frame Services
- **database** - DatabaseService for storing anomalies (schema: arkham_anomalies)
- **vectors** - VectorService for vector-based outlier detection
- **events** - EventBus for pub/sub communication

### Optional Frame Services
- **llm** - LLMService for enhanced anomaly explanation

## Events

### Published Events

- `anomalies.anomaly.detected` - Anomalies found in document
- `anomalies.anomaly.confirmed` - Analyst confirmed anomaly
- `anomalies.anomaly.dismissed` - Analyst dismissed anomaly
- `anomalies.pattern.found` - Pattern detected across anomalies
- `anomalies.stats.updated` - Statistics recalculated

### Subscribed Events

- `embed.embedding.created` - Triggers content anomaly detection when embeddings are created
- `document.processed` - Triggers metadata/statistical detection when documents are processed

## Data Models

### Anomaly

```python
{
    "id": "anom-123",
    "doc_id": "doc-456",
    "anomaly_type": "content",  # content, metadata, temporal, structural, statistical, red_flag
    "status": "detected",        # detected, confirmed, dismissed, false_positive
    "score": 4.2,               # Anomaly score
    "severity": "high",         # critical, high, medium, low
    "confidence": 0.85,         # Detection confidence
    "explanation": "Document is semantically distant from corpus",
    "details": {...},           # Technical details
    "detected_at": "2024-01-01T12:00:00Z",
    "reviewed_by": "analyst-1",
    "notes": "Requires investigation"
}
```

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black arkham_shard_anomalies/

# Type checking
mypy arkham_shard_anomalies/
```

## License

Same as ArkhamFrame (MIT)
