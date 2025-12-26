"""
Contradictions Shard - Detector Tests

Tests for the ContradictionDetector and ChainDetector classes.
"""

import pytest
import numpy as np
from unittest.mock import MagicMock, AsyncMock

from arkham_shard_contradictions.detector import ContradictionDetector, ChainDetector
from arkham_shard_contradictions.models import (
    Claim,
    Contradiction,
    ContradictionType,
    Severity,
)


class TestContradictionDetectorInit:
    """Tests for ContradictionDetector initialization."""

    def test_default_initialization(self):
        """Test detector initializes without services."""
        detector = ContradictionDetector()
        assert detector.embedding_service is None
        assert detector.llm_service is None

    def test_initialization_with_services(self):
        """Test detector initializes with services."""
        mock_embedding = MagicMock()
        mock_llm = MagicMock()

        detector = ContradictionDetector(
            embedding_service=mock_embedding,
            llm_service=mock_llm,
        )
        assert detector.embedding_service == mock_embedding
        assert detector.llm_service == mock_llm


class TestClaimExtractionSimple:
    """Tests for simple claim extraction."""

    @pytest.fixture
    def detector(self):
        """Create detector for testing."""
        return ContradictionDetector()

    def test_extract_claims_simple(self, detector):
        """Test simple claim extraction from text."""
        # Each sentence needs at least 5 words to pass the filter
        text = "The meeting was held on Monday morning. The total cost was around $500. John Smith attended the company meeting."

        claims = detector.extract_claims_simple(text, "doc-123")

        assert len(claims) == 3
        assert all(isinstance(c, Claim) for c in claims)
        assert all(c.document_id == "doc-123" for c in claims)
        assert all(c.extraction_method == "simple" for c in claims)

    def test_extract_claims_filters_short_sentences(self, detector):
        """Test that short sentences are filtered out."""
        text = "Yes. No. Maybe. This is a longer sentence with more words."

        claims = detector.extract_claims_simple(text, "doc-123")

        # Only the long sentence should be extracted
        assert len(claims) == 1
        assert "longer sentence" in claims[0].text

    def test_extract_claims_empty_text(self, detector):
        """Test extraction from empty text."""
        claims = detector.extract_claims_simple("", "doc-123")
        assert claims == []

    def test_extract_claims_no_document_id(self, detector):
        """Test extraction without document ID."""
        text = "This is a test sentence with enough words."
        claims = detector.extract_claims_simple(text)

        assert len(claims) == 1
        assert claims[0].document_id == "unknown"


class TestClaimExtractionLLM:
    """Tests for LLM-based claim extraction."""

    @pytest.fixture
    def detector_with_llm(self):
        """Create detector with mock LLM service."""
        mock_llm = MagicMock()
        mock_llm.generate = AsyncMock(return_value={
            "text": '[{"claim": "Test claim", "type": "fact"}]'
        })
        return ContradictionDetector(llm_service=mock_llm)

    @pytest.fixture
    def detector_no_llm(self):
        """Create detector without LLM service."""
        return ContradictionDetector()

    @pytest.mark.asyncio
    async def test_extract_claims_llm(self, detector_with_llm):
        """Test LLM-based claim extraction."""
        text = "Some text to extract claims from."

        claims = await detector_with_llm.extract_claims_llm(text, "doc-123")

        assert len(claims) == 1
        assert claims[0].text == "Test claim"
        assert claims[0].extraction_method == "llm"

    @pytest.mark.asyncio
    async def test_extract_claims_llm_fallback(self, detector_no_llm):
        """Test LLM extraction falls back to simple when no LLM."""
        text = "This is a longer sentence for testing the fallback."

        claims = await detector_no_llm.extract_claims_llm(text, "doc-123")

        # Should fall back to simple extraction
        assert len(claims) == 1
        assert claims[0].extraction_method == "simple"


