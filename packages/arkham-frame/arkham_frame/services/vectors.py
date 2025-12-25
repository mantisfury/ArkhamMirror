"""
VectorService - Qdrant vector store with collection management and embedding.

Provides vector storage, similarity search, and embedding generation
for semantic search capabilities.
"""

from typing import Optional, List, Dict, Any, Union
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import logging
import uuid

logger = logging.getLogger(__name__)


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

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "vector_size": self.vector_size,
            "distance": self.distance.value if isinstance(self.distance, DistanceMetric) else self.distance,
            "points_count": self.points_count,
            "indexed_vectors_count": self.indexed_vectors_count,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
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


# Default embedding dimensions for common models
EMBEDDING_DIMENSIONS = {
    "bge-m3": 1024,
    "bge-large": 1024,
    "bge-base": 768,
    "bge-small": 384,
    "text-embedding-ada-002": 1536,
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "all-MiniLM-L6-v2": 384,
    "all-mpnet-base-v2": 768,
}


class VectorService:
    """
    Qdrant vector store service with embedding support.

    Provides:
        - Collection management (create, delete, list)
        - Vector operations (upsert, delete, search)
        - Batch operations for performance
        - Optional local embedding generation
    """

    # Standard collections used by the frame
    COLLECTION_DOCUMENTS = "arkham_documents"
    COLLECTION_CHUNKS = "arkham_chunks"
    COLLECTION_ENTITIES = "arkham_entities"

    def __init__(self, config):
        self.config = config
        self._client = None
        self._available = False
        self._embedding_model = None
        self._embedding_available = False
        self._default_dimension = 1024  # BGE-M3 default

    async def initialize(self) -> None:
        """Initialize Qdrant connection and optional embedding model."""
        # Initialize Qdrant client
        try:
            from qdrant_client import QdrantClient

            qdrant_url = self.config.get("qdrant.url", "http://localhost:6333")
            self._client = QdrantClient(url=qdrant_url)

            # Test connection
            self._client.get_collections()
            self._available = True
            logger.info(f"Qdrant connected: {qdrant_url}")

        except Exception as e:
            logger.warning(f"Qdrant connection failed: {e}")
            self._available = False

        # Initialize embedding model if configured
        try:
            embedding_model = self.config.get("vectors.embedding_model", "")
            if embedding_model:
                await self._load_embedding_model(embedding_model)
        except Exception as e:
            logger.warning(f"Embedding model failed to load: {e}")
            self._embedding_available = False

        # Ensure standard collections exist
        if self._available:
            await self._ensure_standard_collections()

    async def _load_embedding_model(self, model_name: str) -> None:
        """Load a local embedding model."""
        try:
            from sentence_transformers import SentenceTransformer

            self._embedding_model = SentenceTransformer(model_name)
            self._default_dimension = self._embedding_model.get_sentence_embedding_dimension()
            self._embedding_available = True
            logger.info(f"Embedding model loaded: {model_name} (dim={self._default_dimension})")

        except ImportError:
            logger.warning("sentence-transformers not installed, embedding disabled")
            self._embedding_available = False
        except Exception as e:
            logger.warning(f"Failed to load embedding model {model_name}: {e}")
            self._embedding_available = False

    async def _ensure_standard_collections(self) -> None:
        """Ensure standard collections exist."""
        standard = [
            (self.COLLECTION_DOCUMENTS, self._default_dimension),
            (self.COLLECTION_CHUNKS, self._default_dimension),
            (self.COLLECTION_ENTITIES, self._default_dimension),
        ]

        for collection_name, dimension in standard:
            try:
                if not await self.collection_exists(collection_name):
                    await self.create_collection(
                        name=collection_name,
                        vector_size=dimension,
                        distance=DistanceMetric.COSINE,
                    )
                    logger.info(f"Created standard collection: {collection_name}")
            except Exception as e:
                logger.warning(f"Failed to create collection {collection_name}: {e}")

    async def shutdown(self) -> None:
        """Close Qdrant connection."""
        self._client = None
        self._available = False
        self._embedding_model = None
        self._embedding_available = False
        logger.info("VectorService shutdown complete")

    def is_available(self) -> bool:
        """Check if Qdrant is available."""
        return self._available

    def embedding_available(self) -> bool:
        """Check if embedding generation is available."""
        return self._embedding_available

    # =========================================================================
    # Collection Management
    # =========================================================================

    async def create_collection(
        self,
        name: str,
        vector_size: int,
        distance: DistanceMetric = DistanceMetric.COSINE,
        on_disk: bool = False,
    ) -> CollectionInfo:
        """Create a new vector collection."""
        if not self._available:
            raise VectorStoreUnavailableError("Qdrant not available")

        try:
            from qdrant_client.models import VectorParams, Distance

            distance_map = {
                DistanceMetric.COSINE: Distance.COSINE,
                DistanceMetric.EUCLIDEAN: Distance.EUCLID,
                DistanceMetric.DOT: Distance.DOT,
            }

            self._client.create_collection(
                collection_name=name,
                vectors_config=VectorParams(
                    size=vector_size,
                    distance=distance_map.get(distance, Distance.COSINE),
                    on_disk=on_disk,
                ),
            )

            logger.info(f"Created collection: {name} (size={vector_size}, distance={distance})")

            return CollectionInfo(
                name=name,
                vector_size=vector_size,
                distance=distance,
                created_at=datetime.utcnow(),
            )

        except Exception as e:
            if "already exists" in str(e).lower():
                raise CollectionExistsError(name)
            raise VectorServiceError(f"Failed to create collection: {e}")

    async def delete_collection(self, name: str) -> bool:
        """Delete a collection."""
        if not self._available:
            raise VectorStoreUnavailableError("Qdrant not available")

        try:
            self._client.delete_collection(collection_name=name)
            logger.info(f"Deleted collection: {name}")
            return True
        except Exception as e:
            if "not found" in str(e).lower() or "doesn't exist" in str(e).lower():
                return False
            raise VectorServiceError(f"Failed to delete collection: {e}")

    async def collection_exists(self, name: str) -> bool:
        """Check if a collection exists."""
        if not self._available:
            return False

        try:
            collections = self._client.get_collections().collections
            return any(c.name == name for c in collections)
        except Exception:
            return False

    async def get_collection(self, name: str) -> CollectionInfo:
        """Get collection information."""
        if not self._available:
            raise VectorStoreUnavailableError("Qdrant not available")

        try:
            info = self._client.get_collection(collection_name=name)

            # Parse distance metric
            distance_str = str(info.config.params.vectors.distance).lower()
            if "cosine" in distance_str:
                distance = DistanceMetric.COSINE
            elif "euclid" in distance_str:
                distance = DistanceMetric.EUCLIDEAN
            else:
                distance = DistanceMetric.DOT

            return CollectionInfo(
                name=name,
                vector_size=info.config.params.vectors.size,
                distance=distance,
                points_count=info.points_count,
                indexed_vectors_count=info.indexed_vectors_count,
                status=str(info.status).lower() if info.status else "unknown",
            )

        except Exception as e:
            if "not found" in str(e).lower() or "doesn't exist" in str(e).lower():
                raise CollectionNotFoundError(name)
            raise VectorServiceError(f"Failed to get collection info: {e}")

    async def list_collections(self) -> List[CollectionInfo]:
        """List all collections."""
        if not self._available:
            return []

        try:
            collections = self._client.get_collections().collections
            result = []

            for c in collections:
                try:
                    info = await self.get_collection(c.name)
                    result.append(info)
                except Exception:
                    # Include basic info even if details fail
                    result.append(CollectionInfo(
                        name=c.name,
                        vector_size=0,
                        distance=DistanceMetric.COSINE,
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
            raise VectorStoreUnavailableError("Qdrant not available")

        if not points:
            return 0

        try:
            from qdrant_client.models import PointStruct

            qdrant_points = [
                PointStruct(
                    id=p.id,
                    vector=p.vector,
                    payload=p.payload,
                )
                for p in points
            ]

            self._client.upsert(
                collection_name=collection,
                points=qdrant_points,
            )

            logger.debug(f"Upserted {len(points)} vectors to {collection}")
            return len(points)

        except Exception as e:
            if "not found" in str(e).lower() or "doesn't exist" in str(e).lower():
                raise CollectionNotFoundError(collection)
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
            raise VectorStoreUnavailableError("Qdrant not available")

        if not ids:
            return 0

        try:
            from qdrant_client.models import PointIdsList

            self._client.delete(
                collection_name=collection,
                points_selector=PointIdsList(points=ids),
            )

            logger.debug(f"Deleted {len(ids)} vectors from {collection}")
            return len(ids)

        except Exception as e:
            if "not found" in str(e).lower() or "doesn't exist" in str(e).lower():
                raise CollectionNotFoundError(collection)
            raise VectorServiceError(f"Failed to delete vectors: {e}")

    async def delete_by_filter(
        self,
        collection: str,
        filter: Dict[str, Any],
    ) -> bool:
        """Delete vectors matching a filter."""
        if not self._available:
            raise VectorStoreUnavailableError("Qdrant not available")

        try:
            from qdrant_client.models import Filter, FieldCondition, MatchValue

            # Build filter conditions
            conditions = []
            for key, value in filter.items():
                conditions.append(
                    FieldCondition(
                        key=key,
                        match=MatchValue(value=value),
                    )
                )

            qdrant_filter = Filter(must=conditions)

            self._client.delete(
                collection_name=collection,
                points_selector=qdrant_filter,
            )

            logger.debug(f"Deleted vectors by filter from {collection}")
            return True

        except Exception as e:
            if "not found" in str(e).lower() or "doesn't exist" in str(e).lower():
                raise CollectionNotFoundError(collection)
            raise VectorServiceError(f"Failed to delete vectors by filter: {e}")

    async def get_vector(
        self,
        collection: str,
        id: str,
        with_vector: bool = False,
    ) -> Optional[VectorPoint]:
        """Get a vector by ID."""
        if not self._available:
            raise VectorStoreUnavailableError("Qdrant not available")

        try:
            result = self._client.retrieve(
                collection_name=collection,
                ids=[id],
                with_vectors=with_vector,
            )

            if result:
                point = result[0]
                return VectorPoint(
                    id=str(point.id),
                    vector=point.vector if with_vector and point.vector else [],
                    payload=point.payload or {},
                )

            return None

        except Exception as e:
            if "not found" in str(e).lower() or "doesn't exist" in str(e).lower():
                raise CollectionNotFoundError(collection)
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
    ) -> List[SearchResult]:
        """Search for similar vectors."""
        if not self._available:
            raise VectorStoreUnavailableError("Qdrant not available")

        try:
            from qdrant_client.models import Filter, FieldCondition, MatchValue

            # Build filter if provided
            qdrant_filter = None
            if filter:
                conditions = []
                for key, value in filter.items():
                    conditions.append(
                        FieldCondition(
                            key=key,
                            match=MatchValue(value=value),
                        )
                    )
                qdrant_filter = Filter(must=conditions)

            results = self._client.search(
                collection_name=collection,
                query_vector=query_vector,
                limit=limit,
                query_filter=qdrant_filter,
                score_threshold=score_threshold,
                with_vectors=with_vectors,
            )

            return [
                SearchResult(
                    id=str(r.id),
                    score=r.score,
                    payload=r.payload or {},
                    vector=r.vector if with_vectors else None,
                )
                for r in results
            ]

        except Exception as e:
            if "not found" in str(e).lower() or "doesn't exist" in str(e).lower():
                raise CollectionNotFoundError(collection)
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
        if not self._embedding_available:
            raise EmbeddingError("Embedding model not available")

        vector = await self.embed_text(text)
        return await self.search(
            collection=collection,
            query_vector=vector,
            limit=limit,
            filter=filter,
            score_threshold=score_threshold,
        )

    async def search_batch(
        self,
        collection: str,
        query_vectors: List[List[float]],
        limit: int = 10,
        filter: Optional[Dict[str, Any]] = None,
    ) -> List[List[SearchResult]]:
        """Batch search for multiple query vectors."""
        if not self._available:
            raise VectorStoreUnavailableError("Qdrant not available")

        try:
            from qdrant_client.models import Filter, FieldCondition, MatchValue, SearchRequest

            # Build filter if provided
            qdrant_filter = None
            if filter:
                conditions = []
                for key, value in filter.items():
                    conditions.append(
                        FieldCondition(
                            key=key,
                            match=MatchValue(value=value),
                        )
                    )
                qdrant_filter = Filter(must=conditions)

            requests = [
                SearchRequest(
                    vector=qv,
                    limit=limit,
                    filter=qdrant_filter,
                )
                for qv in query_vectors
            ]

            batch_results = self._client.search_batch(
                collection_name=collection,
                requests=requests,
            )

            return [
                [
                    SearchResult(
                        id=str(r.id),
                        score=r.score,
                        payload=r.payload or {},
                    )
                    for r in results
                ]
                for results in batch_results
            ]

        except Exception as e:
            if "not found" in str(e).lower() or "doesn't exist" in str(e).lower():
                raise CollectionNotFoundError(collection)
            raise VectorServiceError(f"Batch search failed: {e}")

    # =========================================================================
    # Embedding Operations
    # =========================================================================

    async def embed_text(self, text: str) -> List[float]:
        """Generate embedding for text."""
        if not self._embedding_available:
            raise EmbeddingError("Embedding model not available")

        try:
            embedding = self._embedding_model.encode(text, convert_to_numpy=True)
            return embedding.tolist()
        except Exception as e:
            raise EmbeddingError(f"Failed to generate embedding: {e}")

    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts."""
        if not self._embedding_available:
            raise EmbeddingError("Embedding model not available")

        if not texts:
            return []

        try:
            embeddings = self._embedding_model.encode(texts, convert_to_numpy=True)
            return [e.tolist() for e in embeddings]
        except Exception as e:
            raise EmbeddingError(f"Failed to generate embeddings: {e}")

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
            # Remove text from payload to save space (optional)
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
            info = await self.get_collection(collection)
            return info.points_count
        except CollectionNotFoundError:
            return 0
        except Exception:
            return 0

    async def scroll(
        self,
        collection: str,
        limit: int = 100,
        offset: Optional[str] = None,
        filter: Optional[Dict[str, Any]] = None,
        with_vectors: bool = False,
    ) -> tuple[List[VectorPoint], Optional[str]]:
        """Scroll through vectors in a collection."""
        if not self._available:
            raise VectorStoreUnavailableError("Qdrant not available")

        try:
            from qdrant_client.models import Filter, FieldCondition, MatchValue

            # Build filter if provided
            qdrant_filter = None
            if filter:
                conditions = []
                for key, value in filter.items():
                    conditions.append(
                        FieldCondition(
                            key=key,
                            match=MatchValue(value=value),
                        )
                    )
                qdrant_filter = Filter(must=conditions)

            result = self._client.scroll(
                collection_name=collection,
                limit=limit,
                offset=offset,
                scroll_filter=qdrant_filter,
                with_vectors=with_vectors,
            )

            points = [
                VectorPoint(
                    id=str(p.id),
                    vector=p.vector if with_vectors and p.vector else [],
                    payload=p.payload or {},
                )
                for p in result[0]
            ]

            next_offset = result[1]

            return points, next_offset

        except Exception as e:
            if "not found" in str(e).lower() or "doesn't exist" in str(e).lower():
                raise CollectionNotFoundError(collection)
            raise VectorServiceError(f"Scroll failed: {e}")

    async def get_stats(self) -> Dict[str, Any]:
        """Get vector service statistics."""
        stats = {
            "available": self._available,
            "embedding_available": self._embedding_available,
            "embedding_dimension": self._default_dimension if self._embedding_available else None,
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
