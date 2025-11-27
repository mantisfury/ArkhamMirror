"""
Database migration script for v0.2 Data Extraction features.

This script adds:
1. PDF metadata fields to the Document table
2. sensitive_data_matches table for regex search results

Run this script ONCE after pulling the v0.2 data extraction update:
    python backend/db/migrate_v0.2_data_extraction.py

This is safe to run on existing databases - it only adds new columns and tables.
"""

import os
import sys
from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect, text

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from backend.db.models import Base, SensitiveDataMatch

load_dotenv()

def migrate():
    """Add PDF metadata fields and sensitive_data_matches table."""
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        print("❌ ERROR: DATABASE_URL not found in environment")
        print("   Please ensure .env file exists with DATABASE_URL set")
        sys.exit(1)

    print(f"🔗 Connecting to database...")
    engine = create_engine(database_url)
    inspector = inspect(engine)

    print(f"📊 Checking database schema...")

    # Step 1: Check if Document table needs new columns
    existing_columns = [col['name'] for col in inspector.get_columns('documents')]

    pdf_metadata_columns = [
        ('pdf_author', 'VARCHAR'),
        ('pdf_creator', 'VARCHAR'),
        ('pdf_producer', 'VARCHAR'),
        ('pdf_subject', 'VARCHAR'),
        ('pdf_keywords', 'VARCHAR'),
        ('pdf_creation_date', 'TIMESTAMP'),
        ('pdf_modification_date', 'TIMESTAMP'),
        ('pdf_version', 'VARCHAR'),
        ('is_encrypted', 'INTEGER DEFAULT 0'),
        ('file_size_bytes', 'INTEGER')
    ]

    columns_to_add = []
    for col_name, col_type in pdf_metadata_columns:
        if col_name not in existing_columns:
            columns_to_add.append((col_name, col_type))

    # Step 2: Add missing columns
    if columns_to_add:
        print(f"\n📝 Adding {len(columns_to_add)} PDF metadata field(s) to documents table:")
        with engine.connect() as conn:
            for col_name, col_type in columns_to_add:
                try:
                    alter_sql = f"ALTER TABLE documents ADD COLUMN {col_name} {col_type}"
                    print(f"   + {col_name} ({col_type})")
                    conn.execute(text(alter_sql))
                    conn.commit()
                except Exception as e:
                    print(f"   ⚠️ Error adding {col_name}: {str(e)}")

        print("   ✅ PDF metadata fields added")
    else:
        print("   ⏩ PDF metadata fields already exist, skipping")

    # Step 3: Check if sensitive_data_matches table exists
    existing_tables = inspector.get_table_names()

    if "sensitive_data_matches" not in existing_tables:
        print(f"\n📝 Creating sensitive_data_matches table...")
        try:
            SensitiveDataMatch.__table__.create(bind=engine, checkfirst=True)
            print("   ✅ Table created")
        except Exception as e:
            print(f"   ❌ Error creating table: {str(e)}")
            sys.exit(1)
    else:
        print("   ⏩ sensitive_data_matches table already exists, skipping")

    print("\n✅ Migration complete!")
    print("\n📋 New features added:")
    print("   1. PDF Metadata Extraction:")
    print("      - Document author, creator, producer")
    print("      - Creation and modification dates")
    print("      - PDF version and encryption status")
    print("      - File size tracking")
    print("\n   2. Regex Search / Sensitive Data Detection:")
    print("      - SSN (Social Security Numbers)")
    print("      - Credit Card Numbers")
    print("      - Email Addresses")
    print("      - Phone Numbers")
    print("      - IP Addresses, API Keys, IBANs, Bitcoin addresses")
    print("\n💡 Next steps:")
    print("   1. Metadata extraction happens automatically during PDF processing")
    print("   2. Sensitive data detection runs during chunk processing")
    print("   3. View metadata in Search.py document viewer")
    print("   4. Search for sensitive patterns via regex search UI")

if __name__ == "__main__":
    print("=" * 60)
    print("  v0.2 Data Extraction Migration")
    print("  (Regex Search + PDF Metadata Scrubbing)")
    print("=" * 60)
    migrate()
