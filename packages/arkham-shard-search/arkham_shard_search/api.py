"""Search Shard API endpoints."""

import logging
import time
from typing import Annotated, Any, TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Query, Request
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

try:
    from arkham_frame.auth import (
        current_optional_user,
        require_project_member,
    )
except ImportError:
    async def current_optional_user():
        return None
    async def require_project_member():
        return None

# Import wide event logging utilities (with fallback)
try:
    from arkham_frame import log_operation
    WIDE_EVENTS_AVAILABLE = True
except ImportError:
    WIDE_EVENTS_AVAILABLE = False
    from contextlib import contextmanager
    @contextmanager
    def log_operation(*args, **kwargs):
        yield None

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/search", tags=["search"])

# These get set by the shard on initialization
_semantic_engine = None
_keyword_engine = None
_hybrid_engine = None
_regex_engine = None
_filter_optimizer = None
_event_bus = None


def init_api(semantic_engine, keyword_engine, hybrid_engine, regex_engine, filter_optimizer, event_bus):
    """Initialize API with shard dependencies."""
    global _semantic_engine, _keyword_engine, _hybrid_engine, _regex_engine, _filter_optimizer, _event_bus
    _semantic_engine = semantic_engine
    _keyword_engine = keyword_engine
    _hybrid_engine = hybrid_engine
    _regex_engine = regex_engine
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
async def search(
    req: Request,
    request: SearchRequest,
    user = Depends(current_optional_user),
):
    """
    Main search endpoint - supports hybrid, semantic, and keyword search.

    The search mode determines which engine is used:
    - hybrid: Combines semantic and keyword search with configurable weights
    - semantic: Vector similarity search only
    - keyword: Full-text search only
    
    All searches are scoped to the active project for data isolation.
    """
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required for search")
    
    # Get active project from frame
    shard = get_shard(req)
    active_project_id = await shard.frame.get_active_project_id(str(user.id)) if shard.frame else None
    
    with log_operation("search.execute", query=request.query, mode=request.mode, project_id=active_project_id) as event:
        if event:
            event.user(id=str(user.id))
            event.context("shard", "search")
            event.context("operation", "search")
            event.input(
                query_length=len(request.query),
                mode=request.mode,
                limit=request.limit,
                offset=request.offset,
                has_filters=request.filters is not None,
                semantic_weight=request.semantic_weight,
                keyword_weight=request.keyword_weight,
            )
            if active_project_id:
                event.context("project_id", active_project_id)
        
        if not _hybrid_engine:
            if event:
                event.error("ServiceUnavailable", "Search service not initialized")
            raise HTTPException(status_code=503, detail="Search service not initialized")
        
        if not active_project_id:
            if event:
                event.error("NoActiveProject", "No active project selected")
            raise HTTPException(
                status_code=400, 
                detail="No active project selected. Please select a project to search."
            )
        
        # Verify user is a member of the project
        await require_project_member(active_project_id, user, req)

        start_time = time.time()

        # Parse search mode
        try:
            mode = SearchMode(request.mode.lower())
        except ValueError:
            if event:
                event.error("InvalidSearchMode", f"Invalid search mode: {request.mode}")
            raise HTTPException(status_code=400, detail=f"Invalid search mode: {request.mode}")

        # Parse filters and force project_id
        filters = None
        if request.filters:
            filters = FilterBuilder.from_dict(request.filters)
            is_valid, error = FilterBuilder.validate(filters)
            if not is_valid:
                if event:
                    event.error("InvalidFilters", error)
                raise HTTPException(status_code=400, detail=error)
        else:
            filters = SearchFilters()
        
        # Force project_id to active project for data isolation
        if not filters.project_ids:
            filters.project_ids = []
        if active_project_id not in filters.project_ids:
            filters.project_ids = [active_project_id]

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

        # Execute search with dependency tracking
        search_start = time.time()
        try:
            if mode == SearchMode.SEMANTIC:
                results = await _semantic_engine.search(query)
                search_duration_ms = int((time.time() - search_start) * 1000)
                if event:
                    event.dependency("vector_search", duration_ms=search_duration_ms, mode="semantic")
            elif mode == SearchMode.KEYWORD:
                results = await _keyword_engine.search(query)
                search_duration_ms = int((time.time() - search_start) * 1000)
                if event:
                    event.dependency("keyword_search", duration_ms=search_duration_ms, mode="keyword")
            else:  # HYBRID
                results = await _hybrid_engine.search(query)
                search_duration_ms = int((time.time() - search_start) * 1000)
                if event:
                    event.dependency("hybrid_search", duration_ms=search_duration_ms, mode="hybrid")
        except Exception as e:
            search_duration_ms = int((time.time() - search_start) * 1000)
            logger.error(f"Search failed: {e}", exc_info=True)
            if event:
                event.dependency("search_engine", duration_ms=search_duration_ms, error=str(e))
                event.error("SearchFailed", str(e))
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

        if event:
            event.output(
                result_count=len(results),
                total=total,
                top_score=results[0].score if results else None,
                duration_ms=duration_ms,
            )

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
async def search_semantic(
    req: Request,
    request: SearchRequest,
    user = Depends(current_optional_user),
):
    """Vector-only semantic search."""
    request.mode = "semantic"
    return await search(req, request, user)


