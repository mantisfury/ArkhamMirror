"""
ACH History Migration

Creates the ach_analysis_snapshots table for version history.
"""

import sys
from pathlib import Path

# Add project root to path for central config
project_root = Path(__file__).resolve()
while project_root.name != "ArkhamMirror" and project_root.parent != project_root:
    project_root = project_root.parent
sys.path.insert(0, str(project_root))

from config import DATABASE_URL
from sqlalchemy import create_engine, text


def _table_exists(conn, table_name: str) -> bool:
    """Check if a table exists in the database."""
    result = conn.execute(
        text(
            """
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_name = :table_name
        );
    """
        ),
        {"table_name": table_name},
    ).scalar()
    return result


def run_migration():
    """Create ACH History tables."""
    engine = create_engine(DATABASE_URL)

    with engine.connect() as conn:
        # =====================================================================
        # ACH SNAPSHOTS TABLE
        # =====================================================================
        if not _table_exists(conn, "ach_analysis_snapshots"):
            print("Creating ach_analysis_snapshots table...")
            conn.execute(
                text(
                    """
                CREATE TABLE ach_analysis_snapshots (
                    id SERIAL PRIMARY KEY,
                    analysis_id INTEGER NOT NULL REFERENCES ach_analyses(id) ON DELETE CASCADE,
                    snapshot_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    label VARCHAR(255),
                    description TEXT,
                    data TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX idx_ach_snapshots_analysis ON ach_analysis_snapshots(analysis_id);"
                )
            )
            print("  [OK] ach_analysis_snapshots table created")
        else:
            print("  [OK] ach_analysis_snapshots table already exists")

        conn.commit()

    print("\nACH History migration complete!")


if __name__ == "__main__":
    run_migration()