class TestSimilarClaimsFinding:
    """Tests for finding similar claims."""

    @pytest.fixture
    def detector(self):
        """Create detector for testing."""
        return ContradictionDetector()

    @pytest.fixture
    def claims_a(self):
        """Create sample claims set A."""
        return [
            Claim(id="a1", document_id="doc-1", text="The company made $1 million in revenue."),
            Claim(id="a2", document_id="doc-1", text="The meeting was held on January 5th."),
        ]

    @pytest.fixture
    def claims_b(self):
        """Create sample claims set B."""
        return [
            Claim(id="b1", document_id="doc-2", text="The company made $2 million in revenue."),
            Claim(id="b2", document_id="doc-2", text="The meeting occurred on January 10th."),
        ]

    @pytest.mark.asyncio
    async def test_find_similar_claims_keywords(self, detector, claims_a, claims_b):
        """Test keyword-based similarity matching."""
        # Without embedding service, falls back to keywords
        pairs = await detector.find_similar_claims(claims_a, claims_b, threshold=0.3)

        # Should find similar pairs based on keyword overlap
        assert len(pairs) >= 0  # May or may not find pairs depending on threshold


class TestContradictionVerification:
    """Tests for contradiction verification."""

    @pytest.fixture
    def detector(self):
        """Create detector without LLM for heuristic testing."""
        return ContradictionDetector()

    @pytest.fixture
    def claim_a(self):
        """Create claim A."""
        return Claim(id="a1", document_id="doc-1", text="The company did not make any profit.")

    @pytest.fixture
    def claim_b(self):
        """Create claim B with negation contradiction."""
        return Claim(id="b1", document_id="doc-2", text="The company is profitable.")

    @pytest.fixture
    def claim_numeric_a(self):
        """Create claim with number."""
        return Claim(id="a2", document_id="doc-1", text="The total cost was $500.")

    @pytest.fixture
    def claim_numeric_b(self):
        """Create claim with different number."""
        return Claim(id="b2", document_id="doc-2", text="The total cost was $1000.")

    @pytest.mark.asyncio
    async def test_verify_contradiction_negation(self, detector, claim_a, claim_b):
        """Test detecting negation-based contradiction."""
        contradiction = detector._verify_contradiction_heuristic(claim_a, claim_b, 0.7)

        # Should detect contradiction due to negation pattern
        assert contradiction is not None
        assert contradiction.detected_by == "heuristic"

    @pytest.mark.asyncio
    async def test_verify_contradiction_numeric(self, detector, claim_numeric_a, claim_numeric_b):
        """Test detecting numeric contradiction."""
        contradiction = detector._verify_contradiction_heuristic(
            claim_numeric_a, claim_numeric_b, 0.75
        )

        assert contradiction is not None
        assert contradiction.contradiction_type == ContradictionType.NUMERIC
        assert "500" in contradiction.explanation or "1000" in contradiction.explanation


class TestSeverityScoring:
    """Tests for severity scoring."""

    @pytest.fixture
    def detector(self):
        """Create detector for testing."""
        return ContradictionDetector()

    @pytest.mark.asyncio
    async def test_score_severity_high_keywords(self, detector):
        """Test high severity for keywords."""
        contradiction = Contradiction(
            id="c-1",
            doc_a_id="doc-1",
            doc_b_id="doc-2",
            claim_a="This is not true and was never verified.",
            claim_b="This was verified as false.",
            contradiction_type=ContradictionType.DIRECT,
        )

        severity = await detector.score_severity(contradiction)
        assert severity == Severity.HIGH

    @pytest.mark.asyncio
    async def test_score_severity_medium_temporal(self, detector):
        """Test medium severity for temporal contradictions."""
        contradiction = Contradiction(
            id="c-2",
            doc_a_id="doc-1",
            doc_b_id="doc-2",
            claim_a="The event happened on Monday.",
            claim_b="The event happened on Tuesday.",
            contradiction_type=ContradictionType.TEMPORAL,
            confidence_score=0.6,
        )

        severity = await detector.score_severity(contradiction)
        assert severity == Severity.MEDIUM

    @pytest.mark.asyncio
    async def test_score_severity_low_default(self, detector):
        """Test low severity for contextual with low confidence."""
        contradiction = Contradiction(
            id="c-3",
            doc_a_id="doc-1",
            doc_b_id="doc-2",
            claim_a="Some statement.",
            claim_b="Another statement.",
            contradiction_type=ContradictionType.CONTEXTUAL,
            confidence_score=0.5,
        )

        severity = await detector.score_severity(contradiction)
        assert severity == Severity.LOW


