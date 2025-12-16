import unittest
from app.arkham.services.db.bge_m3 import BGEM3Provider
from backend.embedding_providers.minilm_bm25 import MiniLMBM25Provider


class TestEmbeddingProviders(unittest.TestCase):
    def test_bge_m3_provider(self):
        # Initialize with CPU to avoid CUDA errors in test env if GPU not available
        provider = BGEM3Provider(device="cpu")
        text = "This is a test document."
        result = provider.encode(text)

        self.assertIn("dense", result)
        self.assertIn("sparse", result)
        self.assertEqual(len(result["dense"]), 1024)
        self.assertIsInstance(result["sparse"], dict)
        # BGE-M3 sparse weights are usually non-empty for normal text
        self.assertTrue(len(result["sparse"]) > 0)

    def test_minilm_bm25_provider(self):
        provider = MiniLMBM25Provider(device="cpu")
        text = "This is a test document."
        result = provider.encode(text)

        self.assertIn("dense", result)
        self.assertIn("sparse", result)
        self.assertEqual(len(result["dense"]), 384)
        self.assertIsInstance(result["sparse"], dict)
        self.assertTrue(len(result["sparse"]) > 0)


if __name__ == "__main__":
    unittest.main()
