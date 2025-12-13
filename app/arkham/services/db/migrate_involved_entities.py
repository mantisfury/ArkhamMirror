"""
Migration: Add involved_entity_ids column to contradictions table.

This enables multi-entity contradictions where conflicts span across
different people/entities.
"""

MIGRATION_SQL = """
ALTER TABLE contradictions ADD COLUMN IF NOT EXISTS involved_entity_ids TEXT;
"""

if __name__ == "__main__":
    print("Run this migration via Docker:")
    print()
    print(
        'docker exec arkham_mirror-postgres-1 psql -U anom -d anomdb -c "'
        + MIGRATION_SQL.replace('"', '\\"').replace("\n", " ").strip()
        + '"'
    )
    print()
    print("Or run directly in Python:")
    print()
    print(
        "from app.arkham.services.db.migrate_involved_entities import run_migration"
    )
    print("run_migration()")


def run_migration():
    """Execute migration directly via Python."""
    import os # Keep os
    from sqlalchemy import create_engine, text
    from dotenv import load_dotenv

    from config.settings import DATABASE_URL # Corrected import

    load_dotenv()
    

    if not DATABASE_URL:
        print("ERROR: DATABASE_URL not set")
        return False

    try:
        engine = create_engine(DATABASE_URL)
        with engine.connect() as conn:
            # Check if column already exists
            result = conn.execute(
                text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'contradictions' 
                AND column_name = 'involved_entity_ids'
            """)
            )
            if result.fetchone():
                print("Column 'involved_entity_ids' already exists")
                return True

            # Add column
            conn.execute(
                text("ALTER TABLE contradictions ADD COLUMN involved_entity_ids TEXT")
            )
            conn.commit()
            print(
                "Successfully added 'involved_entity_ids' column to contradictions table"
            )
            return True
    except Exception as e:
        print(f"Migration failed: {e}")
        return False
