"""Search Shard API endpoints."""

import logging
import time
from typing import Annotated, Any, TYPE_CHECKING

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

if TYPE_CHECKING:
    from .shard import SearchShard

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


def get_shard(request: Request) -> "SearchShard":
    """Get the search shard instance from app state."""
    shard = getattr(request.app.state, "search_shard", None)
    if not shard:
        raise HTTPException(status_code=503, detail="Search shard not available")
    return shard


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


class SearchConfigResponse(BaseModel):
    """Current search configuration and weights."""
    embedding_dimensions: int | None
    semantic_weight: float
    keyword_weight: float
    bm25_enabled: bool
    engines: dict


# --- Endpoints ---


@router.get("/config", response_model=SearchConfigResponse)
async def get_search_config():
    """
    Get current search configuration including model-aware weights.

    Returns:
        - embedding_dimensions: Current embedding model dimensions
        - semantic_weight: Weight for semantic/vector search (0.0-1.0)
        - keyword_weight: Weight for BM25 keyword search (0.0-1.0)
        - bm25_enabled: Whether BM25 scoring is active
        - engines: Status of each search engine
    """
    config = {
        "embedding_dimensions": None,
        "semantic_weight": 0.7,
        "keyword_weight": 0.3,
        "bm25_enabled": _keyword_engine is not None,
        "engines": {
            "semantic": _semantic_engine is not None,
            "keyword": _keyword_engine is not None,
            "hybrid": _hybrid_engine is not None,
        },
    }

    if _hybrid_engine:
        config["embedding_dimensions"] = getattr(_hybrid_engine, 'embedding_dimensions', None)
        config["semantic_weight"] = getattr(_hybrid_engine, 'default_semantic_weight', 0.7)
        config["keyword_weight"] = getattr(_hybrid_engine, 'default_keyword_weight', 0.3)

    return SearchConfigResponse(**config)


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

    # Get facets for filtering UI
    facets = {}
    if _filter_optimizer:
        try:
            facets = await _filter_optimizer.get_available_filters(request.query)
        except Exception as e:
            logger.warning(f"Failed to get facets: {e}")

    # Calculate total: if we got fewer results than limit, we know the total
    # Otherwise, estimate based on whether there are more results
    total = len(results)
    if len(results) == request.limit:
        # There may be more results - estimate total from facets if available
        if facets.get("date_ranges", {}).get("last_year", {}).get("count"):
            total = max(total, facets["date_ranges"]["last_year"]["count"])
    has_more = len(results) == request.limit

    return SearchResponse(
        query=request.query,
        mode=mode.value,
        total=total,
        items=[_result_to_dict(r) for r in results],
        duration_ms=duration_ms,
        facets=facets,
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


# --- AI Junior Analyst ---


class AIJuniorAnalystRequest(BaseModel):
    """Request for AI Junior Analyst analysis."""

    target_id: str
    context: dict[str, Any] = {}
    depth: str = "quick"
    session_id: str | None = None
    message: str | None = None
    conversation_history: list[dict[str, str]] | None = None


@router.post("/ai/junior-analyst")
async def ai_junior_analyst(request: Request, body: AIJuniorAnalystRequest):
    """
    AI Junior Analyst endpoint for search analysis.

    Provides streaming AI analysis of search results and corpus insights.
    """
    # Get shard and frame
    shard = get_shard(request)
    frame = shard.frame

    if not frame.ai_analyst:
        raise HTTPException(status_code=503, detail="AI Analyst service not available")

    if not frame.ai_analyst.is_available():
        raise HTTPException(status_code=503, detail="LLM service not available. Configure LLM endpoint in settings.")

    from arkham_frame.services import AnalysisRequest, AnalysisDepth

    # Map depth string to enum (only QUICK and DETAILED exist)
    depth_map = {
        "quick": AnalysisDepth.QUICK,
        "standard": AnalysisDepth.DETAILED,  # Map standard to detailed
        "detailed": AnalysisDepth.DETAILED,
        "deep": AnalysisDepth.DETAILED,  # Map deep to detailed
    }
    depth = depth_map.get(body.depth, AnalysisDepth.QUICK)

    # Create analysis request
    analysis_request = AnalysisRequest(
        shard="search",
        target_id=body.target_id,
        context=body.context,
        depth=depth,
        session_id=body.session_id,
        message=body.message,
        conversation_history=body.conversation_history,
    )

    # Stream the response
    async def generate():
        async for chunk in frame.ai_analyst.stream_analyze(
            request=analysis_request,
            temperature=0.7,
        ):
            yield chunk

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# --- RAG Chat ---


class RAGChatRequest(BaseModel):
    """Request for RAG Chat - conversational Q&A over document corpus."""

    question: str
    conversation_id: str | None = None
    k_chunks: int = 10
    similarity_threshold: float = 0.5
    project_id: str | None = None
    conversation_history: list[dict[str, str]] | None = None


class CitationInfo(BaseModel):
    """Citation information for a source chunk."""

    chunk_id: str
    doc_id: str
    title: str
    page_number: int | None
    excerpt: str
    score: float


class RAGChatResponse(BaseModel):
    """Response from RAG Chat (non-streaming fallback)."""

    message_id: str
    text: str
    citations: list[CitationInfo]
    chunks_retrieved: int


@router.post("/chat")
async def rag_chat(request: Request, body: RAGChatRequest):
    """
    RAG Chat endpoint - conversational Q&A grounded in document corpus.

    Retrieves relevant chunks via vector search, then generates a response
    with citations. Supports streaming responses.
    """
    # Get shard and frame
    shard = get_shard(request)
    frame = shard.frame

    # Check for required services
    llm = frame.llm
    vectors = frame.vectors

    if not llm:
        raise HTTPException(status_code=503, detail="LLM service not available")
    if not vectors:
        raise HTTPException(status_code=503, detail="Vector service not available")

    import json
    import uuid

    async def generate_rag_response():
        """Generator for streaming RAG response."""
        message_id = str(uuid.uuid4())
        conversation_id = body.conversation_id or str(uuid.uuid4())

        # Emit session info
        yield f"data: {json.dumps({'type': 'session', 'message_id': message_id, 'conversation_id': conversation_id})}\n\n"

        # 1. Embed the question and search for relevant chunks
        try:
            # Build filter for project-scoped search if project_id provided
            search_filter = None
            if body.project_id:
                search_filter = {"project_id": body.project_id}

            search_results = await vectors.search_text(
                collection="arkham_chunks",
                text=body.question,
                limit=body.k_chunks,
                score_threshold=body.similarity_threshold,
                filter=search_filter,
            )
        except Exception as e:
            logger.error(f"RAG vector search failed: {e}")
            yield f"data: {json.dumps({'type': 'error', 'error': f'Search failed: {str(e)}'})}\n\n"
            return

        # 2. Format context from retrieved chunks
        citations = []
        context_parts = ["CONTEXT FROM DOCUMENTS:\n"]

        for i, result in enumerate(search_results, 1):
            # SearchResult has id, score, and payload dict
            payload = result.payload or {}
            chunk_id = result.id
            score = result.score or 0.0
            doc_id = payload.get('document_id', '') or payload.get('doc_id', '')
            title = payload.get('document_title', '') or payload.get('title', 'Unknown')
            page_num = payload.get('page_number')
            text = payload.get('text', '') or payload.get('content', '')

            context_parts.append(f"""
[Chunk {i} - Relevance: {score:.2f}]
From: {title}{f' (page {page_num})' if page_num else ''}
---
{text[:1500]}
---
""")
            citations.append({
                "chunk_id": chunk_id,
                "doc_id": doc_id,
                "title": title,
                "page_number": page_num,
                "excerpt": text[:200] + "..." if len(text) > 200 else text,
                "score": round(score, 4),
            })

        # Emit citations
        yield f"data: {json.dumps({'type': 'citations', 'citations': citations, 'chunks_retrieved': len(search_results)})}\n\n"

        if not search_results:
            yield f"data: {json.dumps({'type': 'text', 'content': 'I could not find any relevant information in the document corpus to answer your question.'})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            return

        # 3. Build messages for LLM
        system_prompt = """You are a knowledgeable research assistant answering questions based on provided document excerpts.

IMPORTANT GUIDELINES:
1. Answer based ONLY on the provided context. Do not use external knowledge.
2. If the answer is not in the provided context, explicitly say "I cannot find information about this in the provided documents."
3. Cite your sources using [Source: Document Name, Page X] notation.
4. For uncertain information, indicate your confidence level.
5. If multiple documents provide conflicting information, acknowledge both perspectives.
6. Keep answers concise but complete.

Format citations at the end of relevant sentences, not all at the end."""

        context_text = "\n".join(context_parts)
        user_message = f"{context_text}\n\nQUESTION: {body.question}\n\nANSWER:"

        # Build conversation history for follow-ups
        messages = []
        if body.conversation_history:
            for msg in body.conversation_history[-6:]:  # Last 3 exchanges max
                messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": user_message})

        # 4. Stream LLM response
        try:
            async for chunk in llm.stream_chat(
                messages=messages,
                system_prompt=system_prompt,
                temperature=0.7,
                max_tokens=2000,
            ):
                text = getattr(chunk, 'text', '') or getattr(chunk, 'content', '') or str(chunk)
                if text:
                    yield f"data: {json.dumps({'type': 'text', 'content': text})}\n\n"
        except Exception as e:
            logger.error(f"RAG LLM generation failed: {e}")
            yield f"data: {json.dumps({'type': 'error', 'error': f'Generation failed: {str(e)}'})}\n\n"
            return

        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(
        generate_rag_response(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# --- AI Feedback ---


class AIFeedbackRequest(BaseModel):
    """Request for AI analysis feedback."""

    session_id: str
    message_id: str | None = None
    rating: str  # "up" or "down"
    feedback_text: str | None = None
    context: dict[str, Any] | None = None


class AIFeedbackResponse(BaseModel):
    """Response after submitting feedback."""

    success: bool
    feedback_id: str


@router.post("/ai/feedback", response_model=AIFeedbackResponse)
async def submit_ai_feedback(request: Request, body: AIFeedbackRequest):
    """
    Submit feedback on AI analysis quality.

    Allows users to rate responses with thumbs up/down
    and optionally provide text feedback.
    """
    import uuid

    shard = get_shard(request)
    frame = shard.frame

    feedback_id = str(uuid.uuid4())

    # Emit feedback event for tracking
    if frame.events:
        await frame.events.emit(
            event_type="ai.feedback.submitted",
            payload={
                "feedback_id": feedback_id,
                "session_id": body.session_id,
                "message_id": body.message_id,
                "rating": body.rating,
                "has_text": bool(body.feedback_text),
                "shard": "search",
            },
            source="search-shard",
        )

    # Store feedback in database
    stored = await shard.store_feedback(
        feedback_id=feedback_id,
        session_id=body.session_id,
        rating=body.rating,
        message_id=body.message_id,
        feedback_text=body.feedback_text,
        context=body.context,
    )

    if stored:
        logger.info(f"AI Feedback stored: session={body.session_id}, rating={body.rating}")
    else:
        logger.warning(f"AI Feedback not stored (DB unavailable): session={body.session_id}")

    return AIFeedbackResponse(success=True, feedback_id=feedback_id)
