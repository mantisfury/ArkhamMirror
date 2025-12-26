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

        This is more complex and would use NLP to detect topic shifts.
        For now, fall back to sentence chunking.

        Args:
            text: Text to chunk
            document_id: Source document ID
            page_number: Source page number

        Returns:
            List of text chunks
        """
        # TODO: Implement semantic chunking
        # Would need topic modeling or embedding similarity
        return self._chunk_by_sentences(text, document_id, page_number)
