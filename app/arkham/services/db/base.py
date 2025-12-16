from abc import ABC, abstractmethod
from typing import Dict, List, Union


class EmbeddingProvider(ABC):
    """Abstract base class for all embedding providers."""

    @property
    @abstractmethod
    def dense_dimension(self) -> int:
        """Returns size of dense vector (e.g., 1024 for BGE-m3, 384 for MiniLM)."""
        pass

    @abstractmethod
    def encode(self, text: str) -> Dict[str, Union[List[float], Dict[int, float]]]:
        """
        Encode text into dense and sparse vectors.

        Returns:
            {
                "dense": List[float],      # Always present
                "sparse": Dict[int, float] # Empty dict if not supported
            }
        """
        pass