@router.post("/keyword", response_model=SearchResponse)
async def search_keyword(
    req: Request,
    request: SearchRequest,
    user = Depends(current_optional_user),
):
    """Text-only keyword search."""
    request.mode = "keyword"
    return await search(req, request, user)


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
                collection="arkham_documents",  # Use correct collection name (embeddings are per-chunk in documents)
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
        # Get db pool for enrichment
        db_pool = vectors._pool if hasattr(vectors, '_pool') else None
        db_conn = None
        if db_pool:
            try:
                db_conn = await db_pool.acquire()
            except Exception as e:
                logger.debug(f"Could not acquire db connection for RAG enrichment: {e}")

        citations = []
        context_parts = ["CONTEXT FROM DOCUMENTS:\n"]

        try:
            for i, result in enumerate(search_results, 1):
                # SearchResult has id, score, and payload dict
                payload = result.payload or {}
                chunk_id = payload.get('chunk_id') or result.id
                score = result.score or 0.0
                doc_id = payload.get('document_id', '') or payload.get('doc_id', '')
                title = payload.get('document_title', '') or payload.get('title', '')
                page_num = payload.get('page_number')
                text = payload.get('text', '') or payload.get('content', '')

                # Enrich from database if we have minimal payload
                if db_conn and chunk_id and not text:
                    try:
                        row = await db_conn.fetchrow(
                            """SELECT c.id, c.text, c.page_number,
                                      d.filename, d.mime_type
                               FROM arkham_frame.chunks c
                               LEFT JOIN arkham_frame.documents d ON c.document_id = d.id
                               WHERE c.id = $1""",
                            chunk_id
                        )
                        if row:
                            text = row.get('text', '')
                            if not title:
                                title = row.get('filename', '')
                            if not page_num:
                                page_num = row.get('page_number')
                            if not doc_id:
                                doc_id = row.get('doc_id', '')
                    except Exception as e:
                        logger.debug(f"Could not fetch chunk {chunk_id}: {e}")

                if not title:
                    title = "Unknown"

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
        finally:
            # Release db connection
            if db_conn and db_pool:
                await db_pool.release(db_conn)

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
        # Include system prompt as first message in the messages array
        messages = [{"role": "system", "content": system_prompt}]
        if body.conversation_history:
            for msg in body.conversation_history[-6:]:  # Last 3 exchanges max
                messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": user_message})

        # 4. Stream LLM response
        try:
            async for chunk in llm.stream_chat(
                messages=messages,
                temperature=0.7,
                max_tokens=2000,
            ):
                # Extract text from StreamChunk - don't use str() fallback
                text = getattr(chunk, 'text', None) or getattr(chunk, 'content', None) or ''
                if text and isinstance(text, str) and text.strip():
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


# --- Regex Search ---


