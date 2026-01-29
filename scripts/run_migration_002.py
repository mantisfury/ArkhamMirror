#!/usr/bin/env python3
"""
Run migration 002: Worker requeue safety

Adds worker_requeue_count and max_worker_requeues columns to arkham_jobs.jobs table.
"""

import os
import sys
from pathlib import Path

# Load .env from repo root
root = Path(__file__).resolve().parent.parent
env_file = root / ".env"
if env_file.exists():
    from dotenv import load_dotenv
    load_dotenv(env_file)

try:
    import psycopg2
except ImportError:
    print("Install psycopg2: pip install psycopg2-binary")
    sys.exit(1)

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://arkham:arkhampass@localhost:5432/arkhamdb"
)

# Ensure postgresql:// (psycopg2 expects no +asyncpg)
if DATABASE_URL.startswith("postgresql+asyncpg://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://", 1)

def main():
    migration_file = root / "migrations" / "002_worker_requeue_safety.sql"
    
    if not migration_file.exists():
        print(f"Error: Migration file not found: {migration_file}")
        sys.exit(1)
    
    print(f"Connecting to database...")
    print(f"Running migration: {migration_file.name}")
    
    try:
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = True  # Migration uses IF NOT EXISTS, safe to run multiple times
        
        with conn.cursor() as cur:
            # Read and execute migration
            with open(migration_file, 'r', encoding='utf-8') as f:
                migration_sql = f.read()
            
            cur.execute(migration_sql)
            print("Migration 002 completed successfully!")
            
            # Verify columns were added
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_schema = 'arkham_jobs' 
                  AND table_name = 'jobs' 
                  AND column_name IN ('worker_requeue_count', 'max_worker_requeues')
                ORDER BY column_name
            """)
            columns = [row[0] for row in cur.fetchall()]
            
            if 'worker_requeue_count' in columns and 'max_worker_requeues' in columns:
                print("[OK] Verified: worker_requeue_count and max_worker_requeues columns exist")
            else:
                print("[WARNING] Could not verify columns were created")
        
        conn.close()
        
    except psycopg2.Error as e:
        print(f"Database error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
