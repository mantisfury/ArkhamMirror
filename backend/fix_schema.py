import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

engine = create_engine(os.getenv("DATABASE_URL"))


def run_migration():
    with engine.connect() as conn:
        print("Starting schema migration...")

        # 1. Create projects table if not exists
        print("Checking/Creating projects table...")
        conn.execute(
            text("""
            CREATE TABLE IF NOT EXISTS projects (
                id SERIAL PRIMARY KEY,
                name VARCHAR UNIQUE NOT NULL,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        )

        # 2. Create clusters table if not exists
        print("Checking/Creating clusters table...")
        conn.execute(
            text("""
            CREATE TABLE IF NOT EXISTS clusters (
                id SERIAL PRIMARY KEY,
                project_id INTEGER REFERENCES projects(id),
                label INTEGER NOT NULL,
                name VARCHAR,
                description TEXT,
                size INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        )

        # 3. Add cluster_id to documents if not exists
        print("Checking documents table for cluster_id...")
        try:
            conn.execute(
                text(
                    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS cluster_id INTEGER REFERENCES clusters(id);"
                )
            )
            print("Added cluster_id column to documents (if it didn't exist).")
        except Exception as e:
            print(f"Note on cluster_id: {e}")

        # 4. Add project_id to documents if not exists (just in case)
        print("Checking documents table for project_id...")
        try:
            conn.execute(
                text(
                    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS project_id INTEGER REFERENCES projects(id);"
                )
            )
            print("Added project_id column to documents (if it didn't exist).")
        except Exception as e:
            print(f"Note on project_id: {e}")

        conn.commit()
        print("✅ Migration complete.")


if __name__ == "__main__":
    run_migration()
