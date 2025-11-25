import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from qdrant_client import QdrantClient
from dotenv import load_dotenv
from backend.db.models import Base

load_dotenv()

# 1. Connect to DB
engine = create_engine(os.getenv("DATABASE_URL"))
Session = sessionmaker(bind=engine)
session = Session()

print("⚠️  WARNING: This will delete ALL data in the database and vector store.")
confirm = input("Type 'DELETE' to confirm: ")

if confirm == "DELETE":
    try:
        # 2. Wipe SQL Data
        print("🗑️  Dropping all SQL tables...")
        Base.metadata.drop_all(engine)
        print("✅ SQL tables dropped.")

        # Re-create empty tables
        print("🔨 Re-creating tables...")
        Base.metadata.create_all(engine)
        print("✅ Tables re-created.")

        # 3. Wipe Qdrant Data
        qdrant_client = QdrantClient(url=os.getenv("QDRANT_URL"))
        COLLECTION_NAME = "arkham_mirror_hybrid"

        print(f"🗑️  Deleting Qdrant collection '{COLLECTION_NAME}'...")
        qdrant_client.delete_collection(COLLECTION_NAME)
        print("✅ Collection deleted.")

        # Re-create collection (will be handled by ingest_worker on next run, but good to be clean)

        print("\n✨ System reset complete. You can now start fresh.")

    except Exception as e:
        print(f"❌ Error during reset: {e}")
    finally:
        session.close()
else:
    print("❌ Reset cancelled.")
