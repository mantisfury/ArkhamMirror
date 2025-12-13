"""
Migration: Add anomaly_keywords table.

Enables configurable anomaly detection keywords.
"""

import os
import sys
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

from config.settings import DATABASE_URL

load_dotenv()

def migrate():
    """Add anomaly_keywords table and seed defaults."""
    if not DATABASE_URL:
        print("❌ ERROR: DATABASE_URL not set")
        return False

    try:
        engine = create_engine(DATABASE_URL)
        with engine.connect() as conn:
            # Check if table already exists
            result = conn.execute(
                text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'anomaly_keywords'
                );
            """)
            ).scalar()
            
            if result:
                print("   >> Table 'anomaly_keywords' already exists, skipping")
                return True

            # Create table
            print("   + Creating 'anomaly_keywords' table...")
            conn.execute(
                text("""
                CREATE TABLE anomaly_keywords (
                    id SERIAL PRIMARY KEY,
                    keyword VARCHAR(255) NOT NULL UNIQUE,
                    weight FLOAT DEFAULT 0.2,
                    is_active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            )
            
            # Seed default keywords
            defaults = ["confidential", "secret", "delete", "shred", "hidden"]
            print(f"   + Seeding {len(defaults)} default keywords...")
            
            for kw in defaults:
                conn.execute(
                    text("""
                    INSERT INTO anomaly_keywords (keyword, weight)
                    VALUES (:keyword, 0.2)
                    ON CONFLICT (keyword) DO NOTHING
                """),
                    {"keyword": kw}
                )

            conn.commit()
            print("   OK Migration successful")
            return True
    except Exception as e:
        print(f"   !! Migration failed: {e}")
        return False

if __name__ == "__main__":
    print("Running Anomaly Keywords Migration...")
    migrate()
