"""
Migration: Phase 3 - Enhanced Contradiction Storage

Adds new columns to contradictions and contradiction_evidence tables.
"""

# Run this SQL via Docker:
# docker exec arkham_mirror-postgres-1 psql -U anom -d anomdb -c "..."

MIGRATION_SQL = """
-- Contradiction table enhancements
ALTER TABLE contradictions ADD COLUMN IF NOT EXISTS category VARCHAR;
ALTER TABLE contradictions ADD COLUMN IF NOT EXISTS tags TEXT;
ALTER TABLE contradictions ADD COLUMN IF NOT EXISTS keywords TEXT;
ALTER TABLE contradictions ADD COLUMN IF NOT EXISTS claim_a_chunk_id INTEGER REFERENCES chunks(id);
ALTER TABLE contradictions ADD COLUMN IF NOT EXISTS claim_b_chunk_id INTEGER REFERENCES chunks(id);
ALTER TABLE contradictions ADD COLUMN IF NOT EXISTS claim_a_context TEXT;
ALTER TABLE contradictions ADD COLUMN IF NOT EXISTS claim_b_context TEXT;
ALTER TABLE contradictions ADD COLUMN IF NOT EXISTS chain_id INTEGER;
ALTER TABLE contradictions ADD COLUMN IF NOT EXISTS chain_position INTEGER;
ALTER TABLE contradictions ADD COLUMN IF NOT EXISTS related_contradiction_ids TEXT;
ALTER TABLE contradictions ADD COLUMN IF NOT EXISTS detection_method VARCHAR DEFAULT 'llm';
ALTER TABLE contradictions ADD COLUMN IF NOT EXISTS llm_model VARCHAR;
ALTER TABLE contradictions ADD COLUMN IF NOT EXISTS analysis_duration_ms INTEGER;
ALTER TABLE contradictions ADD COLUMN IF NOT EXISTS user_notes TEXT;
ALTER TABLE contradictions ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMP;

-- ContradictionEvidence table enhancements
ALTER TABLE contradiction_evidence ADD COLUMN IF NOT EXISTS extracted_claim TEXT;
ALTER TABLE contradiction_evidence ADD COLUMN IF NOT EXISTS claim_type VARCHAR;
ALTER TABLE contradiction_evidence ADD COLUMN IF NOT EXISTS evidence_confidence FLOAT;
ALTER TABLE contradiction_evidence ADD COLUMN IF NOT EXISTS context_before TEXT;
ALTER TABLE contradiction_evidence ADD COLUMN IF NOT EXISTS context_after TEXT;

-- Indexes for new columns
CREATE INDEX IF NOT EXISTS idx_contradictions_category ON contradictions(category);
CREATE INDEX IF NOT EXISTS idx_contradictions_chain_id ON contradictions(chain_id);
CREATE INDEX IF NOT EXISTS idx_contradictions_severity ON contradictions(severity);
CREATE INDEX IF NOT EXISTS idx_contradictions_status ON contradictions(status);
"""

if __name__ == "__main__":
    print("Run this migration via Docker:")
    print()
    print(
        'docker exec arkham_mirror-postgres-1 psql -U anom -d anomdb -c "'
        + MIGRATION_SQL.replace('"', '\\"').replace("\n", " ").strip()
        + '"'
    )
