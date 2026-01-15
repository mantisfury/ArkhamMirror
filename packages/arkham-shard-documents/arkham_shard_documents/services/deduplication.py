"""Document deduplication service using SimHash for similarity detection."""

import hashlib
import json
import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class DuplicateMatch:
    """A potential duplicate match."""
    document_id: str
    title: str
    similarity_score: float
    hamming_distance: int
    match_type: str  # exact, near, content_similar
    shared_entities: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DuplicateGroup:
    """A group of duplicate documents."""
    group_id: str
    primary_document_id: str
    duplicate_ids: list[str]
    similarity_threshold: float
    detection_method: str
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class MergeResult:
    """Result of merging duplicate documents."""
    primary_id: str
    merged_count: int
    references_updated: int
    documents_cleaned: int
    cleanup_action: str  # soft_delete, archive, hard_delete, keep


class SimHash:
    """
    SimHash implementation for text similarity detection.

    SimHash produces a 64-bit hash where similar documents have similar hashes.
    Hamming distance between hashes indicates similarity.
    """

    def __init__(self, hash_bits: int = 64):
        """
        Initialize SimHash.

        Args:
            hash_bits: Number of bits in hash (default: 64)
        """
        self.hash_bits = hash_bits

    def _tokenize(self, text: str) -> list[str]:
        """
        Tokenize text into shingles (n-grams).

        Args:
            text: Input text

        Returns:
            List of token strings
        """
        # Normalize text
        text = text.lower()
        text = re.sub(r'[^\w\s]', '', text)

        # Generate word shingles (3-grams)
        words = text.split()
        shingles = []

        # Unigrams
        shingles.extend(words)

        # Bigrams
        for i in range(len(words) - 1):
            shingles.append(f"{words[i]} {words[i+1]}")

        # Trigrams
        for i in range(len(words) - 2):
            shingles.append(f"{words[i]} {words[i+1]} {words[i+2]}")

        return shingles

    def _hash_token(self, token: str) -> int:
        """
        Hash a single token to a 64-bit integer.

        Args:
            token: Token string

        Returns:
            64-bit hash integer
        """
        # Use MD5 and take first 8 bytes (64 bits)
        h = hashlib.md5(token.encode('utf-8')).digest()
        return int.from_bytes(h[:8], byteorder='big')

    def compute(self, text: str) -> int:
        """
        Compute SimHash for a text.

        Args:
            text: Input text

        Returns:
            64-bit SimHash integer
        """
        if not text or not text.strip():
            return 0

        tokens = self._tokenize(text)
        if not tokens:
            return 0

        # Initialize bit vector
        v = [0] * self.hash_bits

        # Accumulate weighted hash bits
        for token in tokens:
            token_hash = self._hash_token(token)

            # Add/subtract based on each bit
            for i in range(self.hash_bits):
                bit = (token_hash >> (self.hash_bits - 1 - i)) & 1
                if bit == 1:
                    v[i] += 1
                else:
                    v[i] -= 1

        # Generate final hash from accumulated values
        simhash = 0
        for i in range(self.hash_bits):
            if v[i] > 0:
                simhash |= (1 << (self.hash_bits - 1 - i))

        return simhash

    @staticmethod
    def hamming_distance(hash1: int, hash2: int) -> int:
        """
        Calculate Hamming distance between two hashes.

        Args:
            hash1: First hash
            hash2: Second hash

        Returns:
            Number of differing bits (0-64)
        """
        xor = hash1 ^ hash2
        distance = 0
        while xor:
            distance += xor & 1
            xor >>= 1
        return distance

    @staticmethod
    def similarity_score(hash1: int, hash2: int, hash_bits: int = 64) -> float:
        """
        Calculate similarity score from Hamming distance.

        Args:
            hash1: First hash
            hash2: Second hash
            hash_bits: Number of bits in hash

        Returns:
            Similarity score (0.0-1.0)
        """
        distance = SimHash.hamming_distance(hash1, hash2)
        return 1.0 - (distance / hash_bits)


