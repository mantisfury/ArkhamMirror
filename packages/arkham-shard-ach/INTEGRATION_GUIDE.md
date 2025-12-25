# ACH Shard Integration Guide

## Installation

From the `arkham-shard-ach` directory:

```bash
pip install -e .
```

Or for production:

```bash
pip install arkham-shard-ach
```

## Auto-Discovery

The shard will be automatically discovered by ArkhamFrame on startup via the entry point defined in `pyproject.toml`:

```toml
[project.entry-points."arkham.shards"]
ach = "arkham_shard_ach:ACHShard"
```

## Frame Integration

### Initialization

When Frame starts, it will:

1. Discover the ACH shard via entry point
2. Instantiate `ACHShard()`
3. Call `await shard.initialize(frame)`
4. Mount the router at `/api/ach`

### Shard Lifecycle

```python
# Frame startup
frame = ArkhamFrame()
await frame.load_shards()  # Discovers and loads ACH shard

# ACH shard receives:
# - frame.get_service("database")
# - frame.get_service("events")
# - frame.get_service("llm")  # optional - enables AI features

# Frame shutdown
await frame.shutdown_shards()  # Calls ACH shard.shutdown()
```

## Using ACH from Other Shards

### Via API (HTTP)

```python
import httpx

async with httpx.AsyncClient(base_url="http://localhost:8100") as client:
    # Create matrix
    response = await client.post(
        "/api/ach/matrix",
        json={
            "title": "Investigation Analysis",
            "description": "Analyzing competing theories",
        }
    )
    matrix = response.json()
    matrix_id = matrix["matrix_id"]

    # Add hypothesis
    await client.post(
        "/api/ach/hypothesis",
        json={
            "matrix_id": matrix_id,
            "title": "Theory 1",
            "description": "First explanation",
        }
    )

    # Add evidence
    await client.post(
        "/api/ach/evidence",
        json={
            "matrix_id": matrix_id,
            "description": "Key observation supporting theory",
            "source": "Field report",
            "evidence_type": "fact",
            "credibility": 0.9,
            "relevance": 0.8,
        }
    )

    # Calculate scores
    scores = await client.post(f"/api/ach/score?matrix_id={matrix_id}")

    # Export to HTML
    export = await client.get(f"/api/ach/export/{matrix_id}?format=html")
```

### Via Frame (Direct)

```python
# From another shard's code
class MyAnalysisShard(ArkhamShard):
    async def initialize(self, frame):
        self.frame = frame

    async def create_analysis(self):
        # Get ACH shard from Frame
        ach_shard = self.frame.get_shard("ach")

        if ach_shard:
            # Use ACH shard directly
            matrix = ach_shard.create_matrix(
                title="My Analysis",
                description="Created by MyAnalysisShard",
            )

            # Work with the matrix
            scores = ach_shard.calculate_scores(matrix.id)

            # Export results
            export = ach_shard.export_matrix(matrix.id, format="json")
```

## Event Subscriptions

Subscribe to ACH events from other shards:

```python
class MyIntegrationShard(ArkhamShard):
    async def initialize(self, frame):
        self.frame = frame
        event_bus = frame.get_service("events")

        if event_bus:
            # Subscribe to ACH events
            event_bus.subscribe("ach.matrix.created", self.on_matrix_created)
            event_bus.subscribe("ach.score.calculated", self.on_scores_updated)
            event_bus.subscribe("ach.hypothesis.added", self.on_hypothesis_added)
            event_bus.subscribe("ach.evidence.added", self.on_evidence_added)

    async def on_matrix_created(self, event: dict):
        matrix_id = event.get("matrix_id")
        title = event.get("title")
        print(f"New ACH matrix created: {title} ({matrix_id})")

    async def on_scores_updated(self, event: dict):
        matrix_id = event.get("matrix_id")
        count = event.get("hypothesis_count")
        print(f"Scores calculated for matrix {matrix_id}: {count} hypotheses")

    async def on_hypothesis_added(self, event: dict):
        matrix_id = event.get("matrix_id")
        title = event.get("title")
        print(f"Hypothesis added: {title}")

    async def on_evidence_added(self, event: dict):
        matrix_id = event.get("matrix_id")
        description = event.get("description")
        print(f"Evidence added: {description[:50]}...")
```