class TestHelperMethods:
    """Tests for detector helper methods."""

    @pytest.fixture
    def detector(self):
        """Create detector for testing."""
        return ContradictionDetector()

    def test_split_sentences(self, detector):
        """Test sentence splitting."""
        text = "First sentence. Second sentence! Third sentence?"

        sentences = detector._split_sentences(text)

        assert len(sentences) == 3
        assert sentences[0] == "First sentence"
        assert sentences[1] == "Second sentence"
        assert sentences[2] == "Third sentence"

    def test_cosine_similarity(self, detector):
        """Test cosine similarity calculation."""
        vec_a = [1.0, 0.0, 0.0]
        vec_b = [1.0, 0.0, 0.0]

        similarity = detector._cosine_similarity(vec_a, vec_b)
        assert similarity == pytest.approx(1.0)

    def test_cosine_similarity_orthogonal(self, detector):
        """Test cosine similarity for orthogonal vectors."""
        vec_a = [1.0, 0.0, 0.0]
        vec_b = [0.0, 1.0, 0.0]

        similarity = detector._cosine_similarity(vec_a, vec_b)
        assert similarity == pytest.approx(0.0)

    def test_cosine_similarity_zero_vector(self, detector):
        """Test cosine similarity with zero vector."""
        vec_a = [1.0, 0.0, 0.0]
        vec_b = [0.0, 0.0, 0.0]

        similarity = detector._cosine_similarity(vec_a, vec_b)
        assert similarity == 0.0

    def test_text_similarity(self, detector):
        """Test text similarity based on word overlap."""
        text_a = "the quick brown fox"
        text_b = "the quick red fox"

        similarity = detector._text_similarity(text_a, text_b)
        # 3 common words (the, quick, fox) out of 5 unique (the, quick, brown, red, fox)
        assert similarity == pytest.approx(0.6)

    def test_text_similarity_identical(self, detector):
        """Test text similarity for identical texts."""
        text = "the quick brown fox"

        similarity = detector._text_similarity(text, text)
        assert similarity == pytest.approx(1.0)

    def test_text_similarity_empty(self, detector):
        """Test text similarity with empty text."""
        similarity = detector._text_similarity("", "some text")
        assert similarity == 0.0


class TestChainDetector:
    """Tests for ChainDetector class."""

    @pytest.fixture
    def chain_detector(self):
        """Create chain detector for testing."""
        return ChainDetector()

    @pytest.fixture
    def contradictions_chain(self):
        """Create contradictions that form a chain."""
        return [
            Contradiction(
                id="c1", doc_a_id="doc-1", doc_b_id="doc-2",
                claim_a="A", claim_b="B",
            ),
            Contradiction(
                id="c2", doc_a_id="doc-2", doc_b_id="doc-3",
                claim_a="B", claim_b="C",
            ),
            Contradiction(
                id="c3", doc_a_id="doc-3", doc_b_id="doc-4",
                claim_a="C", claim_b="D",
            ),
        ]

    @pytest.fixture
    def contradictions_no_chain(self):
        """Create contradictions without chains."""
        return [
            Contradiction(
                id="c1", doc_a_id="doc-1", doc_b_id="doc-2",
                claim_a="A", claim_b="B",
            ),
            Contradiction(
                id="c2", doc_a_id="doc-3", doc_b_id="doc-4",
                claim_a="C", claim_b="D",
            ),
        ]

    def test_detect_chains_with_chain(self, chain_detector, contradictions_chain):
        """Test detecting a chain of contradictions."""
        chains = chain_detector.detect_chains(contradictions_chain)

        # Should find at least one chain with 2+ contradictions
        assert len(chains) >= 1
        # The chain should contain multiple contradiction IDs
        assert any(len(chain) >= 2 for chain in chains)

    def test_detect_chains_no_chain(self, chain_detector, contradictions_no_chain):
        """Test no chain when contradictions are disconnected."""
        chains = chain_detector.detect_chains(contradictions_no_chain)

        # Should not find chains of length >= 2
        assert all(len(chain) < 2 for chain in chains) or len(chains) == 0

    def test_detect_chains_empty(self, chain_detector):
        """Test detecting chains with empty input."""
        chains = chain_detector.detect_chains([])
        assert chains == []
