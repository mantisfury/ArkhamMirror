"""
Migration: Add entity_analysis_cache table

Phase 2 of Contradiction System Upgrade - Intelligent Caching
"""

import sys
from pathlib import Path

# Add project root to path for central config
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from config import DATABASE_URL
from sqlalchemy import create_engine, text


def migrate():
    """Create entity_analysis_cache table."""
    engine = create_engine(DATABASE_URL)

    create_table_sql = """
    CREATE TABLE IF NOT EXISTS entity_analysis_cache (
        id SERIAL PRIMARY KEY,
        entity_id INTEGER UNIQUE NOT NULL REFERENCES canonical_entities(id) ON DELETE CASCADE,
        content_hash VARCHAR NOT NULL,
        last_analyzed_at TIMESTAMP DEFAULT NOW(),
        chunk_count INTEGER DEFAULT 0,
        contradiction_count INTEGER DEFAULT 0
    );
    
    CREATE INDEX IF NOT EXISTS idx_entity_analysis_cache_entity_id 
    ON entity_analysis_cache(entity_id);
    """

    with engine.connect() as conn:
        conn.execute(text(create_table_sql))
        conn.commit()
        print("✓ Created entity_analysis_cache table")


if __name__ == "__main__":
    migrate()
