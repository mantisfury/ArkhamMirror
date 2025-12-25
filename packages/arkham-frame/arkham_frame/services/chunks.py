"""
ChunkService - Text chunking strategies and token management.

Provides intelligent text chunking for document processing, with multiple
strategies optimized for different use cases (embedding, LLM context, etc.).
"""

from typing import Optional, List, Dict, Any, Callable, Iterator
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import logging
import re
import uuid

logger = logging.getLogger(__name__)


class ChunkStrategy(str, Enum):
    """Available chunking strategies."""
    FIXED_SIZE = "fixed_size"          # Fixed character count
    FIXED_TOKENS = "fixed_tokens"       # Fixed token count
    SENTENCE = "sentence"               # Sentence-based boundaries
    PARAGRAPH = "paragraph"             # Paragraph-based boundaries
    SEMANTIC = "semantic"               # Semantic similarity based
    RECURSIVE = "recursive"             # Recursive character splitting
    MARKDOWN = "markdown"               # Markdown-aware splitting
    CODE = "code"                       # Code-aware splitting


@dataclass
class TextChunk:
    """A chunk of text with metadata."""
    id: str
    text: str
    index: int                          # Position in original document
    start_char: int                     # Start character offset
    end_char: int                       # End character offset
    token_count: Optional[int] = None   # Estimated token count
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "text": self.text,
            "index": self.index,
            "start_char": self.start_char,
            "end_char": self.end_char,
            "token_count": self.token_count,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TextChunk":
        return cls(
            id=data["id"],
            text=data["text"],
            index=data["index"],
            start_char=data["start_char"],
            end_char=data["end_char"],
            token_count=data.get("token_count"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class ChunkConfig:
    """Configuration for chunking."""
    strategy: ChunkStrategy = ChunkStrategy.RECURSIVE
    chunk_size: int = 1000              # Target chunk size (chars or tokens)
    chunk_overlap: int = 200            # Overlap between chunks
    min_chunk_size: int = 100           # Minimum chunk size
    max_chunk_size: int = 2000          # Maximum chunk size
    separators: List[str] = field(default_factory=lambda: ["\n\n", "\n", ". ", " ", ""])
    respect_sentence_boundary: bool = True
    include_metadata: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy": self.strategy.value if isinstance(self.strategy, ChunkStrategy) else self.strategy,
            "chunk_size": self.chunk_size,
            "chunk_overlap": self.chunk_overlap,
            "min_chunk_size": self.min_chunk_size,
            "max_chunk_size": self.max_chunk_size,
            "separators": self.separators,
            "respect_sentence_boundary": self.respect_sentence_boundary,
            "include_metadata": self.include_metadata,
        }


class ChunkServiceError(Exception):
    """Base chunk service error."""
    pass


class TokenizerError(ChunkServiceError):
    """Tokenizer error."""
    pass


# Precompiled regex patterns
SENTENCE_PATTERN = re.compile(r'(?<=[.!?])\s+')
PARAGRAPH_PATTERN = re.compile(r'\n\s*\n')
MARKDOWN_HEADER_PATTERN = re.compile(r'^#{1,6}\s+.*$', re.MULTILINE)
CODE_BLOCK_PATTERN = re.compile(r'```[\s\S]*?```|`[^`]+`')


class ChunkService:
    """
    Text chunking service with multiple strategies.

    Provides:
        - Multiple chunking strategies (fixed, sentence, semantic, etc.)
        - Token counting with multiple tokenizer support
        - Overlap management for context preservation
        - Metadata preservation through chunks
    """

    # Default tokenizer ratios (chars per token)
    TOKENIZER_RATIOS = {
        "cl100k_base": 4.0,      # GPT-4, GPT-3.5
        "p50k_base": 4.0,        # Codex
        "r50k_base": 4.0,        # GPT-3
        "gpt2": 4.0,             # GPT-2
        "default": 4.0,          # Default estimate
    }

    def __init__(self, config=None):
        self.config = config
        self._tokenizer = None
        self._tokenizer_name = "default"

    async def initialize(self) -> None:
        """Initialize chunking service with optional tokenizer."""
        # Try to load tiktoken for accurate token counting
        try:
            import tiktoken

            tokenizer_name = "cl100k_base"  # GPT-4/3.5 tokenizer
            if self.config:
                tokenizer_name = self.config.get("chunks.tokenizer", tokenizer_name)

            self._tokenizer = tiktoken.get_encoding(tokenizer_name)
            self._tokenizer_name = tokenizer_name
            logger.info(f"ChunkService initialized with tiktoken ({tokenizer_name})")

        except ImportError:
            logger.info("tiktoken not available, using character-based token estimation")
            self._tokenizer = None

        except Exception as e:
            logger.warning(f"Failed to load tiktoken: {e}")
            self._tokenizer = None

    # =========================================================================
    # Token Counting
    # =========================================================================

    def count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        if not text:
            return 0

        if self._tokenizer:
            try:
                return len(self._tokenizer.encode(text))
            except Exception:
                pass

        # Fallback to character-based estimation
        ratio = self.TOKENIZER_RATIOS.get(self._tokenizer_name, 4.0)
        return int(len(text) / ratio)

    def count_tokens_batch(self, texts: List[str]) -> List[int]:
        """Count tokens for multiple texts."""
        return [self.count_tokens(t) for t in texts]

    def truncate_to_tokens(self, text: str, max_tokens: int) -> str:
        """Truncate text to fit within token limit."""
        if not text:
            return ""

        current_tokens = self.count_tokens(text)
        if current_tokens <= max_tokens:
            return text

        if self._tokenizer:
            try:
                tokens = self._tokenizer.encode(text)[:max_tokens]
                return self._tokenizer.decode(tokens)
            except Exception:
                pass

        # Fallback: estimate characters needed
        ratio = self.TOKENIZER_RATIOS.get(self._tokenizer_name, 4.0)
        max_chars = int(max_tokens * ratio)
        return text[:max_chars]

    # =========================================================================
    # Main Chunking Interface
    # =========================================================================

    def chunk(
        self,
        text: str,
        config: Optional[ChunkConfig] = None,
        document_id: Optional[str] = None,
    ) -> List[TextChunk]:
        """
        Chunk text using specified configuration.

        Args:
            text: Text to chunk
            config: Chunking configuration (uses defaults if not provided)
            document_id: Optional document ID for metadata

        Returns:
            List of TextChunk objects
        """
        if not text:
            return []

        config = config or ChunkConfig()

        # Select chunking strategy
        strategy_map = {
            ChunkStrategy.FIXED_SIZE: self._chunk_fixed_size,
            ChunkStrategy.FIXED_TOKENS: self._chunk_fixed_tokens,
            ChunkStrategy.SENTENCE: self._chunk_sentence,
            ChunkStrategy.PARAGRAPH: self._chunk_paragraph,
            ChunkStrategy.RECURSIVE: self._chunk_recursive,
            ChunkStrategy.MARKDOWN: self._chunk_markdown,
            ChunkStrategy.CODE: self._chunk_code,
            ChunkStrategy.SEMANTIC: self._chunk_semantic,
        }

        chunk_fn = strategy_map.get(config.strategy, self._chunk_recursive)
        chunks = chunk_fn(text, config)

        # Add metadata and token counts
        result = []
        for i, (chunk_text, start, end) in enumerate(chunks):
            chunk = TextChunk(
                id=str(uuid.uuid4()),
                text=chunk_text,
                index=i,
                start_char=start,
                end_char=end,
                token_count=self.count_tokens(chunk_text),
                metadata={
                    "document_id": document_id,
                    "strategy": config.strategy.value if isinstance(config.strategy, ChunkStrategy) else config.strategy,
                } if config.include_metadata else {},
            )
            result.append(chunk)

        logger.debug(f"Chunked text into {len(result)} chunks using {config.strategy}")
        return result

    def chunk_document(
        self,
        pages: List[Dict[str, Any]],
        config: Optional[ChunkConfig] = None,
        document_id: Optional[str] = None,
    ) -> List[TextChunk]:
        """
        Chunk a multi-page document.

        Args:
            pages: List of page dicts with 'text' and optional 'page_number'
            config: Chunking configuration
            document_id: Document ID for metadata

        Returns:
            List of TextChunk objects with page metadata
        """
        config = config or ChunkConfig()
        all_chunks = []
        global_index = 0
        char_offset = 0

        for page in pages:
            page_text = page.get("text", "")
            page_num = page.get("page_number", page.get("page_num", 0))

            if not page_text.strip():
                char_offset += len(page_text)
                continue

            # Chunk this page
            page_chunks = self.chunk(page_text, config, document_id)

            # Adjust offsets and add page metadata
            for chunk in page_chunks:
                chunk.start_char += char_offset
                chunk.end_char += char_offset
                chunk.index = global_index
                chunk.metadata["page_number"] = page_num
                all_chunks.append(chunk)
                global_index += 1

            char_offset += len(page_text)

        return all_chunks

    # =========================================================================
    # Chunking Strategies
    # =========================================================================

    def _chunk_fixed_size(
        self,
        text: str,
        config: ChunkConfig,
    ) -> List[tuple[str, int, int]]:
        """Fixed character size chunking."""
        chunks = []
        start = 0
        text_len = len(text)

        while start < text_len:
            end = min(start + config.chunk_size, text_len)

            # Respect sentence boundary if enabled
            if config.respect_sentence_boundary and end < text_len:
                # Look for sentence end within the chunk
                sentence_end = self._find_sentence_boundary(
                    text, start, end, config.min_chunk_size
                )
                if sentence_end > start:
                    end = sentence_end

            chunk_text = text[start:end]

            # Skip empty chunks
            if chunk_text.strip():
                chunks.append((chunk_text, start, end))

            # Move start with overlap
            start = end - config.chunk_overlap
            if start <= chunks[-1][1] if chunks else 0:
                start = end

        return chunks

    def _chunk_fixed_tokens(
        self,
        text: str,
        config: ChunkConfig,
    ) -> List[tuple[str, int, int]]:
        """Fixed token count chunking."""
        chunks = []

        # Use character estimation if no tokenizer
        if not self._tokenizer:
            # Convert token size to character size
            ratio = self.TOKENIZER_RATIOS.get(self._tokenizer_name, 4.0)
            char_config = ChunkConfig(
                strategy=ChunkStrategy.FIXED_SIZE,
                chunk_size=int(config.chunk_size * ratio),
                chunk_overlap=int(config.chunk_overlap * ratio),
                min_chunk_size=int(config.min_chunk_size * ratio),
                max_chunk_size=int(config.max_chunk_size * ratio),
                respect_sentence_boundary=config.respect_sentence_boundary,
            )
            return self._chunk_fixed_size(text, char_config)

        # Token-based chunking
        tokens = self._tokenizer.encode(text)
        start_token = 0

        while start_token < len(tokens):
            end_token = min(start_token + config.chunk_size, len(tokens))

            # Decode chunk
            chunk_tokens = tokens[start_token:end_token]
            chunk_text = self._tokenizer.decode(chunk_tokens)

            # Calculate character offsets (approximate)
            if chunks:
                start_char = chunks[-1][2]
            else:
                start_char = 0
            end_char = start_char + len(chunk_text)

            if chunk_text.strip():
                chunks.append((chunk_text, start_char, end_char))

            # Move with overlap
            start_token = end_token - config.chunk_overlap
            if start_token <= (len(chunks[-1][0]) if chunks else 0):
                start_token = end_token

        return chunks

    def _chunk_sentence(
        self,
        text: str,
        config: ChunkConfig,
    ) -> List[tuple[str, int, int]]:
        """Sentence-based chunking."""
        # Split into sentences
        sentences = SENTENCE_PATTERN.split(text)
        sentences = [s.strip() for s in sentences if s.strip()]

        chunks = []
        current_chunk = []
        current_len = 0
        current_start = 0
        text_offset = 0

        for sentence in sentences:
            sentence_len = len(sentence)

            if current_len + sentence_len > config.chunk_size and current_chunk:
                # Finalize current chunk
                chunk_text = " ".join(current_chunk)
                chunk_end = current_start + len(chunk_text)
                chunks.append((chunk_text, current_start, chunk_end))

                # Start new chunk with overlap
                if config.chunk_overlap > 0:
                    overlap_sentences = []
                    overlap_len = 0
                    for s in reversed(current_chunk):
                        if overlap_len + len(s) <= config.chunk_overlap:
                            overlap_sentences.insert(0, s)
                            overlap_len += len(s)
                        else:
                            break
                    current_chunk = overlap_sentences
                    current_len = sum(len(s) for s in current_chunk)
                    current_start = chunk_end - current_len
                else:
                    current_chunk = []
                    current_len = 0
                    current_start = chunk_end

            current_chunk.append(sentence)
            current_len += sentence_len

        # Add remaining
        if current_chunk:
            chunk_text = " ".join(current_chunk)
            chunk_end = current_start + len(chunk_text)
            chunks.append((chunk_text, current_start, chunk_end))

        return chunks

    def _chunk_paragraph(
        self,
        text: str,
        config: ChunkConfig,
    ) -> List[tuple[str, int, int]]:
        """Paragraph-based chunking."""
        paragraphs = PARAGRAPH_PATTERN.split(text)
        paragraphs = [(p.strip(), text.find(p)) for p in paragraphs if p.strip()]

        chunks = []
        current_paras = []
        current_len = 0
        current_start = 0

        for para, para_offset in paragraphs:
            para_len = len(para)

            if current_len + para_len > config.chunk_size and current_paras:
                # Finalize current chunk
                chunk_text = "\n\n".join(current_paras)
                chunk_end = current_start + len(chunk_text)
                chunks.append((chunk_text, current_start, chunk_end))

                current_paras = []
                current_len = 0
                current_start = para_offset

            current_paras.append(para)
            current_len += para_len
            if not current_paras[:-1]:  # First para in chunk
                current_start = para_offset

        # Add remaining
        if current_paras:
            chunk_text = "\n\n".join(current_paras)
            chunk_end = current_start + len(chunk_text)
            chunks.append((chunk_text, current_start, chunk_end))

        return chunks

    def _chunk_recursive(
        self,
        text: str,
        config: ChunkConfig,
    ) -> List[tuple[str, int, int]]:
        """Recursive character text splitting (LangChain-style)."""
        return self._recursive_split(
            text,
            config.separators,
            config.chunk_size,
            config.chunk_overlap,
            0,  # offset
        )

    def _recursive_split(
        self,
        text: str,
        separators: List[str],
        chunk_size: int,
        chunk_overlap: int,
        offset: int,
    ) -> List[tuple[str, int, int]]:
        """Recursively split text using separators."""
        final_chunks = []

        # Find the best separator
        separator = separators[-1]  # Default to last (usually "")
        for sep in separators:
            if sep == "":
                separator = sep
                break
            if sep in text:
                separator = sep
                break

        # Split text
        if separator:
            splits = text.split(separator)
        else:
            splits = list(text)

        # Merge small splits
        good_splits = []
        current_split = ""

        for split in splits:
            if len(split) < chunk_size:
                if len(current_split) + len(split) + len(separator) <= chunk_size:
                    current_split += (separator if current_split else "") + split
                else:
                    if current_split:
                        good_splits.append(current_split)
                    current_split = split
            else:
                if current_split:
                    good_splits.append(current_split)
                    current_split = ""
                # Recursively split large pieces
                if len(separators) > 1:
                    sub_chunks = self._recursive_split(
                        split, separators[1:], chunk_size, chunk_overlap, offset
                    )
                    final_chunks.extend(sub_chunks)
                else:
                    # Can't split further, add as is
                    final_chunks.append((split, offset, offset + len(split)))
                offset += len(split) + len(separator)

        if current_split:
            good_splits.append(current_split)

        # Convert good splits to chunks
        for split in good_splits:
            start = offset
            end = offset + len(split)
            final_chunks.append((split, start, end))
            offset = end + len(separator)

        return final_chunks

    def _chunk_markdown(
        self,
        text: str,
        config: ChunkConfig,
    ) -> List[tuple[str, int, int]]:
        """Markdown-aware chunking that respects headers."""
        # Find all header positions
        headers = list(MARKDOWN_HEADER_PATTERN.finditer(text))

        if not headers:
            return self._chunk_recursive(text, config)

        chunks = []
        last_end = 0

        for i, header_match in enumerate(headers):
            # Determine section end
            if i + 1 < len(headers):
                section_end = headers[i + 1].start()
            else:
                section_end = len(text)

            section_start = header_match.start()
            section_text = text[section_start:section_end].strip()

            # If section is too large, split it further
            if len(section_text) > config.chunk_size:
                sub_chunks = self._chunk_recursive(
                    section_text,
                    config.separators,
                    config.chunk_size,
                    config.chunk_overlap,
                    section_start,
                )
                chunks.extend(sub_chunks)
            elif section_text:
                chunks.append((section_text, section_start, section_end))

        return chunks

    def _chunk_code(
        self,
        text: str,
        config: ChunkConfig,
    ) -> List[tuple[str, int, int]]:
        """Code-aware chunking that respects function/class boundaries."""
        # Simple heuristic: split on blank lines between definitions
        separators = [
            "\n\nclass ",
            "\n\ndef ",
            "\n\nasync def ",
            "\n\n",
            "\n",
            " ",
            "",
        ]

        return self._recursive_split(
            text,
            separators,
            config.chunk_size,
            config.chunk_overlap,
            0,
        )

    def _chunk_semantic(
        self,
        text: str,
        config: ChunkConfig,
    ) -> List[tuple[str, int, int]]:
        """
        Semantic chunking (placeholder).

        True semantic chunking requires embeddings to measure similarity
        between adjacent chunks. This is a placeholder that falls back
        to sentence-based chunking.
        """
        logger.info("Semantic chunking not fully implemented, using sentence-based")
        return self._chunk_sentence(text, config)

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _find_sentence_boundary(
        self,
        text: str,
        start: int,
        end: int,
        min_size: int,
    ) -> int:
        """Find the nearest sentence boundary before end."""
        # Look for sentence-ending punctuation
        search_text = text[start:end]

        # Find last sentence end
        for pattern in ['. ', '! ', '? ', '.\n', '!\n', '?\n']:
            last_pos = search_text.rfind(pattern)
            if last_pos > min_size:
                return start + last_pos + len(pattern)

        return end

    def merge_chunks(
        self,
        chunks: List[TextChunk],
        max_size: int,
    ) -> List[TextChunk]:
        """Merge small adjacent chunks up to max_size."""
        if not chunks:
            return []

        merged = []
        current = None

        for chunk in chunks:
            if current is None:
                current = TextChunk(
                    id=str(uuid.uuid4()),
                    text=chunk.text,
                    index=len(merged),
                    start_char=chunk.start_char,
                    end_char=chunk.end_char,
                    token_count=chunk.token_count,
                    metadata=chunk.metadata.copy(),
                )
            elif len(current.text) + len(chunk.text) <= max_size:
                current.text += " " + chunk.text
                current.end_char = chunk.end_char
                current.token_count = self.count_tokens(current.text)
            else:
                merged.append(current)
                current = TextChunk(
                    id=str(uuid.uuid4()),
                    text=chunk.text,
                    index=len(merged),
                    start_char=chunk.start_char,
                    end_char=chunk.end_char,
                    token_count=chunk.token_count,
                    metadata=chunk.metadata.copy(),
                )

        if current:
            merged.append(current)

        return merged

    async def get_stats(self) -> Dict[str, Any]:
        """Get chunk service statistics."""
        return {
            "tokenizer": self._tokenizer_name,
            "tokenizer_available": self._tokenizer is not None,
            "available_strategies": [s.value for s in ChunkStrategy],
        }