### Available Events

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

## LLM Integration

The ACH shard provides comprehensive AI features when the LLM service is available.

### Check AI Availability

```python
# Via API
response = await client.get("/api/ach/ai/status")
# Returns: {"available": true, "llm_service": true}
```

### AI-Powered Endpoints

All `/api/ach/ai/*` endpoints require the LLM service and return 503 if unavailable.

#### Suggest Hypotheses

```python
response = await client.post("/api/ach/ai/hypotheses", json={
    "focus_question": "Who stole the documents from the secure facility?",
    "context": "Documents went missing between 2pm and 4pm on Tuesday",
    "matrix_id": matrix_id,  # Optional - avoids duplicating existing
})
# Returns: {"suggestions": [{"title": "...", "description": "..."}], "count": 5}
```

#### Suggest Evidence

```python
response = await client.post("/api/ach/ai/evidence", json={
    "matrix_id": matrix_id,
    "focus_question": "What evidence would distinguish between hypotheses?",
})
# Returns: {"suggestions": [{"description": "...", "evidence_type": "fact", "source": "..."}]}
```

#### Suggest Ratings

```python
response = await client.post("/api/ach/ai/ratings", json={
    "matrix_id": matrix_id,
    "evidence_id": evidence_id,
})
# Returns: {"suggestions": [{"hypothesis_id": "...", "rating": "++", "explanation": "..."}]}
```

#### Get Analysis Insights

```python
response = await client.post("/api/ach/ai/insights", json={
    "matrix_id": matrix_id,
})
# Returns: {
#     "insights": "Full analysis text...",
#     "leading_hypothesis": "...",
#     "key_evidence": [...],
#     "evidence_gaps": [...],
#     "cognitive_biases": [...],
#     "recommendations": [...]
# }
```

#### Suggest Milestones

```python
response = await client.post("/api/ach/ai/milestones", json={
    "matrix_id": matrix_id,
})
# Returns: {"suggestions": [{"hypothesis_id": "...", "description": "By X date, Y should occur..."}]}
```

#### Devil's Advocate (Full)

```python
response = await client.post("/api/ach/ai/devils-advocate", json={
    "matrix_id": matrix_id,
    "hypothesis_id": hypothesis_id,  # Optional - defaults to leading
})
# Returns: {
#     "hypothesis_id": "...",
#     "challenge_text": "...",
#     "alternative_interpretation": "...",
#     "weaknesses": [...],
#     "evidence_gaps": [...],
#     "recommended_investigations": [...]
# }
```

#### Extract Evidence from Text

```python
response = await client.post("/api/ach/ai/extract-evidence", json={
    "matrix_id": matrix_id,
    "text": "Long document text to analyze...",
    "document_id": "doc-123",  # Optional
    "max_items": 5,
})
# Returns: {"suggestions": [{"description": "...", "evidence_type": "testimony"}]}
```

### Configure LLM

In Frame's configuration:

```yaml
llm:
  provider: lmstudio
  base_url: http://localhost:1234/v1
  model: qwen/qwen3-vl-8b
  timeout: 30
```

## Shell UI Integration

The ACH shard has custom UI pages in the Shell (`packages/arkham-shard-shell/src/pages/ach/`):

- **ACHListPage** - Lists all matrices with status filtering
- **ACHNewPage** - Step-by-step matrix creation wizard
- **ACHPage** - Full matrix editing with ratings grid

The manifest declares `has_custom_ui: true` so the Shell loads these custom components.

### Navigation

The shard appears in the Shell sidebar under "Analysis" category with:
- Badge showing active matrix count
- Sub-routes for "All Matrices" and "New Analysis"

