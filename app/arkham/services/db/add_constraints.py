"""
Migration script to add database constraints for v0.1.5 hardening update.

This script adds:
1. Unique constraints on logical primary keys
2. Indexes for frequently queried columns
3. Check constraints for data integrity
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
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

def add_constraints():
    """Add missing database constraints."""
    engine = create_engine(DATABASE_URL)

    with engine.connect() as conn:
        print("Adding database constraints...")

        # 1. Unique constraint on PageOCR (document_id, page_num)
        # Prevents duplicate OCR entries for the same page
        try:
            conn.execute(text("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_page_ocr_unique
                ON page_ocr(document_id, page_num);
            """))
            print("✓ Added unique index on page_ocr(document_id, page_num)")
        except Exception as e:
            print(f"  Warning: Could not add page_ocr unique index: {e}")

        # 2. Unique constraint on Chunks (doc_id, chunk_index)
        # Ensures no duplicate chunks for the same position
        try:
            conn.execute(text("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_chunk_unique
                ON chunks(doc_id, chunk_index);
            """))
            print("✓ Added unique index on chunks(doc_id, chunk_index)")
        except Exception as e:
            print(f"  Warning: Could not add chunks unique index: {e}")

        # 3. Index on entities(canonical_entity_id) for faster joins
        try:
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_entity_canonical
                ON entities(canonical_entity_id);
            """))
            print("✓ Added index on entities(canonical_entity_id)")
        except Exception as e:
            print(f"  Warning: Could not add entity canonical index: {e}")

        # 4. Index on entity_relationships for faster graph queries
        try:
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_relationship_entity1
                ON entity_relationships(entity1_id);
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_relationship_entity2
                ON entity_relationships(entity2_id);
            """))
            print("✓ Added indexes on entity_relationships(entity1_id, entity2_id)")
        except Exception as e:
            print(f"  Warning: Could not add relationship indexes: {e}")

        # 5. Unique constraint on entity_relationships to prevent duplicate relationships
        try:
            conn.execute(text("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_relationship_unique
                ON entity_relationships(entity1_id, entity2_id, doc_id, relationship_type);
            """))
            print("✓ Added unique index on entity_relationships(entity1_id, entity2_id, doc_id, relationship_type)")
        except Exception as e:
            print(f"  Warning: Could not add relationship unique index: {e}")

        # 6. Index on extracted_tables(doc_id) for faster document queries
        try:
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_table_doc
                ON extracted_tables(doc_id);
            """))
            print("✓ Added index on extracted_tables(doc_id)")
        except Exception as e:
            print(f"  Warning: Could not add extracted_tables index: {e}")

        # 7. Index on anomalies(chunk_id, score) for faster anomaly queries
        try:
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_anomaly_chunk_score
                ON anomalies(chunk_id, score DESC);
            """))
            print("✓ Added index on anomalies(chunk_id, score)")
        except Exception as e:
            print(f"  Warning: Could not add anomaly index: {e}")

        # 8. Check constraint on Document.status
        try:
            conn.execute(text("""
                ALTER TABLE documents
                DROP CONSTRAINT IF EXISTS chk_document_status;
            """))
            conn.execute(text("""
                ALTER TABLE documents
                ADD CONSTRAINT chk_document_status
                CHECK (status IN ('pending', 'processing', 'complete', 'failed'));
            """))
            print("✓ Added check constraint on documents.status")
        except Exception as e:
            print(f"  Warning: Could not add document status constraint: {e}")

        # 9. Check constraint on MiniDoc.status
        try:
            conn.execute(text("""
                ALTER TABLE minidocs
                DROP CONSTRAINT IF EXISTS chk_minidoc_status;
            """))
            conn.execute(text("""
                ALTER TABLE minidocs
                ADD CONSTRAINT chk_minidoc_status
                CHECK (status IN ('pending_ocr', 'ocr_done', 'parsed'));
            """))
            print("✓ Added check constraint on minidocs.status")
        except Exception as e:
            print(f"  Warning: Could not add minidoc status constraint: {e}")

        # 10. Check constraint on anomaly score (must be positive)
        try:
            conn.execute(text("""
                ALTER TABLE anomalies
                DROP CONSTRAINT IF EXISTS chk_anomaly_score;
            """))
            conn.execute(text("""
                ALTER TABLE anomalies
                ADD CONSTRAINT chk_anomaly_score
                CHECK (score >= 0);
            """))
            print("✓ Added check constraint on anomalies.score")
        except Exception as e:
            print(f"  Warning: Could not add anomaly score constraint: {e}")

        # 11. Check constraint on entity_relationships.strength (must be positive)
        try:
            conn.execute(text("""
                ALTER TABLE entity_relationships
                DROP CONSTRAINT IF EXISTS chk_relationship_strength;
            """))
            conn.execute(text("""
                ALTER TABLE entity_relationships
                ADD CONSTRAINT chk_relationship_strength
                CHECK (strength >= 0);
            """))
            print("✓ Added check constraint on entity_relationships.strength")
        except Exception as e:
            print(f"  Warning: Could not add relationship strength constraint: {e}")

        conn.commit()
        print("\n✅ Database constraints migration complete!")


if __name__ == "__main__":
    print("=" * 60)
    print("ArkhamMirror v0.1.5 Database Constraints Migration")
    print("=" * 60)
    add_constraints()
