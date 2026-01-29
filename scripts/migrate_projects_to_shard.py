#!/usr/bin/env python3
"""
Migration script: Copy projects from arkham_frame.projects to public.arkham_projects

This unifies project storage so the projects shard's member/document tables 
can reference projects correctly.

Run from repo root:
  python scripts/migrate_projects_to_shard.py

Uses DATABASE_URL from env, or postgresql://arkham:arkhampass@localhost:5432/arkhamdb.
"""
import os
import sys
import json
from pathlib import Path
from datetime import datetime, timezone

# Load .env from repo root
root = Path(__file__).resolve().parent.parent
env_file = root / ".env"
if env_file.exists():
    from dotenv import load_dotenv
    load_dotenv(env_file)

try:
    import psycopg2
    from psycopg2.extras import execute_values
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
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    cur = conn.cursor()

    # 1) Check if arkham_frame.projects exists and has data
    cur.execute("""
        SELECT COUNT(*) 
        FROM information_schema.tables 
        WHERE table_schema = 'arkham_frame' AND table_name = 'projects'
    """)
    table_exists = cur.fetchone()[0] > 0
    
    if not table_exists:
        print("Table arkham_frame.projects does not exist. Nothing to migrate.")
        conn.close()
        return

    cur.execute("SELECT COUNT(*) FROM arkham_frame.projects")
    count = cur.fetchone()[0]
    print(f"Found {count} project(s) in arkham_frame.projects")

    if count == 0:
        print("No projects to migrate.")
        conn.close()
        return

    # 2) Fetch all projects from arkham_frame.projects
    cur.execute("""
        SELECT 
            id,
            name,
            COALESCE(description, '') as description,
            created_at,
            updated_at,
            settings,
            metadata
        FROM arkham_frame.projects
    """)
    frame_projects = cur.fetchall()

    # 3) Insert/update into public.arkham_projects
    now = datetime.now(timezone.utc).isoformat()
    migrated = 0
    
    for proj in frame_projects:
        proj_id, name, desc, created, updated, settings, metadata = proj
        
        # Parse settings JSONB to extract status and owner_id
        settings_dict = {}
        status = 'active'
        owner_id = 'system'
        
        if settings:
            if isinstance(settings, str):
                try:
                    settings_dict = json.loads(settings)
                except:
                    settings_dict = {}
            else:
                settings_dict = settings if isinstance(settings, dict) else {}
            
            status = settings_dict.get('status', 'active')
            owner_id = settings_dict.get('owner_id', 'system')
        
        # Convert timestamps to ISO strings
        created_str = created.isoformat() if hasattr(created, 'isoformat') else str(created) if created else now
        updated_str = updated.isoformat() if hasattr(updated, 'isoformat') else str(updated) if updated else now
        
        # Serialize settings and metadata
        settings_str = json.dumps(settings_dict) if settings_dict else '{}'
        metadata_str = json.dumps(metadata) if metadata else '{}'
        if not isinstance(metadata_str, str):
            metadata_str = json.dumps(metadata_str)
        
        try:
            cur.execute("""
                INSERT INTO public.arkham_projects 
                (id, name, description, status, owner_id, created_at, updated_at, settings, metadata, member_count, document_count)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 0, 0)
                ON CONFLICT (id) DO UPDATE SET
                    name = EXCLUDED.name,
                    description = EXCLUDED.description,
                    updated_at = EXCLUDED.updated_at,
                    settings = EXCLUDED.settings
            """, (proj_id, name, desc or '', status, owner_id, created_str, updated_str, settings_str, metadata_str))
            migrated += 1
        except Exception as e:
            print(f"Warning: Failed to migrate project {proj_id} ({name}): {e}")
            conn.rollback()
            continue

    conn.commit()
    print(f"Migrated {migrated} project(s) to public.arkham_projects")

    # 4) Update member_count and document_count from existing associations
    print("Updating member_count and document_count...")
    cur.execute("""
        UPDATE public.arkham_projects p SET
            member_count = (
                SELECT COUNT(*) 
                FROM arkham_project_members m 
                WHERE m.project_id = p.id
            ),
            document_count = (
                SELECT COUNT(*) 
                FROM arkham_project_documents d 
                WHERE d.project_id = p.id
            )
    """)
    conn.commit()
    print("Updated project counts from existing associations.")

    cur.close()
    conn.close()
    print("Migration complete.")


if __name__ == "__main__":
    main()
