"""Regex search engine for pattern matching across documents."""

import re
import logging
import time
from typing import Any

from ..models import RegexMatch, RegexSearchQuery, RegexSearchResult

logger = logging.getLogger(__name__)


# Built-in presets (following codebase constant pattern)
REGEX_PRESETS = [
    {
        "id": "email",
        "name": "Email Addresses",
        "pattern": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
        "description": "Match email addresses",
        "category": "contact",
    },
    {
        "id": "phone_us",
        "name": "US Phone Numbers",
        "pattern": r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}",
        "description": "Match US phone number formats",
        "category": "contact",
    },
    {
        "id": "ssn",
        "name": "Social Security Numbers",
        "pattern": r"\d{3}-\d{2}-\d{4}",
        "description": "Match SSN format (XXX-XX-XXXX)",
        "category": "pii",
    },
    {
        "id": "credit_card",
        "name": "Credit Card Numbers",
        "pattern": r"\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}",
        "description": "Match credit card number format",
        "category": "financial",
    },
    {
        "id": "ip_address",
        "name": "IP Addresses",
        "pattern": r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}",
        "description": "Match IPv4 addresses",
        "category": "technical",
    },
    {
        "id": "date_mdy",
        "name": "Dates (MM/DD/YYYY)",
        "pattern": r"\d{1,2}/\d{1,2}/\d{2,4}",
        "description": "Match dates in MM/DD/YYYY format",
        "category": "temporal",
    },
    {
        "id": "url",
        "name": "URLs",
        "pattern": r"https?://[^\s]+",
        "description": "Match HTTP/HTTPS URLs",
        "category": "technical",
    },
    {
        "id": "money_usd",
        "name": "USD Amounts",
        "pattern": r"\$[\d,]+\.?\d*",
        "description": "Match US dollar amounts",
        "category": "financial",
    },
]