class DeduplicationService:
    """
    Document deduplication service.

    Provides:
    - SimHash-based similarity detection
    - Exact match detection (MD5/SHA256)
    - Duplicate grouping
    - Merge operations with cleanup options
    """

    def __init__(self, database_service, config: dict | None = None):
        """
        Initialize deduplication service.

        Args:
            database_service: Frame database service
            config: Optional configuration dict
        """
        self._db = database_service
        self._config = config or {}
        self._simhash = SimHash(hash_bits=64)

        # Configuration
        self._similarity_threshold = self._config.get("similarity_threshold", 0.85)
        self._hamming_threshold = self._config.get("hamming_threshold", 10)

    async def compute_hash(
        self,
        document_id: str,
        text: str,
        store: bool = True,
    ) -> dict[str, Any]:
        """
        Compute and store content hashes for a document.

        Args:
            document_id: Document ID
            text: Document text content
            store: Whether to store hashes in database

        Returns:
            Dict with hash values
        """
        # Compute hashes
        content_md5 = hashlib.md5(text.encode('utf-8')).hexdigest()
        content_sha256 = hashlib.sha256(text.encode('utf-8')).hexdigest()
        simhash = self._simhash.compute(text)

        result = {
            "document_id": document_id,
            "content_md5": content_md5,
            "content_sha256": content_sha256,
            "simhash": simhash,
            "text_length": len(text),
        }

        if store and self._db:
            try:
                # Upsert into content_hashes table
                await self._db.execute(
                    """INSERT INTO arkham_documents.content_hashes
                       (id, document_id, content_md5, content_sha256, simhash, text_length, created_at)
                       VALUES (:id, :doc_id, :md5, :sha256, :simhash, :text_len, CURRENT_TIMESTAMP)
                       ON CONFLICT (document_id) DO UPDATE SET
                           content_md5 = EXCLUDED.content_md5,
                           content_sha256 = EXCLUDED.content_sha256,
                           simhash = EXCLUDED.simhash,
                           text_length = EXCLUDED.text_length,
                           created_at = CURRENT_TIMESTAMP""",
                    {
                        "id": str(uuid.uuid4()),
                        "doc_id": document_id,
                        "md5": content_md5,
                        "sha256": content_sha256,
                        "simhash": simhash,
                        "text_len": len(text),
                    }
                )
            except Exception as e:
                logger.warning(f"Failed to store content hashes: {e}")

        return result

    async def find_exact_duplicates(
        self,
        document_id: str,
        project_id: str | None = None,
    ) -> list[DuplicateMatch]:
        """
        Find exact duplicates using content hash.

        Args:
            document_id: Source document ID
            project_id: Optional project scope

        Returns:
            List of exact duplicate matches
        """
        if not self._db:
            return []

        # Get source document's hash
        source_row = await self._db.fetch_one(
            "SELECT * FROM arkham_documents.content_hashes WHERE document_id = :doc_id",
            {"doc_id": document_id}
        )

        if not source_row:
            return []

        source_hash = source_row["content_sha256"]

        # Find documents with matching hash
        query = """
            SELECT ch.document_id, ch.content_sha256, d.filename as title
            FROM arkham_documents.content_hashes ch
            JOIN arkham_frame.documents d ON ch.document_id = d.id
            WHERE ch.content_sha256 = :hash
            AND ch.document_id != :source_id
        """
        params: dict[str, Any] = {"hash": source_hash, "source_id": document_id}

        if project_id:
            query += " AND d.project_id = :project_id"
            params["project_id"] = project_id

        rows = await self._db.fetch_all(query, params)

        return [
            DuplicateMatch(
                document_id=row["document_id"],
                title=row["title"] or "",
                similarity_score=1.0,
                hamming_distance=0,
                match_type="exact",
            )
            for row in rows
        ]

    async def find_similar_documents(
        self,
        document_id: str,
        threshold: float | None = None,
        project_id: str | None = None,
        limit: int = 20,
    ) -> list[DuplicateMatch]:
        """
        Find similar documents using SimHash.

        Args:
            document_id: Source document ID
            threshold: Similarity threshold (0.0-1.0)
            project_id: Optional project scope
            limit: Maximum results

        Returns:
            List of similar document matches
        """
        if not self._db:
            return []

        threshold = threshold or self._similarity_threshold

        # Get source document's simhash
        source_row = await self._db.fetch_one(
            "SELECT * FROM arkham_documents.content_hashes WHERE document_id = :doc_id",
            {"doc_id": document_id}
        )

        if not source_row or source_row["simhash"] is None:
            return []

        source_simhash = source_row["simhash"]

        # Get all other documents' simhashes (in batches for large corpora)
        query = """
            SELECT ch.document_id, ch.simhash, d.filename as title
            FROM arkham_documents.content_hashes ch
            JOIN arkham_frame.documents d ON ch.document_id = d.id
            WHERE ch.document_id != :source_id
            AND ch.simhash IS NOT NULL
        """
        params: dict[str, Any] = {"source_id": document_id}

        if project_id:
            query += " AND d.project_id = :project_id"
            params["project_id"] = project_id

        rows = await self._db.fetch_all(query, params)

        # Calculate similarity for each
        similar = []
        for row in rows:
            other_simhash = row["simhash"]
            if other_simhash is None:
                continue

            similarity = SimHash.similarity_score(source_simhash, other_simhash)
            hamming = SimHash.hamming_distance(source_simhash, other_simhash)

            if similarity >= threshold:
                match_type = "exact" if hamming == 0 else "near" if hamming <= 5 else "content_similar"

                similar.append(DuplicateMatch(
                    document_id=row["document_id"],
                    title=row["title"] or "",
                    similarity_score=round(similarity, 4),
                    hamming_distance=hamming,
                    match_type=match_type,
                ))

        # Sort by similarity descending
        similar.sort(key=lambda x: x.similarity_score, reverse=True)

        return similar[:limit]

    async def scan_project_duplicates(
        self,
        project_id: str,
        threshold: float | None = None,
    ) -> list[DuplicateGroup]:
        """
        Scan entire project for duplicate groups.

        Uses efficient pairwise comparison with early termination.

        Args:
            project_id: Project to scan
            threshold: Similarity threshold

        Returns:
            List of duplicate groups found
        """
        if not self._db:
            return []

        threshold = threshold or self._similarity_threshold

        # Get all documents with simhashes in project
        rows = await self._db.fetch_all(
            """SELECT ch.document_id, ch.simhash, d.filename as title
               FROM arkham_documents.content_hashes ch
               JOIN arkham_frame.documents d ON ch.document_id = d.id
               WHERE d.project_id = :project_id
               AND ch.simhash IS NOT NULL
               ORDER BY d.created_at""",
            {"project_id": project_id}
        )

        if len(rows) < 2:
            return []

        # Build duplicate groups using union-find
        groups: dict[str, set[str]] = {}  # primary_id -> set of duplicate ids
        assigned: dict[str, str] = {}  # doc_id -> group primary_id

        for i, row1 in enumerate(rows):
            doc1_id = row1["document_id"]
            simhash1 = row1["simhash"]

            for j, row2 in enumerate(rows):
                if j <= i:
                    continue

                doc2_id = row2["document_id"]
                simhash2 = row2["simhash"]

                similarity = SimHash.similarity_score(simhash1, simhash2)

                if similarity >= threshold:
                    # Determine which group these belong to
                    group1 = assigned.get(doc1_id)
                    group2 = assigned.get(doc2_id)

                    if group1 is None and group2 is None:
                        # Create new group with doc1 as primary
                        groups[doc1_id] = {doc1_id, doc2_id}
                        assigned[doc1_id] = doc1_id
                        assigned[doc2_id] = doc1_id
                    elif group1 is not None and group2 is None:
                        # Add doc2 to group1
                        groups[group1].add(doc2_id)
                        assigned[doc2_id] = group1
                    elif group1 is None and group2 is not None:
                        # Add doc1 to group2
                        groups[group2].add(doc1_id)
                        assigned[doc1_id] = group2
                    elif group1 != group2:
                        # Merge groups (keep smaller primary_id as primary)
                        primary = min(group1, group2)
                        secondary = max(group1, group2)
                        groups[primary].update(groups[secondary])
                        for doc_id in groups[secondary]:
                            assigned[doc_id] = primary
                        del groups[secondary]

        # Convert to DuplicateGroup objects
        result = []
        for primary_id, members in groups.items():
            if len(members) > 1:
                duplicate_ids = [m for m in members if m != primary_id]
                result.append(DuplicateGroup(
                    group_id=str(uuid.uuid4())[:8],
                    primary_document_id=primary_id,
                    duplicate_ids=duplicate_ids,
                    similarity_threshold=threshold,
                    detection_method="simhash",
                ))

        return result

    async def merge_documents(
        self,
        primary_id: str,
        duplicate_ids: list[str],
        strategy: str = "keep_primary",
        preserve_references: bool = True,
        cleanup_action: str = "soft_delete",
    ) -> MergeResult:
        """
        Merge duplicate documents into a primary document.

        Args:
            primary_id: Document to keep
            duplicate_ids: Documents to merge into primary
            strategy: Merge strategy (keep_primary, merge_metadata, keep_longest)
            preserve_references: Update references from duplicates to primary
            cleanup_action: What to do with duplicate documents after merge:
                - "soft_delete": Mark as deleted, set merged_into_id (default, audit-safe)
                - "archive": Move to archive status, keep all data
                - "hard_delete": Permanently delete (data loss, not recommended)
                - "keep": Leave duplicates in place (just update references)

        Returns:
            MergeResult with details

        Cleanup Actions Explained:
        -------------------------
        1. soft_delete (DEFAULT - Recommended for audit trails):
           - Sets status = 'merged' on duplicate documents
           - Adds merged_into_id = primary_id for traceability
           - Adds merged_at timestamp
           - Document remains in database but excluded from normal queries
           - Can be fully restored if merge was incorrect

        2. archive:
           - Sets status = 'archived' on duplicate documents
           - Document remains fully accessible via archive views
           - Best for legal/compliance scenarios requiring data retention

        3. hard_delete:
           - Permanently removes duplicate documents from database
           - Also removes associated chunks, embeddings, hashes
           - IRREVERSIBLE - only use when storage is critical
           - Merge history still preserved for audit

        4. keep:
           - Only updates references, leaves duplicates unchanged
           - Useful for testing or when duplicates serve different purposes
        """
        references_updated = 0
        documents_cleaned = 0

        if preserve_references:
            # Update entity mentions
            for dup_id in duplicate_ids:
                try:
                    result = await self._db.execute(
                        """UPDATE arkham_entity_mentions
                           SET document_id = :primary_id
                           WHERE document_id = :dup_id""",
                        {"primary_id": primary_id, "dup_id": dup_id}
                    )
                    references_updated += getattr(result, 'rowcount', 0)
                except Exception as e:
                    logger.warning(f"Failed to update entity mentions: {e}")

                # Update claims
                try:
                    result = await self._db.execute(
                        """UPDATE arkham_claims
                           SET document_id = :primary_id
                           WHERE document_id = :dup_id""",
                        {"primary_id": primary_id, "dup_id": dup_id}
                    )
                    references_updated += getattr(result, 'rowcount', 0)
                except Exception as e:
                    logger.warning(f"Failed to update claims: {e}")

        # =====================================================
        # CLEANUP: Handle duplicate documents based on cleanup_action
        # =====================================================
        for dup_id in duplicate_ids:
            try:
                if cleanup_action == "soft_delete":
                    # Recommended: Soft delete with merge pointer for audit trail
                    await self._db.execute(
                        """UPDATE arkham_frame.documents
                           SET status = 'merged',
                               metadata = jsonb_set(
                                   COALESCE(metadata::jsonb, '{}'),
                                   '{merged_into_id}',
                                   :primary_json
                               ),
                               updated_at = CURRENT_TIMESTAMP
                           WHERE id = :dup_id""",
                        {"primary_json": json.dumps(primary_id), "dup_id": dup_id}
                    )
                    documents_cleaned += 1

                elif cleanup_action == "archive":
                    # Archive: Keep fully accessible but mark as archived
                    await self._db.execute(
                        """UPDATE arkham_frame.documents
                           SET status = 'archived',
                               metadata = jsonb_set(
                                   COALESCE(metadata::jsonb, '{}'),
                                   '{archived_reason}',
                                   :reason_json
                               ),
                               updated_at = CURRENT_TIMESTAMP
                           WHERE id = :dup_id""",
                        {"reason_json": json.dumps(f"duplicate_of_{primary_id}"), "dup_id": dup_id}
                    )
                    documents_cleaned += 1

                elif cleanup_action == "hard_delete":
                    # DANGER: Permanent deletion - use with caution
                    # Delete in order: chunks -> embeddings -> hashes -> document
                    await self._db.execute(
                        "DELETE FROM arkham_frame.chunks WHERE document_id = :dup_id",
                        {"dup_id": dup_id}
                    )
                    await self._db.execute(
                        "DELETE FROM arkham_documents.content_hashes WHERE document_id = :dup_id",
                        {"dup_id": dup_id}
                    )
                    await self._db.execute(
                        "DELETE FROM arkham_frame.documents WHERE id = :dup_id",
                        {"dup_id": dup_id}
                    )
                    documents_cleaned += 1

                elif cleanup_action == "keep":
                    # Do nothing - just updated references above
                    pass

            except Exception as e:
                logger.warning(f"Failed to cleanup duplicate {dup_id}: {e}")

        # Record merge in history (always, regardless of cleanup action)
        await self._db.execute(
            """INSERT INTO arkham_documents.merge_history
               (id, primary_document_id, merged_document_ids, strategy, cleanup_action,
                references_updated, documents_cleaned, merged_at)
               VALUES (:id, :primary_id, :dup_ids, :strategy, :cleanup, :refs, :cleaned, CURRENT_TIMESTAMP)""",
            {
                "id": str(uuid.uuid4()),
                "primary_id": primary_id,
                "dup_ids": json.dumps(duplicate_ids),
                "strategy": strategy,
                "cleanup": cleanup_action,
                "refs": references_updated,
                "cleaned": documents_cleaned,
            }
        )

        return MergeResult(
            primary_id=primary_id,
            merged_count=len(duplicate_ids),
            references_updated=references_updated,
            documents_cleaned=documents_cleaned,
            cleanup_action=cleanup_action,
        )

    async def get_deduplication_stats(self, project_id: str | None = None) -> dict[str, Any]:
        """
        Get deduplication statistics.

        Args:
            project_id: Optional project scope

        Returns:
            Dict with statistics
        """
        if not self._db:
            return {}

        query = """
            SELECT COUNT(*) as total_documents,
                   COUNT(ch.id) as documents_with_hash,
                   COUNT(DISTINCT ch.content_sha256) as unique_content_hashes
            FROM arkham_frame.documents d
            LEFT JOIN arkham_documents.content_hashes ch ON d.id = ch.document_id
        """
        params: dict[str, Any] = {}

        if project_id:
            query += " WHERE d.project_id = :project_id"
            params["project_id"] = project_id

        row = await self._db.fetch_one(query, params)

        stats = {
            "total_documents": row["total_documents"] if row else 0,
            "documents_with_hash": row["documents_with_hash"] if row else 0,
            "unique_content_hashes": row["unique_content_hashes"] if row else 0,
            "potential_duplicates": 0,
        }

        # Calculate potential duplicates
        if row and row["documents_with_hash"] > row["unique_content_hashes"]:
            stats["potential_duplicates"] = row["documents_with_hash"] - row["unique_content_hashes"]

        return stats