class RegexSearchRequest(BaseModel):
    """Request for regex search."""
    pattern: str
    flags: list[str] = []
    project_id: str | None = None
    document_ids: list[str] | None = None
    limit: int = 100
    offset: int = 0
    highlight: bool = True
    context_chars: int = 100


class RegexMatchResponse(BaseModel):
    """Individual regex match."""
    document_id: str
    document_title: str
    page_number: int | None
    chunk_id: str | None
    match_text: str
    context: str
    start_offset: int
    end_offset: int
    line_number: int | None


class RegexSearchResponse(BaseModel):
    """Response for regex search."""
    pattern: str
    matches: list[RegexMatchResponse]
    total_matches: int
    total_chunks_with_matches: int
    documents_searched: int
    duration_ms: float
    error: str | None = None


class ValidatePatternRequest(BaseModel):
    """Request to validate regex pattern."""
    pattern: str


class ValidatePatternResponse(BaseModel):
    """Response for pattern validation."""
    valid: bool
    error: str | None = None
    estimated_performance: str


class RegexPresetResponse(BaseModel):
    """Regex preset."""
    id: str
    name: str
    pattern: str
    description: str
    category: str
    flags: list[str] = []
    is_system: bool = True


class CreatePresetRequest(BaseModel):
    """Request to create custom preset."""
    name: str
    pattern: str
    description: str = ""
    category: str = "custom"
    flags: list[str] = []


