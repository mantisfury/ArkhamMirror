"""
Migration script to add entity linking tables.

Adds:
- canonical_entities table
- entity_relationships table
- canonical_entity_id column to entities table
"""

# Add project root to path for central config
from pathlib import Path
import sys
project_root = Path(__file__).resolve()
while project_root.name != 'ArkhamMirror' and project_root.parent != project_root:
    project_root = project_root.parent
sys.path.insert(0, str(project_root))

from config import DATABASE_URL
import os
import logging
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


engine = create_engine(DATABASE_URL)


def migrate():
    """
    Add new tables and columns for entity linking.
    """
    with engine.connect() as conn:
        # Check if canonical_entities already exists
        result = conn.execute(
            text(
                """
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = 'canonical_entities'
                )
                """
            )
        )
        exists = result.scalar()

        if exists:
            logger.info("canonical_entities table already exists. Skipping migration.")
            return

        logger.info("Creating canonical_entities table...")
        conn.execute(
            text(
                """
                CREATE TABLE canonical_entities (
                    id SERIAL PRIMARY KEY,
                    canonical_name VARCHAR NOT NULL,
                    label VARCHAR NOT NULL,
                    aliases TEXT,
                    total_mentions INTEGER DEFAULT 0,
                    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )
        conn.execute(text("CREATE INDEX idx_canonical_name ON canonical_entities(canonical_name)"))
        logger.info("✓ canonical_entities table created")

        logger.info("Creating entity_relationships table...")
        conn.execute(
            text(
                """
                CREATE TABLE entity_relationships (
                    id SERIAL PRIMARY KEY,
                    entity1_id INTEGER NOT NULL REFERENCES canonical_entities(id),
                    entity2_id INTEGER NOT NULL REFERENCES canonical_entities(id),
                    relationship_type VARCHAR DEFAULT 'co-occurrence',
                    strength FLOAT DEFAULT 1.0,
                    doc_id INTEGER REFERENCES documents(id),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )
        logger.info("✓ entity_relationships table created")

        logger.info("Adding canonical_entity_id column to entities table...")
        conn.execute(
            text(
                """
                ALTER TABLE entities
                ADD COLUMN IF NOT EXISTS canonical_entity_id INTEGER
                REFERENCES canonical_entities(id)
                """
            )
        )
        logger.info("✓ canonical_entity_id column added")

        conn.commit()
        logger.info("Migration complete!")


if __name__ == "__main__":
    migrate()
