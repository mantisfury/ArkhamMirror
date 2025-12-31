"""Corpus search service for ACH evidence extraction."""

import logging
from difflib import SequenceMatcher
from typing import List, Optional, Dict, Any

from .models import (
    ExtractedEvidence,
    EvidenceRelevance,
    SearchScope,
    CorpusSearchConfig,
    Hypothesis,
    ACHMatrix,
)
from .prompts import EVIDENCE_EXTRACTION_PROMPT

logger = logging.getLogger(__name__)


class CorpusSearchService:
    """
    Search document corpus for evidence relevant to hypotheses.
    
    Uses VectorService for semantic search and LLMService for
    evidence classification and extraction.
    """

    COLLECTION_CHUNKS = "arkham_chunks"

    def __init__(self, vectors_service, documents_service, llm_service):
        """
        Initialize CorpusSearchService.
        
        Args:
            vectors_service: VectorService instance for semantic search
            documents_service: DocumentService instance for chunk retrieval
            llm_service: LLMService instance for evidence classification
        """
        self.vectors = vectors_service
        self.documents = documents_service
        self.llm = llm_service
        self.config = CorpusSearchConfig()

    @property
    def is_available(self) -> bool:
        """Check if corpus search is available."""
        return (
            self.vectors is not None
            and self.llm is not None
            and self.llm.is_available()
        )

    async def search_for_evidence(
        self,
        hypothesis_text: str,
        hypothesis_id: str,
        scope: Optional[SearchScope] = None,
        config: Optional[CorpusSearchConfig] = None,
    ) -> List[ExtractedEvidence]:
        """
        Search corpus for evidence relevant to a hypothesis.
        
        Args:
            hypothesis_text: The hypothesis title and description
            hypothesis_id: ID of the hypothesis
            scope: Optional scope filters
            config: Optional search configuration
            
        Returns:
            List of ExtractedEvidence candidates
        """
        cfg = config or self.config
        
        if not self.is_available:
            logger.warning("Corpus search not available")
            return []

        # 1. Vector search for relevant chunks
        filter_dict = self._build_filter(scope)
        
        try:
            results = await self.vectors.search_text(
                collection=self.COLLECTION_CHUNKS,
                text=hypothesis_text,
                limit=cfg.chunk_limit,
                filter=filter_dict,
                score_threshold=cfg.min_similarity,
            )
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            return []

        if not results:
            logger.info(f"No chunks found for hypothesis: {hypothesis_text[:50]}")
            return []

        logger.info(f"Found {len(results)} chunks for hypothesis")

        # 2. Retrieve full chunk text and document metadata
        chunks_with_context = await self._enrich_chunks(results)

        if not chunks_with_context:
            return []

        # 3. LLM analysis in batches
        evidence = await self._analyze_chunks(
            chunks_with_context,
            hypothesis_text,
            hypothesis_id,
            cfg.batch_size,
        )

        # 4. Verify quotes exist in source
        verified = await self._verify_quotes(evidence, chunks_with_context)

        return verified

    def _build_filter(self, scope: Optional[SearchScope]) -> Optional[Dict[str, Any]]:
        """Build filter dict for vector search."""
        if not scope:
            return None

        filter_dict = {}

        if scope.project_id:
            filter_dict["project_id"] = scope.project_id

        if scope.document_ids:
            filter_dict["document_id"] = {"in": scope.document_ids}

        if scope.exclude_documents:
            filter_dict["document_id"] = {"not_in": scope.exclude_documents}

        return filter_dict if filter_dict else None

    async def _enrich_chunks(
        self,
        search_results: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Retrieve full chunk text and document metadata."""
        enriched = []

        for result in search_results:
            try:
                chunk_id = result.get("id")
                payload = result.get("payload", {})
                score = result.get("score", 0.0)

                # Get chunk text from payload or fetch from documents
                chunk_text = payload.get("text", "")
                doc_id = payload.get("document_id")
                doc_name = payload.get("filename", "Unknown")
                page_num = payload.get("page_number")

                if chunk_text:
                    enriched.append({
                        "chunk_id": chunk_id,
                        "text": chunk_text,
                        "document_id": doc_id,
                        "document_name": doc_name,
                        "page_number": page_num,
                        "similarity_score": score,
                    })
            except Exception as e:
                logger.warning(f"Failed to enrich chunk: {e}")
                continue

        return enriched

    async def _analyze_chunks(
        self,
        chunks: List[Dict[str, Any]],
        hypothesis: str,
        hypothesis_id: str,
        batch_size: int = 10,
    ) -> List[ExtractedEvidence]:
        """Analyze chunks with LLM to extract evidence."""
        all_evidence = []

        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]

            # Format chunks for prompt
            chunks_text = self._format_chunks_for_prompt(batch)

            prompt = EVIDENCE_EXTRACTION_PROMPT.format(
                hypothesis=hypothesis,
                chunks=chunks_text,
            )

            try:
                result = await self.llm.extract_json(prompt)

                if isinstance(result, list):
                    for item in result:
                        chunk_idx = item.get("chunk_index", 0)
                        if chunk_idx < len(batch):
                            chunk = batch[chunk_idx]
                            evidence = ExtractedEvidence(
                                quote=item.get("quote", ""),
                                source_document_id=chunk["document_id"],
                                source_document_name=chunk["document_name"],
                                source_chunk_id=chunk["chunk_id"],
                                page_number=chunk.get("page_number"),
                                relevance=EvidenceRelevance(
                                    item.get("classification", "neutral")
                                ),
                                explanation=item.get("explanation", ""),
                                hypothesis_id=hypothesis_id,
                                similarity_score=chunk["similarity_score"],
                            )
                            all_evidence.append(evidence)

            except Exception as e:
                logger.error(f"LLM batch analysis failed: {e}")
                continue

        return all_evidence

    def _format_chunks_for_prompt(self, chunks: List[Dict[str, Any]]) -> str:
        """Format chunks for LLM prompt."""
        parts = []
        for i, chunk in enumerate(chunks):
            parts.append(
                f"[Excerpt {i}] (Source: {chunk['document_name']}, "
                f"Page: {chunk.get('page_number', 'N/A')})\n"
                f"{chunk['text']}\n"
            )
        return "\n---\n".join(parts)

    async def _verify_quotes(
        self,
        evidence: List[ExtractedEvidence],
        chunks: List[Dict[str, Any]],
    ) -> List[ExtractedEvidence]:
        """
        Verify extracted quotes exist in source chunks.
        
        Uses fuzzy matching to handle minor LLM variations.
        """
        # Build chunk lookup
        chunk_lookup = {c["chunk_id"]: c["text"] for c in chunks}

        verified = []
        for ev in evidence:
            chunk_text = chunk_lookup.get(ev.source_chunk_id, "")

            if not chunk_text:
                ev.verified = False
                verified.append(ev)
                continue

            # Try exact substring match first
            if ev.quote.lower() in chunk_text.lower():
                ev.verified = True
                verified.append(ev)
                continue

            # Fuzzy match
            ratio = SequenceMatcher(
                None,
                ev.quote.lower(),
                chunk_text.lower(),
            ).ratio()

            if ratio > 0.7:
                ev.verified = True
            else:
                ev.verified = False
                logger.warning(
                    f"Quote not verified (ratio={ratio:.2f}): {ev.quote[:50]}..."
                )

            verified.append(ev)

        return verified

    async def search_all_hypotheses(
        self,
        matrix: ACHMatrix,
        scope: Optional[SearchScope] = None,
        config: Optional[CorpusSearchConfig] = None,
    ) -> Dict[str, List[ExtractedEvidence]]:
        """
        Search corpus for evidence relevant to all hypotheses.
        
        Args:
            matrix: ACHMatrix containing hypotheses
            scope: Optional scope filters
            config: Optional search configuration
            
        Returns:
            Dict mapping hypothesis_id to list of ExtractedEvidence
        """
        cfg = config or self.config
        results = {}

        for hypothesis in matrix.hypotheses:
            search_text = f"{hypothesis.title} {hypothesis.description}"
            evidence = await self.search_for_evidence(
                hypothesis_text=search_text,
                hypothesis_id=hypothesis.id,
                scope=scope,
                config=cfg,
            )
            results[hypothesis.id] = evidence

        return results

    async def check_duplicates(
        self,
        matrix: ACHMatrix,
        evidence: List[ExtractedEvidence],
        threshold: float = 0.85,
    ) -> List[ExtractedEvidence]:
        """
        Check if extracted evidence duplicates existing matrix evidence.
        
        Args:
            matrix: ACHMatrix with existing evidence
            evidence: List of extracted evidence to check
            threshold: Similarity threshold for duplicate detection
            
        Returns:
            Evidence list with possible_duplicate field set
        """
        if not matrix.evidence:
            return evidence

        for ev in evidence:
            for existing in matrix.evidence:
                ratio = SequenceMatcher(
                    None,
                    ev.quote.lower(),
                    existing.description.lower(),
                ).ratio()

                if ratio > threshold:
                    ev.possible_duplicate = existing.id
                    break

        return evidence
