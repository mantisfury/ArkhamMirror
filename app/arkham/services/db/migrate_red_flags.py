# Add project root to path for central config
from pathlib import Path
import sys

project_root = Path(__file__).resolve()
while project_root.name != "ArkhamMirror" and project_root.parent != project_root:
    project_root = project_root.parent
sys.path.insert(0, str(project_root))

"""
Migration: Create red_flags table for Red Flag Discovery feature.

Run with: python -m arkham.services.db.migrate_red_flags
"""

from config import DATABASE_URL
from sqlalchemy import create_engine, text


def run_migration():
    """Create the red_flags table."""
    engine = create_engine(DATABASE_URL)

    sql = """
    CREATE TABLE IF NOT EXISTS red_flags (
        id SERIAL PRIMARY KEY,
        flag_type VARCHAR(100) NOT NULL,
        flag_category VARCHAR(100) NOT NULL,
        severity VARCHAR(20) NOT NULL,
        title VARCHAR(500) NOT NULL,
        description TEXT,
        evidence TEXT,
        confidence FLOAT DEFAULT 0.5,
        doc_id INTEGER REFERENCES documents(id) ON DELETE SET NULL,
        entity_id INTEGER REFERENCES canonical_entities(id) ON DELETE SET NULL,
        timeline_event_id INTEGER REFERENCES timeline_events(id) ON DELETE SET NULL,
        status VARCHAR(50) DEFAULT 'active',
        reviewer_notes TEXT,
        reviewed_at TIMESTAMP,
        detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    
    CREATE INDEX IF NOT EXISTS idx_red_flags_severity ON red_flags(severity);
    CREATE INDEX IF NOT EXISTS idx_red_flags_status ON red_flags(status);
    CREATE INDEX IF NOT EXISTS idx_red_flags_category ON red_flags(flag_category);
    CREATE INDEX IF NOT EXISTS idx_red_flags_doc_id ON red_flags(doc_id);
    """

    with engine.connect() as conn:
        conn.execute(text(sql))
        conn.commit()
        print("✅ Created red_flags table")


if __name__ == "__main__":
    run_migration()
