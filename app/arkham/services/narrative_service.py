"""
Inference-of-Motive & Narrative Reconstruction Service

LLM-powered hypothesis generation that:
- Reconstructs event sequences from document fragments
- Generates plausible motives based on entity behaviors
- Creates timeline narratives with supporting evidence
"""

import os
import json
import logging
from typing import Dict, Any, List
from datetime import datetime
from sqlalchemy import create_engine, desc
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

from config.settings import DATABASE_URL

from app.arkham.services.db.models import (
    CanonicalEntity,
    Chunk,
    EntityMention,
    EntityRelationship,
)
from app.arkham.services.llm_service import (
    chat_with_llm,
    NARRATIVE_SCHEMA,
    MOTIVE_SCHEMA,
    INVESTIGATION_BRIEF_SCHEMA,
)

load_dotenv()
logger = logging.getLogger(__name__)




class NarrativeService:
    """Service for narrative reconstruction and motive inference."""

    def __init__(self):
        self.engine = create_engine(DATABASE_URL)
        self.Session = sessionmaker(bind=self.engine)

    def _get_entity_context(
        self, session, entity_id: int, limit: int = 20
    ) -> Dict[str, Any]:
        """Get comprehensive context about an entity."""
        entity = session.query(CanonicalEntity).filter_by(id=entity_id).first()
        if not entity:
            return None

        # Get doc_ids where this entity appears (use Entity table, not EntityMention.chunk_id
        # since chunk_id is often null)
        doc_ids = (
            session.query(EntityMention.doc_id)
            .filter(EntityMention.canonical_entity_id == entity_id)
            .distinct()
            .limit(10)
            .all()
        )
        doc_ids = [d[0] for d in doc_ids if d[0] is not None]

        # Get chunks from those documents
        chunks = []
        if doc_ids:
            chunks = (
                session.query(Chunk)
                .filter(Chunk.doc_id.in_(doc_ids))
                .limit(limit)
                .all()
            )

        # Get relationships
        relationships = (
            session.query(EntityRelationship)
            .filter(
                (EntityRelationship.entity1_id == entity_id)
                | (EntityRelationship.entity2_id == entity_id)
            )
            .limit(20)
            .all()
        )

        # Get related entity names
        related_entity_ids = set()
        for rel in relationships:
            related_entity_ids.add(
                rel.entity1_id if rel.entity1_id != entity_id else rel.entity2_id
            )

        related_entities = (
            session.query(CanonicalEntity)
            .filter(CanonicalEntity.id.in_(related_entity_ids))
            .all()
        )

        logger.info(
            f"Entity context for {entity.canonical_name}: {len(chunks)} chunks, {len(relationships)} relationships"
        )

        return {
            "entity": entity,
            "chunks": chunks,
            "relationships": relationships,
            "related_entities": related_entities,
        }

    def reconstruct_narrative(self, entity_id: int) -> Dict[str, Any]:
        """
        Reconstruct a narrative around an entity based on document evidence.
        """
        session = self.Session()
        try:
            context = self._get_entity_context(session, entity_id)
            if not context:
                return {"error": "Entity not found"}

            entity = context["entity"]
            chunks = context["chunks"]
            related = context["related_entities"]

            if not chunks:
                return {
                    "entity_id": entity_id,
                    "entity_name": entity.canonical_name,
                    "narrative": "Insufficient evidence to reconstruct narrative.",
                    "events": [],
                    "confidence": "Low",
                }

            # Build context for LLM
            chunk_texts = "\n\n---\n\n".join(
                [f"[Document {c.doc_id}]: {c.text[:500]}" for c in chunks[:15]]
            )

            related_names = [e.canonical_name for e in related[:10]]

            prompt = f"""Analyze the following document excerpts about "{entity.canonical_name}" and reconstruct a narrative.

Related entities: {", ".join(related_names) if related_names else "None identified"}

Document excerpts:
{chunk_texts}

Provide a structured analysis:

1. NARRATIVE SUMMARY: A coherent story reconstructed from the evidence (2-3 paragraphs)

2. KEY EVENTS: A chronological list of events/actions involving this entity
   Format each as: {{"event": "description", "date": "if known or 'Unknown'", "confidence": "High/Medium/Low"}}

3. RELATIONSHIPS: How this entity connects to others
   Format each as: {{"entity": "name", "relationship": "description", "nature": "positive/negative/neutral"}}

4. GAPS: What information is missing that would complete the picture

Return as JSON:
{{
  "narrative": "Summary text...",
  "events": [...],
  "relationships": [...],
  "gaps": ["gap1", "gap2"],
  "overall_confidence": "High/Medium/Low"
}}

Return valid JSON only."""

            response = chat_with_llm(
                prompt, max_tokens=2500, json_schema=NARRATIVE_SCHEMA
            )

            # Parse response
            try:
                json_start = response.find("{")
                json_end = response.rfind("}") + 1
                if json_start >= 0 and json_end > json_start:
                    result = json.loads(response[json_start:json_end])
                    result["entity_id"] = entity_id
                    result["entity_name"] = entity.canonical_name
                    result["entity_type"] = entity.label
                    return result
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse narrative JSON: {e}")

            return {
                "entity_id": entity_id,
                "entity_name": entity.canonical_name,
                "narrative": response,
                "events": [],
                "relationships": [],
                "gaps": [],
                "overall_confidence": "Low",
            }

        finally:
            session.close()

    def infer_motives(self, entity_id: int) -> Dict[str, Any]:
        """
        Generate hypotheses about an entity's motives based on their actions.
        """
        session = self.Session()
        try:
            context = self._get_entity_context(session, entity_id)
            if not context:
                return {"error": "Entity not found"}

            entity = context["entity"]
            chunks = context["chunks"]
            _ = context["relationships"]  # Available for future use

            if not chunks:
                return {
                    "entity_id": entity_id,
                    "entity_name": entity.canonical_name,
                    "hypotheses": [],
                    "warning": "Insufficient evidence",
                }

            # Build context
            chunk_texts = "\n\n".join([f"- {c.text[:400]}" for c in chunks[:12]])

            prompt = f"""Based on the following evidence about "{entity.canonical_name}", generate hypotheses about their possible motives, goals, and intentions.

Evidence:
{chunk_texts}

Entity type: {entity.label}
Number of document mentions: {entity.total_mentions or "Unknown"}

Generate 3-5 hypotheses about this entity's motives. For each hypothesis:
1. State the hypothesis clearly
2. List supporting evidence (quote or reference)
3. List contradicting evidence (if any)
4. Rate confidence (High/Medium/Low/Speculative)
5. Suggest what additional evidence would confirm or refute it

IMPORTANT: Clearly mark speculative content. These are HYPOTHESES, not facts.

Return as JSON:
{{
  "hypotheses": [
    {{
      "hypothesis": "Clear statement of the hypothesis",
      "supporting_evidence": ["evidence1", "evidence2"],
      "contradicting_evidence": ["evidence if any"],
      "confidence": "Medium",
      "verification_needed": ["what would confirm this"]
    }}
  ],
  "behavioral_patterns": ["pattern1", "pattern2"],
  "risk_flags": ["any concerning patterns"],
  "speculation_warning": "These are hypotheses based on limited evidence..."
}}

Return valid JSON only."""

            response = chat_with_llm(prompt, max_tokens=2500, json_schema=MOTIVE_SCHEMA)

            try:
                json_start = response.find("{")
                json_end = response.rfind("}") + 1
                if json_start >= 0 and json_end > json_start:
                    result = json.loads(response[json_start:json_end])
                    result["entity_id"] = entity_id
                    result["entity_name"] = entity.canonical_name
                    return result
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse motive JSON: {e}")

            return {
                "entity_id": entity_id,
                "entity_name": entity.canonical_name,
                "hypotheses": [],
                "raw_analysis": response,
            }

        finally:
            session.close()

    def generate_investigation_brief(
        self, entity_ids: List[int] = None
    ) -> Dict[str, Any]:
        """
        Generate an investigation brief covering multiple entities or the whole corpus.
        """
        session = self.Session()
        try:
            # If no entities specified, get top entities
            if not entity_ids:
                entities = (
                    session.query(CanonicalEntity)
                    .filter(CanonicalEntity.total_mentions > 0)
                    .order_by(desc(CanonicalEntity.total_mentions))
                    .limit(5)
                    .all()
                )
            else:
                entities = (
                    session.query(CanonicalEntity)
                    .filter(CanonicalEntity.id.in_(entity_ids))
                    .all()
                )

            if not entities:
                return {"error": "No entities found"}

            # Gather context for all entities
            entity_summaries = []
            for entity in entities:
                context = self._get_entity_context(session, entity.id, limit=10)
                if context and context["chunks"]:
                    chunks_text = " ".join(
                        [c.text[:200] for c in context["chunks"][:5]]
                    )
                    entity_summaries.append(
                        f"- {entity.canonical_name} ({entity.label}): {chunks_text[:300]}..."
                    )

            prompt = f"""Generate an investigation brief based on these key entities and their document mentions:

{chr(10).join(entity_summaries)}

Create a comprehensive brief. Return as JSON with these exact fields:
{{
  "title": "Brief title summarizing the investigation",
  "subjects": [
    {{"name": "Entity name", "profile": "Brief description of entity and their role", "risk_level": "High/Medium/Low"}}
  ],
  "connections": [
    {{"from": "Entity1", "to": "Entity2", "nature": "Description of relationship"}}
  ],
  "key_events": [
    {{"event": "What happened", "date": "When (or 'Unknown')", "significance": "Why it matters"}}
  ],
  "evidence_strength": "Overall assessment of evidence quality (Strong/Moderate/Weak)",
  "hypotheses": [
    {{"hypothesis": "Possible explanation", "confidence": "High/Medium/Low", "supporting_evidence": "Brief evidence summary"}}
  ],
  "priority_actions": ["Next step 1", "Next step 2"],
  "risks": ["Risk or red flag 1", "Risk or red flag 2"]
}}

Return valid JSON only, with all required fields filled in."""

            response = chat_with_llm(
                prompt, max_tokens=3000, json_schema=INVESTIGATION_BRIEF_SCHEMA
            )

            try:
                json_start = response.find("{")
                json_end = response.rfind("}") + 1
                if json_start >= 0 and json_end > json_start:
                    data = json.loads(response[json_start:json_end])

                    # Transform to what the state expects
                    result = {
                        "entities_analyzed": [e.canonical_name for e in entities],
                        "executive_summary": data.get("title", "Investigation Brief"),
                        "key_players": [
                            {
                                "name": s.get("name", ""),
                                "role": s.get("profile", ""),
                                "significance": s.get("risk_level", ""),
                            }
                            for s in data.get("subjects", [])
                        ],
                        "red_flags": data.get("risks", []),
                        "hypotheses": data.get("hypotheses", []),
                        "gaps": [
                            f"Evidence: {data.get('evidence_strength', 'Unknown')}"
                        ],
                        "next_steps": data.get("priority_actions", []),
                    }
                    return result
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse brief JSON: {e}")

            return {
                "entities_analyzed": [e.canonical_name for e in entities],
                "raw_brief": response,
                "error": "Failed to structure response",
            }

        finally:
            session.close()

    def get_analyzable_entities(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get list of entities that can be analyzed."""
        session = self.Session()
        try:
            entities = (
                session.query(CanonicalEntity)
                .filter(CanonicalEntity.total_mentions > 0)
                .order_by(desc(CanonicalEntity.total_mentions))
                .limit(limit)
                .all()
            )

            return [
                {
                    "id": e.id,
                    "name": e.canonical_name,
                    "type": e.label,
                    "mentions": e.total_mentions or 0,
                }
                for e in entities
            ]

        finally:
            session.close()


# Singleton
_service_instance = None


def get_narrative_service() -> NarrativeService:
    global _service_instance
    if _service_instance is None:
        _service_instance = NarrativeService()
    return _service_instance
