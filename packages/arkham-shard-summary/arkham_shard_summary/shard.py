"""
Summary Shard - Auto-summarization of documents and collections

Provides LLM-powered summarization with graceful degradation when LLM unavailable.
"""

import logging
import time
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any

from arkham_frame.shard_interface import ArkhamShard

from .models import (
    Summary,
    SummaryType,
    SummaryStatus,
    SourceType,
    SummaryLength,
    SummaryRequest,
    SummaryResult,
    SummaryFilter,
    SummaryStatistics,
    BatchSummaryRequest,
    BatchSummaryResult,
)

logger = logging.getLogger(__name__)


class SummaryShard(ArkhamShard):
    """
    Summary Shard for ArkhamFrame.

    Provides comprehensive auto-summarization capabilities:
    - Single document summarization
    - Multi-document collection summarization
    - Various summary types (brief, detailed, executive, bullet points, abstract)
    - LLM-powered generation with graceful degradation
    - Background batch processing
    - Auto-summarization on document ingestion

    Features:
    - Multiple summary types and lengths
    - Focus areas and topic exclusion
    - Quality metrics (confidence, completeness)
    - Batch processing support
    - Event-driven auto-summarization
    - Graceful degradation when LLM unavailable

    Events Published:
        - summary.summary.created
        - summary.summary.updated
        - summary.summary.deleted
        - summary.batch.started
        - summary.batch.completed
        - summary.batch.failed

    Events Subscribed:
        - document.processed
        - documents.document.created
    """

    name = "summary"
    version = "0.1.0"
    description = "Auto-summarization of documents, collections, and analysis results using LLM"

    def __init__(self):
        super().__init__()
        self._frame = None
        self._db = None
        self._events = None
        self._llm = None
        self._workers = None
        self.llm_available = False
        self._summaries: Dict[str, Summary] = {}  # In-memory storage

    async def initialize(self, frame) -> None:
        """
        Initialize the Summary shard with Frame services.

        Args:
            frame: The ArkhamFrame instance
        """
        self._frame = frame

        logger.info("Initializing Summary Shard...")

        # Get required services
        self._db = frame.get_service("database") or frame.get_service("db")
        if not self._db:
            logger.warning("Database service not available - using in-memory storage")

        self._events = frame.get_service("events")
        if not self._events:
            logger.warning("Events service not available - event publishing disabled")

        # Get optional services
        self._llm = frame.get_service("llm")
        if self._llm:
            try:
                self.llm_available = await self._check_llm_available()
                if self.llm_available:
                    logger.info("LLM service available - AI summarization enabled")
                else:
                    logger.warning("LLM service unavailable - using fallback extractive summarization")
            except Exception as e:
                logger.warning(f"LLM check failed: {e} - using fallback summarization")
                self.llm_available = False
        else:
            logger.warning("LLM service not configured - using fallback extractive summarization")

        self._workers = frame.get_service("workers")
        if self._workers:
            logger.info("Workers service available - batch processing enabled")

        # Create database schema
        if self._db:
            await self._create_schema()

        # Subscribe to events
        if self._events:
            # Auto-summarize new documents
            self._events.subscribe("document.processed", self._on_document_processed)
            self._events.subscribe("documents.document.created", self._on_document_created)
            logger.info("Subscribed to document events for auto-summarization")

        # Register self in app state for API access
        if hasattr(frame, "app") and frame.app:
            frame.app.state.summary_shard = self

        logger.info("Summary Shard initialized")

    async def shutdown(self) -> None:
        """Clean up shard resources."""
        logger.info("Shutting down Summary Shard...")

        # Unsubscribe from events
        if self._events:
            self._events.unsubscribe("document.processed", self._on_document_processed)
            self._events.unsubscribe("documents.document.created", self._on_document_created)

        # Clear in-memory storage
        self._summaries.clear()

        logger.info("Summary Shard shutdown complete")

    def get_routes(self):
        """Return FastAPI router for this shard."""
        from .api import router
        return router

    # === Core Summarization Methods ===

    async def generate_summary(
        self,
        request: SummaryRequest,
    ) -> SummaryResult:
        """
        Generate a summary for the given request.

        Args:
            request: Summary generation request

        Returns:
            SummaryResult with generated content
        """
        start_time = time.time()
        summary_id = str(uuid.uuid4())

        try:
            # Fetch source content
            source_text = await self._fetch_source_content(
                request.source_type,
                request.source_ids,
            )

            if not source_text:
                return SummaryResult(
                    summary_id=summary_id,
                    status=SummaryStatus.FAILED,
                    error_message="No source content found",
                )

            # Generate summary
            if self.llm_available:
                content, key_points, title = await self._generate_llm_summary(
                    source_text,
                    request,
                )
            else:
                content, key_points, title = await self._generate_extractive_summary(
                    source_text,
                    request,
                )

            # Calculate metrics
            word_count = len(content.split())
            token_count = int(word_count * 1.3)  # Rough estimate
            processing_time_ms = (time.time() - start_time) * 1000

            # Create summary object
            summary = Summary(
                id=summary_id,
                summary_type=request.summary_type,
                status=SummaryStatus.COMPLETED,
                source_type=request.source_type,
                source_ids=request.source_ids,
                content=content,
                key_points=key_points,
                title=title if request.include_title else None,
                model_used=await self._get_llm_model_name() if self.llm_available else "extractive",
                token_count=token_count,
                word_count=word_count,
                target_length=request.target_length,
                focus_areas=request.focus_areas,
                exclude_topics=request.exclude_topics,
                processing_time_ms=processing_time_ms,
                tags=request.tags,
            )

            # Store summary
            await self._store_summary(summary)

            # Publish event
            if self._events:
                await self._events.emit(
                    "summary.summary.created",
                    {
                        "summary_id": summary_id,
                        "source_type": request.source_type.value,
                        "source_ids": request.source_ids,
                        "summary_type": request.summary_type.value,
                        "word_count": word_count,
                    },
                    source=self.name,
                )

            return SummaryResult(
                summary_id=summary_id,
                status=SummaryStatus.COMPLETED,
                content=content,
                key_points=key_points,
                title=title,
                token_count=token_count,
                word_count=word_count,
                processing_time_ms=processing_time_ms,
                confidence=1.0 if self.llm_available else 0.7,
            )

        except Exception as e:
            logger.error(f"Failed to generate summary: {e}", exc_info=True)

            if self._events:
                await self._events.emit(
                    "summary.batch.failed",
                    {
                        "summary_id": summary_id,
                        "error": str(e),
                    },
                    source=self.name,
                )

            return SummaryResult(
                summary_id=summary_id,
                status=SummaryStatus.FAILED,
                error_message=str(e),
            )

    async def generate_batch_summaries(
        self,
        batch_request: BatchSummaryRequest,
    ) -> BatchSummaryResult:
        """
        Generate summaries for multiple sources.

        Args:
            batch_request: Batch summary request

        Returns:
            BatchSummaryResult with all generated summaries
        """
        start_time = time.time()

        if self._events:
            await self._events.emit(
                "summary.batch.started",
                {
                    "count": len(batch_request.requests),
                    "parallel": batch_request.parallel,
                },
                source=self.name,
            )

        results = []
        errors = []
        successful = 0
        failed = 0

        for req in batch_request.requests:
            try:
                result = await self.generate_summary(req)
                results.append(result)

                if result.status == SummaryStatus.COMPLETED:
                    successful += 1
                else:
                    failed += 1
                    if result.error_message:
                        errors.append(result.error_message)

                if batch_request.stop_on_error and result.status == SummaryStatus.FAILED:
                    break

            except Exception as e:
                logger.error(f"Batch summary failed: {e}")
                failed += 1
                errors.append(str(e))

                if batch_request.stop_on_error:
                    break

        total_time_ms = (time.time() - start_time) * 1000

        if self._events:
            await self._events.emit(
                "summary.batch.completed",
                {
                    "total": len(batch_request.requests),
                    "successful": successful,
                    "failed": failed,
                    "processing_time_ms": total_time_ms,
                },
                source=self.name,
            )

        return BatchSummaryResult(
            total=len(batch_request.requests),
            successful=successful,
            failed=failed,
            summaries=results,
            errors=errors,
            total_processing_time_ms=total_time_ms,
        )

    # === CRUD Operations ===

    async def get_summary(self, summary_id: str) -> Optional[Summary]:
        """Get a summary by ID."""
        if not self._db:
            raise RuntimeError("Shard not initialized")

        # Check memory cache first
        if summary_id in self._summaries:
            return self._summaries[summary_id]

        # Query database
        row = await self._db.fetch_one(
            "SELECT * FROM arkham_summaries WHERE id = :id",
            {"id": summary_id}
        )

        if row:
            summary = self._row_to_summary(row)
            self._summaries[summary_id] = summary
            return summary

        return None

    async def list_summaries(
        self,
        filter: Optional[SummaryFilter] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> List[Summary]:
        """List summaries with optional filtering."""
        if not self._db:
            raise RuntimeError("Shard not initialized")

        # Build query with filters
        query = "SELECT * FROM arkham_summaries WHERE 1=1"
        params: Dict[str, Any] = {}

        if filter:
            if filter.summary_type:
                query += " AND summary_type = :summary_type"
                params["summary_type"] = filter.summary_type.value
            if filter.source_type:
                query += " AND source_type = :source_type"
                params["source_type"] = filter.source_type.value
            if filter.source_id:
                query += " AND source_ids @> :source_id"
                import json
                params["source_id"] = json.dumps([filter.source_id])
            if filter.status:
                query += " AND status = :status"
                params["status"] = filter.status.value
            if filter.search_text:
                query += " AND (content ILIKE :search OR title ILIKE :search)"
                params["search"] = f"%{filter.search_text}%"

        query += " ORDER BY created_at DESC"
        query += f" LIMIT {page_size} OFFSET {(page - 1) * page_size}"

        rows = await self._db.fetch_all(query, params)
        summaries = [self._row_to_summary(row) for row in rows]

        # Update cache
        for summary in summaries:
            self._summaries[summary.id] = summary

        return summaries

    async def delete_summary(self, summary_id: str) -> bool:
        """Delete a summary."""
        if not self._db:
            raise RuntimeError("Shard not initialized")

        # Delete from database
        result = await self._db.execute(
            "DELETE FROM arkham_summaries WHERE id = :id",
            {"id": summary_id}
        )

        # Remove from cache
        if summary_id in self._summaries:
            del self._summaries[summary_id]

        if self._events:
            await self._events.emit(
                "summary.summary.deleted",
                {"summary_id": summary_id},
                source=self.name,
            )

        return True

    async def get_count(self) -> int:
        """Get total number of summaries."""
        if not self._db:
            raise RuntimeError("Shard not initialized")

        row = await self._db.fetch_one("SELECT COUNT(*) as count FROM arkham_summaries")
        return row["count"] if row else 0

    async def get_statistics(self) -> SummaryStatistics:
        """Get statistics about summaries."""
        summaries = list(self._summaries.values())

        stats = SummaryStatistics(
            total_summaries=len(summaries),
        )

        # Count by type
        for summary in summaries:
            stats.by_type[summary.summary_type.value] = stats.by_type.get(summary.summary_type.value, 0) + 1
            stats.by_source_type[summary.source_type.value] = stats.by_source_type.get(summary.source_type.value, 0) + 1
            stats.by_status[summary.status.value] = stats.by_status.get(summary.status.value, 0) + 1

        # Calculate averages
        if summaries:
            stats.avg_confidence = sum(s.confidence for s in summaries) / len(summaries)
            stats.avg_word_count = sum(s.word_count for s in summaries) / len(summaries)
            stats.avg_processing_time_ms = sum(s.processing_time_ms for s in summaries) / len(summaries)

        return stats

    # === LLM Integration ===

    async def _check_llm_available(self) -> bool:
        """Check if LLM service is available."""
        if not self._llm:
            return False

        try:
            # Check if LLM service has required methods
            return hasattr(self._llm, 'generate') or hasattr(self._llm, 'complete')
        except Exception as e:
            logger.error(f"LLM availability check failed: {e}")
            return False

    async def _get_llm_model_name(self) -> str:
        """Get the name of the LLM model in use."""
        if not self._llm:
            return "unknown"

        try:
            if hasattr(self._llm, 'model_name'):
                return self._llm.model_name
            if hasattr(self._llm, 'get_model_name'):
                return await self._llm.get_model_name()
        except Exception:
            pass

        return "llm"

    async def _generate_llm_summary(
        self,
        text: str,
        request: SummaryRequest,
    ) -> tuple[str, List[str], Optional[str]]:
        """
        Generate summary using LLM.

        Args:
            text: Source text to summarize
            request: Summary request with parameters

        Returns:
            Tuple of (summary_content, key_points, title)
        """
        prompt = self._build_prompt(text, request)

        try:
            # Call LLM
            if hasattr(self._llm, 'generate'):
                response = await self._llm.generate(prompt)
            elif hasattr(self._llm, 'complete'):
                response = await self._llm.complete(prompt)
            else:
                raise RuntimeError("LLM service has no generate/complete method")

            # Parse response
            content, key_points, title = self._parse_llm_response(response, request)
            return content, key_points, title

        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            # Fallback to extractive
            return await self._generate_extractive_summary(text, request)

    def _build_prompt(self, text: str, request: SummaryRequest) -> str:
        """Build LLM prompt for summarization."""
        length_map = {
            SummaryLength.VERY_SHORT: "very brief (about 50 words)",
            SummaryLength.SHORT: "short (about 100 words)",
            SummaryLength.MEDIUM: "medium-length (about 250 words)",
            SummaryLength.LONG: "long (about 500 words)",
            SummaryLength.VERY_LONG: "very detailed (about 1000 words)",
        }

        type_instructions = {
            SummaryType.BRIEF: "Provide a concise 1-2 sentence summary.",
            SummaryType.DETAILED: "Provide a comprehensive summary covering all major points.",
            SummaryType.EXECUTIVE: "Provide an executive summary with key findings and recommendations.",
            SummaryType.BULLET_POINTS: "Provide a summary as a list of key bullet points.",
            SummaryType.ABSTRACT: "Provide an academic-style abstract.",
        }

        prompt = f"""Summarize the following text.

Type: {type_instructions.get(request.summary_type, "Provide a summary.")}
Length: {length_map.get(request.target_length, "medium-length")}
"""

        if request.focus_areas:
            prompt += f"\nFocus on: {', '.join(request.focus_areas)}"

        if request.exclude_topics:
            prompt += f"\nExclude: {', '.join(request.exclude_topics)}"

        if request.include_key_points:
            prompt += "\n\nAfter the summary, provide 3-5 key points as a bulleted list."

        if request.include_title:
            prompt += "\nAlso provide a concise title for the content."

        prompt += f"\n\nText to summarize:\n{text[:8000]}\n"  # Limit to ~8k chars

        return prompt

    def _parse_llm_response(
        self,
        response: str,
        request: SummaryRequest,
    ) -> tuple[str, List[str], Optional[str]]:
        """
        Parse LLM response to extract summary, key points, and title.

        Args:
            response: Raw LLM response
            request: Original request

        Returns:
            Tuple of (content, key_points, title)
        """
        # Simple parsing - in production would be more sophisticated
        lines = response.strip().split('\n')

        content = response.strip()
        key_points = []
        title = None

        # Try to extract title (look for first line that looks like a title)
        if request.include_title and lines:
            first_line = lines[0].strip()
            if len(first_line) < 100 and not first_line.endswith('.'):
                title = first_line.strip('#').strip()
                content = '\n'.join(lines[1:]).strip()

        # Try to extract key points (look for bullet points)
        if request.include_key_points:
            for line in lines:
                line = line.strip()
                if line.startswith('- ') or line.startswith('* ') or line.startswith('• '):
                    key_points.append(line[2:].strip())

        return content, key_points, title

    async def _generate_extractive_summary(
        self,
        text: str,
        request: SummaryRequest,
    ) -> tuple[str, List[str], Optional[str]]:
        """
        Generate extractive summary (fallback when LLM unavailable).

        Uses simple heuristics to extract key sentences.

        Args:
            text: Source text
            request: Summary request

        Returns:
            Tuple of (summary_content, key_points, title)
        """
        # Simple extractive summarization
        sentences = text.split('. ')

        # Target sentence count based on length
        target_sentences = {
            SummaryLength.VERY_SHORT: 2,
            SummaryLength.SHORT: 4,
            SummaryLength.MEDIUM: 8,
            SummaryLength.LONG: 15,
            SummaryLength.VERY_LONG: 25,
        }

        num_sentences = min(
            target_sentences.get(request.target_length, 8),
            len(sentences),
        )

        # Take first N sentences (simple but effective baseline)
        summary_sentences = sentences[:num_sentences]
        content = '. '.join(summary_sentences)

        # Extract key points (first sentence of each paragraph)
        paragraphs = text.split('\n\n')
        key_points = [p.split('. ')[0] for p in paragraphs[:5] if p.strip()]

        # Generate simple title
        title = None
        if request.include_title and sentences:
            title = sentences[0][:80] + "..." if len(sentences[0]) > 80 else sentences[0]

        return content, key_points, title

    # === Helper Methods ===

    def _parse_jsonb(self, value: Any, default: Any = None) -> Any:
        """Parse a JSONB field that may be str, dict, list, or None.

        PostgreSQL JSONB with SQLAlchemy may return:
        - Already parsed Python objects (dict, list, bool, int, float)
        - String that IS the value (when JSON string was stored)
        - String that needs parsing (raw JSON)
        """
        if value is None:
            return default
        if isinstance(value, (dict, list, bool, int, float)):
            return value
        if isinstance(value, str):
            if not value or value.strip() == "":
                return default
            # Try to parse as JSON first (for complex values)
            try:
                import json
                return json.loads(value)
            except json.JSONDecodeError:
                # If it's not valid JSON, it's already the string value
                return value
        return default

    def _row_to_summary(self, row: Dict[str, Any]) -> Summary:
        """Convert database row to Summary object."""
        # Parse JSONB fields
        source_ids = self._parse_jsonb(row.get("source_ids"), [])
        source_titles = self._parse_jsonb(row.get("source_titles"), [])
        key_points = self._parse_jsonb(row.get("key_points"), [])
        focus_areas = self._parse_jsonb(row.get("focus_areas"), [])
        exclude_topics = self._parse_jsonb(row.get("exclude_topics"), [])
        metadata = self._parse_jsonb(row.get("metadata"), {})
        tags = self._parse_jsonb(row.get("tags"), [])

        return Summary(
            id=row["id"],
            summary_type=SummaryType(row["summary_type"]),
            status=SummaryStatus(row["status"]),
            source_type=SourceType(row["source_type"]),
            source_ids=source_ids,
            source_titles=source_titles,
            content=row.get("content", ""),
            key_points=key_points,
            title=row.get("title"),
            model_used=row.get("model_used"),
            token_count=row.get("token_count", 0),
            word_count=row.get("word_count", 0),
            target_length=SummaryLength(row["target_length"]),
            confidence=row.get("confidence", 1.0),
            completeness=row.get("completeness", 1.0),
            focus_areas=focus_areas,
            exclude_topics=exclude_topics,
            processing_time_ms=row.get("processing_time_ms", 0),
            error_message=row.get("error_message"),
            created_at=row.get("created_at", datetime.utcnow()),
            updated_at=row.get("updated_at", datetime.utcnow()),
            source_updated_at=row.get("source_updated_at"),
            metadata=metadata,
            tags=tags,
        )

    # === Data Access ===

    async def _fetch_source_content(
        self,
        source_type: SourceType,
        source_ids: List[str],
    ) -> str:
        """
        Fetch source content for summarization.

        Args:
            source_type: Type of source
            source_ids: IDs of sources

        Returns:
            Combined text from all sources
        """
        # This would fetch from the appropriate Frame service
        # For now, return mock content
        if source_type == SourceType.DOCUMENT:
            return f"Mock document content for ID: {source_ids[0]}"
        elif source_type == SourceType.DOCUMENTS:
            return f"Mock content for {len(source_ids)} documents"
        else:
            return f"Mock content for {source_type.value}"

    async def _store_summary(self, summary: Summary) -> None:
        """Store summary in database or memory."""
        self._summaries[summary.id] = summary

        if self._db:
            import json
            await self._db.execute(
                """
                INSERT INTO arkham_summaries (
                    id, summary_type, status, source_type, source_ids, source_titles,
                    content, key_points, title, model_used, token_count, word_count,
                    target_length, confidence, completeness, focus_areas, exclude_topics,
                    processing_time_ms, error_message, created_at, updated_at,
                    source_updated_at, metadata, tags
                ) VALUES (
                    :id, :summary_type, :status, :source_type, :source_ids, :source_titles,
                    :content, :key_points, :title, :model_used, :token_count, :word_count,
                    :target_length, :confidence, :completeness, :focus_areas, :exclude_topics,
                    :processing_time_ms, :error_message, :created_at, :updated_at,
                    :source_updated_at, :metadata, :tags
                )
                ON CONFLICT (id) DO UPDATE SET
                    content = EXCLUDED.content,
                    key_points = EXCLUDED.key_points,
                    title = EXCLUDED.title,
                    updated_at = EXCLUDED.updated_at
                """,
                {
                    "id": summary.id,
                    "summary_type": summary.summary_type.value,
                    "status": summary.status.value,
                    "source_type": summary.source_type.value,
                    "source_ids": json.dumps(summary.source_ids),
                    "source_titles": json.dumps(summary.source_titles),
                    "content": summary.content,
                    "key_points": json.dumps(summary.key_points),
                    "title": summary.title,
                    "model_used": summary.model_used,
                    "token_count": summary.token_count,
                    "word_count": summary.word_count,
                    "target_length": summary.target_length.value,
                    "confidence": summary.confidence,
                    "completeness": summary.completeness,
                    "focus_areas": json.dumps(summary.focus_areas),
                    "exclude_topics": json.dumps(summary.exclude_topics),
                    "processing_time_ms": summary.processing_time_ms,
                    "error_message": summary.error_message,
                    "created_at": summary.created_at,
                    "updated_at": summary.updated_at,
                    "source_updated_at": summary.source_updated_at,
                    "metadata": json.dumps(summary.metadata),
                    "tags": json.dumps(summary.tags),
                }
            )

    async def _create_schema(self) -> None:
        """Create database schema for summaries."""
        if not self._db:
            return

        # Create summaries table
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS arkham_summaries (
                id TEXT PRIMARY KEY,
                summary_type TEXT NOT NULL,
                status TEXT NOT NULL,
                source_type TEXT NOT NULL,
                source_ids JSONB NOT NULL DEFAULT '[]',
                source_titles JSONB NOT NULL DEFAULT '[]',
                content TEXT NOT NULL DEFAULT '',
                key_points JSONB NOT NULL DEFAULT '[]',
                title TEXT,
                model_used TEXT,
                token_count INTEGER DEFAULT 0,
                word_count INTEGER DEFAULT 0,
                target_length TEXT NOT NULL,
                confidence REAL DEFAULT 1.0,
                completeness REAL DEFAULT 1.0,
                focus_areas JSONB DEFAULT '[]',
                exclude_topics JSONB DEFAULT '[]',
                processing_time_ms REAL DEFAULT 0,
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                source_updated_at TIMESTAMP,
                metadata JSONB DEFAULT '{}',
                tags JSONB DEFAULT '[]'
            )
        """)

        # Create indexes
        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_arkham_summaries_source_type
            ON arkham_summaries(source_type)
        """)

        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_arkham_summaries_summary_type
            ON arkham_summaries(summary_type)
        """)

        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_arkham_summaries_status
            ON arkham_summaries(status)
        """)

        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_arkham_summaries_created_at
            ON arkham_summaries(created_at DESC)
        """)

        logger.info("Summary database schema created")

    # === Event Handlers ===

    async def _on_document_processed(self, event: dict) -> None:
        """
        Handle document processed event.

        Auto-generate summary for newly processed documents.

        Args:
            event: Event data
        """
        doc_id = event.get("doc_id") or event.get("document_id")
        if not doc_id:
            return

        logger.debug(f"Document processed: {doc_id} - would auto-generate summary")

        # In production, would check if auto-summarization is enabled
        # and enqueue a background job

    async def _on_document_created(self, event: dict) -> None:
        """
        Handle document created event.

        Args:
            event: Event data
        """
        doc_id = event.get("doc_id") or event.get("document_id")
        if not doc_id:
            return

        logger.debug(f"Document created: {doc_id} - would auto-generate summary")
