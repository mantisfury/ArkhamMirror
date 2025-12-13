"""
Cross-Document Fact Comparison Service

Automated fact-checking across the document corpus to identify:
- Corroborating evidence (facts that support each other)
- Contradicting evidence (facts that conflict)
- Claim propagation (how facts spread across documents)
"""

import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from sqlalchemy import create_engine, desc
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

from config.settings import DATABASE_URL

from app.arkham.services.db.models import (
    CanonicalEntity,
    Chunk,
    FactComparisonCache,
)
from app.arkham.services.llm_service import (
    chat_with_llm,
    FACTS_SCHEMA,
    FACT_COMPARISON_SCHEMA,
)

load_dotenv()
logger = logging.getLogger(__name__)

# Cache settings
CACHE_DURATION_HOURS = 24


class FactComparisonService:
    """Service for cross-document fact comparison and verification."""

    def __init__(self):
        self.engine = create_engine(DATABASE_URL)
        self.Session = sessionmaker(bind=self.engine)

    def _compute_cache_key(
        self,
        entity_ids: list[int] | None = None,
        doc_ids: list[int] | None = None,
        limit: int = 10,
    ) -> str:
        """Create deterministic cache key from entity and document IDs."""
        import hashlib

        # Build a unique string representation
        parts = []
        if entity_ids:
            parts.append(f"e:{','.join(str(i) for i in sorted(entity_ids))}")
        else:
            parts.append(f"top:{limit}")
        if doc_ids:
            parts.append(f"d:{','.join(str(i) for i in sorted(doc_ids))}")
        else:
            parts.append("d:all")

        key_string = "|".join(parts)
        return hashlib.sha256(key_string.encode()).hexdigest()

    def get_cached_results(
        self,
        entity_ids: list[int] | None = None,
        doc_ids: list[int] | None = None,
        limit: int = 10,
    ) -> dict | None:
        """Check for valid (non-expired) cached results."""
        from datetime import datetime

        cache_key = self._compute_cache_key(entity_ids, doc_ids, limit)

        with self.Session() as session:
            cache_entry = (
                session.query(FactComparisonCache)
                .filter(
                    FactComparisonCache.cache_key == cache_key,
                    FactComparisonCache.expires_at > datetime.utcnow(),
                )
                .first()
            )

            if cache_entry:
                try:
                    results = json.loads(cache_entry.results_json)
                    results["from_cache"] = True
                    results["cached_at"] = cache_entry.created_at.isoformat()
                    results["expires_at"] = cache_entry.expires_at.isoformat()
                    logger.info(
                        f"Loaded fact analysis from database cache (key: {cache_key[:8]}...)"
                    )
                    return results
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse cached JSON: {e}")

        return None

    def save_to_cache(
        self,
        results: dict,
        entity_ids: list[int] | None = None,
        doc_ids: list[int] | None = None,
        limit: int = 10,
    ) -> None:
        """Save results to database cache with expiration."""
        from datetime import datetime, timedelta

        cache_key = self._compute_cache_key(entity_ids, doc_ids, limit)
        expires_at = datetime.utcnow() + timedelta(hours=CACHE_DURATION_HOURS)

        # Remove from_cache flag before saving
        results_to_save = {
            k: v
            for k, v in results.items()
            if k not in ("from_cache", "cached_at", "expires_at")
        }

        with self.Session() as session:
            # Upsert logic
            existing = (
                session.query(FactComparisonCache)
                .filter(FactComparisonCache.cache_key == cache_key)
                .first()
            )

            summary = results_to_save.get("summary", {})

            if existing:
                existing.results_json = json.dumps(results_to_save)
                existing.entity_count = summary.get("entities_analyzed", 0)
                existing.fact_count = summary.get("total_facts", 0)
                existing.created_at = datetime.utcnow()
                existing.expires_at = expires_at
            else:
                cache_entry = FactComparisonCache(
                    cache_key=cache_key,
                    results_json=json.dumps(results_to_save),
                    entity_count=summary.get("entities_analyzed", 0),
                    fact_count=summary.get("total_facts", 0),
                    expires_at=expires_at,
                )
                session.add(cache_entry)

            session.commit()
            logger.info(
                f"Saved fact analysis to database cache (key: {cache_key[:8]}...)"
            )

    def clear_cache(self) -> int:
        """Clear all cached results. Returns number of entries deleted."""
        with self.Session() as session:
            count = session.query(FactComparisonCache).delete()
            session.commit()
            logger.info(f"Cleared {count} cache entries")
            return count

    def extract_facts_from_chunks(
        self, chunks: list, entity_name: str = None
    ) -> list[Dict[str, Any]]:
        """
        Use LLM to extract factual claims from text chunks.

        Post-processes LLM output to:
        - Fix doc_id using actual chunk->doc mapping
        - Add doc_title from document records
        - Add chunk_text excerpt for evidence
        - Rename 'confidence' to 'reliability'
        """
        if not chunks:
            return []

        # Build chunk info map for post-processing
        # This maps chunk_id to actual doc_id, doc_title, and text excerpt
        session = self.Session()
        try:
            from app.arkham.services.db.models import Document

            # Get document titles for all docs in these chunks
            doc_ids = list(set(c.doc_id for c in chunks if c.doc_id))
            doc_titles = {}
            if doc_ids:
                docs = session.query(Document).filter(Document.id.in_(doc_ids)).all()
                doc_titles = {d.id: d.title or f"Document {d.id}" for d in docs}

            # Build chunk info map
            chunk_info = {}
            for c in chunks:
                chunk_info[c.id] = {
                    "doc_id": c.doc_id,
                    "doc_title": doc_titles.get(c.doc_id, f"Document {c.doc_id}"),
                    "chunk_text": c.text[:200]
                    if c.text
                    else "",  # First 200 chars as excerpt
                }
        finally:
            session.close()

        # Combine chunks for analysis - limit text to prevent token overflow
        combined_text = "\n\n---\n\n".join(
            [f"[Doc {c.doc_id}, Chunk {c.id}]: {c.text[:500]}" for c in chunks[:10]]
        )

        context = f" related to '{entity_name}'" if entity_name else ""

        prompt = f"""Analyze the text excerpts and extract distinct factual claims{context}.

IMPORTANT JSON FORMATTING RULES:
- Return ONLY valid JSON, nothing else
- No trailing commas after the last item in arrays or objects  
- Ensure all strings are properly escaped
- Use exact doc_id and chunk_id values from the [Doc X, Chunk Y] markers

For each fact provide:
- claim: The factual statement
- doc_id: Integer from the [Doc X, ...] marker
- chunk_id: Integer from the [..., Chunk Y] marker  
- reliability: "High", "Medium", or "Low"
- category: One of "Date", "Location", "Relationship", "Amount", "Event", "Role", "Other"

Text excerpts:
{combined_text}

Return this exact JSON structure:
{{"facts": [{{"claim": "statement", "doc_id": 1, "chunk_id": 1, "reliability": "High", "category": "Date"}}]}}

Extract verifiable facts only. Ensure the JSON is complete and valid."""

        try:
            logger.info(
                f"Extracting facts for entity '{entity_name}' from {len(chunks)} chunks"
            )
            logger.info(f"Prompt length: {len(prompt)} chars")

            # Higher max_tokens to prevent truncation of JSON output
            response = chat_with_llm(prompt, max_tokens=3500, json_schema=FACTS_SCHEMA)

            logger.info(f"LLM response length: {len(response)} chars")
            logger.debug(f"LLM response preview: {response[:500]}...")

            # Parse JSON from response - schema returns {"facts": [...]}
            json_start = response.find("{")
            json_end = response.rfind("}") + 1

            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                result = json.loads(json_str)
                # Schema wraps in {"facts": [...]}
                facts = result.get("facts", [])

                # Post-process facts to fix doc_id and add metadata
                for fact in facts:
                    chunk_id = fact.get("chunk_id")

                    # Fix doc_id using chunk info map
                    if chunk_id and chunk_id in chunk_info:
                        info = chunk_info[chunk_id]
                        fact["doc_id"] = info["doc_id"]
                        fact["doc_title"] = info["doc_title"]
                        fact["chunk_text"] = info["chunk_text"]
                    else:
                        # Fallback: try to find a valid chunk
                        if chunk_info:
                            first_chunk_id = next(iter(chunk_info))
                            info = chunk_info[first_chunk_id]
                            fact["doc_id"] = info["doc_id"]
                            fact["doc_title"] = info["doc_title"]
                            fact["chunk_text"] = info["chunk_text"]
                        else:
                            fact["doc_id"] = 0
                            fact["doc_title"] = "Unknown"
                            fact["chunk_text"] = ""

                    # Rename 'confidence' to 'reliability' if LLM used old name
                    if "confidence" in fact and "reliability" not in fact:
                        fact["reliability"] = fact.pop("confidence")
                    elif "reliability" not in fact:
                        fact["reliability"] = "Medium"

                logger.info(f"Extracted {len(facts)} facts successfully")
                if facts:
                    logger.info(f"First fact sample: {facts[0]}")
                return facts
            else:
                logger.warning(
                    f"No JSON object found in LLM response. Response: {response[:300]}..."
                )

        except json.JSONDecodeError as je:
            logger.error(f"JSON parse error extracting facts: {je}")
            logger.error(f"Response was: {response[:500]}...")
        except Exception as e:
            logger.error(f"Error extracting facts: {e}")

        return []

    def compare_facts(self, facts: list[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Use LLM to compare extracted facts and identify agreements/conflicts.
        """
        if len(facts) < 2:
            return {"corroborating": [], "conflicting": [], "unique": facts}

        facts_text = json.dumps(facts, indent=2)

        prompt = f"""Analyze these factual claims and identify:
1. CORROBORATING: Facts that support/confirm each other
2. CONFLICTING: Facts that contradict each other
3. UNIQUE: Facts that stand alone (neither confirmed nor contradicted)

Facts to analyze:
{facts_text}

Return a JSON object:
{{
  "corroborating": [
    {{
      "facts": [0, 3],  // indices of related facts
      "explanation": "Both confirm the same date",
      "confidence": "High"
    }}
  ],
  "conflicting": [
    {{
      "facts": [1, 4],  // indices of conflicting facts
      "explanation": "Dates differ by 2 years",
      "severity": "High",
      "confidence": "High"
    }}
  ],
  "unique": [2, 5]  // indices of standalone facts
}}

Return valid JSON only."""

        try:
            logger.info(f"Comparing {len(facts)} facts for corroboration/conflicts...")
            response = chat_with_llm(
                prompt, max_tokens=2000, json_schema=FACT_COMPARISON_SCHEMA
            )
            logger.info(f"Comparison response length: {len(response)} chars")

            json_start = response.find("{")
            json_end = response.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                comparison = json.loads(response[json_start:json_end])
                logger.info(
                    f"Comparison result: {len(comparison.get('corroborating', []))} corroborating, "
                    f"{len(comparison.get('conflicting', []))} conflicting, "
                    f"{len(comparison.get('unique', []))} unique"
                )
                return comparison
        except Exception as e:
            logger.error(f"Error comparing facts: {e}")

        return {
            "corroborating": [],
            "conflicting": [],
            "unique": list(range(len(facts))),
        }

    def analyze_entity_facts(
        self, entity_id: int, doc_ids_filter: Optional[List[int]] = None
    ) -> Dict[str, Any]:
        """
        Analyze facts about a specific entity across documents.

        Args:
            entity_id: ID of the entity to analyze
            doc_ids_filter: Optional list of document IDs to restrict analysis to
        """
        session = self.Session()
        try:
            # Get entity
            entity = session.query(CanonicalEntity).filter_by(id=entity_id).first()
            if not entity:
                return {"error": "Entity not found"}

            # Get document IDs where this entity appears
            # Use Entity table instead of EntityMention since chunk_id is not populated
            from app.arkham.services.db.models import Entity

            query = session.query(Entity.doc_id).filter(
                Entity.canonical_entity_id == entity_id
            )

            # Apply document filter if provided
            if doc_ids_filter:
                query = query.filter(Entity.doc_id.in_(doc_ids_filter))

            doc_ids = query.distinct().limit(10).all()
            doc_ids = [d[0] for d in doc_ids if d[0] is not None]

            if not doc_ids:
                return {
                    "entity_id": entity_id,
                    "entity_name": entity.canonical_name,
                    "facts": [],
                    "comparison": {
                        "corroborating": [],
                        "conflicting": [],
                        "unique": [],
                    },
                    "summary": {"total_facts": 0, "conflicts": 0, "confirmations": 0},
                }

            # Get chunks from documents where entity appears
            chunks = (
                session.query(Chunk).filter(Chunk.doc_id.in_(doc_ids)).limit(30).all()
            )

            if not chunks:
                return {
                    "entity_id": entity_id,
                    "entity_name": entity.canonical_name,
                    "facts": [],
                    "comparison": {
                        "corroborating": [],
                        "conflicting": [],
                        "unique": [],
                    },
                    "summary": {"total_facts": 0, "conflicts": 0, "confirmations": 0},
                }

            # Extract facts from chunks using LLM
            facts = self.extract_facts_from_chunks(chunks, entity.canonical_name)

            if not facts:
                return {
                    "entity_id": entity_id,
                    "entity_name": entity.canonical_name,
                    "facts": [],
                    "comparison": {
                        "corroborating": [],
                        "conflicting": [],
                        "unique": [],
                    },
                    "summary": {"total_facts": 0, "conflicts": 0, "confirmations": 0},
                }

            # Compare facts using LLM
            comparison = self.compare_facts(facts)

            return {
                "entity_id": entity_id,
                "entity_name": entity.canonical_name,
                "facts": facts,
                "comparison": comparison,
                "summary": {
                    "total_facts": len(facts),
                    "conflicts": len(comparison.get("conflicting", [])),
                    "confirmations": len(comparison.get("corroborating", [])),
                },
            }

        finally:
            session.close()

    def run_corpus_analysis(
        self,
        limit: int = 10,
        use_cache: bool = True,
        doc_ids_filter: Optional[List[int]] = None,
        entity_ids_filter: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        """
        Run fact comparison for selected or top entities in the corpus.

        Args:
            limit: Max number of entities to analyze
            use_cache: Whether to use cached results
            doc_ids_filter: Optional list of document IDs to restrict analysis to
            entity_ids_filter: Optional list of entity IDs to analyze (overrides top entities)

        Returns:
            Dict with entities, entity_details, summary, and cache metadata
        """
        # Try loading from database cache if enabled
        if use_cache:
            cached = self.get_cached_results(entity_ids_filter, doc_ids_filter, limit)
            if cached:
                return cached

        session = self.Session()
        try:
            # Get entities to analyze
            if entity_ids_filter:
                # User selected specific entities
                entities = (
                    session.query(CanonicalEntity)
                    .filter(CanonicalEntity.id.in_(entity_ids_filter))
                    .all()
                )
            else:
                # Default: top entities by mention count
                entities = (
                    session.query(CanonicalEntity)
                    .filter(CanonicalEntity.total_mentions > 0)
                    .order_by(desc(CanonicalEntity.total_mentions))
                    .limit(limit)
                    .all()
                )

            results = []
            entity_details = {}  # Store full analysis per entity
            total_facts = 0
            total_conflicts = 0
            total_confirmations = 0

            for entity in entities:
                analysis = self.analyze_entity_facts(entity.id, doc_ids_filter)
                if "error" not in analysis:
                    results.append(
                        {
                            "entity_id": entity.id,
                            "entity_name": entity.canonical_name,
                            "total_facts": analysis["summary"]["total_facts"],
                            "conflicts": analysis["summary"]["conflicts"],
                            "confirmations": analysis["summary"]["confirmations"],
                        }
                    )
                    # Store the full analysis for later retrieval
                    entity_details[str(entity.id)] = analysis

                    total_facts += analysis["summary"]["total_facts"]
                    total_conflicts += analysis["summary"]["conflicts"]
                    total_confirmations += analysis["summary"]["confirmations"]

            final_result = {
                "entities": results,
                "entity_details": entity_details,  # Include full analysis per entity
                "summary": {
                    "entities_analyzed": len(results),
                    "total_facts": total_facts,
                    "total_conflicts": total_conflicts,
                    "total_confirmations": total_confirmations,
                    "analyzed_at": datetime.now().isoformat(),
                },
                "from_cache": False,  # Fresh analysis
            }

            # Save to database cache
            self.save_to_cache(final_result, entity_ids_filter, doc_ids_filter, limit)

            return final_result

        finally:
            session.close()

    def get_fact_concordance(self, category: str = None) -> list[Dict[str, Any]]:
        """
        Get a concordance report of facts, optionally filtered by category.
        """
        session = self.Session()
        try:
            # Get recent chunks for sampling
            chunks = session.query(Chunk).order_by(desc(Chunk.id)).limit(50).all()

            if not chunks:
                return []

            # Extract facts
            facts = self.extract_facts_from_chunks(chunks)

            # Filter by category if specified
            if category:
                facts = [
                    f
                    for f in facts
                    if f.get("category", "").lower() == category.lower()
                ]

            # Group by claim similarity (simplified - just by category for now)
            grouped = {}
            for fact in facts:
                cat = fact.get("category", "Other")
                if cat not in grouped:
                    grouped[cat] = []
                grouped[cat].append(fact)

            return [
                {"category": cat, "facts": cat_facts, "count": len(cat_facts)}
                for cat, cat_facts in grouped.items()
            ]

        finally:
            session.close()


# Singleton
_service_instance = None


def get_fact_comparison_service() -> FactComparisonService:
    global _service_instance
    if _service_instance is None:
        _service_instance = FactComparisonService()
    return _service_instance
