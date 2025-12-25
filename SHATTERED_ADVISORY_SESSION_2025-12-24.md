# SHATTERED Architecture Advisory
## Session Date: 2025-12-24

This document consolidates observations, recommendations, and open questions from an architectural review session. Nothing here is a decision—these are options and considerations for future deliberation.

---

## 1. Overall Assessment

The SHATTERED architecture is coherent and well-documented. The three core specs (Frame, Shell, Manifest) form a complete contract. The system demonstrates a consistent pattern applied across domains:

```
INGEST → EXTRACT → ORGANIZE → ANALYZE → ACT
```

This pattern holds across all 67 proposed bundles and 58 shards. The architecture is deliberately simple—no route collision detection, no event delivery guarantees, no manifest schema validation at runtime. This is appropriate for a local-first, single-developer system.

**Key Strengths:**
- Frame is a clean orchestrator that doesn't overreach
- Shell is non-authoritative (presentation only, no business logic)
- Shard isolation is enforced structurally (own DB schema, own API prefix, no direct imports)
- Graceful degradation is built in (partial shard loading, service unavailability handling)

---

## 2. GPT's Critique: What Was Valid, What Was Already Solved

### GPT's Valid Concerns (Worth Considering)

| Concern | Status |
|---------|--------|
| UI Shell needs to throttle complexity | Valid—but your shell spec already makes it non-authoritative. The question is whether shards need visibility gating based on workflow phase |
| Evidence maturity gating | Valid for legal/medical/journalism bundles. Not currently formalized |
| Cognitive load budgeting | Worth considering: max N actions per screen, progressive disclosure |
| Domain banners for regulated contexts | Lightweight way to prime users ("LEGAL RESEARCH MODE") without adding liability |

### GPT's Concerns Already Addressed

| Concern | How It's Solved |
|---------|-----------------|
| Shard purity / no meta-shards | Manifest schema enforces this—shards declare dependencies, don't orchestrate |
| UI shell as constraint engine | Solved differently—shell is dumb, Frame + Manifest own constraints |
| Ontology explosion | Bundles are suggestions, not restrictions; users self-select complexity |

### Where GPT Missed the Mark

GPT suggested making the UI shell a "constraint engine" and "governor." Your architecture correctly puts governance in the Frame and contracts in the Manifest. The shell stays dumb. This is cleaner.

---

## 3. Frame Hardening Recommendations

### 3.1 Event Delivery Tracking (Recommended)

**Problem:** EventBus is best-effort with silent failures. When something breaks, you can't see which callback failed on which event.

**Lightweight Solution (~20 lines):**

```python
class EventBus:
    def __init__(self):
        self.subscribers = defaultdict(list)
        self.history = deque(maxlen=1000)
        self.delivery_failures = deque(maxlen=500)  # NEW
        self.sequence = 0
    
    async def emit(self, event_type: str, payload: dict, source: str):
        event = {
            "seq": self.sequence,
            "type": event_type,
            "payload": payload,
            "source": source,
            "timestamp": datetime.utcnow().isoformat(),
            "delivered_to": [],
            "failed_to": [],
        }
        self.sequence += 1
        
        for pattern, callbacks in self.subscribers.items():
            if fnmatch(event_type, pattern):
                for callback in callbacks:
                    try:
                        await callback(event)
                        event["delivered_to"].append(f"{pattern}:{callback.__qualname__}")
                    except Exception as e:
                        failure = {
                            "event_seq": event["seq"],
                            "event_type": event_type,
                            "pattern": pattern,
                            "callback": callback.__qualname__,
                            "error": str(e),
                            "timestamp": datetime.utcnow().isoformat(),
                        }
                        event["failed_to"].append(failure)
                        self.delivery_failures.append(failure)
                        logger.error(f"Event delivery failed: {event_type} -> {callback.__qualname__}: {e}")
        
        self.history.append(event)
        return event
```

**Add endpoint:**
```python
@router.get("/api/frame/events/failures")
async def get_delivery_failures(limit: int = 100):
    return list(event_bus.delivery_failures)[-limit:]
```

**Cost:** Minimal memory overhead, no runtime performance impact.
**Benefit:** When something breaks, you see exactly what failed.

---

### 3.2 Route Collision Detection (Recommended)

**Problem:** If multiple shards register the same route, first wins silently. You won't know until you're debugging why an endpoint doesn't work.

**Solution (startup-only, zero runtime cost):**

