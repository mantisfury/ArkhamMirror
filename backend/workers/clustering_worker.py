import os
import sys
import numpy as np
import hdbscan
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from qdrant_client import QdrantClient
from dotenv import load_dotenv
from backend.db.models import Document, Cluster, Chunk, Base
from openai import OpenAI
import argparse

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

load_dotenv()

# Database Setup
engine = create_engine(os.getenv("DATABASE_URL"))
Session = sessionmaker(bind=engine)
Base.metadata.create_all(engine)

# Qdrant Setup
qdrant_client = QdrantClient(url=os.getenv("QDRANT_URL"))
COLLECTION_NAME = "arkham_mirror_hybrid"

# LLM Setup
llm_client = OpenAI(base_url=os.getenv("LM_STUDIO_URL"), api_key="lm-studio")


def generate_cluster_name(texts):
    """Generates a short name for a cluster based on a sample of its texts."""
    if not texts:
        return "Unknown Cluster"

    # Take a sample of texts (first 500 chars of first 5 docs)
    context = "\n---\n".join([t[:500] for t in texts[:5]])

    try:
        response = llm_client.chat.completions.create(
            model="local-model",
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful librarian. Read the following document snippets and generate a short, specific topic name (max 5 words) that describes them all. Do not use quotes.",
                },
                {
                    "role": "user",
                    "content": f"Snippets:\n{context}\n\nTopic Name:",
                },
            ],
            temperature=0.3,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"LLM Error: {e}")
        return "Unnamed Cluster"


def run_clustering(project_id=None):
    session = Session()
    try:
        print(f"Starting clustering (Project ID: {project_id})...")

        # 1. Fetch Documents
        query = session.query(Document)
        if project_id:
            query = query.filter(Document.project_id == project_id)
        docs = query.all()

        if not docs:
            print("No documents found to cluster.")
            return

        print(f"Found {len(docs)} documents. Fetching vectors...")

        # 2. Fetch Vectors & Compute Centroids
        doc_vectors = []
        valid_doc_ids = []

        for doc in docs:
            # Get all chunks for this doc
            chunks = session.query(Chunk).filter(Chunk.doc_id == doc.id).all()
            if not chunks:
                continue

            # Retrieve vectors from Qdrant for these chunks
            # Note: This is inefficient for huge datasets, but fine for local use.
            # Ideally we'd store the doc centroid in the DB or Qdrant payload.
            chunk_ids = [c.id for c in chunks]
            points = qdrant_client.retrieve(
                collection_name=COLLECTION_NAME, ids=chunk_ids, with_vectors=True
            )

            vectors = [p.vector["dense"] for p in points if p.vector]
            if vectors:
                centroid = np.mean(vectors, axis=0)
                doc_vectors.append(centroid)
                valid_doc_ids.append(doc.id)

        if not doc_vectors:
            print("No vectors found.")
            return

        X = np.array(doc_vectors)
        print(f"Clustering {len(X)} document vectors...")

        # 3. Run HDBSCAN
        # min_cluster_size: smallest size grouping that we consider a cluster
        # min_samples: how conservative the clustering is (larger = more noise points)
        clusterer = hdbscan.HDBSCAN(
            min_cluster_size=3, min_samples=2, metric="euclidean"
        )
        labels = clusterer.fit_predict(X)

        # 4. Save Clusters
        # Clear old clusters for this project (optional, but cleaner for re-runs)
        # For now, let's just create new ones and update docs.

        unique_labels = set(labels)
        print(
            f"Found {len(unique_labels) - (1 if -1 in unique_labels else 0)} clusters."
        )

        cluster_map = {}  # label -> Cluster object

        for label in unique_labels:
            if label == -1:
                continue  # Noise

            # Create Cluster Record
            cluster = Cluster(
                project_id=project_id,
                label=int(label),
                name=f"Cluster {label}",  # Placeholder
                size=int(np.sum(labels == label)),
            )
            session.add(cluster)
            session.flush()  # Get ID
            cluster_map[label] = cluster

        # 5. Update Documents & Name Clusters
        print("Updating documents and naming clusters...")

        # Group docs by label for naming
        cluster_docs_text = {label: [] for label in unique_labels if label != -1}

        for doc_id, label in zip(valid_doc_ids, labels):
            doc = session.query(Document).get(doc_id)
            if label != -1:
                doc.cluster_id = cluster_map[label].id
                # Add text for naming
                # Get first chunk text as sample
                first_chunk = (
                    session.query(Chunk).filter(Chunk.doc_id == doc.id).first()
                )
                if first_chunk:
                    cluster_docs_text[label].append(first_chunk.text)
            else:
                doc.cluster_id = None  # Noise

        session.commit()

        # 6. Generate Names with LLM
        for label, texts in cluster_docs_text.items():
            name = generate_cluster_name(texts)
            cluster = cluster_map[label]
            cluster.name = name
            print(f"   - Cluster {label}: {name} ({cluster.size} docs)")

        session.commit()
        print("Clustering complete.")

    except Exception as e:
        print(f"Error: {e}")
        session.rollback()
    finally:
        session.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--project_id", type=int, default=None)
    args = parser.parse_args()
    run_clustering(args.project_id)