@router.post("/regex", response_model=RegexSearchResponse)
async def search_regex(request: Request, body: RegexSearchRequest):
    """
    Search using regex pattern across document content.

    Supports flags: case_insensitive, multiline, dotall

    The search uses PostgreSQL native regex matching for scalability,
    with pattern matching happening in the database.
    """
    if not _regex_engine:
        raise HTTPException(status_code=503, detail="Regex search not initialized")

    # Validate pattern first
    valid, error, perf = _regex_engine.validate_pattern(body.pattern)
    if not valid:
        raise HTTPException(status_code=400, detail=f"Invalid regex pattern: {error}")
    if perf == "dangerous":
        raise HTTPException(
            status_code=400,
            detail="Pattern may cause performance issues (catastrophic backtracking)"
        )

    from .models import RegexSearchQuery

    query = RegexSearchQuery(
        pattern=body.pattern,
        flags=body.flags,
        project_id=body.project_id,
        document_ids=body.document_ids,
        limit=body.limit,
        offset=body.offset,
        highlight=body.highlight,
        context_chars=body.context_chars,
    )

    try:
        result = await _regex_engine.search(query)
    except Exception as e:
        logger.error(f"Regex search failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

    # Emit event (following existing pattern)
    if _event_bus:
        await _event_bus.emit(
            "search.regex.executed",
            {
                "pattern": body.pattern,
                "flags": body.flags,
                "matches_count": result.total_matches,
                "documents_searched": result.documents_searched,
                "duration_ms": result.duration_ms,
            },
            source="search-shard",
        )

    return RegexSearchResponse(
        pattern=result.pattern,
        matches=[
            RegexMatchResponse(
                document_id=m.document_id,
                document_title=m.document_title,
                page_number=m.page_number,
                chunk_id=m.chunk_id,
                match_text=m.match_text,
                context=m.context,
                start_offset=m.start_offset,
                end_offset=m.end_offset,
                line_number=m.line_number,
            )
            for m in result.matches
        ],
        total_matches=result.total_matches,
        total_chunks_with_matches=result.total_chunks_with_matches,
        documents_searched=result.documents_searched,
        duration_ms=result.duration_ms,
        error=result.error,
    )


@router.post("/regex/validate", response_model=ValidatePatternResponse)
async def validate_regex_pattern(body: ValidatePatternRequest):
    """
    Validate a regex pattern and estimate performance.

    Returns validation status, error message (if invalid),
    and performance estimate (fast/moderate/slow/dangerous).
    """
    if not _regex_engine:
        raise HTTPException(status_code=503, detail="Regex search not initialized")

    valid, error, perf = _regex_engine.validate_pattern(body.pattern)

    return ValidatePatternResponse(
        valid=valid,
        error=error,
        estimated_performance=perf,
    )


@router.get("/regex/presets", response_model=list[RegexPresetResponse])
async def get_regex_presets(category: str | None = None):
    """
    Get available regex presets.

    Categories: pii, contact, financial, technical, temporal, custom

    Returns both system presets and custom user-defined presets.
    """
    if not _regex_engine:
        raise HTTPException(status_code=503, detail="Regex search not initialized")

    presets = await _regex_engine.get_presets(category=category)

    return [
        RegexPresetResponse(
            id=p["id"],
            name=p["name"],
            pattern=p["pattern"],
            description=p.get("description", ""),
            category=p["category"],
            flags=p.get("flags", []),
            is_system=p.get("is_system", True),
        )
        for p in presets
    ]


@router.post("/regex/presets", response_model=RegexPresetResponse)
async def create_regex_preset(request: Request, body: CreatePresetRequest):
    """
    Create a custom regex preset.

    Custom presets are stored in the database and can be
    retrieved alongside system presets.
    """
    if not _regex_engine:
        raise HTTPException(status_code=503, detail="Regex search not initialized")

    # Validate pattern
    valid, error, _ = _regex_engine.validate_pattern(body.pattern)
    if not valid:
        raise HTTPException(status_code=400, detail=f"Invalid pattern: {error}")

    # Get tenant_id if available (following codebase pattern)
    shard = get_shard(request)
    tenant_id = shard.get_tenant_id_or_none() if hasattr(shard, 'get_tenant_id_or_none') else None

    try:
        preset = await _regex_engine.save_custom_preset(
            name=body.name,
            pattern=body.pattern,
            description=body.description,
            category=body.category,
            flags=body.flags,
            tenant_id=str(tenant_id) if tenant_id else None,
        )
    except Exception as e:
        logger.error(f"Failed to create preset: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create preset: {str(e)}")

    # Emit event
    if _event_bus:
        await _event_bus.emit(
            "search.regex.preset_created",
            {"preset_id": preset["id"], "name": preset["name"]},
            source="search-shard",
        )

    return RegexPresetResponse(**preset)


@router.delete("/regex/presets/{preset_id}")
async def delete_regex_preset(request: Request, preset_id: str):
    """
    Delete a custom regex preset.

    System presets cannot be deleted.
    """
    if not _regex_engine:
        raise HTTPException(status_code=503, detail="Regex search not initialized")

    # Get tenant_id if available
    shard = get_shard(request)
    tenant_id = shard.get_tenant_id_or_none() if hasattr(shard, 'get_tenant_id_or_none') else None

    try:
        deleted = await _regex_engine.delete_custom_preset(
            preset_id=preset_id,
            tenant_id=str(tenant_id) if tenant_id else None,
        )
    except Exception as e:
        logger.error(f"Failed to delete preset: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to delete preset: {str(e)}")

    if not deleted:
        raise HTTPException(status_code=404, detail="Preset not found or is a system preset")

    return {"success": True, "preset_id": preset_id}


# --- Pattern Extractions API ---


class PatternExtractionResponse(BaseModel):
    """Individual pattern extraction."""
    id: str
    document_id: str
    preset_id: str
    preset_name: str | None
    category: str | None
    match_text: str
    context: str | None
    page_number: int | None
    chunk_id: str | None
    start_offset: int | None
    end_offset: int | None
    line_number: int | None
    extracted_at: str | None


class ExtractionsListResponse(BaseModel):
    """Response for pattern extractions list."""
    extractions: list[PatternExtractionResponse]
    total: int
    document_id: str | None = None
    preset_id: str | None = None
    category: str | None = None


class ExtractionStatsResponse(BaseModel):
    """Response for extraction statistics."""
    total_extractions: int
    documents_with_patterns: int
    by_category: dict[str, int]
    by_preset: dict[str, int]


@router.get("/regex/extractions", response_model=ExtractionsListResponse)
async def get_pattern_extractions(
    request: Request,
    document_id: str | None = None,
    preset_id: str | None = None,
    category: str | None = None,
    limit: int = 100,
    offset: int = 0,
):
    """
    Get auto-extracted pattern matches.

    These are patterns automatically extracted when documents are parsed.
    Filter by document_id, preset_id, or category.
    """
    shard = get_shard(request)

    if not shard._db:
        raise HTTPException(status_code=503, detail="Database not available")

    query = """
        SELECT id, document_id, preset_id, preset_name, category, match_text,
               context, page_number, chunk_id, start_offset, end_offset,
               line_number, extracted_at
        FROM arkham_search.pattern_extractions
        WHERE 1=1
    """
    params: dict = {}

    if document_id:
        query += " AND document_id = :document_id"
        params["document_id"] = document_id

    if preset_id:
        query += " AND preset_id = :preset_id"
        params["preset_id"] = preset_id

    if category:
        query += " AND category = :category"
        params["category"] = category

    # Get total count
    count_query = """
        SELECT COUNT(*) as total FROM arkham_search.pattern_extractions WHERE 1=1
    """
    if document_id:
        count_query += " AND document_id = :document_id"
    if preset_id:
        count_query += " AND preset_id = :preset_id"
    if category:
        count_query += " AND category = :category"

    try:
        count_row = await shard._db.fetch_one(count_query, params)
        total = count_row["total"] if count_row else 0
    except Exception:
        total = 0

    query += " ORDER BY extracted_at DESC LIMIT :limit OFFSET :offset"
    params["limit"] = limit
    params["offset"] = offset

    try:
        rows = await shard._db.fetch_all(query, params)
    except Exception as e:
        logger.error(f"Failed to fetch extractions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch extractions: {str(e)}")

    extractions = [
        PatternExtractionResponse(
            id=row["id"],
            document_id=row["document_id"],
            preset_id=row["preset_id"],
            preset_name=row["preset_name"],
            category=row["category"],
            match_text=row["match_text"],
            context=row["context"],
            page_number=row["page_number"],
            chunk_id=row["chunk_id"],
            start_offset=row["start_offset"],
            end_offset=row["end_offset"],
            line_number=row["line_number"],
            extracted_at=str(row["extracted_at"]) if row["extracted_at"] else None,
        )
        for row in rows
    ]

    return ExtractionsListResponse(
        extractions=extractions,
        total=total,
        document_id=document_id,
        preset_id=preset_id,
        category=category,
    )


@router.get("/regex/extractions/stats", response_model=ExtractionStatsResponse)
async def get_extraction_stats(
    request: Request,
    project_id: str | None = None,
):
    """
    Get statistics on pattern extractions.

    Returns counts by category and preset.
    """
    shard = get_shard(request)

    if not shard._db:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        # Total extractions
        total_row = await shard._db.fetch_one(
            "SELECT COUNT(*) as total FROM arkham_search.pattern_extractions"
        )
        total = total_row["total"] if total_row else 0

        # Documents with patterns
        doc_row = await shard._db.fetch_one(
            "SELECT COUNT(DISTINCT document_id) as cnt FROM arkham_search.pattern_extractions"
        )
        docs_with_patterns = doc_row["cnt"] if doc_row else 0

        # By category
        cat_rows = await shard._db.fetch_all(
            "SELECT category, COUNT(*) as cnt FROM arkham_search.pattern_extractions GROUP BY category"
        )
        by_category = {row["category"]: row["cnt"] for row in cat_rows} if cat_rows else {}

        # By preset
        preset_rows = await shard._db.fetch_all(
            "SELECT preset_id, COUNT(*) as cnt FROM arkham_search.pattern_extractions GROUP BY preset_id"
        )
        by_preset = {row["preset_id"]: row["cnt"] for row in preset_rows} if preset_rows else {}

    except Exception as e:
        logger.error(f"Failed to fetch extraction stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch stats: {str(e)}")

    return ExtractionStatsResponse(
        total_extractions=total,
        documents_with_patterns=docs_with_patterns,
        by_category=by_category,
        by_preset=by_preset,
    )


@router.post("/regex/extract/{document_id}")
async def trigger_pattern_extraction(
    request: Request,
    document_id: str,
    preset_ids: list[str] | None = None,
):
    """
    Manually trigger pattern extraction for a specific document.

    By default runs all system presets. Optionally specify preset_ids
    to run only specific presets.
    """
    import re
    import uuid

    shard = get_shard(request)

    if not shard._db:
        raise HTTPException(status_code=503, detail="Database not available")

    # Check document exists
    doc_row = await shard._db.fetch_one(
        "SELECT id FROM arkham_frame.documents WHERE id = :doc_id",
        {"doc_id": document_id}
    )
    if not doc_row:
        raise HTTPException(status_code=404, detail="Document not found")

    # Fetch chunks
    chunks = await shard._db.fetch_all(
        """
        SELECT id, text, chunk_index, page_number
        FROM arkham_frame.chunks
        WHERE document_id = :doc_id
        ORDER BY chunk_index
        """,
        {"doc_id": document_id}
    )

    if not chunks:
        return {"document_id": document_id, "extractions": 0, "message": "No chunks found"}

    # Get presets to use
    from .engines.regex import REGEX_PRESETS

    if preset_ids:
        presets = [p for p in REGEX_PRESETS if p["id"] in preset_ids]
        # Also get custom presets from DB
        if shard._db:
            custom_query = """
                SELECT id, name, pattern, category FROM arkham_search.regex_presets
                WHERE id = ANY(:ids)
            """
            custom_rows = await shard._db.fetch_all(custom_query, {"ids": preset_ids})
            for row in custom_rows:
                presets.append({
                    "id": row["id"],
                    "name": row["name"],
                    "pattern": row["pattern"],
                    "category": row["category"],
                })
    else:
        presets = list(REGEX_PRESETS)

    # Clear existing extractions for this document (re-extract)
    await shard._db.execute(
        "DELETE FROM arkham_search.pattern_extractions WHERE document_id = :doc_id",
        {"doc_id": document_id}
    )

    # Extract patterns
    extractions = []
    for preset in presets:
        preset_id = preset["id"]
        preset_name = preset["name"]
        category = preset["category"]
        pattern = preset["pattern"]

        try:
            compiled = re.compile(pattern, re.IGNORECASE)
        except re.error:
            continue

        for chunk in chunks:
            text = chunk["text"] or ""
            chunk_id = chunk["id"]
            page_number = chunk["page_number"]

            for match in compiled.finditer(text):
                match_text = match.group(0)
                match_start = match.start()
                match_end = match.end()

                ctx_start = max(0, match_start - 50)
                ctx_end = min(len(text), match_end + 50)
                context = text[ctx_start:ctx_end]
                if ctx_start > 0:
                    context = "..." + context
                if ctx_end < len(text):
                    context = context + "..."

                line_number = text[:match_start].count('\n') + 1

                extractions.append({
                    "id": str(uuid.uuid4())[:12],
                    "document_id": document_id,
                    "preset_id": preset_id,
                    "preset_name": preset_name,
                    "category": category,
                    "match_text": match_text,
                    "context": context,
                    "page_number": page_number,
                    "chunk_id": chunk_id,
                    "start_offset": match_start,
                    "end_offset": match_end,
                    "line_number": line_number,
                })

    # Store extractions
    for ext in extractions:
        await shard._db.execute(
            """
            INSERT INTO arkham_search.pattern_extractions
            (id, document_id, preset_id, preset_name, category, match_text,
             context, page_number, chunk_id, start_offset, end_offset, line_number)
            VALUES (:id, :document_id, :preset_id, :preset_name, :category, :match_text,
                    :context, :page_number, :chunk_id, :start_offset, :end_offset, :line_number)
            ON CONFLICT (id) DO NOTHING
            """,
            ext
        )

    # Emit event
    if _event_bus:
        await _event_bus.emit(
            "search.patterns.extracted",
            {
                "document_id": document_id,
                "total_matches": len(extractions),
                "manual_trigger": True,
            },
            source="search-shard",
        )

    return {
        "document_id": document_id,
        "extractions": len(extractions),
        "presets_used": [p["id"] for p in presets],
    }
