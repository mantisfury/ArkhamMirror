import os
from qdrant_client import QdrantClient
from dotenv import load_dotenv

load_dotenv()

qdrant_client = QdrantClient(url=os.getenv("QDRANT_URL"))
COLLECTION_NAME = "arkham_mirror_hybrid"

try:
    qdrant_client.delete_collection(COLLECTION_NAME)
    print(f"Deleted collection {COLLECTION_NAME}")
except Exception as e:
    print(f"Error deleting collection: {e}")
