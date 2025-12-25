"""Core contradiction detection logic."""

import logging
import re
import uuid
from datetime import datetime
from typing import Any

import numpy as np

from .models import (
    Claim,
    Contradiction,
    ContradictionType,
    ContradictionStatus,
    Severity,
)

logger = logging.getLogger(__name__)


class ContradictionDetector:
    """
    Multi-stage contradiction detection engine.

    Stages:
    1. Claim extraction from text
    2. Semantic similarity matching
    3. LLM-based contradiction verification
    4. Severity scoring
    """

    def __init__(self, embedding_service=None, llm_service=None):
        """
        Initialize the detector.

        Args:
            embedding_service: Service for generating embeddings
            llm_service: Service for LLM-based verification
        """
        self.embedding_service = embedding_service
        self.llm_service = llm_service

    # --- Claim Extraction ---

    def extract_claims_simple(self, text: str, document_id: str | None = None) -> list[Claim]:
        """
        Extract claims using simple sentence splitting.

        Args:
            text: Input text
            document_id: Optional document ID

        Returns:
            List of Claim objects
        """
        # Split into sentences
        sentences = self._split_sentences(text)

        claims = []
        for i, sentence in enumerate(sentences):
            # Filter out very short or non-factual sentences
            if len(sentence.split()) < 5:
                continue

            claim = Claim(
                id=str(uuid.uuid4()),
                document_id=document_id or "unknown",
                text=sentence.strip(),
                location=f"sentence_{i+1}",
                extraction_method="simple",
            )
            claims.append(claim)

        logger.info(f"Extracted {len(claims)} claims from text (simple method)")
        return claims

    async def extract_claims_llm(
        self, text: str, document_id: str | None = None
    ) -> list[Claim]:
        """
        Extract claims using LLM.

        Args:
            text: Input text
            document_id: Optional document ID

        Returns:
            List of Claim objects
        """
        if not self.llm_service:
            logger.warning("LLM service not available, falling back to simple extraction")
            return self.extract_claims_simple(text, document_id)

        prompt = f"""Extract factual claims from the following text.
For each claim, identify:
- The claim text
- Whether it's a fact, opinion, prediction, or attribution

Text:
{text}

Return a JSON array of claims with format:
[
  {{"claim": "...", "type": "fact"}},
  ...
]"""

        try:
            response = await self.llm_service.generate(prompt)

            # Parse JSON response
            import json
            claims_data = json.loads(response.get("text", "[]"))

            claims = []
            for i, claim_data in enumerate(claims_data):
                claim = Claim(
                    id=str(uuid.uuid4()),
                    document_id=document_id or "unknown",
                    text=claim_data.get("claim", ""),
                    claim_type=claim_data.get("type", "fact"),
                    location=f"claim_{i+1}",
                    extraction_method="llm",
                )
                claims.append(claim)

            logger.info(f"Extracted {len(claims)} claims from text (LLM method)")
            return claims

        except Exception as e:
            logger.error(f"LLM claim extraction failed: {e}")
            return self.extract_claims_simple(text, document_id)

    # --- Semantic Matching ---

    async def find_similar_claims(
        self, claims_a: list[Claim], claims_b: list[Claim], threshold: float = 0.7
    ) -> list[tuple[Claim, Claim, float]]:
        """
        Find semantically similar claim pairs using embeddings.

        Args:
            claims_a: Claims from first document
            claims_b: Claims from second document
            threshold: Similarity threshold (0.0 to 1.0)

        Returns:
            List of (claim_a, claim_b, similarity_score) tuples
        """
        if not self.embedding_service:
            logger.warning("Embedding service not available, using keyword matching")
            return self._find_similar_claims_keywords(claims_a, claims_b, threshold)

        # Generate embeddings for all claims
        await self._embed_claims(claims_a)
        await self._embed_claims(claims_b)

        # Find similar pairs
        similar_pairs = []
        for claim_a in claims_a:
            if claim_a.embedding is None:
                continue

            for claim_b in claims_b:
                if claim_b.embedding is None:
                    continue

                # Calculate cosine similarity
                similarity = self._cosine_similarity(claim_a.embedding, claim_b.embedding)

                if similarity >= threshold:
                    similar_pairs.append((claim_a, claim_b, similarity))

        # Sort by similarity descending
        similar_pairs.sort(key=lambda x: x[2], reverse=True)

        logger.info(f"Found {len(similar_pairs)} similar claim pairs (threshold={threshold})")
        return similar_pairs

    async def _embed_claims(self, claims: list[Claim]) -> None:
        """Generate embeddings for claims that don't have them."""
        if not self.embedding_service:
            return

        for claim in claims:
            if claim.embedding is None:
                try:
                    embedding = await self.embedding_service.embed_text(claim.text)
                    claim.embedding = embedding
                except Exception as e:
                    logger.error(f"Failed to embed claim: {e}")

    # --- Contradiction Verification ---

    async def verify_contradiction(
        self, claim_a: Claim, claim_b: Claim, similarity: float
    ) -> Contradiction | None:
        """
        Verify if two similar claims are actually contradictory.

        Args:
            claim_a: First claim
            claim_b: Second claim
            similarity: Semantic similarity score

        Returns:
            Contradiction object if verified, None otherwise
        """
        if not self.llm_service:
            logger.warning("LLM service not available, using heuristic verification")
            return self._verify_contradiction_heuristic(claim_a, claim_b, similarity)

        prompt = f"""Analyze if these two claims contradict each other.

Claim A: {claim_a.text}
Claim B: {claim_b.text}

Determine:
1. Do they contradict? (yes/no)
2. Type of contradiction: direct, temporal, numeric, entity, logical, contextual
3. Severity: high, medium, low
4. Explanation of the contradiction
5. Confidence score (0.0 to 1.0)

Return JSON format:
{{
  "contradicts": true/false,
  "type": "direct|temporal|numeric|entity|logical|contextual",
  "severity": "high|medium|low",
  "explanation": "...",
  "confidence": 0.0-1.0
}}"""

        try:
            response = await self.llm_service.generate(prompt)

            # Parse response
            import json
            result = json.loads(response.get("text", "{}"))

            if not result.get("contradicts", False):
                return None

            # Create contradiction object
            contradiction = Contradiction(
                id=str(uuid.uuid4()),
                doc_a_id=claim_a.document_id,
                doc_b_id=claim_b.document_id,
                claim_a=claim_a.text,
                claim_b=claim_b.text,
                claim_a_location=claim_a.location,
                claim_b_location=claim_b.location,
                contradiction_type=ContradictionType[result.get("type", "DIRECT").upper()],
                severity=Severity[result.get("severity", "MEDIUM").upper()],
                status=ContradictionStatus.DETECTED,
                explanation=result.get("explanation", ""),
                confidence_score=result.get("confidence", similarity),
                detected_by="llm",
            )

            logger.info(f"Verified contradiction: {contradiction.id}")
            return contradiction

        except Exception as e:
            logger.error(f"LLM verification failed: {e}")
            return self._verify_contradiction_heuristic(claim_a, claim_b, similarity)

    def _verify_contradiction_heuristic(
        self, claim_a: Claim, claim_b: Claim, similarity: float
    ) -> Contradiction | None:
        """
        Heuristic-based contradiction verification.

        Uses keyword patterns to detect contradictions.
        """
        text_a = claim_a.text.lower()
        text_b = claim_b.text.lower()

        # Negation patterns
        negation_patterns = [
            (r"\bnot\b", r"\bis\b"),
            (r"\bno\b", r"\byes\b"),
            (r"\bnever\b", r"\balways\b"),
            (r"\bdid not\b", r"\bdid\b"),
        ]

        # Check for negation contradictions
        for neg_pattern, pos_pattern in negation_patterns:
            if re.search(neg_pattern, text_a) and re.search(pos_pattern, text_b):
                contradiction = Contradiction(
                    id=str(uuid.uuid4()),
                    doc_a_id=claim_a.document_id,
                    doc_b_id=claim_b.document_id,
                    claim_a=claim_a.text,
                    claim_b=claim_b.text,
                    claim_a_location=claim_a.location,
                    claim_b_location=claim_b.location,
                    contradiction_type=ContradictionType.DIRECT,
                    severity=Severity.HIGH,
                    status=ContradictionStatus.DETECTED,
                    explanation="Negation pattern detected",
                    confidence_score=similarity * 0.8,
                    detected_by="heuristic",
                )
                return contradiction

        # Numeric contradictions
        numbers_a = re.findall(r'\b\d+(?:,\d{3})*(?:\.\d+)?\b', text_a)
        numbers_b = re.findall(r'\b\d+(?:,\d{3})*(?:\.\d+)?\b', text_b)

        if numbers_a and numbers_b and numbers_a != numbers_b:
            # Check if claims are otherwise similar (without numbers)
            text_a_no_nums = re.sub(r'\b\d+(?:,\d{3})*(?:\.\d+)?\b', 'NUM', text_a)
            text_b_no_nums = re.sub(r'\b\d+(?:,\d{3})*(?:\.\d+)?\b', 'NUM', text_b)

            if self._text_similarity(text_a_no_nums, text_b_no_nums) > 0.7:
                contradiction = Contradiction(
                    id=str(uuid.uuid4()),
                    doc_a_id=claim_a.document_id,
                    doc_b_id=claim_b.document_id,
                    claim_a=claim_a.text,
                    claim_b=claim_b.text,
                    claim_a_location=claim_a.location,
                    claim_b_location=claim_b.location,
                    contradiction_type=ContradictionType.NUMERIC,
                    severity=Severity.MEDIUM,
                    status=ContradictionStatus.DETECTED,
                    explanation=f"Different numbers: {numbers_a} vs {numbers_b}",
                    confidence_score=similarity * 0.7,
                    detected_by="heuristic",
                )
                return contradiction

        # If highly similar but not obviously contradictory, might be duplicate
        if similarity > 0.9:
            return None

        # Default: potential contradiction if moderately similar
        if similarity > 0.6:
            contradiction = Contradiction(
                id=str(uuid.uuid4()),
                doc_a_id=claim_a.document_id,
                doc_b_id=claim_b.document_id,
                claim_a=claim_a.text,
                claim_b=claim_b.text,
                claim_a_location=claim_a.location,
                claim_b_location=claim_b.location,
                contradiction_type=ContradictionType.CONTEXTUAL,
                severity=Severity.LOW,
                status=ContradictionStatus.DETECTED,
                explanation="Claims are semantically similar but may differ in meaning",
                confidence_score=similarity,
                detected_by="heuristic",
            )
            return contradiction

        return None

    # --- Severity Scoring ---

    async def score_severity(self, contradiction: Contradiction) -> Severity:
        """
        Score the severity of a contradiction.

        Args:
            contradiction: Contradiction to score

        Returns:
            Severity level
        """
        # High severity indicators
        high_keywords = ["not", "never", "opposite", "false", "denied", "refuted"]

        # Check for high severity keywords
        claim_a_lower = contradiction.claim_a.lower()
        claim_b_lower = contradiction.claim_b.lower()

        high_count = sum(
            1 for keyword in high_keywords
            if keyword in claim_a_lower or keyword in claim_b_lower
        )

        if high_count >= 2 or contradiction.contradiction_type == ContradictionType.DIRECT:
            return Severity.HIGH

        if contradiction.contradiction_type in [ContradictionType.TEMPORAL, ContradictionType.NUMERIC]:
            return Severity.MEDIUM

        if contradiction.confidence_score > 0.8:
            return Severity.MEDIUM

        return Severity.LOW

    # --- Helper Methods ---

    def _split_sentences(self, text: str) -> list[str]:
        """Split text into sentences."""
        # Simple sentence splitting
        sentences = re.split(r'[.!?]+', text)
        return [s.strip() for s in sentences if s.strip()]

    def _cosine_similarity(self, vec_a: list[float], vec_b: list[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        a = np.array(vec_a)
        b = np.array(vec_b)

        dot_product = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return float(dot_product / (norm_a * norm_b))

    def _text_similarity(self, text_a: str, text_b: str) -> float:
        """Calculate simple text similarity based on word overlap."""
        words_a = set(text_a.lower().split())
        words_b = set(text_b.lower().split())

        if not words_a or not words_b:
            return 0.0

        intersection = words_a.intersection(words_b)
        union = words_a.union(words_b)

        return len(intersection) / len(union)

    def _find_similar_claims_keywords(
        self, claims_a: list[Claim], claims_b: list[Claim], threshold: float
    ) -> list[tuple[Claim, Claim, float]]:
        """Keyword-based similarity matching fallback."""
        similar_pairs = []

        for claim_a in claims_a:
            for claim_b in claims_b:
                similarity = self._text_similarity(claim_a.text, claim_b.text)

                if similarity >= threshold:
                    similar_pairs.append((claim_a, claim_b, similarity))

        similar_pairs.sort(key=lambda x: x[2], reverse=True)
        return similar_pairs


class ChainDetector:
    """Detect chains of contradictions (A contradicts B, B contradicts C, etc.)."""

    def detect_chains(self, contradictions: list[Contradiction]) -> list[list[str]]:
        """
        Detect contradiction chains using graph traversal.

        Args:
            contradictions: List of contradictions

        Returns:
            List of chains (each chain is a list of contradiction IDs)
        """
        # Build graph of document relationships
        graph: dict[str, set[str]] = {}
        contradiction_map: dict[tuple[str, str], str] = {}

        for c in contradictions:
            # Add edges
            if c.doc_a_id not in graph:
                graph[c.doc_a_id] = set()
            if c.doc_b_id not in graph:
                graph[c.doc_b_id] = set()

            graph[c.doc_a_id].add(c.doc_b_id)
            graph[c.doc_b_id].add(c.doc_a_id)

            # Map document pairs to contradiction IDs
            key = tuple(sorted([c.doc_a_id, c.doc_b_id]))
            contradiction_map[key] = c.id

        # Find chains (paths of length >= 3)
        chains = []
        visited = set()

        for start_doc in graph:
            if start_doc in visited:
                continue

            # DFS to find paths
            path_contradictions = self._dfs_find_paths(
                start_doc, graph, contradiction_map, visited, max_depth=5
            )

            if len(path_contradictions) >= 2:  # Chain of at least 2 contradictions
                chains.append(path_contradictions)

        logger.info(f"Detected {len(chains)} contradiction chains")
        return chains

    def _dfs_find_paths(
        self,
        current: str,
        graph: dict[str, set[str]],
        contradiction_map: dict[tuple[str, str], str],
        visited: set[str],
        path: list[str] | None = None,
        max_depth: int = 5,
    ) -> list[str]:
        """DFS to find longest path of contradictions."""
        if path is None:
            path = [current]

        if len(path) >= max_depth:
            return []

        visited.add(current)
        longest_chain = []

        for neighbor in graph.get(current, set()):
            if neighbor not in path:  # Avoid cycles
                key = tuple(sorted([current, neighbor]))
                contradiction_id = contradiction_map.get(key)

                if contradiction_id:
                    new_path = path + [neighbor]
                    chain = [contradiction_id]

                    # Recurse
                    sub_chain = self._dfs_find_paths(
                        neighbor, graph, contradiction_map, visited, new_path, max_depth
                    )

                    if sub_chain:
                        chain.extend(sub_chain)

                    if len(chain) > len(longest_chain):
                        longest_chain = chain

        return longest_chain
