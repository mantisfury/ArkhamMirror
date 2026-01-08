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
            await self._events.subscribe("document.processed", self._on_document_processed)
            await self._events.subscribe("documents.document.created", self._on_document_created)
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
            await self._events.unsubscribe("document.processed", self._on_document_processed)
            await self._events.unsubscribe("documents.document.created", self._on_document_created)

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

        # Filter by tenant_id for multi-tenancy
        tenant_id = self.get_tenant_id_or_none()
        if tenant_id:
            row = await self._db.fetch_one(
                "SELECT * FROM arkham_summaries WHERE id = :id AND tenant_id = :tenant_id",
                {"id": summary_id, "tenant_id": str(tenant_id)}
            )
        else:
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

        # Filter by tenant_id for multi-tenancy
        tenant_id = self.get_tenant_id_or_none()
        if tenant_id:
            query += " AND tenant_id = :tenant_id"
            params["tenant_id"] = str(tenant_id)

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

        # Filter by tenant_id for multi-tenancy
        tenant_id = self.get_tenant_id_or_none()
        if tenant_id:
            await self._db.execute(
                "DELETE FROM arkham_summaries WHERE id = :id AND tenant_id = :tenant_id",
                {"id": summary_id, "tenant_id": str(tenant_id)}
            )
        else:
            await self._db.execute(
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

        # Filter by tenant_id for multi-tenancy
        tenant_id = self.get_tenant_id_or_none()
        if tenant_id:
            row = await self._db.fetch_one(
                "SELECT COUNT(*) as count FROM arkham_summaries WHERE tenant_id = :tenant_id",
                {"tenant_id": str(tenant_id)}
            )
        else:
            row = await self._db.fetch_one("SELECT COUNT(*) as count FROM arkham_summaries")
        return row["count"] if row else 0

    async def get_statistics(self) -> SummaryStatistics:
        """Get statistics about summaries from database."""
        stats = SummaryStatistics()

        if not self._db:
            # Fallback to in-memory if no database
            summaries = list(self._summaries.values())
            stats.total_summaries = len(summaries)
            for summary in summaries:
                stats.by_type[summary.summary_type.value] = stats.by_type.get(summary.summary_type.value, 0) + 1
                stats.by_source_type[summary.source_type.value] = stats.by_source_type.get(summary.source_type.value, 0) + 1
                stats.by_status[summary.status.value] = stats.by_status.get(summary.status.value, 0) + 1
            if summaries:
                stats.avg_confidence = sum(s.confidence for s in summaries) / len(summaries)
                stats.avg_word_count = sum(s.word_count for s in summaries) / len(summaries)
                stats.avg_processing_time_ms = sum(s.processing_time_ms for s in summaries) / len(summaries)
            return stats

        # Filter by tenant_id for multi-tenancy
        tenant_id = self.get_tenant_id_or_none()
        tenant_filter = " WHERE tenant_id = :tenant_id" if tenant_id else ""
        tenant_filter_and = " AND tenant_id = :tenant_id" if tenant_id else ""
        params = {"tenant_id": str(tenant_id)} if tenant_id else {}

        try:
            # Get total count
            total_row = await self._db.fetch_one(
                f"SELECT COUNT(*) as count FROM arkham_summaries{tenant_filter}",
                params
            )
            stats.total_summaries = total_row["count"] if total_row else 0

            # Get counts by type
            type_rows = await self._db.fetch_all(
                f"SELECT summary_type, COUNT(*) as count FROM arkham_summaries{tenant_filter} GROUP BY summary_type",
                params
            )
            for row in type_rows:
                stats.by_type[row["summary_type"]] = row["count"]

            # Get counts by source type
            source_rows = await self._db.fetch_all(
                f"SELECT source_type, COUNT(*) as count FROM arkham_summaries{tenant_filter} GROUP BY source_type",
                params
            )
            for row in source_rows:
                stats.by_source_type[row["source_type"]] = row["count"]

            # Get counts by status
            status_rows = await self._db.fetch_all(
                f"SELECT status, COUNT(*) as count FROM arkham_summaries{tenant_filter} GROUP BY status",
                params
            )
            for row in status_rows:
                stats.by_status[row["status"]] = row["count"]

            # Get counts by model
            model_rows = await self._db.fetch_all(
                f"SELECT model_used, COUNT(*) as count FROM arkham_summaries WHERE model_used IS NOT NULL{tenant_filter_and} GROUP BY model_used",
                params
            )
            for row in model_rows:
                stats.by_model[row["model_used"]] = row["count"]

            # Get averages
            avg_row = await self._db.fetch_one(
                f"""
                SELECT
                    AVG(confidence) as avg_confidence,
                    AVG(completeness) as avg_completeness,
                    AVG(word_count) as avg_word_count,
                    AVG(processing_time_ms) as avg_processing_time,
                    SUM(word_count) as total_words,
                    SUM(token_count) as total_tokens
                FROM arkham_summaries
                WHERE status = 'completed'{tenant_filter_and}
                """,
                params
            )
            if avg_row:
                stats.avg_confidence = float(avg_row["avg_confidence"] or 0)
                stats.avg_completeness = float(avg_row["avg_completeness"] or 0)
                stats.avg_word_count = float(avg_row["avg_word_count"] or 0)
                stats.avg_processing_time_ms = float(avg_row["avg_processing_time"] or 0)
                stats.total_words_generated = int(avg_row["total_words"] or 0)
                stats.total_tokens_used = int(avg_row["total_tokens"] or 0)

            # Get recent activity (last 24 hours)
            recent_row = await self._db.fetch_one(
                f"""
                SELECT
                    COUNT(*) FILTER (WHERE status = 'completed') as generated,
                    COUNT(*) FILTER (WHERE status = 'failed') as failed
                FROM arkham_summaries
                WHERE created_at >= NOW() - INTERVAL '24 hours'{tenant_filter_and}
                """,
                params
            )
            if recent_row:
                stats.generated_last_24h = int(recent_row["generated"] or 0)
                stats.failed_last_24h = int(recent_row["failed"] or 0)

        except Exception as e:
            logger.error(f"Failed to get statistics from database: {e}")
            # Return empty stats on error
            pass

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

            # Extract text from LLMResponse object
            if hasattr(response, 'text'):
                response_text = response.text
            elif isinstance(response, dict) and 'text' in response:
                response_text = response['text']
            elif isinstance(response, str):
                response_text = response
            else:
                raise RuntimeError(f"Unexpected LLM response type: {type(response)}")

            # Parse response
            content, key_points, title = self._parse_llm_response(response_text, request)
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
        Fetch source content for summarization from various database sources.

        Args:
            source_type: Type of source (document, documents, entity, project, claim_set, timeline, analysis)
            source_ids: IDs of sources to fetch

        Returns:
            Combined text from all sources, separated by dividers
        """
        if not self._db:
            logger.warning("Database not available for fetching source content")
            return ""

        if not source_ids:
            return ""

        contents = []

        try:
            if source_type == SourceType.DOCUMENT:
                # Single document - fetch from arkham_frame.documents table
                for doc_id in source_ids:
                    content = await self._fetch_document_content(doc_id)
                    if content:
                        contents.append(content)

            elif source_type == SourceType.DOCUMENTS:
                # Multiple documents - fetch each one
                for doc_id in source_ids:
                    content = await self._fetch_document_content(doc_id)
                    if content:
                        contents.append(content)

            elif source_type == SourceType.ENTITY:
                # Entities from arkham_entities table
                for entity_id in source_ids:
                    content = await self._fetch_entity_content(entity_id)
                    if content:
                        contents.append(content)

            elif source_type == SourceType.PROJECT:
                # Projects from arkham_projects table
                for project_id in source_ids:
                    content = await self._fetch_project_content(project_id)
                    if content:
                        contents.append(content)

            elif source_type == SourceType.CLAIM_SET:
                # Claims from arkham_claims table
                for claim_id in source_ids:
                    content = await self._fetch_claim_content(claim_id)
                    if content:
                        contents.append(content)

            elif source_type == SourceType.TIMELINE:
                # Timeline events from arkham_timeline_events table
                for event_id in source_ids:
                    content = await self._fetch_timeline_content(event_id)
                    if content:
                        contents.append(content)

            elif source_type == SourceType.ANALYSIS:
                # Analysis results (ACH matrices, etc.) - try multiple sources
                for analysis_id in source_ids:
                    content = await self._fetch_analysis_content(analysis_id)
                    if content:
                        contents.append(content)

            if not contents:
                logger.warning(f"No content found for {source_type.value} with IDs: {source_ids}")
                return ""

            return "\n\n---\n\n".join(contents)

        except Exception as e:
            logger.error(f"Error fetching source content for {source_type.value}: {e}", exc_info=True)
            return ""

    async def _fetch_document_content(self, doc_id: str) -> Optional[str]:
        """
        Fetch content for a single document.

        Tries multiple table structures to find the document content.

        Args:
            doc_id: Document ID

        Returns:
            Formatted document content or None
        """
        if not self._db:
            return None

        # Try arkham_frame.documents first (canonical location)
        try:
            row = await self._db.fetch_one(
                """
                SELECT id, filename, metadata
                FROM arkham_frame.documents
                WHERE id = :id
                """,
                {"id": doc_id}
            )
            if row:
                filename = row.get("filename", "Document")
                # Content might be in metadata or we need to fetch chunks
                metadata = self._parse_jsonb(row.get("metadata"), {})
                content = metadata.get("content", "")

                if content:
                    return f"# {filename}\n\n{content}"

                # Try to get content from chunks table
                chunk_content = await self._fetch_document_chunks(doc_id)
                if chunk_content:
                    return f"# {filename}\n\n{chunk_content}"

        except Exception as e:
            logger.debug(f"Could not fetch from arkham_frame.documents: {e}")

        # Try arkham_documents table (older schema)
        try:
            row = await self._db.fetch_one(
                """
                SELECT id, file_name, content
                FROM arkham_documents
                WHERE id = :id
                """,
                {"id": doc_id}
            )
            if row:
                filename = row.get("file_name") or "Document"
                content = row.get("content", "")
                if content:
                    return f"# {filename}\n\n{content}"
        except Exception as e:
            logger.debug(f"Could not fetch from arkham_documents: {e}")

        return None

    async def _fetch_document_chunks(self, doc_id: str) -> Optional[str]:
        """
        Fetch document content from chunks table.

        Args:
            doc_id: Document ID

        Returns:
            Combined chunk content or None
        """
        if not self._db:
            return None

        try:
            # Try to get chunks from arkham_frame.chunks
            rows = await self._db.fetch_all(
                """
                SELECT text, chunk_index
                FROM arkham_frame.chunks
                WHERE document_id = :doc_id
                ORDER BY chunk_index
                """,
                {"doc_id": doc_id}
            )
            if rows:
                chunks = [row.get("text", "") for row in rows]
                return "\n\n".join(chunks)
        except Exception as e:
            logger.debug(f"Could not fetch chunks: {e}")

        return None

    async def _fetch_entity_content(self, entity_id: str) -> Optional[str]:
        """
        Fetch content for an entity.

        Args:
            entity_id: Entity ID

        Returns:
            Formatted entity content or None
        """
        if not self._db:
            return None

        try:
            row = await self._db.fetch_one(
                """
                SELECT id, name, entity_type, description, aliases, document_ids, mention_count
                FROM arkham_entities
                WHERE id = :id
                """,
                {"id": entity_id}
            )
            if row:
                name = row.get("name", "Unknown")
                entity_type = row.get("entity_type", "Unknown")
                description = row.get("description", "")
                aliases = self._parse_jsonb(row.get("aliases"), [])
                mention_count = row.get("mention_count", 0)
                document_ids = self._parse_jsonb(row.get("document_ids"), [])

                content_parts = [f"## Entity: {name}"]
                content_parts.append(f"**Type:** {entity_type}")

                if aliases:
                    content_parts.append(f"**Also known as:** {', '.join(aliases)}")

                content_parts.append(f"**Mentions:** {mention_count}")
                content_parts.append(f"**Referenced in:** {len(document_ids)} document(s)")

                if description:
                    content_parts.append(f"\n**Description:**\n{description}")

                return "\n".join(content_parts)

        except Exception as e:
            logger.debug(f"Could not fetch entity: {e}")

        return None

    async def _fetch_project_content(self, project_id: str) -> Optional[str]:
        """
        Fetch content for a project, including its documents.

        Args:
            project_id: Project ID

        Returns:
            Formatted project content or None
        """
        if not self._db:
            return None

        try:
            # Fetch project metadata
            row = await self._db.fetch_one(
                """
                SELECT id, name, description, status, document_count, member_count, settings
                FROM arkham_projects
                WHERE id = :id
                """,
                {"id": project_id}
            )
            if row:
                name = row.get("name", "Unknown Project")
                description = row.get("description", "")
                status = row.get("status", "active")
                doc_count = row.get("document_count", 0)
                member_count = row.get("member_count", 0)

                content_parts = [f"# Project: {name}"]
                content_parts.append(f"**Status:** {status}")
                content_parts.append(f"**Documents:** {doc_count}")
                content_parts.append(f"**Members:** {member_count}")

                if description:
                    content_parts.append(f"\n**Description:**\n{description}")

                # Fetch project documents and include their content
                doc_rows = await self._db.fetch_all(
                    """
                    SELECT document_id
                    FROM arkham_project_documents
                    WHERE project_id = :project_id
                    LIMIT 10
                    """,
                    {"project_id": project_id}
                )

                if doc_rows:
                    content_parts.append("\n## Project Documents\n")
                    for doc_row in doc_rows:
                        doc_content = await self._fetch_document_content(doc_row["document_id"])
                        if doc_content:
                            content_parts.append(doc_content)

                return "\n".join(content_parts)

        except Exception as e:
            logger.debug(f"Could not fetch project: {e}")

        return None

    async def _fetch_claim_content(self, claim_id: str) -> Optional[str]:
        """
        Fetch content for a claim and its evidence.

        Args:
            claim_id: Claim ID

        Returns:
            Formatted claim content or None
        """
        if not self._db:
            return None

        try:
            row = await self._db.fetch_one(
                """
                SELECT id, text, claim_type, status, confidence, source_context,
                       evidence_count, supporting_count, refuting_count
                FROM arkham_claims
                WHERE id = :id
                """,
                {"id": claim_id}
            )
            if row:
                claim_text = row.get("text", "")
                claim_type = row.get("claim_type", "factual")
                status = row.get("status", "unverified")
                confidence = row.get("confidence", 1.0)
                source_context = row.get("source_context", "")
                evidence_count = row.get("evidence_count", 0)
                supporting = row.get("supporting_count", 0)
                refuting = row.get("refuting_count", 0)

                content_parts = [f"## Claim ({claim_type})"]
                content_parts.append(f"**Statement:** {claim_text}")
                content_parts.append(f"**Status:** {status}")
                content_parts.append(f"**Confidence:** {confidence * 100:.0f}%")
                content_parts.append(f"**Evidence:** {evidence_count} total ({supporting} supporting, {refuting} refuting)")

                if source_context:
                    content_parts.append(f"\n**Context:**\n{source_context}")

                # Fetch evidence for this claim
                evidence_rows = await self._db.fetch_all(
                    """
                    SELECT evidence_type, relationship, strength, excerpt, notes
                    FROM arkham_claim_evidence
                    WHERE claim_id = :claim_id
                    LIMIT 10
                    """,
                    {"claim_id": claim_id}
                )

                if evidence_rows:
                    content_parts.append("\n### Evidence\n")
                    for ev in evidence_rows:
                        ev_type = ev.get("evidence_type", "unknown")
                        relationship = ev.get("relationship", "neutral")
                        strength = ev.get("strength", "moderate")
                        excerpt = ev.get("excerpt", "")

                        content_parts.append(f"- **{relationship.capitalize()}** ({ev_type}, {strength})")
                        if excerpt:
                            content_parts.append(f"  > {excerpt[:200]}...")

                return "\n".join(content_parts)

        except Exception as e:
            logger.debug(f"Could not fetch claim: {e}")

        return None

    async def _fetch_timeline_content(self, event_id: str) -> Optional[str]:
        """
        Fetch content for a timeline event.

        Args:
            event_id: Timeline event ID

        Returns:
            Formatted timeline event content or None
        """
        if not self._db:
            return None

        try:
            row = await self._db.fetch_one(
                """
                SELECT id, text, event_type, date_start, date_end, precision, confidence, entities
                FROM arkham_timeline_events
                WHERE id = :id
                """,
                {"id": event_id}
            )
            if row:
                text = row.get("text", "")
                event_type = row.get("event_type", "event")
                date_start = row.get("date_start", "Unknown date")
                date_end = row.get("date_end")
                precision = row.get("precision", "unknown")
                confidence = row.get("confidence", 1.0)
                entities = self._parse_jsonb(row.get("entities"), [])

                # Format date
                date_str = str(date_start)
                if date_end and date_end != date_start:
                    date_str = f"{date_start} to {date_end}"

                content_parts = [f"## Event: {text[:100]}"]
                content_parts.append(f"**Type:** {event_type}")
                content_parts.append(f"**Date:** {date_str} ({precision} precision)")
                content_parts.append(f"**Confidence:** {confidence * 100:.0f}%")

                if entities:
                    entity_names = [e.get("name", str(e)) if isinstance(e, dict) else str(e) for e in entities]
                    content_parts.append(f"**Entities involved:** {', '.join(entity_names[:5])}")

                content_parts.append(f"\n**Details:**\n{text}")

                return "\n".join(content_parts)

        except Exception as e:
            logger.debug(f"Could not fetch timeline event: {e}")

        return None

    async def _fetch_analysis_content(self, analysis_id: str) -> Optional[str]:
        """
        Fetch content from analysis results (ACH matrices, patterns, etc.).

        Args:
            analysis_id: Analysis ID

        Returns:
            Formatted analysis content or None
        """
        if not self._db:
            return None

        # Try to fetch from various analysis tables

        # Try ACH matrices (note: ACH uses in-memory storage, but we'll try database)
        # ACH shard might store matrices in a table we can query

        # Try patterns
        try:
            row = await self._db.fetch_one(
                """
                SELECT id, name, pattern_type, description, confidence, document_ids
                FROM arkham_patterns
                WHERE id = :id
                """,
                {"id": analysis_id}
            )
            if row:
                name = row.get("name", "Pattern")
                pattern_type = row.get("pattern_type", "unknown")
                description = row.get("description", "")
                confidence = row.get("confidence", 1.0)

                content_parts = [f"## Pattern: {name}"]
                content_parts.append(f"**Type:** {pattern_type}")
                content_parts.append(f"**Confidence:** {confidence * 100:.0f}%")
                if description:
                    content_parts.append(f"\n**Description:**\n{description}")

                return "\n".join(content_parts)

        except Exception as e:
            logger.debug(f"Could not fetch pattern: {e}")

        # Try anomalies
        try:
            row = await self._db.fetch_one(
                """
                SELECT id, anomaly_type, description, severity, confidence
                FROM arkham_anomalies
                WHERE id = :id
                """,
                {"id": analysis_id}
            )
            if row:
                anomaly_type = row.get("anomaly_type", "unknown")
                description = row.get("description", "")
                severity = row.get("severity", "medium")
                confidence = row.get("confidence", 1.0)

                content_parts = [f"## Anomaly ({anomaly_type})"]
                content_parts.append(f"**Severity:** {severity}")
                content_parts.append(f"**Confidence:** {confidence * 100:.0f}%")
                if description:
                    content_parts.append(f"\n**Description:**\n{description}")

                return "\n".join(content_parts)

        except Exception as e:
            logger.debug(f"Could not fetch anomaly: {e}")

        # Try contradictions
        try:
            row = await self._db.fetch_one(
                """
                SELECT id, contradiction_type, description, severity, resolution_status
                FROM arkham_contradictions
                WHERE id = :id
                """,
                {"id": analysis_id}
            )
            if row:
                contradiction_type = row.get("contradiction_type", "unknown")
                description = row.get("description", "")
                severity = row.get("severity", "medium")
                resolution = row.get("resolution_status", "unresolved")

                content_parts = [f"## Contradiction ({contradiction_type})"]
                content_parts.append(f"**Severity:** {severity}")
                content_parts.append(f"**Status:** {resolution}")
                if description:
                    content_parts.append(f"\n**Description:**\n{description}")

                return "\n".join(content_parts)

        except Exception as e:
            logger.debug(f"Could not fetch contradiction: {e}")

        logger.debug(f"No analysis content found for ID: {analysis_id}")
        return None

    async def _store_summary(self, summary: Summary) -> None:
        """Store summary in database or memory."""
        self._summaries[summary.id] = summary

        if self._db:
            import json
            # Include tenant_id for multi-tenancy
            tenant_id = self.get_tenant_id_or_none()
            await self._db.execute(
                """
                INSERT INTO arkham_summaries (
                    id, summary_type, status, source_type, source_ids, source_titles,
                    content, key_points, title, model_used, token_count, word_count,
                    target_length, confidence, completeness, focus_areas, exclude_topics,
                    processing_time_ms, error_message, created_at, updated_at,
                    source_updated_at, metadata, tags, tenant_id
                ) VALUES (
                    :id, :summary_type, :status, :source_type, :source_ids, :source_titles,
                    :content, :key_points, :title, :model_used, :token_count, :word_count,
                    :target_length, :confidence, :completeness, :focus_areas, :exclude_topics,
                    :processing_time_ms, :error_message, :created_at, :updated_at,
                    :source_updated_at, :metadata, :tags, :tenant_id
                )
                ON CONFLICT (id) DO UPDATE SET
                    content = EXCLUDED.content,
                    key_points = EXCLUDED.key_points,
                    title = EXCLUDED.title,
                    updated_at = EXCLUDED.updated_at,
                    tenant_id = EXCLUDED.tenant_id
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
                    "tenant_id": str(tenant_id) if tenant_id else None,
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

        # ===========================================
        # Multi-tenancy Migration
        # ===========================================
        await self._db.execute("""
            DO $$
            DECLARE
                tables_to_update TEXT[] := ARRAY['arkham_summaries'];
                tbl TEXT;
            BEGIN
                FOREACH tbl IN ARRAY tables_to_update LOOP
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_schema = 'public'
                        AND table_name = tbl
                        AND column_name = 'tenant_id'
                    ) THEN
                        EXECUTE format('ALTER TABLE %I ADD COLUMN tenant_id UUID', tbl);
                    END IF;
                END LOOP;
            END $$;
        """)

        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_arkham_summaries_tenant
            ON arkham_summaries(tenant_id)
        """)

        logger.info("Summary database schema created")

    # === Event Handlers ===

    async def _on_document_processed(self, event: dict) -> None:
        """
        Handle document processed event.

        Auto-generate summary for newly processed documents when auto-summarization is enabled.

        Args:
            event: Event data containing doc_id/document_id
        """
        doc_id = event.get("doc_id") or event.get("document_id")
        if not doc_id:
            logger.debug("Document processed event missing document ID")
            return

        logger.info(f"Document processed: {doc_id} - checking auto-summarization settings")

        # Check if auto-summarization is enabled
        auto_summarize = await self._get_auto_summarize_setting()
        if not auto_summarize:
            logger.debug(f"Auto-summarization disabled, skipping {doc_id}")
            return

        # Check if summary already exists for this document
        existing = await self._check_existing_summary(doc_id, SourceType.DOCUMENT)
        if existing:
            logger.debug(f"Summary already exists for document {doc_id}")
            return

        # Generate summary in background
        try:
            await self._auto_generate_summary(doc_id, SourceType.DOCUMENT)
        except Exception as e:
            logger.error(f"Auto-summarization failed for document {doc_id}: {e}")

    async def _on_document_created(self, event: dict) -> None:
        """
        Handle document created event.

        Only triggers auto-summarization if document has content and auto-summarization is enabled.

        Args:
            event: Event data containing doc_id/document_id
        """
        doc_id = event.get("doc_id") or event.get("document_id")
        if not doc_id:
            logger.debug("Document created event missing document ID")
            return

        logger.info(f"Document created: {doc_id} - checking auto-summarization settings")

        # Check if auto-summarization is enabled
        auto_summarize = await self._get_auto_summarize_setting()
        if not auto_summarize:
            logger.debug(f"Auto-summarization disabled, skipping {doc_id}")
            return

        # For created events, we might want to wait for processing
        # Check if document has content
        content = await self._fetch_document_content(doc_id)
        if not content or len(content.strip()) < 100:
            logger.debug(f"Document {doc_id} has no content yet, skipping auto-summarization")
            return

        # Check if summary already exists
        existing = await self._check_existing_summary(doc_id, SourceType.DOCUMENT)
        if existing:
            logger.debug(f"Summary already exists for document {doc_id}")
            return

        # Generate summary
        try:
            await self._auto_generate_summary(doc_id, SourceType.DOCUMENT)
        except Exception as e:
            logger.error(f"Auto-summarization failed for document {doc_id}: {e}")

    async def _get_auto_summarize_setting(self) -> bool:
        """
        Check if auto-summarization is enabled in settings.

        Returns:
            True if auto-summarization is enabled, False otherwise
        """
        # Check for setting in database
        if self._db:
            try:
                row = await self._db.fetch_one(
                    """
                    SELECT value FROM arkham_settings
                    WHERE key = 'summary.auto_summarize'
                    """
                )
                if row:
                    value = row.get("value", "false")
                    return value.lower() in ("true", "1", "yes", "enabled")
            except Exception:
                pass  # Table might not exist

        # Default to disabled
        return False

    async def _check_existing_summary(self, source_id: str, source_type: SourceType) -> bool:
        """
        Check if a summary already exists for a source.

        Args:
            source_id: ID of the source
            source_type: Type of source

        Returns:
            True if summary exists, False otherwise
        """
        if not self._db:
            # Check in-memory cache
            for summary in self._summaries.values():
                if source_id in summary.source_ids and summary.source_type == source_type:
                    return True
            return False

        try:
            import json
            # Filter by tenant_id for multi-tenancy
            tenant_id = self.get_tenant_id_or_none()
            if tenant_id:
                row = await self._db.fetch_one(
                    """
                    SELECT id FROM arkham_summaries
                    WHERE source_type = :source_type
                    AND source_ids @> :source_id
                    AND tenant_id = :tenant_id
                    LIMIT 1
                    """,
                    {
                        "source_type": source_type.value,
                        "source_id": json.dumps([source_id]),
                        "tenant_id": str(tenant_id)
                    }
                )
            else:
                row = await self._db.fetch_one(
                    """
                    SELECT id FROM arkham_summaries
                    WHERE source_type = :source_type
                    AND source_ids @> :source_id
                    LIMIT 1
                    """,
                    {
                        "source_type": source_type.value,
                        "source_id": json.dumps([source_id])
                    }
                )
            return row is not None
        except Exception as e:
            logger.debug(f"Error checking existing summary: {e}")
            return False

    async def _auto_generate_summary(
        self,
        source_id: str,
        source_type: SourceType,
        summary_type: SummaryType = SummaryType.BRIEF,
        target_length: SummaryLength = SummaryLength.SHORT,
    ) -> Optional[SummaryResult]:
        """
        Auto-generate a summary for a source.

        Uses brief summary type and short length by default for auto-generated summaries.

        Args:
            source_id: ID of the source to summarize
            source_type: Type of source
            summary_type: Type of summary to generate (default: brief)
            target_length: Target length (default: short)

        Returns:
            SummaryResult or None if generation failed
        """
        logger.info(f"Auto-generating {summary_type.value} summary for {source_type.value}: {source_id}")

        request = SummaryRequest(
            source_type=source_type,
            source_ids=[source_id],
            summary_type=summary_type,
            target_length=target_length,
            include_key_points=True,
            include_title=True,
            tags=["auto-generated"],
        )

        try:
            result = await self.generate_summary(request)

            if result.status == SummaryStatus.COMPLETED:
                logger.info(f"Auto-generated summary {result.summary_id} for {source_id}")

                # Emit event for auto-generated summary
                if self._events:
                    await self._events.emit(
                        "summary.auto.generated",
                        {
                            "summary_id": result.summary_id,
                            "source_type": source_type.value,
                            "source_id": source_id,
                            "word_count": result.word_count,
                        },
                        source=self.name,
                    )
            else:
                logger.warning(f"Auto-summary generation failed for {source_id}: {result.error_message}")

            return result

        except Exception as e:
            logger.error(f"Error auto-generating summary for {source_id}: {e}", exc_info=True)
            return None