```python
def validate_routes(shards: list[ArkhamShard]) -> list[str]:
    """Call during startup, after discovery, before mounting."""
    all_routes = []
    warnings = []
    
    for shard in shards:
        router = shard.get_routes()
        if not router:
            continue
        
        for route in router.routes:
            path = getattr(route, 'path', None)
            if not path:
                continue
            
            for existing_shard, existing_path in all_routes:
                if path == existing_path:
                    msg = f"ROUTE COLLISION: '{path}' registered by both '{existing_shard}' and '{shard.name}' - first wins"
                    logger.warning(msg)
                    warnings.append(msg)
            
            all_routes.append((shard.name, path))
    
    return warnings

# In startup sequence:
warnings = validate_routes(loaded_shards)
if warnings:
    logger.warning(f"Startup completed with {len(warnings)} route collision warnings")
```

**Cost:** One pass through routes at startup (milliseconds).
**Benefit:** No more silent collisions. Especially important for swarm-coding where multiple AI agents might accidentally use the same prefix.

**Swarm-coding prompt addition:**
> "Before implementing, verify your API prefix `/api/{shard_name}/` does not conflict with existing shards. Check `/api/shards/` endpoint or SHARDS_AND_BUNDLES.md for reserved names."

---

### 3.3 Redis Graceful Degradation (Consider)

**Question:** Should the platform function when Redis is down?

**Context:** Redis powers the WorkerService job queues. If Redis is unavailable, background jobs can't be enqueued.

**Option A: Redis Required (Current Implicit Behavior)**
- Simpler mental model
- Workers just fail if Redis is down
- Appropriate if Redis is always running in your setup

**Option B: Sync Fallback with Loud Warnings**
```python
class WorkerService:
    async def enqueue(self, pool: str, job_id: str, payload: dict, priority: int = 5):
        if not self.is_available():
            logger.warning(f"Redis unavailable - executing {job_id} synchronously")
            return await self._execute_sync(pool, job_id, payload)
        # Normal Redis enqueue...
    
    async def _execute_sync(self, pool: str, job_id: str, payload: dict):
        """Fallback: run the job in the current process."""
        # Slower but works
        ...
```

**Trade-off:** 
- Sync fallback keeps the system running but slower
- May cause request timeouts if jobs are heavy
- Good for resilience, but adds code paths to test

**Decision needed:** Is Redis being up a hard requirement for your deployment environment?

---

### 3.4 Service Dependency Validation (Optional)

**Current behavior:** Shards declare `dependencies.services` in manifest, but Frame doesn't validate against actual availability. A shard requiring `llm` will load, then fail at runtime.

**Your stated philosophy:** "If a shard *requires* llm, it should have it baked in or the shard shouldn't exist. Shards should only *require* services provided through the Frame."

**This is a policy decision, not a code change.** The manifest schema already distinguishes:
```yaml
dependencies:
  services: [database, events]    # Required
  optional: [llm, vectors]        # Nice to have
```

**Recommendation:** Document this clearly in shard development guidelines:
- `services`: Must be Frame-provided (database, events, workers, vectors)
- `optional`: May be unavailable; shard must handle gracefully
- LLM is always optional unless shard bundles its own

---

## 4. Provenance Tracking

### The Problem

For legal/medical/journalism bundles, users need to answer: "Where did this claim come from?"

The EventBus is ephemeral (1000 events in memory, lost on restart). This is fine for UI coordination but inadequate for evidence chains.

### Option A: Dedicated Provenance Shard

A shard that:
- Subscribes to relevant events (`claim.extracted`, `evidence.linked`, `contradiction.detected`)
- Writes to persistent storage (its own DB schema)
- Provides query API: "Show me the lineage of this claim"

