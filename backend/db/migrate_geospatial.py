import os
import sys
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker

# Add parent directory to path to allow imports
sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from backend.config import get_settings


def migrate_geospatial():
    """
    Add geospatial columns to canonical_entities table.
    """
    settings = get_settings()
    db_url = f"postgresql://{settings.db_user}:{settings.db_password}@{settings.db_host}:{settings.db_port}/{settings.db_name}"

    engine = create_engine(db_url)
    inspector = inspect(engine)

    print("🔍 Checking database schema for geospatial columns...")

    # Check if canonical_entities table exists
    if not inspector.has_table("canonical_entities"):
        print(
            "❌ Table 'canonical_entities' does not exist! Run previous migrations first."
        )
        return

    columns = [col["name"] for col in inspector.get_columns("canonical_entities")]

    with engine.connect() as conn:
        # Add latitude
        if "latitude" not in columns:
            print("➕ Adding 'latitude' column...")
            conn.execute(
                text("ALTER TABLE canonical_entities ADD COLUMN latitude FLOAT")
            )
        else:
            print("✅ 'latitude' column already exists.")

        # Add longitude
        if "longitude" not in columns:
            print("➕ Adding 'longitude' column...")
            conn.execute(
                text("ALTER TABLE canonical_entities ADD COLUMN longitude FLOAT")
            )
        else:
            print("✅ 'longitude' column already exists.")

        # Add resolved_address
        if "resolved_address" not in columns:
            print("➕ Adding 'resolved_address' column...")
            conn.execute(
                text(
                    "ALTER TABLE canonical_entities ADD COLUMN resolved_address VARCHAR"
                )
            )
        else:
            print("✅ 'resolved_address' column already exists.")

        conn.commit()

    print("✨ Geospatial migration completed successfully!")


if __name__ == "__main__":
    migrate_geospatial()
