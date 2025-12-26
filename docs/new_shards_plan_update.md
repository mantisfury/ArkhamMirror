# New Shards Development Plan

> Master plan for building production-ready shards for the SHATTERED architecture
> Based on `shard_manifest_schema_prod.md` and reference implementation `arkham-shard-ach`

---

## Table of Contents

1. [Overview](#1-overview)
2. [Current State](#2-current-state)
3. [Navigation Slot Allocation](#3-navigation-slot-allocation)
4. [Shard Development Checklist](#4-shard-development-checklist)
5. [Production Compliance Requirements](#5-production-compliance-requirements)
6. [Shard Templates](#6-shard-templates)
7. [New Shard Candidates](#7-new-shard-candidates)
8. [Bundle Composition](#8-bundle-composition)
9. [Implementation Guidelines](#9-implementation-guidelines)
10. [Quality Gates](#10-quality-gates)

---

## 1. Overview

### 1.1 Architecture Pattern

All shards follow the intelligence analysis pipeline:

```
INGEST → EXTRACT → ORGANIZE → ANALYZE → ACT
  ↓        ↓         ↓          ↓       ↓
 Data     Parse    Search    Analysis  Export
 Shards   Shards   Shards    Shards   Shards
```

### 1.2 Core Principles

1. **Frame is Immutable**: Shards depend on the Frame, never the reverse
2. **No Shard Dependencies**: Shards MUST NOT import other shards directly
3. **Schema Isolation**: Each shard gets `arkham_{shard_name}` database schema
4. **Event-Driven Communication**: Shards communicate via EventBus only
5. **Self-Contained**: Each shard has manifest, API, workers, and optionally UI

### 1.3 Production Standards

All new shards MUST comply with `shard_manifest_schema_prod.md`:
- Valid manifest structure
- Correct navigation category and order range
- Event naming: `{shard}.{entity}.{action}`
- Standard capability names from registry
- Empty `dependencies.shards: []`

---

## 2. Current State

### 2.1 Implemented Shards (25)

| Shard | Category | Order | Status |
|-------|----------|-------|--------|
| dashboard | System | 0 | Production |
| projects | System | 2 | Production |
| settings | System | 5 | Production |
| ingest | Data | 10 | Production |
| ocr | Data | 11 | Production |
| parse | Data | 12 | Production |
| documents | Data | 13 | Production |
| entities | Data | 14 | Production |
| search | Search | 20 | Production |
| embed | Search | 25 | Production |
| ach | Analysis | 30 | Production (Reference) |
| claims | Analysis | 31 | Production |
| provenance | Analysis | 32 | Production |
| credibility | Analysis | 33 | Production |
| contradictions | Analysis | 35 | Production |
| patterns | Analysis | 36 | Production |
| anomalies | Analysis | 37 | Production |
| summary | Analysis | 39 | Production |
| graph | Visualize | 40 | Production |
| timeline | Visualize | 45 | Production |
| export | Export | 50 | Production |
| letters | Export | 51 | Production |
| templates | Export | 52 | Production |
| reports | Export | 55 | Production |
| packets | Export | 58 | Production |

### 2.2 Available Slots

| Category | Range | Used Slots | Available Slots |
|----------|-------|------------|-----------------|
| System | 0-9 | 0, 2, 5 | 1, 3-4, 6-9 (7 slots) |
| Data | 10-19 | 10, 11, 12, 13, 14 | 15-19 (5 slots) |
| Search | 20-29 | 20, 25 | 21-24, 26-29 (8 slots) |
| Analysis | 30-39 | 30, 31, 32, 33, 35, 36, 37, 39 | 34, 38 (2 slots) |
| Visualize | 40-49 | 40, 45 | 41-44, 46-49 (8 slots) |
| Export | 50-59 | 50, 51, 52, 55, 58 | 53-54, 56-57, 59 (5 slots) |

**Total available slots: 35**

---

*Updated: 2025-12-26*
*Status: All 25 shards production-ready and compliant*