**Pros:**
- Opt-in (bundles that need it include it, others don't)
- Doesn't bloat Frame or other shards
- Single responsibility

**Cons:**
- Shards that want provenance must emit the right events
- Need to define what events constitute "provenance-worthy"

### Option B: Frame-Level Audit Log

Frame persists all events (or events matching certain patterns) to database.

**Pros:**
- Automatic, no shard opt-in needed
- Complete record

**Cons:**
- Storage grows unbounded
- Most events aren't provenance-relevant
- Bloats Frame responsibility

### Recommendation

Option A (dedicated shard) fits your philosophy better. Provenance is a feature for bundles that care about it, not a universal requirement. Define the event contracts that provenance-relevant shards should emit, then build the provenance shard to consume them.

---

## 5. Ingestion & LLM Bottlenecks

### What You've Already Solved

| Problem | Your Solution |
|---------|---------------|
| Bulk ingest overwhelms system | Batch processing, not mass ingest |
| LLM batching corrupts JSON | Single calls, throw out failures |
| Contradiction detection is slow | Priority queue (high-confidence first) + caching |

These are correct. The "clever" optimizations (bulk everything, batch LLM calls) break in practice.

### Remaining Considerations

**Ingestion backpressure:**
If batching is the model, consider explicit backpressure—don't start batch N+1 until batch N clears the pipeline. This prevents memory bloat and keeps the system responsive.

**LLM call optimization (without batching):**
- **Caching:** If you've compared claim A to claim B, don't do it again
- **Cheap pre-filter:** Use embedding similarity or keyword overlap to skip obvious non-contradictions before LLM
- **Progressive depth:** First pass = fast/cheap, second pass = LLM on candidates only

**Fast path / slow path:**
You mentioned adding a fast path. The pattern:
- **Fast path:** Store raw + basic metadata immediately (user sees progress)
- **Slow path:** Full extraction, entity recognition, embedding—runs in background
- User can work with partially-processed documents while slow path catches up

---

## 6. Shell Considerations

### What the Shell Already Does Right

- Non-authoritative (doesn't make data decisions)
- Manifest-driven (reads shard declarations, doesn't infer)
- Generic UI for simple shards, custom UI escape hatch for complex ones

### Potential Additions (Not Currently Specified)

| Feature | Purpose | Complexity |
|---------|---------|------------|
| Workspace/Profile system | Named, saveable shard visibility configurations | Medium |
| Domain banners | Static "LEGAL RESEARCH MODE" headers for regulated contexts | Low |
| Cognitive load limits | Max N primary actions per screen | Low (CSS/layout) |
| Evidence maturity indicators | Visual cues for "raw vs verified" data | Medium |

These are UX enhancements, not architectural changes. Implement if/when user testing reveals confusion.

---

## 7. Swarm-Coding Preparation

### What's Ready

- Frame spec is complete
- Shell spec is complete  
- Manifest schema is complete
- Shard isolation is enforced structurally

### Recommended Additions Before Heavy Swarm-Coding

1. **Route collision warnings** (prevents silent bugs across agents)
2. **Event delivery failure logging** (debugging across shards)
3. **Shard template repo** (known-good starting point for AI agents)

### Prompt Guidance for AI Agents

Include in swarm-coding prompts:

```
SHARD DEVELOPMENT RULES:
1. API prefix MUST be /api/{shard_name}/ - check SHARDS_AND_BUNDLES.md for reserved names
2. Constructor takes NO arguments
3. Store frame reference in initialize(): self.frame = frame
4. Check service availability before use: if self.llm and self.llm.is_available()
5. Handle your own exceptions in event callbacks
6. Use your own DB schema: arkham_{shard_name}
7. Never import other shards directly—use events
8. Emit events for actions other shards might care about
```

---

## 8. Open Questions for Future Deliberation

| Question | Context |
|----------|---------|
| Is Redis a hard requirement? | Determines whether to implement sync fallback |
| Which bundle is the pilot for integration testing? | Journalism bundle matches existing monolith for comparison |
| What events constitute "provenance-worthy"? | Needed before building provenance shard |
| Should route collisions fail startup or just warn? | Warnings are safer; hard fail is cleaner |
| Do you need workspace/profile persistence? | Currently shell configs are implicit in the build |

---

## 9. Priority Ranking (If Implementing)

Based on effort vs. impact:

| Priority | Item | Effort | Impact |
|----------|------|--------|--------|
| 1 | Event delivery failure logging | 30 min | High (debugging) |
| 2 | Route collision warnings | 30 min | High (prevents silent bugs) |
| 3 | Shard template repo | 1-2 hrs | High (swarm-coding quality) |
| 4 | Redis graceful degradation | 2-3 hrs | Medium (resilience) |
| 5 | Provenance shard design | 4+ hrs | Medium (needed for some bundles) |
| 6 | Domain banners in shell | 1 hr | Low (UX polish) |

---

## 10. Summary

The architecture is sound. The gaps identified are:

1. **Observability:** Event failures are silent (easy fix)
2. **Developer safety:** Route collisions are silent (easy fix)  
3. **Resilience:** Redis down = unclear behavior (decision needed)
4. **Provenance:** Ephemeral events can't support evidence chains (shard needed)

None of these are architectural flaws—they're hardening opportunities. The core pattern (Frame orchestrates, Shell presents, Shards isolate) is correct and doesn't need revision.

---

*Document generated from advisory session. Not prescriptive—these are options for consideration.*
