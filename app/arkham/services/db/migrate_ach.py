"""
ACH (Analysis of Competing Hypotheses) Database Migration

Creates the ACH tables for Heuer's 8-step methodology:
- ach_analyses: Analysis sessions with focus questions
- ach_hypotheses: Competing hypotheses for each analysis
- ach_evidence: Evidence items with reliability ratings
- ach_ratings: Matrix cells (evidence x hypothesis ratings)
- ach_milestones: Future indicators for Step 8

Run this script to add the ACH tables:
    cd app && python -m arkham.services.db.migrate_ach

Or tables will be created automatically on app startup via db_init.py
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
    """Create ACH tables if they don't exist."""
    engine = create_engine(DATABASE_URL)

    with engine.connect() as conn:
        # =====================================================================
        # ACH ANALYSES TABLE
        # =====================================================================
        if not _table_exists(conn, "ach_analyses"):
            print("Creating ach_analyses table...")
            conn.execute(
                text(
                    """
                CREATE TABLE ach_analyses (
                    id SERIAL PRIMARY KEY,
                    project_id INTEGER REFERENCES projects(id),
                    title VARCHAR(255) NOT NULL,
                    focus_question TEXT NOT NULL,
                    description TEXT,
                    status VARCHAR(50) DEFAULT 'draft',
                    sensitivity_notes TEXT,
                    key_assumptions TEXT,
                    current_step INTEGER DEFAULT 1,
                    steps_completed TEXT DEFAULT '[]',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX idx_ach_analyses_project ON ach_analyses(project_id);"
                )
            )
            conn.execute(
                text("CREATE INDEX idx_ach_analyses_status ON ach_analyses(status);")
            )
            print("  [OK] ach_analyses table created")
        else:
            print("  [OK] ach_analyses table already exists")

        # =====================================================================
        # ACH HYPOTHESES TABLE
        # =====================================================================
        if not _table_exists(conn, "ach_hypotheses"):
            print("Creating ach_hypotheses table...")
            conn.execute(
                text(
                    """
                CREATE TABLE ach_hypotheses (
                    id SERIAL PRIMARY KEY,
                    analysis_id INTEGER NOT NULL REFERENCES ach_analyses(id) ON DELETE CASCADE,
                    label VARCHAR(50) NOT NULL,
                    description TEXT NOT NULL,
                    display_order INTEGER DEFAULT 0,
                    color VARCHAR(20) DEFAULT '#3b82f6',
                    inconsistency_score FLOAT DEFAULT 0.0,
                    future_indicators TEXT,
                    indicator_timeframe VARCHAR(50),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX idx_ach_hypotheses_analysis ON ach_hypotheses(analysis_id);"
                )
            )
            print("  [OK] ach_hypotheses table created")
        else:
            print("  [OK] ach_hypotheses table already exists")

        # =====================================================================
        # ACH EVIDENCE TABLE
        # =====================================================================
        if not _table_exists(conn, "ach_evidence"):
            print("Creating ach_evidence table...")
            conn.execute(
                text(
                    """
                CREATE TABLE ach_evidence (
                    id SERIAL PRIMARY KEY,
                    analysis_id INTEGER NOT NULL REFERENCES ach_analyses(id) ON DELETE CASCADE,
                    label VARCHAR(50) NOT NULL,
                    description TEXT NOT NULL,
                    display_order INTEGER DEFAULT 0,
                    evidence_type VARCHAR(50) DEFAULT 'fact',
                    reliability VARCHAR(20) DEFAULT 'medium',
                    source TEXT,
                    source_document_id INTEGER REFERENCES documents(id),
                    diagnosticity_score FLOAT DEFAULT 0.0,
                    is_critical INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX idx_ach_evidence_analysis ON ach_evidence(analysis_id);"
                )
            )
            print("  [OK] ach_evidence table created")
        else:
            print("  [OK] ach_evidence table already exists")

        # =====================================================================
        # ACH RATINGS TABLE
        # =====================================================================
        if not _table_exists(conn, "ach_ratings"):
            print("Creating ach_ratings table...")
            conn.execute(
                text(
                    """
                CREATE TABLE ach_ratings (
                    id SERIAL PRIMARY KEY,
                    analysis_id INTEGER NOT NULL REFERENCES ach_analyses(id) ON DELETE CASCADE,
                    hypothesis_id INTEGER NOT NULL REFERENCES ach_hypotheses(id) ON DELETE CASCADE,
                    evidence_id INTEGER NOT NULL REFERENCES ach_evidence(id) ON DELETE CASCADE,
                    rating VARCHAR(10) DEFAULT '',
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(hypothesis_id, evidence_id)
                );
            """
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX idx_ach_ratings_analysis ON ach_ratings(analysis_id);"
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX idx_ach_ratings_hypothesis ON ach_ratings(hypothesis_id);"
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX idx_ach_ratings_evidence ON ach_ratings(evidence_id);"
                )
            )
            print("  [OK] ach_ratings table created")
        else:
            print("  [OK] ach_ratings table already exists")

        # =====================================================================
        # ACH MILESTONES TABLE
        # =====================================================================
        if not _table_exists(conn, "ach_milestones"):
            print("Creating ach_milestones table...")
            conn.execute(
                text(
                    """
                CREATE TABLE ach_milestones (
                    id SERIAL PRIMARY KEY,
                    analysis_id INTEGER NOT NULL REFERENCES ach_analyses(id) ON DELETE CASCADE,
                    hypothesis_id INTEGER NOT NULL REFERENCES ach_hypotheses(id) ON DELETE CASCADE,
                    description TEXT NOT NULL,
                    expected_by TIMESTAMP,
                    observed INTEGER DEFAULT 0,
                    observed_date TIMESTAMP,
                    observation_notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX idx_ach_milestones_analysis ON ach_milestones(analysis_id);"
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX idx_ach_milestones_hypothesis ON ach_milestones(hypothesis_id);"
                )
            )
            print("  [OK] ach_milestones table created")
        else:
            print("  [OK] ach_milestones table already exists")

        conn.commit()

    print("\nACH migration complete!")
    print("Tables created: ach_analyses, ach_hypotheses, ach_evidence, ach_ratings, ach_milestones")


if __name__ == "__main__":
    run_migration()