class RegexSearchEngine:
    """
    Regex search engine that searches across document content.

    Follows the same pattern as SemanticSearchEngine and KeywordSearchEngine.

    IMPORTANT: Uses PostgreSQL native regex (~, ~*) for scalability.
    Pattern matching happens in the database, not in Python memory.
    This prevents memory blowup on large corpora.
    """

    def __init__(self, database_service, documents_service=None, config=None):
        """
        Initialize regex search engine.

        Args:
            database_service: Frame database service (required)
            documents_service: Frame documents service (optional)
            config: Configuration dict (optional)
        """
        self._db = database_service
        self._documents_service = documents_service
        self._config = config or {}
        self._max_results = self._config.get("max_results", 1000)
        self._context_chars = self._config.get("context_chars", 100)
        self._timeout_ms = self._config.get("timeout_ms", 30000)

    def validate_pattern(self, pattern: str) -> tuple[bool, str | None, str]:
        """
        Validate regex pattern and estimate performance.

        Args:
            pattern: Regex pattern to validate

        Returns:
            Tuple of (is_valid, error_message, performance_estimate)
        """
        try:
            re.compile(pattern)
        except re.error as e:
            return False, str(e), "invalid"

        # Check for dangerous patterns (catastrophic backtracking)
        dangerous_patterns = [
            r'(.+)+',   # Nested quantifiers
            r'(.*)*',   # Nested stars
            r'(a|a)+',  # Exponential alternatives
            r'([^"]*)*',  # Nested negated character class with star
        ]

        for dp in dangerous_patterns:
            if dp in pattern:
                return True, None, "dangerous"

        # Estimate performance based on pattern complexity
        if len(pattern) < 10 and not any(c in pattern for c in '*+?{}'):
            return True, None, "fast"
        elif len(pattern) < 50:
            return True, None, "moderate"
        else:
            return True, None, "slow"

    async def search(self, query: RegexSearchQuery) -> RegexSearchResult:
        """
        Search for regex pattern across document content.

        IMPORTANT: Uses PostgreSQL native regex (~, ~*) for scalability.
        Pattern matching happens in the database, not in Python memory.
        This prevents memory blowup on large corpora.

        Args:
            query: RegexSearchQuery with pattern and filters

        Returns:
            RegexSearchResult with matches
        """
        start_time = time.time()

        # Validate pattern syntax using Python regex (for better error messages)
        try:
            re.compile(query.pattern)
        except re.error as e:
            logger.error(f"Invalid regex pattern: {e}")
            return RegexSearchResult(
                pattern=query.pattern,
                matches=[],
                total_matches=0,
                documents_searched=0,
                duration_ms=(time.time() - start_time) * 1000,
                error=f"Invalid regex: {e}",
            )

        # Build PostgreSQL regex operator based on flags
        # ~  = case-sensitive match
        # ~* = case-insensitive match
        case_insensitive = any(f in ("case_insensitive", "i") for f in query.flags)
        regex_op = "~*" if case_insensitive else "~"

        # PostgreSQL regex uses different syntax for some features:
        # - DOTALL (s flag) not directly supported, but newlines match . in bracket expressions
        # - MULTILINE (m flag) is default behavior in PostgreSQL
        pg_pattern = query.pattern

        # First, get total count (for pagination info) - uses COUNT with regex
        count_sql = f"""
            SELECT COUNT(DISTINCT c.id) as match_count,
                   COUNT(DISTINCT c.document_id) as doc_count
            FROM arkham_frame.chunks c
            JOIN arkham_frame.documents d ON c.document_id = d.id
            WHERE c.text {regex_op} :pattern
        """
        params: dict[str, Any] = {"pattern": pg_pattern}

        if query.project_id:
            count_sql += " AND d.project_id = :project_id"
            params["project_id"] = query.project_id

        if query.document_ids:
            count_sql += " AND d.id = ANY(:document_ids)"
            params["document_ids"] = query.document_ids

        try:
            count_row = await self._db.fetch_one(count_sql, params)
            total_chunks_with_matches = count_row["match_count"] if count_row else 0
            documents_searched = count_row["doc_count"] if count_row else 0
        except Exception as e:
            logger.error(f"Regex count query failed: {e}", exc_info=True)
            return RegexSearchResult(
                pattern=query.pattern,
                matches=[],
                total_matches=0,
                documents_searched=0,
                duration_ms=(time.time() - start_time) * 1000,
                error=f"Database error: {e}",
            )

        # Now fetch actual matches with pagination
        # Use subquery for matching chunks, then extract match positions in Python
        # (PostgreSQL regexp_matches with 'g' flag returns multiple rows per match,
        # which can be complex to handle in SQL - we'll extract in Python)
        search_sql = f"""
            SELECT c.id as chunk_id, c.document_id, c.text, c.chunk_index,
                   d.filename as document_title, c.page_number
            FROM arkham_frame.chunks c
            JOIN arkham_frame.documents d ON c.document_id = d.id
            WHERE c.text {regex_op} :pattern
        """

        if query.project_id:
            search_sql += " AND d.project_id = :project_id"

        if query.document_ids:
            search_sql += " AND d.id = ANY(:document_ids)"

        search_sql += """
            ORDER BY d.id, c.chunk_index
            LIMIT :chunk_limit
        """

        params["chunk_limit"] = min(1000, self._max_results)  # Cap chunks to prevent memory issues

        matches = []
        try:
            rows = await self._db.fetch_all(search_sql, params)

            # Build Python regex for match extraction with flags
            py_flags = 0
            if case_insensitive:
                py_flags |= re.IGNORECASE
            if "multiline" in query.flags:
                py_flags |= re.MULTILINE
            if "dotall" in query.flags:
                py_flags |= re.DOTALL

            compiled_pattern = re.compile(query.pattern, py_flags)

            for row in rows:
                text = row["text"] or ""
                document_id = row["document_id"]
                document_title = row["document_title"] or ""
                page_number = row["page_number"]
                chunk_id = row["chunk_id"]

                # Find all matches in this chunk's text
                for match in compiled_pattern.finditer(text):
                    match_text = match.group(0)
                    match_start = match.start()
                    match_end = match.end()

                    # Extract context around match
                    context_chars = query.context_chars
                    ctx_start = max(0, match_start - context_chars)
                    ctx_end = min(len(text), match_end + context_chars)
                    context = text[ctx_start:ctx_end]

                    # Add ellipsis if truncated
                    if ctx_start > 0:
                        context = "..." + context
                    if ctx_end < len(text):
                        context = context + "..."

                    # Calculate line number
                    line_number = text[:match_start].count('\n') + 1

                    matches.append(RegexMatch(
                        document_id=document_id,
                        document_title=document_title,
                        page_number=page_number,
                        chunk_id=chunk_id,
                        match_text=match_text,
                        context=context,
                        start_offset=match_start,
                        end_offset=match_end,
                        line_number=line_number,
                    ))

                    if len(matches) >= self._max_results:
                        break

                if len(matches) >= self._max_results:
                    break

        except Exception as e:
            logger.error(f"Regex search failed: {e}", exc_info=True)
            return RegexSearchResult(
                pattern=query.pattern,
                matches=[],
                total_matches=0,
                documents_searched=0,
                duration_ms=(time.time() - start_time) * 1000,
                error=f"Search failed: {e}",
            )

        # Apply pagination to results
        paginated_matches = matches[query.offset:query.offset + query.limit]

        duration_ms = (time.time() - start_time) * 1000

        logger.info(
            f"Regex search '{query.pattern}' found {len(matches)} matches "
            f"in {total_chunks_with_matches} chunks across {documents_searched} documents "
            f"({duration_ms:.1f}ms)"
        )

        return RegexSearchResult(
            pattern=query.pattern,
            matches=paginated_matches,
            total_matches=len(matches),  # Total from this batch
            total_chunks_with_matches=total_chunks_with_matches,  # True total
            documents_searched=documents_searched,
            duration_ms=duration_ms,
        )

    async def get_presets(self, category: str | None = None) -> list[dict]:
        """
        Get available regex presets (system + custom from database).

        Args:
            category: Optional category filter

        Returns:
            List of preset dictionaries
        """
        # Start with system presets
        presets = list(REGEX_PRESETS)

        # Add custom presets from database
        if self._db:
            try:
                query = """
                    SELECT id, name, pattern, description, category, flags, is_system
                    FROM arkham_search.regex_presets
                    WHERE 1=1
                """
                params: dict[str, Any] = {}

                if category:
                    query += " AND category = :category"
                    params["category"] = category

                query += " ORDER BY name"

                rows = await self._db.fetch_all(query, params)
                for row in rows:
                    import json
                    presets.append({
                        "id": row["id"],
                        "name": row["name"],
                        "pattern": row["pattern"],
                        "description": row.get("description", ""),
                        "category": row["category"],
                        "flags": json.loads(row["flags"]) if isinstance(row["flags"], str) else (row["flags"] or []),
                        "is_system": row.get("is_system", False),
                    })
            except Exception as e:
                logger.warning(f"Failed to fetch custom presets: {e}")

        # Filter system presets by category if specified
        if category:
            presets = [p for p in presets if p["category"] == category]

        return presets

    async def save_custom_preset(
        self,
        name: str,
        pattern: str,
        description: str = "",
        category: str = "custom",
        flags: list[str] | None = None,
        tenant_id: str | None = None,
    ) -> dict:
        """
        Save a custom regex preset to the database.

        Args:
            name: Preset name
            pattern: Regex pattern
            description: Optional description
            category: Category (default: custom)
            flags: Optional regex flags
            tenant_id: Optional tenant ID for multi-tenancy

        Returns:
            Created preset dictionary
        """
        import uuid
        import json

        preset_id = str(uuid.uuid4())[:8]

        await self._db.execute(
            """
            INSERT INTO arkham_search.regex_presets
            (id, tenant_id, name, pattern, description, category, flags, is_system, created_at)
            VALUES (:id, :tenant_id, :name, :pattern, :description, :category, :flags, FALSE, CURRENT_TIMESTAMP)
            """,
            {
                "id": preset_id,
                "tenant_id": tenant_id,
                "name": name,
                "pattern": pattern,
                "description": description,
                "category": category,
                "flags": json.dumps(flags or []),
            }
        )

        return {
            "id": preset_id,
            "name": name,
            "pattern": pattern,
            "description": description,
            "category": category,
            "flags": flags or [],
            "is_system": False,
        }

    async def delete_custom_preset(self, preset_id: str, tenant_id: str | None = None) -> bool:
        """
        Delete a custom regex preset.

        Args:
            preset_id: Preset ID to delete
            tenant_id: Optional tenant ID for multi-tenancy

        Returns:
            True if deleted successfully
        """
        try:
            query = """
                DELETE FROM arkham_search.regex_presets
                WHERE id = :id AND is_system = FALSE
            """
            params: dict[str, Any] = {"id": preset_id}

            if tenant_id:
                query += " AND tenant_id = :tenant_id"
                params["tenant_id"] = tenant_id

            await self._db.execute(query, params)
            return True
        except Exception as e:
            logger.error(f"Failed to delete preset: {e}")
            return False
