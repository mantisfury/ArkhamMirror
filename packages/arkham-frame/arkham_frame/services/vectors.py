"""
VectorService - pgvector vector store with IVFFlat indexes and embedding.

Provides vector storage, similarity search, and embedding generation
for semantic search capabilities using PostgreSQL + pgvector.

Uses a single-database architecture with pgvector extension.
"""

from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import logging
import uuid
import json
import hashlib
import time

logger = logging.getLogger(__name__)

# Import wide event logging utilities (with fallback)
try:
    from arkham_frame import log_operation, create_wide_event
    WIDE_EVENTS_AVAILABLE = True
except ImportError:
    WIDE_EVENTS_AVAILABLE = False
    # Fallback: create no-op context manager
    from contextlib import contextmanager
    @contextmanager
    def log_operation(*args, **kwargs):
        yield None
    def create_wide_event(*args, **kwargs):
        return None


class DistanceMetric(str, Enum):
    """Vector distance metrics."""
    COSINE = "cosine"
    EUCLIDEAN = "euclidean"
    DOT = "dot"


@dataclass
class VectorPoint:
    """A point in vector space."""
    id: str
    vector: List[float]
    payload: Dict[str, Any] = field(default_factory=dict)
    score: Optional[float] = None  # Similarity score when returned from search

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "vector": self.vector,
            "payload": self.payload,
            "score": self.score,
        }


@dataclass
class CollectionInfo:
    """Information about a vector collection."""
    name: str
    vector_size: int
    distance: DistanceMetric
    points_count: int = 0
    indexed_vectors_count: int = 0
    status: str = "green"
    created_at: Optional[datetime] = None
    # IVFFlat specific
    index_type: str = "ivfflat"
    lists: int = 100
    probes: int = 10
    last_reindex: Optional[datetime] = None
    # Binary quantization for high dimensions (>2000)
    uses_binary_quantization: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "vector_size": self.vector_size,
            "distance": self.distance.value if isinstance(self.distance, DistanceMetric) else self.distance,
            "points_count": self.points_count,
            "indexed_vectors_count": self.indexed_vectors_count,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "index_type": self.index_type,
            "lists": self.lists,
            "probes": self.probes,
            "last_reindex": self.last_reindex.isoformat() if self.last_reindex else None,
            "uses_binary_quantization": self.uses_binary_quantization,
        }


@dataclass
class SearchResult:
    """A vector search result."""
    id: str
    score: float
    payload: Dict[str, Any] = field(default_factory=dict)
    vector: Optional[List[float]] = None

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "score": self.score,
            "payload": self.payload,
        }
        if self.vector:
            result["vector"] = self.vector
        return result


class VectorServiceError(Exception):
    """Base vector service error."""
    pass


class VectorStoreUnavailableError(VectorServiceError):
    """Vector store not available."""
    pass


class CollectionNotFoundError(VectorServiceError):
    """Collection does not exist."""
    def __init__(self, collection: str):
        super().__init__(f"Collection not found: {collection}")
        self.collection = collection


class CollectionExistsError(VectorServiceError):
    """Collection already exists."""
    def __init__(self, collection: str):
        super().__init__(f"Collection already exists: {collection}")
        self.collection = collection


class EmbeddingError(VectorServiceError):
    """Embedding generation failed."""
    pass


class VectorDimensionError(VectorServiceError):
    """Vector dimension mismatch."""
    def __init__(self, expected: int, got: int):
        super().__init__(f"Vector dimension mismatch: expected {expected}, got {got}")
        self.expected = expected
        self.got = got


class UnsupportedDimensionError(VectorServiceError):
    """Model produces vectors exceeding pgvector limit."""
    def __init__(self, model: str, dimensions: int, max_dims: int = 2000):
        super().__init__(
            f"Model '{model}' produces {dimensions}-dimensional embeddings, "
            f"but pgvector IVFFlat supports max {max_dims} dimensions"
        )
        self.model = model
        self.dimensions = dimensions


# Maximum dimensions for pgvector vector type (supports up to 16,000)
MAX_VECTOR_DIMENSIONS = 16000
# Threshold for using binary quantization (bit type supports up to 64,000 dims)
# For dimensions > 2000, we use binary quantization with bit type for indexing
BINARY_QUANTIZATION_THRESHOLD = 2000

# Default embedding dimensions for common models
# Local models (via SentenceTransformer)
LOCAL_EMBEDDING_MODELS = {
    "all-MiniLM-L6-v2": 384,
    "all-mpnet-base-v2": 768,
    "BAAI/bge-m3": 1024,
    "BAAI/bge-large-en-v1.5": 1024,
    "BAAI/bge-base-en-v1.5": 768,
    "BAAI/bge-small-en-v1.5": 384,
    "sentence-transformers/all-MiniLM-L6-v2": 384,
    "sentence-transformers/all-mpnet-base-v2": 768,
    # Legacy short names
    "bge-m3": 1024,
    "bge-large": 1024,
    "bge-base": 768,
    "bge-small": 384,
}

# Cloud API models (via OpenAI-compatible API)
# Only available when cloud LLM is configured (OPENAI_API_KEY or LLM_API_KEY set)
CLOUD_EMBEDDING_MODELS = {
    "text-embedding-3-small": 1536,  # Best cost/quality ratio
    "text-embedding-3-large": 3072,  # Uses binary quantization (bit type) for indexing
}

# Combined lookup for backwards compatibility
EMBEDDING_DIMENSIONS = {**LOCAL_EMBEDDING_MODELS, **CLOUD_EMBEDDING_MODELS}


