from backend.config import get_config
from backend.embedding_providers.bge_m3 import BGEM3Provider
from backend.embedding_providers.minilm_bm25 import MiniLMBM25Provider

_provider_instance = None


def get_provider():
    """
    Factory function to get the configured embedding provider instance.
    Singleton pattern to avoid reloading models.
    """
    global _provider_instance
    if _provider_instance is None:
        provider_name = get_config("embedding.provider", "bge-m3")
        device = get_config("embedding.device", "cpu")

        if provider_name == "bge-m3":
            model_name = get_config(
                "embedding.providers.bge-m3.model_name", "BAAI/bge-m3"
            )
            _provider_instance = BGEM3Provider(model_name=model_name, device=device)
        elif provider_name == "minilm-bm25":
            model_name = get_config(
                "embedding.providers.minilm-bm25.dense_model",
                "sentence-transformers/all-MiniLM-L6-v2",
            )
            _provider_instance = MiniLMBM25Provider(
                model_name=model_name, device=device
            )
        else:
            raise ValueError(f"Unknown embedding provider: {provider_name}")

    return _provider_instance


def embed_hybrid(text):
    """
    Generates hybrid embeddings (dense + sparse) using the configured provider.

    Returns:
        {
            "dense": List[float],
            "sparse": Dict[int, float]
        }
    """
    provider = get_provider()
    return provider.encode(text)
