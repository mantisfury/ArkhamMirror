"""Keyword search engine using BM25 ranking."""

import logging
import math
import re
from typing import Any
from collections import Counter

from ..models import SearchQuery, SearchResultItem

logger = logging.getLogger(__name__)


class BM25Scorer:
    """
    BM25 scoring implementation for keyword search.

    BM25 (Best Matching 25) is a ranking function used by search engines
    to rank matching documents according to their relevance to a given query.

    Formula:
        score(D,Q) = sum over terms t in Q:
            IDF(t) * (f(t,D) * (k1 + 1)) / (f(t,D) + k1 * (1 - b + b * |D|/avgdl))

    Where:
        - f(t,D) = term frequency of t in D
        - |D| = document length
        - avgdl = average document length
        - k1 = term frequency saturation parameter (default: 1.5)
        - b = length normalization parameter (default: 0.75)
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        """
        Initialize BM25 scorer.

        Args:
            k1: Term frequency saturation (1.2-2.0 typical, higher = more weight on TF)
            b: Length normalization (0-1, higher = more penalty for long docs)
        """
        self.k1 = k1
        self.b = b
        self._stop_words = {
            'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for', 'from',
            'has', 'he', 'in', 'is', 'it', 'its', 'of', 'on', 'or', 'that',
            'the', 'to', 'was', 'were', 'will', 'with', 'this', 'they',
            'but', 'have', 'had', 'what', 'when', 'where', 'who', 'which',
        }

    def tokenize(self, text: str) -> list[str]:
        """
        Tokenize text into terms.

        Args:
            text: Input text

        Returns:
            List of lowercase terms (words)
        """
        # Convert to lowercase and split on non-alphanumeric
        tokens = re.findall(r'\b\w+\b', text.lower())
        # Filter out very short tokens and stop words
        return [t for t in tokens if len(t) > 1 and t not in self._stop_words]

    def compute_idf(self, term: str, doc_freq: int, total_docs: int) -> float:
        """
        Compute Inverse Document Frequency for a term.

        Uses the Robertson-Sparck Jones IDF formula:
            IDF(t) = log((N - n(t) + 0.5) / (n(t) + 0.5) + 1)

        Args:
            term: The term
            doc_freq: Number of documents containing the term
            total_docs: Total number of documents

        Returns:
            IDF score
        """
        if doc_freq == 0:
            return 0.0
        # Adding 1 prevents negative IDF for very common terms
        return math.log((total_docs - doc_freq + 0.5) / (doc_freq + 0.5) + 1)

    def score_document(
        self,
        query_terms: list[str],
        doc_tokens: list[str],
        avg_doc_length: float,
        idf_scores: dict[str, float],
    ) -> float:
        """
        Score a document for a query using BM25.

        Args:
            query_terms: Tokenized query terms
            doc_tokens: Tokenized document terms
            avg_doc_length: Average document length in corpus
            idf_scores: Pre-computed IDF scores for query terms

        Returns:
            BM25 score
        """
        doc_length = len(doc_tokens)
        if doc_length == 0:
            return 0.0

        # Count term frequencies in document
        doc_tf = Counter(doc_tokens)

        score = 0.0
        for term in query_terms:
            if term not in doc_tf:
                continue

            tf = doc_tf[term]
            idf = idf_scores.get(term, 1.0)

            # BM25 formula
            numerator = tf * (self.k1 + 1)
            denominator = tf + self.k1 * (1 - self.b + self.b * (doc_length / avg_doc_length))

            score += idf * (numerator / denominator)

        return score


class KeywordSearchEngine:
    """
    Keyword search using BM25 ranking algorithm.

    Performs text-based matching with proper BM25 relevance scoring
    for high-quality keyword search results.
    """

    def __init__(self, database_service, documents_service=None):
        """
        Initialize keyword search engine.

        Args:
            database_service: PostgreSQL database service
            documents_service: Optional documents service for metadata
        """
        self.db = database_service
        self.documents = documents_service
        self.bm25 = BM25Scorer(k1=1.5, b=0.75)

        # Cached corpus stats (refreshed periodically)
        self._total_docs = 0
        self._avg_doc_length = 500  # Default estimate
        self._cache_timestamp = 0

    async def _get_corpus_stats(self) -> tuple[int, float]:
        """
        Get corpus statistics for BM25 scoring.

        Returns:
            (total_docs, avg_doc_length) tuple
        """
        import time
        current_time = time.time()

        # Refresh cache every 5 minutes
        if current_time - self._cache_timestamp > 300:
            try:
                # Get total chunk count
                count_result = await self.db.fetch_one(
                    "SELECT COUNT(*) as count FROM arkham_frame.chunks"
                )
                self._total_docs = count_result["count"] if count_result else 0

                # Get average document length
                avg_result = await self.db.fetch_one(
                    "SELECT AVG(LENGTH(text)) as avg_length FROM arkham_frame.chunks"
                )
                if avg_result and avg_result["avg_length"]:
                    self._avg_doc_length = float(avg_result["avg_length"])

                self._cache_timestamp = current_time
                logger.debug(f"BM25 corpus stats: {self._total_docs} docs, avg length {self._avg_doc_length:.0f}")
            except Exception as e:
                logger.warning(f"Failed to get corpus stats: {e}")

        return self._total_docs, self._avg_doc_length

    async def _get_document_frequencies(self, terms: list[str]) -> dict[str, int]:
        """
        Get document frequencies for terms (how many docs contain each term).

        Args:
            terms: List of terms to look up

        Returns:
            Dict mapping term -> document count
        """
        if not terms:
            return {}

        doc_freqs = {}

        try:
            # For each term, count documents containing it
            # This is an approximation - in production, you'd have an inverted index
            for term in terms[:10]:  # Limit to avoid too many queries
                result = await self.db.fetch_one(
                    """
                    SELECT COUNT(DISTINCT document_id) as count
                    FROM arkham_frame.chunks
                    WHERE LOWER(text) LIKE :pattern
                    """,
                    {"pattern": f"%{term}%"}
                )
                doc_freqs[term] = result["count"] if result else 0
        except Exception as e:
            logger.warning(f"Failed to get document frequencies: {e}")
            # Return estimate based on corpus size
            for term in terms:
                doc_freqs[term] = max(1, self._total_docs // 10)

        return doc_freqs

    async def search(self, query: SearchQuery) -> list[SearchResultItem]:
        """
        Perform keyword search with BM25 ranking.

        Args:
            query: SearchQuery object

        Returns:
            List of SearchResultItem sorted by BM25 score
        """
        logger.info(f"BM25 keyword search: '{query.query}' (limit={query.limit})")

        if not self.db:
            logger.warning("Database service not available")
            return []

        # Tokenize query
        query_terms = self.bm25.tokenize(query.query)
        if not query_terms:
            logger.warning("Query produced no terms after tokenization")
            return []

        logger.debug(f"Query terms: {query_terms}")

        # Get corpus statistics
        total_docs, avg_doc_length = await self._get_corpus_stats()

        # Get document frequencies for IDF calculation
        doc_freqs = await self._get_document_frequencies(query_terms)

        # Compute IDF scores
        idf_scores = {
            term: self.bm25.compute_idf(term, doc_freqs.get(term, 1), max(total_docs, 1))
            for term in query_terms
        }
        logger.debug(f"IDF scores: {idf_scores}")

        try:
            # Build query conditions for term matching
            # Match any of the query terms
            conditions = []
            for i, term in enumerate(query_terms[:5]):  # Limit terms for query efficiency
                conditions.append(f"LOWER(c.text) LIKE :term{i}")

            where_clause = " OR ".join(conditions) if conditions else "1=1"

            params = {f"term{i}": f"%{term}%" for i, term in enumerate(query_terms[:5])}
            params["limit"] = query.limit * 3  # Fetch more for re-ranking
            params["offset"] = query.offset if hasattr(query, 'offset') else 0

            sql = f"""
                SELECT
                    c.id as chunk_id,
                    c.document_id,
                    c.text,
                    c.page_number,
                    c.chunk_index,
                    d.filename as title,
                    d.mime_type,
                    d.created_at
                FROM arkham_frame.chunks c
                LEFT JOIN arkham_frame.documents d ON c.document_id = d.id
                WHERE {where_clause}
                LIMIT :limit OFFSET :offset
            """

            rows = await self.db.fetch_all(sql, params)

        except Exception as e:
            logger.error(f"Keyword search query failed: {e}")
            return []

        # Score results with BM25
        scored_results = []
        for row in rows:
            text = row.get("text", "") or ""
            doc_tokens = self.bm25.tokenize(text)

            # Calculate BM25 score
            score = self.bm25.score_document(
                query_terms=query_terms,
                doc_tokens=doc_tokens,
                avg_doc_length=avg_doc_length,
                idf_scores=idf_scores,
            )

            # Skip very low scores
            if score < 0.01:
                continue

            highlights = self._extract_highlights(text, query.query)

            item = SearchResultItem(
                doc_id=row.get("document_id", ""),
                chunk_id=row.get("chunk_id"),
                title=row.get("title", ""),
                excerpt=text[:300] if text else "",
                score=score,
                file_type=row.get("mime_type"),
                created_at=row.get("created_at"),
                page_number=row.get("page_number"),
                highlights=highlights,
                entities=[],
                project_ids=[],
                metadata={"bm25_score": score},
            )
            scored_results.append(item)

        # Sort by BM25 score descending
        scored_results.sort(key=lambda x: x.score, reverse=True)

        # Normalize scores to 0-1 range
        if scored_results:
            max_score = scored_results[0].score
            if max_score > 0:
                for item in scored_results:
                    item.score = item.score / max_score

        # Return top results
        final_results = scored_results[:query.limit]
        logger.info(f"BM25 search returned {len(final_results)} results (max score: {final_results[0].score if final_results else 0:.3f})")

        return final_results

    async def suggest(self, prefix: str, limit: int = 10) -> list[tuple[str, float]]:
        """
        Generate autocomplete suggestions.

        Args:
            prefix: Search prefix
            limit: Maximum suggestions

        Returns:
            List of (suggestion, score) tuples
        """
        logger.info(f"Autocomplete: '{prefix}' (limit={limit})")

        if not self.db or len(prefix) < 2:
            return []

        try:
            # Get document titles matching prefix
            rows = await self.db.fetch_all(
                """
                SELECT DISTINCT filename, 1.0 as score
                FROM arkham_frame.documents
                WHERE LOWER(filename) LIKE :prefix
                ORDER BY filename
                LIMIT :limit
                """,
                {"prefix": f"{prefix.lower()}%", "limit": limit}
            )

            return [(row["filename"], row["score"]) for row in rows]
        except Exception as e:
            logger.warning(f"Autocomplete query failed: {e}")
            return []

    def _extract_highlights(self, text: str, query: str, max_highlights: int = 3) -> list[str]:
        """
        Extract highlighted snippets from text.

        Args:
            text: Full text
            query: Search query
            max_highlights: Maximum number of highlights

        Returns:
            List of highlighted snippets
        """
        highlights = []
        query_terms = self.bm25.tokenize(query)
        text_lower = text.lower()

        # Find occurrences of each query term
        found_positions = []
        for term in query_terms:
            pos = 0
            while pos < len(text_lower):
                idx = text_lower.find(term, pos)
                if idx == -1:
                    break
                found_positions.append((idx, len(term)))
                pos = idx + len(term)

        # Sort by position and take first N unique positions
        found_positions.sort()
        seen_ranges = set()

        for idx, term_len in found_positions:
            if len(highlights) >= max_highlights:
                break

            # Check if this position overlaps with an existing highlight
            start = max(0, idx - 60)
            end = min(len(text), idx + term_len + 60)
            range_key = (start // 100, end // 100)  # Bucket ranges

            if range_key in seen_ranges:
                continue
            seen_ranges.add(range_key)

            # Extract context around match
            snippet = text[start:end]

            # Add ellipsis if needed
            if start > 0:
                snippet = "..." + snippet
            if end < len(text):
                snippet = snippet + "..."

            highlights.append(snippet)

        return highlights

    def _build_where_clause(self, filters) -> tuple[str, list[Any]]:
        """
        Build WHERE clause from SearchFilters.

        Args:
            filters: SearchFilters object

        Returns:
            (where_clause, params) tuple
        """
        if not filters:
            return "", []

        conditions = []
        params = []

        # Date range
        if filters.date_range:
            if filters.date_range.start:
                conditions.append("created_at >= %s")
                params.append(filters.date_range.start)
            if filters.date_range.end:
                conditions.append("created_at <= %s")
                params.append(filters.date_range.end)

        # Entity filter (assuming many-to-many relationship)
        if filters.entity_ids:
            conditions.append("EXISTS (SELECT 1 FROM document_entities WHERE document_id = doc_id AND entity_id = ANY(%s))")
            params.append(filters.entity_ids)

        # Project filter
        if filters.project_ids:
            conditions.append("project_id = ANY(%s)")
            params.append(filters.project_ids)

        # File type filter
        if filters.file_types:
            conditions.append("file_type = ANY(%s)")
            params.append(filters.file_types)

        # Tags filter (assuming array column)
        if filters.tags:
            conditions.append("tags && %s")
            params.append(filters.tags)

        where_clause = " AND ".join(conditions) if conditions else ""
        return where_clause, params
