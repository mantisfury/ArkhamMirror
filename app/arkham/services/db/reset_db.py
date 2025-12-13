from config.settings import DATABASE_URL, REDIS_URL, QDRANT_URL
import os
import sys
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
from qdrant_client import QdrantClient

from app.arkham.services.db.models import Base

load_dotenv()


def reset_db():
    # 1. Reset SQL Database
    database_url = DATABASE_URL
    print(f"Connecting to SQL database...")
    engine = create_engine(database_url)

    print("Dropping all tables...")
    Base.metadata.drop_all(engine)

    print("Recreating all tables...")
    Base.metadata.create_all(engine)
    print("SQL Database reset complete.")

    # 2. Reset Qdrant Collection
    qdrant_url = QDRANT_URL
    if qdrant_url:
        print(f"Connecting to Qdrant at {qdrant_url}...")
        client = QdrantClient(url=qdrant_url)
        collection_name = "arkham_mirror_hybrid"

        try:
            client.delete_collection(collection_name)
            print(f"Deleted collection '{collection_name}'.")
        except Exception as e:
            print(f"Collection '{collection_name}' might not exist or error: {e}")

        # Recreate is handled by ingest worker on first run, but we can do it here too if needed.
        # For now, let's just delete it to ensure a clean slate.
        print("Qdrant reset complete.")

    # 3. Clear Redis Queue (Optional but recommended)
    try:
        from redis import Redis
        from rq import Queue

        redis_url = REDIS_URL
        if redis_url:
            print("Clearing Redis queues...")
            conn = Redis.from_url(redis_url)
            q = Queue(connection=conn)
            q.empty()
            print("Redis default queue cleared.")
    except Exception as e:
        print(f"Redis clear failed: {e}")


if __name__ == "__main__":
    confirm = input("Are you sure you want to WIPE ALL DATA? (yes/no): ")
    if confirm.lower() == "yes":
        reset_db()
    else:
        print("Operation cancelled.")
