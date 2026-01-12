"""Text chunking for embeddings."""

import logging
from typing import List
from uuid import uuid4

from .models import TextChunk

logger = logging.getLogger(__name__)


class TextChunker:
    """
    Chunk text into embedding-ready segments.

    Strategies:
    - Fixed size: Split at N characters/tokens
    - Sentence-based: Split at sentence boundaries
    - Semantic: Split at topic changes (requires analysis)
    """

    def __init__(
        self,
        chunk_size: int = 500,
        overlap: int = 50,
        method: str = "fixed",
    ):
        """
        Initialize chunker.

        Args:
            chunk_size: Target chunk size in characters
            overlap: Overlap between chunks
            method: Chunking method (fixed, sentence, semantic)
        """
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.method = method

    def chunk_text(
        self,
        text: str,
        document_id: str,
        page_number: int | None = None,
    ) -> List[TextChunk]:
        """
        Chunk text into segments.

        Args:
            text: Text to chunk
            document_id: Source document ID
            page_number: Source page number

        Returns:
            List of text chunks
        """
        if self.method == "sentence":
            return self._chunk_by_sentences(text, document_id, page_number)
        elif self.method == "semantic":
            return self._chunk_semantic(text, document_id, page_number)
        else:
            return self._chunk_fixed(text, document_id, page_number)

    def _chunk_fixed(
        self,
        text: str,
        document_id: str,
        page_number: int | None = None,
    ) -> List[TextChunk]:
        """
        Chunk text at fixed character intervals.

        Args:
            text: Text to chunk
            document_id: Source document ID
            page_number: Source page number

        Returns:
            List of text chunks
        """
        chunks = []
        text_len = len(text)
        chunk_index = 0

        # Ensure step is at least 1 to prevent infinite loops
        step = max(1, self.chunk_size - self.overlap)

        i = 0
        while i < text_len:
            chunk_end = min(i + self.chunk_size, text_len)
            chunk_text = text[i:chunk_end]

            chunk = TextChunk(
                id=str(uuid4()),
                text=chunk_text,
                chunk_index=chunk_index,
                document_id=document_id,
                page_number=page_number,
                chunk_method="fixed",
                char_start=i,
                char_end=chunk_end,
                token_count=len(chunk_text.split()),
            )
            chunks.append(chunk)

            chunk_index += 1
            i += step

        logger.debug(f"Created {len(chunks)} fixed chunks")
        return chunks

    def _chunk_by_sentences(
        self,
        text: str,
        document_id: str,
        page_number: int | None = None,
    ) -> List[TextChunk]:
        """
        Chunk text at sentence boundaries.

        Args:
            text: Text to chunk
            document_id: Source document ID
            page_number: Source page number

        Returns:
            List of text chunks
        """
        # Simple sentence splitting on period, exclamation, question mark
        import re
        sentences = re.split(r'[.!?]+', text)

        chunks = []
        chunk_index = 0
        current_chunk = []
        current_size = 0
        char_start = 0

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            sentence_len = len(sentence)

            if current_size + sentence_len > self.chunk_size and current_chunk:
                # Create chunk
                chunk_text = ' '.join(current_chunk)
                chunk = TextChunk(
                    id=str(uuid4()),
                    text=chunk_text,
                    chunk_index=chunk_index,
                    document_id=document_id,
                    page_number=page_number,
                    chunk_method="sentence",
                    char_start=char_start,
                    char_end=char_start + len(chunk_text),
                    token_count=len(chunk_text.split()),
                )
                chunks.append(chunk)

                chunk_index += 1
                char_start += len(chunk_text)
                current_chunk = []
                current_size = 0

            current_chunk.append(sentence)
            current_size += sentence_len

        # Add final chunk
        if current_chunk:
            chunk_text = ' '.join(current_chunk)
            chunk = TextChunk(
                id=str(uuid4()),
                text=chunk_text,
                chunk_index=chunk_index,
                document_id=document_id,
                page_number=page_number,
                chunk_method="sentence",
                char_start=char_start,
                char_end=char_start + len(chunk_text),
                token_count=len(chunk_text.split()),
            )
            chunks.append(chunk)

        logger.debug(f"Created {len(chunks)} sentence chunks")
        return chunks

    def _chunk_semantic(
        self,
        text: str,
        document_id: str,
        page_number: int | None = None,
    ) -> List[TextChunk]:
        """
        Chunk text at semantic boundaries (topic changes).

        Uses sentence embeddings to detect topic shifts by measuring
        cosine similarity between adjacent sentence groups. When similarity
        drops below a threshold, a new chunk is started.

        Args:
            text: Text to chunk
            document_id: Source document ID
            page_number: Source page number

        Returns:
            List of text chunks
        """
        import re
        import numpy as np

        # Split into sentences
        sentences = re.split(r'(?<=[.!?])\s+', text)
        sentences = [s.strip() for s in sentences if s.strip()]

        if len(sentences) < 3:
            # Too few sentences, fall back to sentence chunking
            return self._chunk_by_sentences(text, document_id, page_number)

        # Try to get embeddings for semantic similarity
        embeddings = self._get_sentence_embeddings(sentences)

        if embeddings is None:
            # No embedding model available, fall back to sentence chunking
            logger.debug("No embedding model available, using sentence chunking")
            return self._chunk_by_sentences(text, document_id, page_number)

        # Calculate similarity between adjacent sentence windows
        # Use a sliding window of 2 sentences for comparison
        window_size = 2
        similarities = []

        for i in range(len(sentences) - window_size):
            # Get embeddings for current window and next window
            current_window = embeddings[i:i + window_size]
            next_window = embeddings[i + 1:i + 1 + window_size]

            # Calculate mean embedding for each window
            current_mean = np.mean(current_window, axis=0)
            next_mean = np.mean(next_window, axis=0)

            # Cosine similarity
            similarity = np.dot(current_mean, next_mean) / (
                np.linalg.norm(current_mean) * np.linalg.norm(next_mean) + 1e-8
            )
            similarities.append(similarity)

        # Find breakpoints where similarity drops significantly
        # Use adaptive threshold based on distribution
        if similarities:
            mean_sim = np.mean(similarities)
            std_sim = np.std(similarities)
            threshold = mean_sim - std_sim  # Break at significant drops
            threshold = max(threshold, 0.5)  # Minimum threshold
        else:
            threshold = 0.7

        # Build chunks based on breakpoints
        chunks = []
        chunk_index = 0
        current_sentences = []
        current_size = 0
        char_start = 0

        for i, sentence in enumerate(sentences):
            current_sentences.append(sentence)
            current_size += len(sentence)

            # Check if we should break here
            should_break = False

            # Break on semantic boundary (low similarity to next)
            if i < len(similarities) and similarities[i] < threshold:
                should_break = True

            # Also break if chunk is getting too large
            if current_size >= self.chunk_size:
                should_break = True

            # Minimum chunk size check
            if should_break and current_size < self.chunk_size // 3:
                should_break = False  # Don't create tiny chunks

            if should_break and current_sentences:
                chunk_text = ' '.join(current_sentences)
                chunk = TextChunk(
                    id=str(uuid4()),
                    text=chunk_text,
                    chunk_index=chunk_index,
                    document_id=document_id,
                    page_number=page_number,
                    chunk_method="semantic",
                    char_start=char_start,
                    char_end=char_start + len(chunk_text),
                    token_count=len(chunk_text.split()),
                )
                chunks.append(chunk)

                chunk_index += 1
                char_start += len(chunk_text) + 1
                current_sentences = []
                current_size = 0

        # Add final chunk
        if current_sentences:
            chunk_text = ' '.join(current_sentences)
            chunk = TextChunk(
                id=str(uuid4()),
                text=chunk_text,
                chunk_index=chunk_index,
                document_id=document_id,
                page_number=page_number,
                chunk_method="semantic",
                char_start=char_start,
                char_end=char_start + len(chunk_text),
                token_count=len(chunk_text.split()),
            )
            chunks.append(chunk)

        logger.debug(f"Created {len(chunks)} semantic chunks (threshold={threshold:.3f})")
        return chunks

    def _get_sentence_embeddings(self, sentences: List[str]) -> "np.ndarray | None":
        """
        Get embeddings for sentences using available embedding model.

        Args:
            sentences: List of sentences to embed

        Returns:
            numpy array of embeddings or None if not available
        """
        try:
            # Try to use sentence-transformers if available
            from sentence_transformers import SentenceTransformer
            import numpy as np

            # Use a lightweight model for chunking
            # This is cached after first load
            if not hasattr(self, '_embed_model'):
                try:
                    self._embed_model = SentenceTransformer('all-MiniLM-L6-v2')
                except Exception as e:
                    logger.warning(f"Could not load embedding model: {e}")
                    self._embed_model = None

            if self._embed_model is None:
                return None

            embeddings = self._embed_model.encode(sentences, show_progress_bar=False)
            return np.array(embeddings)

        except ImportError:
            logger.debug("sentence-transformers not available for semantic chunking")
            return None
        except Exception as e:
            logger.warning(f"Error getting embeddings: {e}")
            return None
