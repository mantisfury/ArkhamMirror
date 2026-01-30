# arkham-shard-pii

PII (Personally Identifiable Information) detection and analysis shard for SHATTERED. Single source for PII discovery: when Presidio is configured it is used; otherwise an improved regex/heuristic fallback runs.

## How it works

- **Ingest integration**: During document registration, the ingest shard calls this shard (when installed) to analyze all metadata strings. Results are stored in document metadata: `pii_detected`, `pii_types`, `pii_entities`, `pii_count`, and optionally `pii_backend` (`presidio` or `fallback`).
- **Other shards**: For **new** data analysis, call this shard’s `analyze_text()` or `analyze_metadata()`. For **existing** documents, read PII from the document metadata table (or `documents.metadata`) where ingest has already stored the result.
- **Backends**:
  - **Presidio** (preferred): Microsoft Presidio Analyzer over HTTP. Configure with `PII_PRESIDIO_URL` or frame config `pii.presidio_url`.
  - **Fallback**: Built-in regex/heuristic detector (email, phone, SSN, credit card, etc.) when Presidio is not configured or unreachable.

## Installation

```bash
cd packages/arkham-shard-pii && pip install -e .
```

## Presidio (optional)

To use Presidio Analyzer, run it as a service and point the PII shard at it.

### Run Presidio with Docker

Presidio provides Analyzer (and optionally Anonymizer) images. For analysis only:

```bash
docker run -d --name presidio-analyzer -p 3000:3000 mcr.microsoft.com/presidio-analyzer
```

Then set the URL for the frame (e.g. in `.env`):

```bash
PII_PRESIDIO_URL=http://localhost:3000
```

If the frame runs inside Docker, use the host’s address (e.g. `http://host.docker.internal:3000` on Docker Desktop) or the service name if you run Presidio in the same compose network.

### Docker Compose example

```yaml
services:
  presidio-analyzer:
      image: mcr.microsoft.com/presidio-analyzer:latest
      ports:
        - "3000:3000"
      environment:
        - LOG_LEVEL=WARNING
      restart: unless-stopped
      healthcheck:
        test: ["CMD", "curl", "-f", "http://localhost:3000/health"]
        interval: 30s
        timeout: 10s
        retries: 3
        start_period: 40s
```

In your app’s `.env`:

```bash
PII_PRESIDIO_URL=http://presidio-analyzer:3000
```

### Health

The PII shard checks Presidio at startup via a health request. If the URL is set but the service is down, the shard logs a warning and uses the fallback detector.

## API

- **Analyze text**: `POST /api/pii/analyze` (or use the shard’s `analyze_text(text, language, score_threshold)` when calling from another shard).
- **Analyze metadata**: Used internally by ingest; other shards can call `pii_shard.analyze_metadata(metadata_dict)` for ad-hoc analysis.

## Configuration

| Option | Source | Description |
|--------|--------|-------------|
| `PII_PRESIDIO_URL` | env | Base URL of Presidio Analyzer (e.g. `http://localhost:3000`) |
| `pii.presidio_url` | frame config | Same, from config file |
