"""
Database migration script for Timeline Analysis feature (v0.3).

This script adds two new tables:
1. timeline_events - Stores extracted events with dates and descriptions
2. date_mentions - Stores all date references found in text

Run this script ONCE after pulling the timeline analysis update:
    python backend/db/migrate_timeline.py

This is safe to run on existing databases - it only adds new tables.
"""

import os
import sys
from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from backend.db.models import Base, TimelineEvent, DateMention

load_dotenv()

def migrate():
    """Add timeline_events and date_mentions tables to the database."""
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        print("❌ ERROR: DATABASE_URL not found in environment")
        print("   Please ensure .env file exists with DATABASE_URL set")
        sys.exit(1)

    print(f"🔗 Connecting to database...")
    engine = create_engine(database_url)
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()

    print(f"📊 Found {len(existing_tables)} existing tables")

    # Check which tables need to be created
    tables_to_create = []

    if "timeline_events" not in existing_tables:
        tables_to_create.append("timeline_events")
    else:
        print("   ⏩ timeline_events already exists, skipping")

    if "date_mentions" not in existing_tables:
        tables_to_create.append("date_mentions")
    else:
        print("   ⏩ date_mentions already exists, skipping")

    if not tables_to_create:
        print("\n✅ All timeline tables already exist. No migration needed.")
        return

    print(f"\n📝 Creating {len(tables_to_create)} new table(s): {', '.join(tables_to_create)}")

    # Create only the timeline-related tables
    try:
        TimelineEvent.__table__.create(bind=engine, checkfirst=True)
        DateMention.__table__.create(bind=engine, checkfirst=True)

        print("\n✅ Migration complete!")
        print("\n📋 New tables added:")
        print("   - timeline_events: Stores extracted events with temporal information")
        print("   - date_mentions: Stores all date references found in text")
        print("\n💡 Next steps:")
        print("   1. Process documents to extract timeline events")
        print("   2. View timeline in Streamlit: 4_Visualizations.py > 'Timeline Analysis'")

    except Exception as e:
        print(f"\n❌ Migration failed: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    print("=" * 60)
    print("  Timeline Analysis Migration (v0.3)")
    print("=" * 60)
    migrate()
