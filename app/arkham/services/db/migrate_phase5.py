"""
Phase 5.2 Database Migration: Add ingestion_errors and entity_filter_rules tables

Run this script to add the new tables:
    cd arkham && python -m arkham.services.db.migrate_phase5
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
import sys
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Add paths
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
load_dotenv()




def run_migration():
    """Create Phase 5.2 tables if they don't exist."""
    engine = create_engine(DATABASE_URL)

    with engine.connect() as conn:
        # Check if ingestion_errors table exists
        result = conn.execute(
            text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'ingestion_errors'
            );
        """)
        ).scalar()

        if not result:
            print("Creating ingestion_errors table...")
            conn.execute(
                text("""
                CREATE TABLE ingestion_errors (
                    id SERIAL PRIMARY KEY,
                    document_id INTEGER REFERENCES documents(id) ON DELETE SET NULL,
                    chunk_id INTEGER REFERENCES chunks(id) ON DELETE SET NULL,
                    stage VARCHAR(50) NOT NULL,
                    error_type VARCHAR(100) NOT NULL,
                    error_message TEXT NOT NULL,
                    stack_trace TEXT,
                    is_resolved INTEGER DEFAULT 0,
                    retry_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            )
            conn.execute(
                text("""
                CREATE INDEX idx_ingestion_errors_doc_id ON ingestion_errors(document_id);
            """)
            )
            conn.execute(
                text("""
                CREATE INDEX idx_ingestion_errors_stage ON ingestion_errors(stage);
            """)
            )
            conn.execute(
                text("""
                CREATE INDEX idx_ingestion_errors_unresolved ON ingestion_errors(is_resolved) WHERE is_resolved = 0;
            """)
            )
            print("✓ ingestion_errors table created")
        else:
            print("✓ ingestion_errors table already exists")

        # Check if entity_filter_rules table exists
        result = conn.execute(
            text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'entity_filter_rules'
            );
        """)
        ).scalar()

        if not result:
            print("Creating entity_filter_rules table...")
            conn.execute(
                text("""
                CREATE TABLE entity_filter_rules (
                    id SERIAL PRIMARY KEY,
                    pattern VARCHAR(255) NOT NULL,
                    is_regex INTEGER DEFAULT 1,
                    created_by VARCHAR(50) DEFAULT 'system',
                    description VARCHAR(500),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            )

            # Insert default filter rules for noisy entities
            default_rules = [
                (r"^\d+$", "Pure numbers"),
                (r"^[\W_]+$", "Only special characters"),
                (r"^.{1,2}$", "Too short (1-2 chars)"),
                (r"^\d{1,2}/\d{1,2}(/\d{2,4})?$", "Date patterns like 12/25"),
                (
                    r"^(january|february|march|april|may|june|july|august|september|october|november|december)$",
                    "Month names",
                ),
                (r"^page\s*\d+$", "Page markers"),
                (
                    r"^(start|end|figure|table|section|chapter)$",
                    "Document structure words",
                ),
            ]

            for pattern, description in default_rules:
                conn.execute(
                    text("""
                    INSERT INTO entity_filter_rules (pattern, is_regex, created_by, description)
                    VALUES (:pattern, 1, 'system', :description)
                """),
                    {"pattern": pattern, "description": description},
                )

            print(
                f"✓ entity_filter_rules table created with {len(default_rules)} default rules"
            )
        else:
            print("✓ entity_filter_rules table already exists")

        conn.commit()

    print("\nPhase 5.2 migration complete!")


if __name__ == "__main__":
    run_migration()
