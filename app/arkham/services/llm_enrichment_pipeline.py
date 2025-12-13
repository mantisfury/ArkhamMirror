"""
Phase 5.5: LLM Enrichment Pipeline

Provides LLM-powered extraction for timeline events, entity relationships,
document summaries, and topic classification. Only runs in Enhanced/Vision modes
and gracefully degrades if LM Studio is unavailable.
"""

import logging
import json
import re
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional

# Add project root to path for central config
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from config import LM_STUDIO_URL

logger = logging.getLogger(__name__)


def check_llm_available() -> bool:
    """Check if LM Studio is available and responding."""
    try:
        import requests

        response = requests.get(f"{LM_STUDIO_URL}/models", timeout=2)
        return response.status_code == 200
    except Exception:
        return False


def call_llm(
    prompt: str, max_tokens: int = 500, temperature: float = 0.3
) -> Optional[str]:
    """
    Call the local LLM with a prompt.

    Args:
        prompt: The prompt to send
        max_tokens: Maximum tokens in response
        temperature: Sampling temperature

    Returns:
        Response text or None if failed
    """
    try:
        import requests

        base_url = LM_STUDIO_URL

        response = requests.post(
            f"{base_url}/chat/completions",
            json={
                "model": "local-model",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
            timeout=60,
        )

        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"]
        else:
            logger.warning(f"LLM returned status {response.status_code}")
            return None

    except Exception as e:
        logger.error(f"LLM call failed: {e}")
        return None


def parse_json_response(text: str) -> Optional[Any]:
    """Parse JSON from LLM response, handling common issues."""
    if not text:
        return None

    # Try to find JSON in the response
    text = text.strip()

    # Remove markdown code blocks
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    # Remove trailing commas
    text = re.sub(r",(\s*[}\]])", r"\1", text)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to extract JSON object or array
        match = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

    return None


def extract_timeline_events(text: str, context: str = "") -> List[Dict[str, Any]]:
    """
    Extract timeline events from text using LLM.

    Args:
        text: The text to analyze (usually a chunk)
        context: Additional context (document title, etc.)

    Returns:
        List of event dicts with date, description, type, confidence
    """
    prompt = f"""Extract timeline events from this text. Return JSON array:
[{{"date": "YYYY-MM-DD or text", "description": "event description", "type": "meeting/transaction/communication/other", "confidence": 0.0-1.0}}]

Context: {context}
Text: {text[:1500]}

Return ONLY the JSON array, no other text."""

    response = call_llm(prompt, max_tokens=600)
    events = parse_json_response(response)

    if isinstance(events, list):
        return events
    return []


def extract_entity_relationships(
    text: str, entities: List[str] = None
) -> List[Dict[str, Any]]:
    """
    Extract relationships between entities using LLM.

    Args:
        text: The text to analyze
        entities: Optional list of known entities to focus on

    Returns:
        List of relationship dicts with entity1, entity2, relationship_type
    """
    entity_hint = ""
    if entities:
        entity_hint = f"\nKnown entities: {', '.join(entities[:10])}"

    prompt = f"""Extract entity relationships from this text. Return JSON array:
[{{"entity1": "name", "entity2": "name", "relationship": "type", "evidence": "brief quote"}}]

Types: works_for, owns, married_to, associated_with, located_in, part_of, transacted_with
{entity_hint}
Text: {text[:1500]}

Return ONLY the JSON array, no other text."""

    response = call_llm(prompt, max_tokens=500)
    relationships = parse_json_response(response)

    if isinstance(relationships, list):
        return relationships
    return []


def generate_document_summary(text: str, title: str = "") -> Optional[str]:
    """
    Generate a summary of document content.

    Args:
        text: Full document text (will be truncated)
        title: Document title for context

    Returns:
        Summary string or None
    """
    prompt = f"""Summarize this document in 2-3 sentences for an investigator.
Focus on: key entities, events, and notable information.

Title: {title}
Content: {text[:3000]}

Summary:"""

    return call_llm(prompt, max_tokens=200, temperature=0.2)


def classify_topics(text: str) -> List[str]:
    """
    Classify document into topic categories.

    Args:
        text: Document text

    Returns:
        List of topic tags
    """
    prompt = f"""Classify this document into relevant topics. Choose from:
financial, legal, communications, personnel, real_estate, government, 
healthcare, technology, travel, corporate, personal, contracts, media

Text: {text[:2000]}

Return ONLY a JSON array of applicable topics (max 5): ["topic1", "topic2"]"""

    response = call_llm(prompt, max_tokens=100)
    topics = parse_json_response(response)

    if isinstance(topics, list):
        return [t for t in topics if isinstance(t, str)][:5]
    return []


class LLMEnrichmentPipeline:
    """
    Pipeline for LLM-based document enrichment.

    Runs all enrichment steps in sequence, handling failures gracefully.
    """

    def __init__(self):
        self._llm_available = None

    def is_llm_available(self, force_check: bool = False) -> bool:
        """Check if LLM is available, with caching."""
        if self._llm_available is None or force_check:
            self._llm_available = check_llm_available()
        return self._llm_available

    def enrich_chunk(
        self,
        chunk_text: str,
        document_title: str = "",
        known_entities: List[str] = None,
    ) -> Dict[str, Any]:
        """
        Run full enrichment on a single chunk.

        Args:
            chunk_text: The chunk text to enrich
            document_title: Title for context
            known_entities: Known entities for relationship extraction

        Returns:
            Dict with timeline_events, relationships, and status
        """
        if not self.is_llm_available():
            return {
                "status": "llm_unavailable",
                "timeline_events": [],
                "relationships": [],
                "error": "LM Studio not available",
            }

        result = {
            "status": "success",
            "timeline_events": [],
            "relationships": [],
        }

        try:
            result["timeline_events"] = extract_timeline_events(
                chunk_text, context=document_title
            )
        except Exception as e:
            logger.error(f"Timeline extraction failed: {e}")
            result["timeline_error"] = str(e)

        try:
            result["relationships"] = extract_entity_relationships(
                chunk_text, entities=known_entities
            )
        except Exception as e:
            logger.error(f"Relationship extraction failed: {e}")
            result["relationship_error"] = str(e)

        return result

    def enrich_document(
        self,
        full_text: str,
        title: str = "",
    ) -> Dict[str, Any]:
        """
        Run document-level enrichment (summary, topics).

        Args:
            full_text: Full document text
            title: Document title

        Returns:
            Dict with summary, topics, and status
        """
        if not self.is_llm_available():
            return {
                "status": "llm_unavailable",
                "summary": None,
                "topics": [],
            }

        result = {
            "status": "success",
            "summary": None,
            "topics": [],
        }

        try:
            result["summary"] = generate_document_summary(full_text, title)
        except Exception as e:
            logger.error(f"Summary generation failed: {e}")

        try:
            result["topics"] = classify_topics(full_text)
        except Exception as e:
            logger.error(f"Topic classification failed: {e}")

        return result


# Singleton instance
_pipeline: Optional[LLMEnrichmentPipeline] = None


def get_enrichment_pipeline() -> LLMEnrichmentPipeline:
    """Get the singleton enrichment pipeline."""
    global _pipeline
    if _pipeline is None:
        _pipeline = LLMEnrichmentPipeline()
    return _pipeline
