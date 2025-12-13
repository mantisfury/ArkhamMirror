"""
Migration: Add affected_entity_ids to entity_merge_audit.

Enables unmerge functionality by tracking which entity mentions were moved.
"""

import os
import sys
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

from config.settings import DATABASE_URL

load_dotenv()

def migrate():
    """Add affected_entity_ids column to entity_merge_audit table."""
    if not DATABASE_URL:
        print("❌ ERROR: DATABASE_URL not set")
        return False

    try:
        engine = create_engine(DATABASE_URL)
        with engine.connect() as conn:
            # Check if column already exists
            result = conn.execute(
                text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'entity_merge_audit' 
                AND column_name = 'affected_entity_ids'
            """)
            )
            if result.fetchone():
                print("   >> Column 'affected_entity_ids' already exists, skipping")
                return True

            # Add column
            print("   + Adding 'affected_entity_ids' column...")
            conn.execute(
                text("ALTER TABLE entity_merge_audit ADD COLUMN affected_entity_ids TEXT")
            )
            conn.commit()
            print("   OK Migration successful")
            return True
    except Exception as e:
        print(f"   !! Migration failed: {e}")
        return False

if __name__ == "__main__":
    print("Running Unmerge Support Migration...")
    migrate()
