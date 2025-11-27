import os
import sys
import time
from tqdm import tqdm

# Add parent dir to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from qdrant_client import QdrantClient, models
from dotenv import load_dotenv

from backend.db.models import Document, Chunk
from backend.embedding_services import get_provider, embed_hybrid
from backend.config import get_config

load_dotenv()


def reindex():
    print(
        "⚠️  WARNING: This will DELETE the existing vector collection and re-embed all documents."
    )
    print("    This is required when switching embedding providers.")
    confirm = input("Type 'yes' to continue: ")

    if confirm.lower() != "yes":
        print("Aborted.")
        return

    # 1. Setup
    DATABASE_URL = os.getenv("DATABASE_URL")
    QDRANT_URL = os.getenv("QDRANT_URL")
    COLLECTION_NAME = "arkham_mirror_hybrid"

    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    qdrant = QdrantClient(url=QDRANT_URL)

    # 2. Initialize Provider
    print("Loading embedding provider...")
    provider = get_provider()
    dense_dim = provider.dense_dimension
    print(f"Provider loaded. Dense dimension: {dense_dim}")

    # 3. Re-create Collection
    print(f"Re-creating collection '{COLLECTION_NAME}'...")
    qdrant.recreate_collection(
        collection_name=COLLECTION_NAME,
        vectors_config={
            "dense": models.VectorParams(
                size=dense_dim,
                distance=models.Distance.COSINE,
            )
        },
        sparse_vectors_config={
            "sparse": models.SparseVectorParams(
                index=models.SparseIndexParams(
                    on_disk=False,
                )
            )
        },
    )
    print("Collection created.")

    # 4. Fetch Chunks
    print("Fetching chunks from database...")
    total_chunks = session.query(Chunk).count()
    print(f"Found {total_chunks} chunks to re-index.")

    chunks = session.query(Chunk).all()

    # 5. Re-embed and Upsert
    batch_size = 50
    points = []

    for chunk in tqdm(chunks, desc="Re-indexing"):
        try:
            # Generate new embedding
            emb_result = provider.encode(chunk.text)

            # Fetch doc metadata (could optimize this with a join)
            doc = session.query(Document).get(chunk.doc_id)
            if not doc:
                continue

            point = models.PointStruct(
                id=chunk.id,
                vector={
                    "dense": emb_result["dense"],
                    "sparse": {
                        "indices": list(map(int, emb_result["sparse"].keys())),
                        "values": list(map(float, emb_result["sparse"].values())),
                    },
                },
                payload={
                    "doc_id": doc.id,
                    "text": chunk.text,
                    "doc_type": doc.doc_type,
                    "project_id": doc.project_id,
                    "chunk_index": chunk.chunk_index,
                },
            )
            points.append(point)

            if len(points) >= batch_size:
                qdrant.upsert(collection_name=COLLECTION_NAME, points=points)
                points = []

        except Exception as e:
            print(f"Error processing chunk {chunk.id}: {e}")

    # Upsert remaining
    if points:
        qdrant.upsert(collection_name=COLLECTION_NAME, points=points)

    print("✅ Re-indexing complete.")
    session.close()


if __name__ == "__main__":
    reindex()
