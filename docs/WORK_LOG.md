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

---
