# SHATTERED Shard Wiring Status

## Audit Summary

**Date**: 2025-12-29
**Audited By**: Claude (Sonnet 4.5)
**Assigned Shards**: ingest, ach, anomalies, contradictions, entities, claims

## Overview

This audit assessed the integration status of 6 SHATTERED shards to determine which are fully wired (complete frontend-backend integration) versus stub/incomplete.

### Status Categories

- **FULLY WIRED**: Complete backend implementation with database persistence, complete frontend with API integration, data flows end-to-end
- **PARTIAL**: Database schema exists, some endpoints work, but missing key integration pieces (e.g., event handlers, data population)
- **STUB**: API structure exists but uses in-memory storage or placeholder data, will lose data on restart

## Audit Results

| Shard | Status | Complexity | Est. Time | Priority |
|-------|--------|------------|-----------|----------|
| **ingest** | ✅ FULLY WIRED | - | - | - |
| **ach** | ✅ FULLY WIRED | - | - | HIGH |
| **anomalies** | 🟡 STUB | MEDIUM-LARGE | 4h | MEDIUM |
| **contradictions** | 🟡 STUB | MEDIUM-LARGE | 4.5h | HIGH |
| **entities** | 🟠 PARTIAL | MEDIUM | 4h | MEDIUM |
| **claims** | 🟠 PARTIAL | MEDIUM-LARGE | 4h | HIGH |

### Fully Wired Shards

#### ✅ Ingest Shard
**Status**: Complete and production-ready

**Features**:
- Full file upload with drag-and-drop
- Multi-stage worker pipeline (extract → file → archive → image)
- Image quality assessment (CLEAN/FIXABLE/MESSY)
- OCR routing (auto/paddle/qwen modes)
- Batch processing with staggering
- Job queue management with retry logic
- Settings panel with pipeline optimization toggles
- Complete frontend with real-time queue stats

**Assessment**: Reference implementation for what "fully wired" means.

#### ✅ ACH Shard
**Status**: Complete and production-ready

**Features**:
- Complete ACH matrix implementation (Heuer's 8-step methodology)
- Hypothesis and evidence management
- Consistency rating system (++, +, N, -, --)
- Automated scoring and ranking
- Devil's advocate mode (LLM-powered)
- AI-powered hypothesis/evidence suggestions
- Diagnosticity and sensitivity analysis
- Multi-format export (JSON, CSV, HTML, Markdown)
- Complete React UI with matrix visualization

**Assessment**: Sophisticated implementation with LLM integration.

### Shards Needing Work

#### 🟡 Anomalies Shard
**Status**: STUB - In-memory storage only

**What Works**:
- Complete detector logic (statistical, embedding-based, temporal, metadata, red flags)
- Full API structure
- Complete frontend UI

**What's Missing**:
- Database persistence (uses `dict` storage)
- Schema creation not implemented
- Detection endpoints return placeholder data
- Will lose all data on restart

**Wiring Plan**: `anomalies_wiring_plan.md`
**Effort**: 4 hours (MEDIUM-LARGE)

**Key Tasks**:
1. Add database schema creation (30 min)
2. Convert storage.py from in-memory to database (2h)
3. Wire up detection logic to persist results (1h)
4. Test end-to-end (30 min)

---

#### 🟡 Contradictions Shard
**Status**: STUB - In-memory storage + placeholder document fetching

**What Works**:
- Complete detector logic (claim extraction, semantic similarity, LLM verification)
- Chain detection for transitive contradictions
- Full API structure
- Complete frontend UI

**What's Missing**:
- Database persistence (uses `dict` storage)
- Schema creation not implemented
- Uses placeholder document content (`doc_a_text = f"Document {id} content"`)
- Cannot analyze real documents

**Wiring Plan**: `contradictions_wiring_plan.md`
**Effort**: 4.5 hours (MEDIUM-LARGE)

**Key Tasks**:
1. Add database schema creation (30 min)
2. Convert storage.py to database (2h)
3. Implement real document fetching (45 min)
4. Verify LLM integration (30 min)
5. Test end-to-end (45 min)

---

#### 🟠 Entities Shard
**Status**: PARTIAL - Schema exists but no data population

**What Works**:
- Database schema creation (entities, mentions, relationships)
- Full API structure
- Complete frontend UI with search/filtering

**What's Missing**:
- Event handlers are commented out
- No mechanism to receive entities from parse shard
- Merge functionality incomplete
- Will return empty lists until integrated

**Wiring Plan**: `entities_wiring_plan.md`
**Effort**: 4 hours (MEDIUM)

**Key Tasks**:
1. Implement event handlers for parse shard (1.5h)
2. Verify list endpoint returns real data (30 min)
3. Implement merge functionality (1h)
4. Test integration with parse shard (1h)

**Note**: This shard is primarily a **viewer/manager** for entities extracted by the parse shard. Success depends on parse shard emitting proper events.

---

#### 🟠 Claims Shard
**Status**: PARTIAL - Schema exists but no claim extraction

**What Works**:
- Database schema creation (claims, evidence)
- Full API structure
- Complete frontend UI with status workflow

**What's Missing**:
- No automatic claim extraction from documents
- Event handlers stubbed out
- Manual extraction endpoint needs LLM integration
- Will return empty lists until integrated

**Wiring Plan**: `claims_wiring_plan.md`
**Effort**: 4 hours (MEDIUM-LARGE)

**Key Tasks**:
1. Implement event handlers and extraction logic (2.5h)
2. Wire up manual extraction endpoint (30 min)
3. Test integration (1h)

**Note**: Requires parse shard to emit `parse.document.completed` events with document content.

## Priority Recommendations

### High Priority
1. **Contradictions** - Critical for intelligence analysis workflow
2. **Claims** - Foundation for contradiction detection and fact-checking
3. **ACH** - Already complete, promote as showcase feature

### Medium Priority
4. **Entities** - Useful for entity resolution but depends on parse shard
5. **Anomalies** - Helpful for QA but not core workflow

### Dependencies

Several shards depend on the **parse shard** emitting proper events:
- **Entities**: Needs `parse.entity.extracted` events
- **Claims**: Needs `parse.document.completed` events with content
- **Contradictions**: Needs document content from parse or documents shard

**Recommendation**: Audit the parse shard next to ensure it's emitting the required events.

## Total Estimated Effort

**To complete all 4 incomplete shards**: ~16.5 hours

**Breakdown**:
- Anomalies: 4h
- Contradictions: 4.5h
- Entities: 4h
- Claims: 4h

**Note**: This is serial time. With proper task breakdown, multiple shards could be completed in parallel.

## Next Steps

1. **Immediate**: Review this audit summary with the team
2. **Next Audit**: Parse shard (to verify event emissions)
3. **Implementation**: Start with Contradictions (highest value, 4.5h)
4. **Testing**: Set up integration tests for event flows between shards

## Files Generated

All wiring plans are in `docs/wiring_plans/`:
- `anomalies_wiring_plan.md` - Complete implementation guide
- `contradictions_wiring_plan.md` - Complete implementation guide
- `entities_wiring_plan.md` - Complete implementation guide
- `claims_wiring_plan.md` - Complete implementation guide
- `README.md` - This summary document
