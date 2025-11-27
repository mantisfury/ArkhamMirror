import unittest
import os
from dotenv import load_dotenv
from qdrant_client import QdrantClient, models
from backend.embedding_services import embed_hybrid
from backend.config import get_config

# Load env vars
load_dotenv()


class TestHybridSearchIntegration(unittest.TestCase):
    def setUp(self):
        self.qdrant_client = QdrantClient(url=os.getenv("QDRANT_URL"))
        self.collection_name = "arkham_mirror_hybrid"

        # Check if collection exists, if not, skip
        collections = self.qdrant_client.get_collections().collections
        if not any(c.name == self.collection_name for c in collections):
            self.skipTest(f"Collection {self.collection_name} does not exist")

    def test_hybrid_search_execution(self):
        """Test that the hybrid search query structure is valid and executes."""
        query_text = "test query"
        q_vecs = embed_hybrid(query_text)

        # Prepare sparse vector
        sparse_indices = list(map(int, q_vecs["sparse"].keys()))
        sparse_values = list(map(float, q_vecs["sparse"].values()))
        sparse_vector = models.SparseVector(
            indices=sparse_indices, values=sparse_values
        )

        limit = 5

        try:
            hits = self.qdrant_client.query_points(
                collection_name=self.collection_name,
                prefetch=[
                    models.Prefetch(
                        query=q_vecs["dense"],
                        using="dense",
                        limit=limit,
                    ),
                    models.Prefetch(
                        query=sparse_vector,
                        using="sparse",
                        limit=limit,
                    ),
                ],
                query=models.FusionQuery(fusion=models.Fusion.RRF),
                limit=limit,
            ).points

            # If we get here, the query structure is valid
            print(f"Hybrid search executed successfully. Found {len(hits)} hits.")

        except Exception as e:
            self.fail(f"Hybrid search query failed: {e}")


if __name__ == "__main__":
    unittest.main()