class VectorService:
    """
    pgvector vector store service with IVFFlat indexes and embedding support.

    Provides:
        - Collection management (create, delete, list) via PostgreSQL
        - Vector operations (upsert, delete, search) via pgvector
        - IVFFlat indexes with configurable lists/probes
        - Batch operations for performance
        - Optional local or cloud embedding generation
    """

    # Standard collections used by the frame
    COLLECTION_DOCUMENTS = "arkham_documents"
    COLLECTION_CHUNKS = "arkham_chunks"
    COLLECTION_ENTITIES = "arkham_entities"

    def __init__(self, config):
        self.config = config
        self._pool = None
        self._available = False
        self._embedding_model = None
        self._embedding_available = False
        self._default_dimension = 384  # all-MiniLM-L6-v2 default (fast testing)
        # Cloud embedding support
        self._use_cloud_embeddings = False
        self._cloud_embedding_model = None
        self._cloud_api_key = None
        self._cloud_api_url = None
        # IVFFlat default recall target
        self._target_recall = 0.95

    async def initialize(self) -> None:
        """Initialize PostgreSQL/pgvector connection and optional embedding model."""
        import asyncpg

        # JSON codec setup for asyncpg
        async def init_connection(conn):
            """Initialize connection with JSON codecs."""
            await conn.set_type_codec(
                'jsonb',
                encoder=json.dumps,
                decoder=json.loads,
                schema='pg_catalog'
            )
            await conn.set_type_codec(
                'json',
                encoder=json.dumps,
                decoder=json.loads,
                schema='pg_catalog'
            )

        # Initialize PostgreSQL connection pool
        try:
            database_url = self.config.database_url
            if not database_url:
                raise ValueError("DATABASE_URL not configured")

            self._pool = await asyncpg.create_pool(
                database_url,
                min_size=2,
                max_size=10,
                command_timeout=60,
                init=init_connection,  # Set up JSON codecs for each connection
            )

            # Verify pgvector extension is available
            async with self._pool.acquire() as conn:
                result = await conn.fetchval(
                    "SELECT 1 FROM pg_extension WHERE extname = 'vector'"
                )
                if not result:
                    raise ValueError("pgvector extension not installed")

                # Register vector type
                await conn.execute("SELECT '[1,2,3]'::vector")  # Test vector type

            self._available = True
            logger.info(f"pgvector connected: {database_url.split('@')[-1]}")

        except Exception as e:
            logger.warning(f"pgvector connection failed: {e}")
            self._available = False

        # Initialize embedding model (only if explicitly configured)
        try:
            import os
            embedding_model = os.environ.get("EMBED_MODEL", "")

            # If not set via env, try to read from settings database
            if not embedding_model:
                embedding_model = await self._get_embedding_model_from_settings()

            # Only load model if explicitly configured - no default auto-load
            # This prevents blocking on first Docker start when no model is cached
            if embedding_model:
                await self._load_embedding_model(embedding_model)
            else:
                logger.info("Embedding model not configured - semantic search disabled")
                logger.info("Set EMBED_MODEL env var or configure in Settings > Advanced")
                self._embedding_available = False
        except Exception as e:
            logger.warning(f"Embedding model failed to load: {e}")
            self._embedding_available = False

        # Ensure standard collections exist
        if self._available:
            await self._ensure_standard_collections()

    async def _get_embedding_model_from_settings(self) -> str:
        """
        Try to read embedding model from settings database.

        Returns empty string if not found or database unavailable.
        """
        if not self._pool:
            return ""

        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT value FROM arkham_settings WHERE key = $1",
                    "advanced.embedding_model"
                )
                if row and row["value"]:
                    value = row["value"]
                    if isinstance(value, str):
                        return value.strip('"')
                    return str(value) if value else ""
                return ""
        except Exception as e:
            logger.debug(f"Could not read embedding model from settings: {e}")
            return ""

    async def _load_embedding_model(self, model_name: str) -> None:
        """Load an embedding model (local or cloud API)."""
        import os

        # Check if this is a cloud API model
        if model_name in CLOUD_EMBEDDING_MODELS:
            await self._load_cloud_embedding_model(model_name)
            return

        # Validate dimension limit for local models
        dims = LOCAL_EMBEDDING_MODELS.get(model_name, 0)
        if dims > MAX_VECTOR_DIMENSIONS:
            raise UnsupportedDimensionError(model_name, dims, MAX_VECTOR_DIMENSIONS)
        elif dims > BINARY_QUANTIZATION_THRESHOLD:
            logger.warning(
                f"Model '{model_name}' produces {dims}-dimensional embeddings. "
                f"Using binary quantization (bit type) for indexing (supports up to 64,000 dimensions)."
            )

        # Load local model via SentenceTransformer
        # Run in thread pool to avoid blocking the event loop during model download/load
        try:
            import asyncio
            from sentence_transformers import SentenceTransformer

            def _load_model():
                return SentenceTransformer(model_name)

            logger.info(f"Loading embedding model '{model_name}' (this may download on first use)...")
            self._embedding_model = await asyncio.to_thread(_load_model)
            self._default_dimension = self._embedding_model.get_sentence_embedding_dimension()

            # Final dimension check
            if self._default_dimension > MAX_VECTOR_DIMENSIONS:
                raise UnsupportedDimensionError(model_name, self._default_dimension, MAX_VECTOR_DIMENSIONS)
            elif self._default_dimension > BINARY_QUANTIZATION_THRESHOLD:
                logger.warning(
                    f"Model '{model_name}' produces {self._default_dimension}-dimensional embeddings. "
                    f"Using binary quantization (bit type) for indexing (supports up to 64,000 dimensions)."
                )

            self._embedding_available = True
            self._use_cloud_embeddings = False
            logger.info(f"Local embedding model loaded: {model_name} (dim={self._default_dimension})")

        except ImportError:
            logger.warning("sentence-transformers not installed, embedding disabled")
            self._embedding_available = False
        except Exception as e:
            logger.warning(f"Failed to load embedding model {model_name}: {e}")
            self._embedding_available = False

    async def _load_cloud_embedding_model(self, model_name: str) -> None:
        """Configure cloud API embedding model."""
        import os

        # Check for API key
        api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("LLM_API_KEY")
        if not api_key:
            logger.warning(
                f"Cloud embedding model '{model_name}' requires OPENAI_API_KEY or LLM_API_KEY. "
                "Falling back to local model."
            )
            await self._load_embedding_model("all-MiniLM-L6-v2")
            return

        # Validate dimension limit
        dims = CLOUD_EMBEDDING_MODELS[model_name]
        if dims > MAX_VECTOR_DIMENSIONS:
            raise UnsupportedDimensionError(model_name, dims, MAX_VECTOR_DIMENSIONS)
        elif dims > BINARY_QUANTIZATION_THRESHOLD:
            logger.warning(
                f"Model '{model_name}' produces {dims}-dimensional embeddings. "
                f"Using binary quantization (bit type) for indexing (supports up to 64,000 dimensions)."
            )

        # Configure cloud embedding
        self._cloud_api_key = api_key
        # No default - must be explicitly configured for cloud embeddings
        self._cloud_api_url = os.environ.get("EMBED_API_URL", "")
        if not self._cloud_api_url:
            raise ValueError("EMBED_API_URL environment variable required for cloud embeddings")
        self._cloud_embedding_model = model_name
        self._default_dimension = dims
        self._use_cloud_embeddings = True
        self._embedding_available = True
        self._embedding_model = None

        logger.info(
            f"Cloud embedding configured: {model_name} (dim={self._default_dimension}) "
            f"via {self._cloud_api_url}"
        )

    def is_using_cloud_embeddings(self) -> bool:
        """Check if cloud API embeddings are in use."""
        return self._use_cloud_embeddings

    def get_embedding_model_info(self) -> dict:
        """Get information about the current embedding configuration."""
        return {
            "model": self._cloud_embedding_model if self._use_cloud_embeddings else
                     (self._embedding_model.get_config_dict().get("model_name_or_path", "unknown")
                      if self._embedding_model else None),
            "dimensions": self._default_dimension,
            "is_cloud": self._use_cloud_embeddings,
            "api_url": self._cloud_api_url if self._use_cloud_embeddings else None,
            "available": self._embedding_available,
        }

    async def _ensure_standard_collections(self) -> None:
        """Ensure standard collections exist with correct dimensions."""
        standard = [
            (self.COLLECTION_DOCUMENTS, self._default_dimension, 316),   # ~100k expected
            (self.COLLECTION_CHUNKS, self._default_dimension, 1000),     # ~1M expected
            (self.COLLECTION_ENTITIES, self._default_dimension, 707),    # ~500k expected
        ]

        for collection_name, dimension, lists in standard:
            try:
                if await self.collection_exists(collection_name):
                    # Collection exists - check if dimension matches and index exists
                    info = await self.get_collection(collection_name)
                    
                    # Check if index exists
                    safe_name = self._safe_index_name(collection_name)
                    async with self._pool.acquire() as conn:
                        index_exists = await conn.fetchval("""
                            SELECT 1 FROM pg_indexes 
                            WHERE schemaname = 'arkham_vectors' 
                            AND indexname = $1
                        """, f"idx_ivfflat_{safe_name}")
                    
                    # If dimension mismatch and collection is empty, recreate
                    if info.vector_size != dimension:
                        if info.points_count == 0:
                            logger.warning(
                                f"Collection {collection_name} has wrong dimension "
                                f"({info.vector_size} vs {dimension}), recreating..."
                            )
                            await self.delete_collection(collection_name)
                            await self.create_collection(
                                name=collection_name,
                                vector_size=dimension,
                                distance=DistanceMetric.COSINE,
                                lists=lists,
                            )
                            logger.info(f"Recreated collection: {collection_name} (dim={dimension})")
                        else:
                            # Warn if using high dimensions (will use binary quantization)
                            if info.vector_size > BINARY_QUANTIZATION_THRESHOLD:
                                if info.vector_size > MAX_VECTOR_DIMENSIONS:
                                    logger.error(
                                        f"Collection {collection_name} has dimension {info.vector_size} "
                                        f"which exceeds pgvector vector type maximum of {MAX_VECTOR_DIMENSIONS}. "
                                        f"Contains {info.points_count} vectors. "
                                        "Please fix the data or use a different embedding model."
                                    )
                                    continue
                                else:
                                    logger.info(
                                        f"Collection {collection_name} has {info.vector_size} dimensions. "
                                        f"Using binary quantization (bit type) for indexing."
                                    )
                            
                            logger.warning(
                                f"Collection {collection_name} has wrong dimension "
                                f"({info.vector_size} vs {dimension}) but contains {info.points_count} vectors. "
                                f"Using existing dimension {info.vector_size}."
                            )
                            # Update dimension to match existing collection
                            dimension = info.vector_size
                    
                    # Ensure index exists (may have failed during migration)
                    if not index_exists:
                        logger.info(f"Creating missing index for collection {collection_name}")
                        await self._create_collection_index(collection_name, dimension, lists)
                else:
                    # Collection doesn't exist - create it
                    await self.create_collection(
                        name=collection_name,
                        vector_size=dimension,
                        distance=DistanceMetric.COSINE,
                        lists=lists,
                    )
                    logger.info(f"Created standard collection: {collection_name} (dim={dimension})")
            except Exception as e:
                logger.warning(f"Failed to ensure collection {collection_name}: {e}")
    
    async def _create_collection_index(self, collection_name: str, vector_size: int, lists: int) -> None:
        """Create IVFFlat index for a collection (helper for fixing missing indexes)."""
        safe_name = self._safe_index_name(collection_name)
        escaped_name = collection_name.replace("'", "''")
        
        async with self._pool.acquire() as conn:
            # Check if we have any vectors - index can only be created if vectors exist
            # (pgvector needs dimensions which come from actual vectors with untyped vector column)
            sample_vector = await conn.fetchval("""
                SELECT embedding FROM arkham_vectors.embeddings 
                WHERE collection = $1 
                LIMIT 1
            """, collection_name)
            
            if sample_vector:
                # Verify dimension matches expected (for validation)
                actual_dimension = len(sample_vector) if hasattr(sample_vector, '__len__') else None
                if actual_dimension:
                    if actual_dimension != vector_size:
                        logger.warning(
                            f"Collection {collection_name} has dimension mismatch: "
                            f"expected {vector_size}, actual {actual_dimension}. Using actual dimension."
                        )
                    
                    # Check if dimension exceeds vector type limit
                    if actual_dimension > MAX_VECTOR_DIMENSIONS:
                        logger.error(
                            f"Collection {collection_name} has vectors with {actual_dimension} dimensions, "
                            f"which exceeds pgvector vector type maximum of {MAX_VECTOR_DIMENSIONS}. "
                            "Index creation skipped. Please fix the data or use a different embedding model."
                        )
                        return
                    elif actual_dimension > BINARY_QUANTIZATION_THRESHOLD:
                        logger.info(
                            f"Collection {collection_name} has {actual_dimension} dimensions. "
                            f"Using binary quantization (bit type) for indexing."
                        )
                
                # We have vectors, can create index
                try:
                    use_binary_quant = self._should_use_binary_quantization(actual_dimension or vector_size)
                    if use_binary_quant:
                        # Use binary quantization with bit type for high dimensions
                        await conn.execute(f"""
                            CREATE INDEX IF NOT EXISTS idx_ivfflat_{safe_name}
                            ON arkham_vectors.embeddings
                            USING ivfflat ((binary_quantize(embedding)::bit({actual_dimension or vector_size})) bit_hamming_ops)
                            WITH (lists = {lists})
                            WHERE collection = '{escaped_name}'
                        """)
                    else:
                        # Standard vector index for dimensions <= 2000
                        await conn.execute(f"""
                            CREATE INDEX IF NOT EXISTS idx_ivfflat_{safe_name}
                            ON arkham_vectors.embeddings
                            USING ivfflat (embedding vector_cosine_ops)
                            WITH (lists = {lists})
                            WHERE collection = '{escaped_name}'
                        """)
                    logger.info(
                        f"Created index for collection {collection_name} "
                        f"(dim={actual_dimension or vector_size}, lists={lists}, binary_quant={use_binary_quant})"
                    )
                except Exception as e:
                    logger.warning(f"Failed to create index for {collection_name}: {e}")
            else:
                # No vectors yet - index will be created when first vector is inserted
                logger.debug(
                    f"Collection {collection_name} is empty (expected dim={vector_size}), "
                    "index will be created on first insert"
                )

    async def shutdown(self) -> None:
        """Close PostgreSQL connection pool."""
        if self._pool:
            await self._pool.close()
        self._pool = None
        self._available = False
        self._embedding_model = None
        self._embedding_available = False
        logger.info("VectorService shutdown complete")

    def is_available(self) -> bool:
        """Check if pgvector is available."""
        return self._available

    def embedding_available(self) -> bool:
        """Check if embedding generation is available."""
        return self._embedding_available

    # =========================================================================
    # IVFFlat Parameter Helpers
    # =========================================================================

    def _optimal_lists(self, expected_rows: int) -> int:
        """Calculate optimal IVFFlat lists parameter."""
        if expected_rows < 1000:
            return 10
        elif expected_rows < 1_000_000:
            return max(10, expected_rows // 1000)
        else:
            return max(100, int(expected_rows ** 0.5))

    def _optimal_probes(self, lists: int, target_recall: float = None) -> int:
        """Calculate optimal probes for target recall."""
        if target_recall is None:
            target_recall = self._target_recall

        if target_recall >= 0.99:
            return max(lists // 2, int(lists ** 0.5) * 3)
        elif target_recall >= 0.95:
            return max(10, int(lists ** 0.5))
        else:
            return max(5, lists // 10)

    def _should_use_binary_quantization(self, vector_size: int) -> bool:
        """Check if binary quantization should be used for this vector size."""
        return vector_size > BINARY_QUANTIZATION_THRESHOLD

    def _safe_index_name(self, collection_name: str) -> str:
        """
        Generate a safe PostgreSQL index name from collection name.
        
        PostgreSQL identifiers are limited to 63 characters. Index name format is
        'idx_ivfflat_{safe_name}', so safe_name can be at most 50 characters.
        If the collection name is too long, truncate and append a hash suffix.
        """
        # Replace unsafe characters
        safe_name = collection_name.replace("-", "_").replace(".", "_")
        
        # PostgreSQL index name limit: 63 chars total, "idx_ivfflat_" = 13 chars
        # So safe_name can be at most 50 characters
        max_safe_length = 50
        
        if len(safe_name) <= max_safe_length:
            return safe_name
        
        # Truncate and append hash for uniqueness
        # Use first 40 chars + 10 char hash = 50 chars total
        hash_suffix = hashlib.md5(collection_name.encode()).hexdigest()[:10]
        truncated = safe_name[:40]
        return f"{truncated}_{hash_suffix}"

    # =========================================================================
    # Collection Management
    # =========================================================================

    async def create_collection(
        self,
        name: str,
        vector_size: int,
        distance: DistanceMetric = DistanceMetric.COSINE,
        lists: int = None,
        expected_rows: int = 100000,
        project_id: str = None,
    ) -> CollectionInfo:
        """Create a new vector collection with IVFFlat index."""
        if not self._available:
            raise VectorStoreUnavailableError("pgvector not available")

        # Apply project prefix if provided
        collection_name = f"project_{project_id}_{name}" if project_id else name
        safe_name = self._safe_index_name(collection_name)

        # Calculate optimal IVFFlat parameters
        if lists is None:
            lists = self._optimal_lists(expected_rows)
        probes = self._optimal_probes(lists)

        # Map distance metric to pgvector operator class
        ops_map = {
            DistanceMetric.COSINE: "vector_cosine_ops",
            DistanceMetric.EUCLIDEAN: "vector_l2_ops",
            DistanceMetric.DOT: "vector_ip_ops",
        }
        ops = ops_map.get(distance, "vector_cosine_ops")

        try:
            async with self._pool.acquire() as conn:
                # Check if collection exists
                existing = await conn.fetchval(
                    "SELECT 1 FROM arkham_vectors.collections WHERE name = $1",
                    collection_name
                )
                if existing:
                    raise CollectionExistsError(collection_name)

                # Check if binary quantization should be used
                use_binary_quant = self._should_use_binary_quantization(vector_size)
                if use_binary_quant:
                    logger.warning(
                        f"Collection {collection_name} has {vector_size} dimensions (> {BINARY_QUANTIZATION_THRESHOLD}). "
                        f"Using binary quantization (bit type) for indexing (supports up to 64,000 dimensions)."
                    )

                async with conn.transaction():
                    # Insert collection metadata
                    await conn.execute("""
                        INSERT INTO arkham_vectors.collections
                            (name, vector_size, distance_metric, index_type, lists, probes)
                        VALUES ($1, $2, $3, 'ivfflat', $4, $5)
                    """, collection_name, vector_size, distance.value, lists, probes)

                    # Create IVFFlat partial index only if vectors exist
                    # With untyped vector column, pgvector needs actual vectors to infer dimensions
                    escaped_name = collection_name.replace("'", "''")
                    has_vectors = await conn.fetchval("""
                        SELECT 1 FROM arkham_vectors.embeddings 
                        WHERE collection = $1 
                        LIMIT 1
                    """, collection_name)
                    
                    if has_vectors:
                        # Vectors exist - can create index now
                        if use_binary_quant:
                            # Use binary quantization with bit type for high dimensions
                            await conn.execute(f"""
                                CREATE INDEX IF NOT EXISTS idx_ivfflat_{safe_name}
                                ON arkham_vectors.embeddings
                                USING ivfflat ((binary_quantize(embedding)::bit({vector_size})) bit_hamming_ops)
                                WITH (lists = {lists})
                                WHERE collection = '{escaped_name}'
                            """)
                        else:
                            # Standard vector index for dimensions <= 2000
                            await conn.execute(f"""
                                CREATE INDEX IF NOT EXISTS idx_ivfflat_{safe_name}
                                ON arkham_vectors.embeddings
                                USING ivfflat (embedding {ops})
                                WITH (lists = {lists})
                                WHERE collection = '{escaped_name}'
                            """)
                    # If no vectors, index will be created automatically on first insert

            logger.info(f"Created collection: {collection_name} (size={vector_size}, lists={lists}, binary_quant={use_binary_quant})")

            return CollectionInfo(
                name=collection_name,
                vector_size=vector_size,
                distance=distance,
                created_at=datetime.utcnow(),
                index_type="ivfflat",
                lists=lists,
                probes=probes,
                uses_binary_quantization=use_binary_quant,
            )

        except CollectionExistsError:
            raise
        except Exception as e:
            raise VectorServiceError(f"Failed to create collection: {e}")

    async def delete_collection(self, name: str) -> bool:
        """Delete a collection and its index."""
        if not self._available:
            raise VectorStoreUnavailableError("pgvector not available")

        safe_name = self._safe_index_name(name)

        try:
            async with self._pool.acquire() as conn:
                async with conn.transaction():
                    # Delete vectors
                    await conn.execute(
                        "DELETE FROM arkham_vectors.embeddings WHERE collection = $1",
                        name
                    )

                    # Drop index
                    await conn.execute(f"DROP INDEX IF EXISTS arkham_vectors.idx_ivfflat_{safe_name}")

                    # Delete metadata
                    result = await conn.execute(
                        "DELETE FROM arkham_vectors.collections WHERE name = $1",
                        name
                    )

            deleted = "DELETE 1" in result
            if deleted:
                logger.info(f"Deleted collection: {name}")
            return deleted

        except Exception as e:
            raise VectorServiceError(f"Failed to delete collection: {e}")

    async def collection_exists(self, name: str) -> bool:
        """Check if a collection exists."""
        if not self._available:
            return False

        try:
            async with self._pool.acquire() as conn:
                result = await conn.fetchval(
                    "SELECT 1 FROM arkham_vectors.collections WHERE name = $1",
                    name
                )
                return result is not None
        except Exception:
            return False

    async def get_collection(self, name: str) -> CollectionInfo:
        """Get collection information."""
        if not self._available:
            raise VectorStoreUnavailableError("pgvector not available")

        try:
            async with self._pool.acquire() as conn:
                # Get collection metadata
                row = await conn.fetchrow(
                    "SELECT * FROM arkham_vectors.collections WHERE name = $1",
                    name
                )
                if not row:
                    raise CollectionNotFoundError(name)

                # Get actual vector count
                count = await conn.fetchval(
                    "SELECT COUNT(*) FROM arkham_vectors.embeddings WHERE collection = $1",
                    name
                )

                # Parse distance metric
                distance_str = row['distance_metric']
                distance = DistanceMetric(distance_str) if distance_str else DistanceMetric.COSINE

                # Check if binary quantization should be used
                vector_size = row['vector_size']
                uses_binary_quant = self._should_use_binary_quantization(vector_size)

                return CollectionInfo(
                    name=name,
                    vector_size=vector_size,
                    distance=distance,
                    points_count=count or 0,
                    indexed_vectors_count=row['vector_count'] or 0,
                    status="green",
                    created_at=row['created_at'],
                    index_type=row['index_type'] or 'ivfflat',
                    lists=row['lists'] or 100,
                    probes=row['probes'] or 10,
                    last_reindex=row['last_reindex'],
                    uses_binary_quantization=uses_binary_quant,
                )

        except CollectionNotFoundError:
            raise
        except Exception as e:
            raise VectorServiceError(f"Failed to get collection info: {e}")

    async def list_collections(self) -> List[CollectionInfo]:
        """List all collections."""
        if not self._available:
            return []

        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(
                    "SELECT * FROM arkham_vectors.collections ORDER BY name"
                )

                result = []
                for row in rows:
                    count = await conn.fetchval(
                        "SELECT COUNT(*) FROM arkham_vectors.embeddings WHERE collection = $1",
                        row['name']
                    )

                    distance_str = row['distance_metric']
                    distance = DistanceMetric(distance_str) if distance_str else DistanceMetric.COSINE

                    # Check if binary quantization should be used
                    vector_size = row['vector_size']
                    uses_binary_quant = self._should_use_binary_quantization(vector_size)

                    result.append(CollectionInfo(
                        name=row['name'],
                        vector_size=vector_size,
                        distance=distance,
                        points_count=count or 0,
                        indexed_vectors_count=row['vector_count'] or 0,
                        status="green",
                        created_at=row['created_at'],
                        index_type=row['index_type'] or 'ivfflat',
                        lists=row['lists'] or 100,
                        probes=row['probes'] or 10,
                        last_reindex=row['last_reindex'],
                        uses_binary_quantization=uses_binary_quant,
                    ))

                return result

        except Exception as e:
            logger.error(f"Failed to list collections: {e}")
            return []

    # =========================================================================
    # Vector Operations
    # =========================================================================

    async def upsert(
        self,
        collection: str,
        points: List[VectorPoint],
    ) -> int:
        """Upsert vectors into a collection."""
        if not self._available:
            raise VectorStoreUnavailableError("pgvector not available")

        if not points:
            return 0

        try:
            async with self._pool.acquire() as conn:
                # Verify collection exists
                coll_info = await conn.fetchrow(
                    "SELECT vector_size, lists, distance_metric FROM arkham_vectors.collections WHERE name = $1",
                    collection
                )
                if not coll_info:
                    raise CollectionNotFoundError(collection)

                # Check if index exists - create if missing (first insert)
                safe_name = self._safe_index_name(collection)
                index_exists = await conn.fetchval("""
                    SELECT 1 FROM pg_indexes 
                    WHERE schemaname = 'arkham_vectors' 
                    AND indexname = $1
                """, f"idx_ivfflat_{safe_name}")

                # Batch upsert
                # Note: payload may be dict or already a JSON string - handle both
                def serialize_payload(payload):
                    if isinstance(payload, str):
                        return payload  # Already JSON string
                    return json.dumps(payload)

                await conn.executemany("""
                    INSERT INTO arkham_vectors.embeddings (id, collection, embedding, payload)
                    VALUES ($1, $2, $3::vector, $4::jsonb)
                    ON CONFLICT (id) DO UPDATE SET
                        embedding = EXCLUDED.embedding,
                        payload = EXCLUDED.payload,
                        updated_at = CURRENT_TIMESTAMP
                """, [
                    (p.id, collection, str(p.vector), serialize_payload(p.payload))
                    for p in points
                ])

                # Create index if missing (now that we have vectors, dimensions are known)
                if not index_exists:
                    try:
                        lists = coll_info['lists'] or 100
                        distance_metric = coll_info['distance_metric'] or 'cosine'
                        vector_size = coll_info['vector_size']
                        escaped_name = collection.replace("'", "''")
                        
                        # Check if binary quantization should be used
                        use_binary_quant = self._should_use_binary_quantization(vector_size)
                        
                        if use_binary_quant:
                            # Use binary quantization with bit type for high dimensions
                            await conn.execute(f"""
                                CREATE INDEX IF NOT EXISTS idx_ivfflat_{safe_name}
                                ON arkham_vectors.embeddings
                                USING ivfflat ((binary_quantize(embedding)::bit({vector_size})) bit_hamming_ops)
                                WITH (lists = {lists})
                                WHERE collection = '{escaped_name}'
                            """)
                        else:
                            # Standard vector index for dimensions <= 2000
                            ops_map = {
                                'cosine': 'vector_cosine_ops',
                                'euclidean': 'vector_l2_ops',
                                'dot': 'vector_ip_ops',
                            }
                            ops = ops_map.get(distance_metric, 'vector_cosine_ops')
                            await conn.execute(f"""
                                CREATE INDEX IF NOT EXISTS idx_ivfflat_{safe_name}
                                ON arkham_vectors.embeddings
                                USING ivfflat (embedding {ops})
                                WITH (lists = {lists})
                                WHERE collection = '{escaped_name}'
                            """)
                        logger.info(f"Created IVFFlat index for collection {collection} (binary_quant={use_binary_quant})")
                    except Exception as idx_error:
                        logger.warning(f"Failed to create index for {collection}: {idx_error}")

            logger.debug(f"Upserted {len(points)} vectors to {collection}")
            return len(points)

        except CollectionNotFoundError:
            raise
        except Exception as e:
            raise VectorServiceError(f"Failed to upsert vectors: {e}")

    async def upsert_single(
        self,
        collection: str,
        id: str,
        vector: List[float],
        payload: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Upsert a single vector."""
        point = VectorPoint(id=id, vector=vector, payload=payload or {})
        count = await self.upsert(collection, [point])
        return count == 1

    async def delete_vectors(
        self,
        collection: str,
        ids: List[str],
    ) -> int:
        """Delete vectors by ID."""
        if not self._available:
            raise VectorStoreUnavailableError("pgvector not available")

        if not ids:
            return 0

        try:
            async with self._pool.acquire() as conn:
                result = await conn.execute(
                    "DELETE FROM arkham_vectors.embeddings WHERE collection = $1 AND id = ANY($2)",
                    collection, ids
                )
                deleted = int(result.split()[-1]) if result else 0

            logger.debug(f"Deleted {deleted} vectors from {collection}")
            return deleted

        except Exception as e:
            raise VectorServiceError(f"Failed to delete vectors: {e}")

    async def delete_by_filter(
        self,
        collection: str,
        filter: Dict[str, Any],
    ) -> bool:
        """Delete vectors matching a filter."""
        if not self._available:
            raise VectorStoreUnavailableError("pgvector not available")

        try:
            async with self._pool.acquire() as conn:
                await conn.execute(
                    "DELETE FROM arkham_vectors.embeddings WHERE collection = $1 AND payload @> $2::jsonb",
                    collection, json.dumps(filter)
                )

            logger.debug(f"Deleted vectors by filter from {collection}")
            return True

        except Exception as e:
            raise VectorServiceError(f"Failed to delete vectors by filter: {e}")

    async def get_vector(
        self,
        collection: str,
        id: str,
        with_vector: bool = False,
    ) -> Optional[VectorPoint]:
        """Get a vector by ID."""
        if not self._available:
            raise VectorStoreUnavailableError("pgvector not available")

        try:
            async with self._pool.acquire() as conn:
                if with_vector:
                    row = await conn.fetchrow(
                        "SELECT id, embedding, payload FROM arkham_vectors.embeddings WHERE collection = $1 AND id = $2",
                        collection, id
                    )
                else:
                    row = await conn.fetchrow(
                        "SELECT id, payload FROM arkham_vectors.embeddings WHERE collection = $1 AND id = $2",
                        collection, id
                    )

                if row:
                    vector = list(row['embedding']) if with_vector and row.get('embedding') else []
                    return VectorPoint(
                        id=row['id'],
                        vector=vector,
                        payload=row['payload'] or {},
                    )

                return None

        except Exception as e:
            raise VectorServiceError(f"Failed to get vector: {e}")

    # =========================================================================
    # Search Operations
    # =========================================================================

    async def search(
        self,
        collection: str,
        query_vector: List[float],
        limit: int = 10,
        filter: Optional[Dict[str, Any]] = None,
        score_threshold: Optional[float] = None,
        with_vectors: bool = False,
        recall_target: Optional[float] = None,
    ) -> List[SearchResult]:
        """Search for similar vectors using IVFFlat."""
        with log_operation("vector.search", collection=collection) as event:
            if event:
                event.input(
                    collection=collection,
                    vector_dimension=len(query_vector) if query_vector else 0,
                    limit=limit,
                    has_filter=filter is not None,
                    score_threshold=score_threshold,
                    with_vectors=with_vectors,
                    recall_target=recall_target,
                )
            
            if not self._available:
                if event:
                    event.error("VectorStoreUnavailable", "pgvector not available")
                raise VectorStoreUnavailableError("pgvector not available")

            start_time = time.time()
            try:
                async with self._pool.acquire() as conn:
                    # Get collection info for probes setting and vector size
                    coll = await conn.fetchrow(
                        "SELECT lists, probes, distance_metric, vector_size FROM arkham_vectors.collections WHERE name = $1",
                        collection
                    )
                    if not coll:
                        raise CollectionNotFoundError(collection)

                    # Check if binary quantization is used
                    use_binary_quant = self._should_use_binary_quantization(coll['vector_size'])

                    # Calculate probes for this search
                    if recall_target:
                        probes = self._optimal_probes(coll['lists'], recall_target)
                    else:
                        probes = coll['probes']

                    # Set probes for this query
                    await conn.execute(f"SET LOCAL ivfflat.probes = {probes}")

                    if use_binary_quant:
                        # Use binary quantization with Hamming distance for high dimensions
                        vector_size = coll['vector_size']
                        # Build score expression using Hamming distance (lower = better, so negate for score)
                        score_expr = f"-((binary_quantize(embedding)::bit({vector_size}) <~> binary_quantize($1::vector)::bit({vector_size})))"
                        
                        # Build select columns
                        select_cols = f"id, payload, {score_expr} AS score"
                        if with_vectors:
                            select_cols += ", embedding"

                        # Build query with binary quantization
                        sql = f"""
                            SELECT {select_cols}
                            FROM arkham_vectors.embeddings
                            WHERE collection = $2
                        """
                        params = [str(query_vector), collection]
                        param_idx = 3

                        # Add filter
                        if filter:
                            sql += f" AND payload @> ${param_idx}::jsonb"
                            params.append(json.dumps(filter))
                            param_idx += 1

                        # Add score threshold (for Hamming, lower distance is better)
                        if score_threshold:
                            sql += f" AND {score_expr} >= ${param_idx}"
                            params.append(score_threshold)
                            param_idx += 1

                        # Order by Hamming distance (lower is better)
                        sql += f" ORDER BY binary_quantize(embedding)::bit({vector_size}) <~> binary_quantize($1::vector)::bit({vector_size}) LIMIT ${param_idx}"
                        params.append(limit)
                    else:
                        # Standard vector search for dimensions <= 2000
                        # Determine distance operator
                        distance_metric = coll['distance_metric'] or 'cosine'
                        distance_ops = {
                            'cosine': '<=>',
                            'euclidean': '<->',
                            'dot': '<#>',
                        }
                        op = distance_ops.get(distance_metric, '<=>')

                        # Build score expression (higher = better)
                        if distance_metric == 'cosine':
                            score_expr = f"1 - (embedding {op} $1::vector)"
                        elif distance_metric == 'dot':
                            score_expr = f"-(embedding {op} $1::vector)"
                        else:
                            score_expr = f"embedding {op} $1::vector"

                        # Build select columns
                        select_cols = f"id, payload, {score_expr} AS score"
                        if with_vectors:
                            select_cols += ", embedding"

                        # Build query
                        sql = f"""
                            SELECT {select_cols}
                            FROM arkham_vectors.embeddings
                            WHERE collection = $2
                        """
                        params = [str(query_vector), collection]
                        param_idx = 3

                        # Add filter
                        if filter:
                            sql += f" AND payload @> ${param_idx}::jsonb"
                            params.append(json.dumps(filter))
                            param_idx += 1

                        # Add score threshold
                        if score_threshold and distance_metric == 'cosine':
                            sql += f" AND {score_expr} >= ${param_idx}"
                            params.append(score_threshold)
                            param_idx += 1

                        # Order and limit
                        sql += f" ORDER BY embedding {op} $1::vector LIMIT ${param_idx}"
                        params.append(limit)

                    rows = await conn.fetch(sql, *params)
                    duration_ms = int((time.time() - start_time) * 1000)

                    results = [
                        SearchResult(
                            id=r['id'],
                            score=float(r['score']),
                            payload=r['payload'] or {},
                            vector=list(r['embedding']) if with_vectors and r.get('embedding') else None,
                        )
                        for r in rows
                    ]
                    
                    if event:
                        event.dependency("pgvector_search", duration_ms=duration_ms)
                        event.output(
                            result_count=len(results),
                            top_score=results[0].score if results else None,
                            collection=collection,
                        )
                    
                    return results

            except CollectionNotFoundError:
                if event:
                    event.error("CollectionNotFound", f"Collection '{collection}' not found")
                raise
            except Exception as e:
                if event:
                    event.error("VectorSearchFailed", str(e))
                raise VectorServiceError(f"Search failed: {e}")

    async def search_text(
        self,
        collection: str,
        text: str,
        limit: int = 10,
        filter: Optional[Dict[str, Any]] = None,
        score_threshold: Optional[float] = None,
    ) -> List[SearchResult]:
        """Search using text (requires embedding model)."""
        with log_operation("vector.search_text", collection=collection) as event:
            if event:
                event.input(
                    collection=collection,
                    text_length=len(text),
                    limit=limit,
                    has_filter=filter is not None,
                    score_threshold=score_threshold,
                )
            
            if not self._embedding_available:
                if event:
                    event.error("EmbeddingUnavailable", "Embedding model not available")
                raise EmbeddingError("Embedding model not available")

            embed_start = time.time()
            vector = await self.embed_text(text)
            embed_duration_ms = int((time.time() - embed_start) * 1000)
            
            if event:
                event.dependency("embedding", duration_ms=embed_duration_ms, dimension=len(vector))
            
            results = await self.search(
                collection=collection,
                query_vector=vector,
                limit=limit,
                filter=filter,
                score_threshold=score_threshold,
            )
            
            if event:
                event.output(
                    result_count=len(results),
                    top_score=results[0].score if results else None,
                )
            
            return results

    async def search_batch(
        self,
        collection: str,
        query_vectors: List[List[float]],
        limit: int = 10,
        filter: Optional[Dict[str, Any]] = None,
    ) -> List[List[SearchResult]]:
        """Batch search for multiple query vectors."""
        # For simplicity, execute searches sequentially
        # Could be optimized with LATERAL join for better performance
        results = []
        for query_vector in query_vectors:
            result = await self.search(
                collection=collection,
                query_vector=query_vector,
                limit=limit,
                filter=filter,
            )
            results.append(result)
        return results

    # =========================================================================
    # Embedding Operations
    # =========================================================================

    async def embed_text(self, text: str) -> List[float]:
        """Generate embedding for text (local or cloud API)."""
        if not self._embedding_available:
            raise EmbeddingError("Embedding model not available")

        # Use cloud API if configured
        if self._use_cloud_embeddings:
            embeddings = await self._embed_via_cloud_api([text])
            return embeddings[0]

        # Use local model
        try:
            embedding = self._embedding_model.encode(text, convert_to_numpy=True)
            return embedding.tolist()
        except Exception as e:
            raise EmbeddingError(f"Failed to generate embedding: {e}")

    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts (local or cloud API)."""
        with log_operation("vector.create_embeddings", text_count=len(texts)) as event:
            if event:
                event.input(
                    text_count=len(texts),
                    total_text_length=sum(len(t) for t in texts),
                    use_cloud=self._use_cloud_embeddings,
                )
            
            if not self._embedding_available:
                if event:
                    event.error("EmbeddingUnavailable", "Embedding model not available")
                raise EmbeddingError("Embedding model not available")

            if not texts:
                if event:
                    event.output(embedding_count=0)
                return []

            start_time = time.time()
            
            # Use cloud API if configured
            if self._use_cloud_embeddings:
                embeddings = await self._embed_via_cloud_api(texts)
                duration_ms = int((time.time() - start_time) * 1000)
                if event:
                    event.dependency("cloud_embedding_api", duration_ms=duration_ms)
                    event.output(
                        embedding_count=len(embeddings),
                        dimension=len(embeddings[0]) if embeddings else 0,
                    )
                return embeddings

            # Use local model
            try:
                embeddings = self._embedding_model.encode(texts, convert_to_numpy=True)
                result = [e.tolist() for e in embeddings]
                duration_ms = int((time.time() - start_time) * 1000)
                
                if event:
                    event.dependency("local_embedding_model", duration_ms=duration_ms)
                    event.output(
                        embedding_count=len(result),
                        dimension=len(result[0]) if result else 0,
                    )
                
                return result
            except Exception as e:
                if event:
                    event.error("EmbeddingFailed", str(e))
                raise EmbeddingError(f"Failed to generate embeddings: {e}")

    async def _embed_via_cloud_api(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings via OpenAI-compatible cloud API."""
        import httpx

        if not self._cloud_api_key:
            raise EmbeddingError("Cloud API key not configured")

        try:
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(
                    f"{self._cloud_api_url}/embeddings",
                    headers={
                        "Authorization": f"Bearer {self._cloud_api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self._cloud_embedding_model,
                        "input": texts,
                    },
                )
                response.raise_for_status()
                data = response.json()

                # Sort by index to maintain order
                sorted_embeddings = sorted(data["data"], key=lambda x: x["index"])
                embeddings = [e["embedding"] for e in sorted_embeddings]

                logger.debug(
                    f"Cloud embedding API: {len(texts)} texts, "
                    f"{data.get('usage', {}).get('total_tokens', 'N/A')} tokens"
                )
                return embeddings

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise EmbeddingError("Cloud embedding API authentication failed - check API key")
            elif e.response.status_code == 429:
                raise EmbeddingError("Cloud embedding API rate limit exceeded")
            else:
                raise EmbeddingError(f"Cloud embedding API error: {e.response.status_code}")
        except httpx.TimeoutException:
            raise EmbeddingError("Cloud embedding API request timed out")
        except Exception as e:
            raise EmbeddingError(f"Cloud embedding API failed: {e}")

    async def embed_and_upsert(
        self,
        collection: str,
        items: List[Dict[str, Any]],
        text_field: str = "text",
        id_field: str = "id",
    ) -> int:
        """Embed texts and upsert to collection."""
        if not self._embedding_available:
            raise EmbeddingError("Embedding model not available")

        if not items:
            return 0

        # Extract texts
        texts = [item.get(text_field, "") for item in items]

        # Generate embeddings
        embeddings = await self.embed_texts(texts)

        # Build points
        points = []
        for i, item in enumerate(items):
            payload = {k: v for k, v in item.items() if k != text_field}

            points.append(VectorPoint(
                id=str(item.get(id_field, str(uuid.uuid4()))),
                vector=embeddings[i],
                payload=payload,
            ))

        # Upsert
        return await self.upsert(collection, points)

    # =========================================================================
    # Utility Methods
    # =========================================================================

    async def count(self, collection: str) -> int:
        """Get vector count in collection."""
        try:
            async with self._pool.acquire() as conn:
                count = await conn.fetchval(
                    "SELECT COUNT(*) FROM arkham_vectors.embeddings WHERE collection = $1",
                    collection
                )
                return count or 0
        except Exception:
            return 0

    async def scroll(
        self,
        collection: str,
        limit: int = 100,
        offset: Optional[str] = None,
        filter: Optional[Dict[str, Any]] = None,
        with_vectors: bool = False,
    ) -> Tuple[List[VectorPoint], Optional[str]]:
        """Scroll through vectors in a collection (cursor-based pagination)."""
        if not self._available:
            raise VectorStoreUnavailableError("pgvector not available")

        try:
            async with self._pool.acquire() as conn:
                # Build select columns
                select_cols = "id, payload"
                if with_vectors:
                    select_cols += ", embedding"

                # Build query
                sql = f"""
                    SELECT {select_cols}
                    FROM arkham_vectors.embeddings
                    WHERE collection = $1
                """
                params = [collection]
                param_idx = 2

                # Cursor-based pagination (use ID as cursor)
                if offset:
                    sql += f" AND id > ${param_idx}"
                    params.append(offset)
                    param_idx += 1

                # Add filter
                if filter:
                    sql += f" AND payload @> ${param_idx}::jsonb"
                    params.append(json.dumps(filter))
                    param_idx += 1

                # Order and limit (fetch one extra to detect if more exist)
                sql += f" ORDER BY id LIMIT ${param_idx}"
                params.append(limit + 1)

                rows = await conn.fetch(sql, *params)

                # Check if there are more results
                has_more = len(rows) > limit
                if has_more:
                    rows = rows[:limit]

                points = [
                    VectorPoint(
                        id=r['id'],
                        vector=list(r['embedding']) if with_vectors and r.get('embedding') else [],
                        payload=r['payload'] or {},
                    )
                    for r in rows
                ]

                next_offset = rows[-1]['id'] if has_more and rows else None
                return points, next_offset

        except Exception as e:
            raise VectorServiceError(f"Scroll failed: {e}")

    async def get_stats(self) -> Dict[str, Any]:
        """Get vector service statistics."""
        embedding_model_name = None
        if self._embedding_model is not None:
            try:
                embedding_model_name = getattr(
                    self._embedding_model,
                    "model_card_data",
                    {}
                ).get("model_name", None)
                if not embedding_model_name:
                    embedding_model_name = str(getattr(
                        self._embedding_model, "_model_card_vars", {}
                    ).get("model_name", "unknown"))
            except Exception:
                embedding_model_name = "loaded"

        stats = {
            "available": self._available,
            "backend": "pgvector",
            "embedding_available": self._embedding_available,
            "embedding_dimension": self._default_dimension if self._embedding_available else None,
            "embedding_model": embedding_model_name,
            "is_cloud_embedding": self._use_cloud_embeddings,
            "collections": [],
        }

        if self._available:
            try:
                collections = await self.list_collections()
                stats["collections"] = [c.to_dict() for c in collections]
                stats["total_vectors"] = sum(c.points_count for c in collections)
            except Exception as e:
                logger.error(f"Failed to get vector stats: {e}")

        return stats

    # =========================================================================
    # Maintenance Operations (for Settings UI)
    # =========================================================================

    async def reindex_collection(self, name: str) -> Dict[str, Any]:
        """
        Rebuild IVFFlat index for a collection.

        Call this from Settings UI when user requests manual reindex.
        """
        if not self._available:
            raise VectorStoreUnavailableError("pgvector not available")

        logger.info(f"Starting reindex for collection '{name}'")

        try:
            async with self._pool.acquire() as conn:
                # Get collection info
                coll = await conn.fetchrow(
                    "SELECT * FROM arkham_vectors.collections WHERE name = $1",
                    name
                )
                if not coll:
                    raise CollectionNotFoundError(name)

                # Get actual count
                count = await conn.fetchval(
                    "SELECT COUNT(*) FROM arkham_vectors.embeddings WHERE collection = $1",
                    name
                )

                # Check dimension if vectors exist
                vector_size = coll['vector_size']
                if count > 0:
                    sample_vector = await conn.fetchval("""
                        SELECT embedding FROM arkham_vectors.embeddings 
                        WHERE collection = $1 
                        LIMIT 1
                    """, name)
                    if sample_vector:
                        actual_dimension = len(sample_vector) if hasattr(sample_vector, '__len__') else None
                        if actual_dimension and actual_dimension > MAX_VECTOR_DIMENSIONS:
                            raise UnsupportedDimensionError(
                                f"Collection '{name}'",
                                actual_dimension,
                                MAX_VECTOR_DIMENSIONS
                            )
                        elif actual_dimension:
                            vector_size = actual_dimension

                # Calculate new optimal parameters
                new_lists = self._optimal_lists(count)
                new_probes = self._optimal_probes(new_lists, self._target_recall)

                safe_name = self._safe_index_name(name)

                # Check if binary quantization should be used
                use_binary_quant = self._should_use_binary_quantization(vector_size)

                # Drop and recreate index
                await conn.execute(f"DROP INDEX IF EXISTS arkham_vectors.idx_ivfflat_{safe_name}")

                if use_binary_quant:
                    # Use binary quantization with bit type for high dimensions
                    await conn.execute(f"""
                        CREATE INDEX idx_ivfflat_{safe_name}
                        ON arkham_vectors.embeddings
                        USING ivfflat ((binary_quantize(embedding)::bit({vector_size})) bit_hamming_ops)
                        WITH (lists = {new_lists})
                        WHERE collection = $1
                    """, name)
                else:
                    # Standard vector index for dimensions <= 2000
                    ops_map = {
                        'cosine': 'vector_cosine_ops',
                        'euclidean': 'vector_l2_ops',
                        'dot': 'vector_ip_ops',
                    }
                    ops = ops_map.get(coll['distance_metric'], 'vector_cosine_ops')
                    await conn.execute(f"""
                        CREATE INDEX idx_ivfflat_{safe_name}
                        ON arkham_vectors.embeddings
                        USING ivfflat (embedding {ops})
                        WITH (lists = {new_lists})
                        WHERE collection = $1
                    """, name)

                # Update metadata
                await conn.execute("""
                    UPDATE arkham_vectors.collections
                    SET lists = $2, probes = $3, last_reindex = NOW(), vector_count = $4
                    WHERE name = $1
                """, name, new_lists, new_probes, count)

            logger.info(f"Reindex complete for '{name}': lists={new_lists}, probes={new_probes}, vectors={count}")

            return {
                "collection": name,
                "vectors": count,
                "lists": new_lists,
                "probes": new_probes,
                "status": "success",
            }

        except CollectionNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Reindex failed for '{name}': {e}")
            raise VectorServiceError(f"Reindex failed: {e}")

    async def reindex_all(self) -> List[Dict[str, Any]]:
        """Reindex all collections. Called from Settings UI or scheduled task."""
        results = []

        collections = await self.list_collections()
        for coll in collections:
            try:
                result = await self.reindex_collection(coll.name)
                results.append(result)
            except Exception as e:
                results.append({
                    "collection": coll.name,
                    "status": "error",
                    "error": str(e),
                })

        return results