## Testing

### Unit Tests

```bash
cd packages/arkham-shard-ach
python test_basic.py
```

### Integration Tests

```bash
# Start Frame with ACH shard loaded
cd packages/arkham-frame
python -m uvicorn arkham_frame.main:app --host 127.0.0.1 --port 8100

# In another terminal, test endpoints
curl http://localhost:8100/api/ach/matrices
curl http://localhost:8100/api/ach/ai/status
```

### API Documentation

Once Frame is running, access auto-generated API docs:

```
http://localhost:8100/docs#/ach
```

## Example Workflow

Complete example using ACH shard with AI assistance:

```python
import asyncio
import httpx

async def main():
    async with httpx.AsyncClient(base_url="http://localhost:8100") as client:
        # Create matrix
        response = await client.post("/api/ach/matrix", json={
            "title": "Document Leak Investigation",
            "description": "Who leaked the classified documents?",
        })
        matrix_id = response.json()["matrix_id"]

        # Get AI-suggested hypotheses
        ai_hyp = await client.post("/api/ach/ai/hypotheses", json={
            "focus_question": "Who leaked the classified documents?",
            "context": "Documents were accessed from secure server during business hours",
        })

        # Add suggested hypotheses
        for suggestion in ai_hyp.json()["suggestions"]:
            await client.post("/api/ach/hypothesis", json={
                "matrix_id": matrix_id,
                "title": suggestion["title"],
                "description": suggestion.get("description", ""),
            })

        # Add evidence
        e1 = await client.post("/api/ach/evidence", json={
            "matrix_id": matrix_id,
            "description": "Access logs show activity during business hours",
            "source": "Security audit",
            "credibility": 0.9,
            "relevance": 0.9,
        })
        evidence_id = e1.json()["evidence_id"]

        # Get AI-suggested ratings
        ratings = await client.post("/api/ach/ai/ratings", json={
            "matrix_id": matrix_id,
            "evidence_id": evidence_id,
        })

        # Apply suggested ratings
        for rating in ratings.json()["suggestions"]:
            await client.put("/api/ach/rating", json={
                "matrix_id": matrix_id,
                "evidence_id": evidence_id,
                "hypothesis_id": rating["hypothesis_id"],
                "rating": rating["rating"],
                "reasoning": rating["explanation"],
            })

        # Calculate scores
        scores = await client.post(f"/api/ach/score?matrix_id={matrix_id}")
        print("Scores:", scores.json())

        # Get analysis insights
        insights = await client.post("/api/ach/ai/insights", json={
            "matrix_id": matrix_id,
        })
        print("Insights:", insights.json()["insights"])

        # Export report
        export = await client.get(f"/api/ach/export/{matrix_id}?format=html")
        with open("ach_report.html", "w") as f:
            f.write(export.json()["content"])

        print("Report exported to ach_report.html")

if __name__ == "__main__":
    asyncio.run(main())
```

## Troubleshooting

### Shard Not Loading

```python
# Check if shard was discovered
frame = ArkhamFrame()
print(frame.list_shards())  # Should include 'ach'
```

### AI Features Return 503

```python
# Verify LLM service is available
response = await client.get("/api/ach/ai/status")
if not response.json()["available"]:
    print("LLM service not configured - AI features disabled")
```

### Import Errors

```bash
# Ensure package is installed
pip list | grep arkham-shard-ach

# Reinstall if needed
cd packages/arkham-shard-ach
pip install -e .
```

### Events Not Firing

```python
# Verify EventBus is available
event_bus = frame.get_service("events")
if not event_bus:
    print("EventBus not available - events disabled")
```

## Further Reading

- [README.md](README.md) - User documentation
- [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md) - Technical details
- [CLAUDE.md](../../CLAUDE.md) - Project-wide shard standards
- ACH Methodology: Richards J. Heuer Jr., "Psychology of Intelligence Analysis"
