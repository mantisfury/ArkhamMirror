"""Search Shard API endpoints."""

import logging
import time
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from .models import (
    SearchMode,
    SearchQuery,
    SearchResult,
    SearchResultItem,
    SearchFilters,
    SortBy,
    SortOrder,
    SuggestionItem,
    SimilarityRequest,
)
from .filters import FilterBuilder

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/search", tags=["search"])

# These get set by the shard on initialization
_semantic_engine = None
_keyword_engine = None
_hybrid_engine = None
_filter_optimizer = None
_event_bus = None


def init_api(semantic_engine, keyword_engine, hybrid_engine, filter_optimizer, event_bus):
    """Initialize API with shard dependencies."""
    global _semantic_engine, _keyword_engine, _hybrid_engine, _filter_optimizer, _event_bus
    _semantic_engine = semantic_engine
    _keyword_engine = keyword_engine
    _hybrid_engine = hybrid_engine
    _filter_optimizer = filter_optimizer
    _event_bus = event_bus


# --- Request/Response Models ---


class SearchRequest(BaseModel):
    query: str
    mode: str = "hybrid"
    filters: dict | None = None
    limit: int = 20
    offset: int = 0
    sort_by: str = "relevance"
    sort_order: str = "desc"
    semantic_weight: float = 0.7
    keyword_weight: float = 0.3


class SearchResponse(BaseModel):
    query: str
    mode: str
    total: int
    items: list[dict]
    duration_ms: float
    facets: dict
    offset: int
    limit: int
    has_more: bool


class SuggestResponse(BaseModel):
    suggestions: list[dict]


class SimilarResponse(BaseModel):
    doc_id: str
    similar: list[dict]
    total: int


class FiltersResponse(BaseModel):
    available: dict


# --- Endpoints ---


@router.post("/", response_model=SearchResponse)
async def search(request: SearchRequest):
    """
    Main search endpoint - supports hybrid, semantic, and keyword search.

    The search mode determines which engine is used:
    - hybrid: Combines semantic and keyword search with configurable weights
    - semantic: Vector similarity search only
    - keyword: Full-text search only
    """
    if not _hybrid_engine:
        raise HTTPException(status_code=503, detail="Search service not initialized")

    start_time = time.time()

    # Parse search mode
    try:
        mode = SearchMode(request.mode.lower())
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid search mode: {request.mode}")

    # Parse filters
    filters = None
    if request.filters:
        filters = FilterBuilder.from_dict(request.filters)
        is_valid, error = FilterBuilder.validate(filters)
        if not is_valid:
            raise HTTPException(status_code=400, detail=error)

    # Parse sort options
    try:
        sort_by = SortBy(request.sort_by.lower())
        sort_order = SortOrder(request.sort_order.lower())
    except ValueError:
        sort_by = SortBy.RELEVANCE
        sort_order = SortOrder.DESC

    # Build query
    query = SearchQuery(
        query=request.query,
        mode=mode,
        filters=filters,
        limit=request.limit,
        offset=request.offset,
        sort_by=sort_by,
        sort_order=sort_order,
        semantic_weight=request.semantic_weight,
        keyword_weight=request.keyword_weight,
    )

    # Execute search
    try:
        if mode == SearchMode.SEMANTIC:
            results = await _semantic_engine.search(query)
        elif mode == SearchMode.KEYWORD:
            results = await _keyword_engine.search(query)
        else:  # HYBRID
            results = await _hybrid_engine.search(query)
    except Exception as e:
        logger.error(f"Search failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

    duration_ms = (time.time() - start_time) * 1000

    # Emit event
    if _event_bus:
        await _event_bus.emit(
            "search.query.executed",
            {
                "query": request.query,
                "mode": mode.value,
                "results_count": len(results),
                "duration_ms": duration_ms,
            },
            source="search-shard",
        )

    # Build response
    total = len(results)  # TODO: Get actual total from database
    has_more = (request.offset + len(results)) < total

    return SearchResponse(
        query=request.query,
        mode=mode.value,
        total=total,
        items=[_result_to_dict(r) for r in results],
        duration_ms=duration_ms,
        facets={},  # TODO: Add facet aggregations
        offset=request.offset,
        limit=request.limit,
        has_more=has_more,
    )


@router.post("/semantic", response_model=SearchResponse)
async def search_semantic(request: SearchRequest):
    """Vector-only semantic search."""
    request.mode = "semantic"
    return await search(request)


@router.post("/keyword", response_model=SearchResponse)
async def search_keyword(request: SearchRequest):
    """Text-only keyword search."""
    request.mode = "keyword"
    return await search(request)


@router.get("/suggest", response_model=SuggestResponse)
async def autocomplete_suggest(
    q: Annotated[str, Query(min_length=1)] = "",
    limit: int = 10,
):
    """
    Get autocomplete suggestions based on query prefix.

    Returns suggestions from:
    - Document titles
    - Entity names
    - Common search terms
    """
    if not _keyword_engine:
        raise HTTPException(status_code=503, detail="Search service not initialized")

    if not q:
        return SuggestResponse(suggestions=[])

    try:
        suggestions = await _keyword_engine.suggest(q, limit=limit)
    except Exception as e:
        logger.error(f"Autocomplete failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Autocomplete failed: {str(e)}")

    return SuggestResponse(
        suggestions=[
            {
                "text": text,
                "score": score,
                "type": "term",
            }
            for text, score in suggestions
        ]
    )


@router.post("/similar/{doc_id}", response_model=SimilarResponse)
async def find_similar_documents(
    doc_id: str,
    limit: int = 10,
    min_similarity: float = 0.5,
    filters: dict | None = None,
):
    """
    Find documents similar to a given document.

    Uses vector similarity to find related documents.
    """
    if not _semantic_engine:
        raise HTTPException(status_code=503, detail="Search service not initialized")

    # Parse filters
    search_filters = None
    if filters:
        search_filters = FilterBuilder.from_dict(filters)

    try:
        results = await _semantic_engine.find_similar(
            doc_id=doc_id,
            limit=limit,
            min_similarity=min_similarity,
        )
    except Exception as e:
        logger.error(f"Similar search failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Similar search failed: {str(e)}")

    return SimilarResponse(
        doc_id=doc_id,
        similar=[_result_to_dict(r) for r in results],
        total=len(results),
    )


@router.get("/filters", response_model=FiltersResponse)
async def get_available_filters(q: str | None = None):
    """
    Get available filter options for the current query.

    Returns counts for each filter option to help users refine searches.
    """
    if not _filter_optimizer:
        raise HTTPException(status_code=503, detail="Search service not initialized")

    try:
        available = await _filter_optimizer.get_available_filters(q)
    except Exception as e:
        logger.error(f"Failed to get filters: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get filters: {str(e)}")

    return FiltersResponse(available=available)


# --- Helper Functions ---


def _result_to_dict(result: SearchResultItem) -> dict:
    """Convert SearchResultItem to dictionary for JSON response."""
    return {
        "doc_id": result.doc_id,
        "chunk_id": result.chunk_id,
        "title": result.title,
        "excerpt": result.excerpt,
        "score": round(result.score, 4),
        "file_type": result.file_type,
        "created_at": result.created_at.isoformat() if result.created_at else None,
        "page_number": result.page_number,
        "highlights": result.highlights,
        "entities": result.entities,
        "project_ids": result.project_ids,
        "metadata": result.metadata,
    }
