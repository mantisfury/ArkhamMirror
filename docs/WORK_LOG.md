# ArkhamFrame Implementation Work Log

## Phase 1: Foundation - COMPLETE (2025-12-25)

### Completed Services
1. **ResourceService** (services/resources.py)
   - Hardware detection (GPU, CPU, RAM, disk)
   - Resource tier assignment (minimal/standard/recommended/power)
   - GPU memory management
   - CPU thread management
   - Per-tier pool configurations
   - Configuration overrides

2. **StorageService** (services/storage.py)
   - File/blob storage with categories
   - Temp file management
   - Project-scoped storage
   - Metadata caching

3. **DocumentService** (services/documents.py)
   - Full CRUD operations
   - Page and chunk management
   - Vector search integration
   - Batch operations
   - Database tables (documents, chunks, pages)

4. **ProjectService** (services/projects.py)
   - Full CRUD with unique names
   - Settings management (dot notation)
   - Statistics
   - Export/import

---

## Phase 2: Data Services - IN PROGRESS

### Started: 2025-12-25

### Tasks
- [ ] EntityService completion
- [ ] VectorService completion
- [ ] ChunkService implementation (NEW)
- [ ] LLMService enhancements

### Progress Log

#### 2025-12-31: SQLAlchemy Parameter Fixes & UI Enhancements

**SQLAlchemy Parameter Error Fixes:**
Fixed SQLAlchemy `ArgumentError: List argument must consist only of dictionaries` across 4 shards. The database service uses SQLAlchemy's `text()` which requires named parameters (`:param_name`) with dictionary params, but shards were using positional `?` placeholders with list/tuple params.

- **Claims shard** (`arkham-shard-claims/shard.py`)
  - Fixed: `list_claims`, `get_claim`, `get_claim_evidence`, `get_count`
  - Fixed: `_save_claim`, `_save_evidence`, `_update_claim_evidence_counts`, `_link_claims_to_entity`

- **Patterns shard** (`arkham-shard-patterns/shard.py`)
  - Fixed: `list_patterns`, `get_pattern`, `get_pattern_matches`, `delete_pattern`, `remove_match`, `get_count`, `get_match_count`
  - Fixed: `_save_pattern`, `_save_match`, `_update_pattern_counts`

- **Reports shard** (`arkham-shard-reports/shard.py`)
  - Fixed: `list_reports`, `get_report`, `list_templates`, `get_template`, `delete_report`, `delete_schedule`, `get_count`
  - Fixed: `_save_report`, `_save_template`, `_save_schedule`

- **Packets shard** (`arkham-shard-packets/shard.py`)
  - Fixed: `list_packets`, `get_packet`, `get_packet_contents`, `get_packet_shares`, `get_packet_versions`, `remove_content`, `revoke_share`, `get_count`
  - Fixed: `_save_packet`, `_save_content`, `_save_share`, `_save_version`, `_update_packet_counts`

**UI Enhancements:**
- Added chunking configuration UI to ParsePage.tsx (settings panel with chunk size, overlap, method)
- Integrated LinkedDocumentsSection into ACH matrix detail view

**Documentation:**
- Updated CLAUDE.md with file write workaround for known Claude Code bug

#### 2025-12-31: ACH Shard Major UI/UX Improvements

**Corpus Search UI:**
- Converted inline corpus search results to modal dialog (`CorpusSearchDialog.tsx`)
- Fixed CSS conflicts with global `.hypothesis-header` styles (was constrained to 200px max-width)
- Scoped all dialog styles to `.corpus-dialog` to avoid conflicts

**Matrix Display Improvements:**
- Changed matrix headers to compact format: `H1`, `H2`, `E1`, `E2` instead of full titles
- Added hover tooltips showing full hypothesis/evidence text with descriptions
- Columns now 50px wide allowing many more hypotheses to fit on screen
- Increased page max-width from 1200px to 1400px
- Added horizontal scroll support for matrices with many hypotheses

**PDF/HTML Export Fixes:**
- Fixed corrupted table output in HTML export (was `<\td>` typo)
- Changed hypothesis scores from table format to list format for better readability
- Each score now displays as `#1 — Hypothesis Title` with details below
- Handles long hypothesis titles without text overflow/corruption

**Milestone Enhancements:**
- Created `MilestoneDialog.tsx` for proper add/edit modal
- Added fields: Description, Related Hypothesis, Expected By date, Status, Observation Notes
- Added inline status dropdown (PENDING/OBSERVED/CONTRADICTED) with color coding
- Replaced `window.prompt()` approach with proper form dialog

**Scores Section Fixes:**
- Fixed hover tooltips showing "undefined" for hypothesis titles
- ScoresSection now accepts `hypotheses` prop to look up titles
- Falls back to hypotheses list if `hypothesis_title` not in score object

**Devil's Advocate:**
- Added hypothesis picker dropdown to select which hypothesis to challenge
- No longer auto-picks the first hypothesis

**AI Ratings Dialog:**
- Fixed modal not scrolling when many suggestions present
- Dialog now has max-height 80vh with scrollable suggestion list
- Action buttons (Close, Accept All) stay fixed at bottom

**Files Modified:**
- `packages/arkham-shard-shell/src/pages/ach/components/CorpusSearchDialog.tsx` (new)
- `packages/arkham-shard-shell/src/pages/ach/components/MilestoneDialog.tsx` (new)
- `packages/arkham-shard-shell/src/pages/ach/components/AIDialogs.tsx`
- `packages/arkham-shard-shell/src/pages/ach/components/sections/ScoresSection.tsx`
- `packages/arkham-shard-shell/src/pages/ach/components/sections/MilestonesSection.tsx`
- `packages/arkham-shard-shell/src/pages/ach/components/sections/CorpusSearchSection.tsx`
- `packages/arkham-shard-shell/src/pages/ach/components/index.ts`
- `packages/arkham-shard-shell/src/pages/ach/ACHPage.tsx`
- `packages/arkham-shard-shell/src/styles/index.css`
- `packages/arkham-shard-ach/arkham_shard_ach/export.py`

---
