"""
Migration: Create contradiction_batch table for batch tracking.

Run with: python -m arkham.services.db.migrate_batch_tracking
"""

import sys
from pathlib import Path

# Add project root to path for central config
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from config import DATABASE_URL
from sqlalchemy import create_engine, text


def run_migration():
    """Create the contradiction_batch table."""
    engine = create_engine(DATABASE_URL)

    sql = """
    CREATE TABLE IF NOT EXISTS contradiction_batch (
        id SERIAL PRIMARY KEY,
        batch_number INT NOT NULL,
        status VARCHAR(20) DEFAULT 'pending',
        entity_offset INT NOT NULL,
        entity_count INT NOT NULL,
        contradictions_found INT DEFAULT 0,
        started_at TIMESTAMP,
        completed_at TIMESTAMP,
        job_id VARCHAR(20),
        error TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    
    CREATE INDEX IF NOT EXISTS idx_batch_number ON contradiction_batch(batch_number);
    CREATE INDEX IF NOT EXISTS idx_batch_status ON contradiction_batch(status);
    """

    with engine.connect() as conn:
        conn.execute(text(sql))
        conn.commit()
        print("✅ Created contradiction_batch table")


if __name__ == "__main__":
    run_migration()
