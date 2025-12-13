import torch
import logging
from sentence_transformers import SentenceTransformer
from collections import Counter
from .base import EmbeddingProvider

logger = logging.getLogger(__name__)


class MiniLMBM25Provider(EmbeddingProvider):
    """
    Lightweight provider using MiniLM for dense and TF (Bag-of-Words) for sparse.

    Note: While named 'BM25', this implementation currently uses Term Frequency (TF)
    for the sparse weights because global IDF is not available at ingestion time
    without a pre-computed model. This still enables effective exact-keyword matching
    via Qdrant's sparse index.
    """

    def __init__(
        self,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        device: str = None,
    ):
        if device is None:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device

        logger.info(f"Loading MiniLM Model ({model_name}) on {self.device}...")
        self.model = SentenceTransformer(model_name, device=self.device)
        self.tokenizer = self.model.tokenizer

    @property
    def dense_dimension(self) -> int:
        return 384

    def encode(self, text: str) -> dict:
        # Dense embedding
        dense = self.model.encode(text).tolist()

        # Sparse embedding (TF)
        # We use the model's tokenizer to ensure consistent tokenization
        # Qdrant expects integer indices for sparse vectors
        tokens = self.tokenizer.tokenize(text)
        input_ids = self.tokenizer.convert_tokens_to_ids(tokens)

        # Calculate Term Frequency
        # TODO: In v0.4, consider loading a pre-computed IDF dictionary for true BM25
        counts = Counter(input_ids)

        # Convert to float for consistency with BGE-M3 interface
        sparse = {k: float(v) for k, v in counts.items()}

        return {"dense": dense, "sparse": sparse}
