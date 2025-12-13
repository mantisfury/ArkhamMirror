"""
Speculation Mode Service

LLM-generated hypotheses and investigative leads:
- "What-if" scenario generation
- Gap-filling suggestions (missing documents, unexplored connections)
- Investigative question generator
"""

import os
import json
import logging
from typing import Dict, Any, List
from datetime import datetime
from sqlalchemy import create_engine, desc, func
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

from config.settings import DATABASE_URL

from app.arkham.services.db.models import (
    CanonicalEntity,
    Document,
    Chunk,
    EntityMention,
    EntityRelationship,
)
from app.arkham.services.llm_service import (
    chat_with_llm,
    SPECULATION_SCENARIOS_SCHEMA,
    GAPS_SCHEMA,
    QUESTIONS_SCHEMA,
)

load_dotenv()
logger = logging.getLogger(__name__)




class SpeculationService:
    """Service for generating investigative hypotheses and leads."""

    def __init__(self):
        self.engine = create_engine(DATABASE_URL)
        self.Session = sessionmaker(bind=self.engine)

    def get_filter_options(self) -> Dict[str, Any]:
        """Get available documents and entities for filtering."""
        session = self.Session()
        try:
            # Get all documents
            documents = (
                session.query(Document.id, Document.title)
                .order_by(Document.title)
                .all()
            )

            # Get top entities (limit to prevent overwhelming UI)
            entities = (
                session.query(
                    CanonicalEntity.id,
                    CanonicalEntity.canonical_name,
                    CanonicalEntity.label,
                )
                .filter(CanonicalEntity.total_mentions > 0)
                .order_by(desc(CanonicalEntity.total_mentions))
                .limit(100)
                .all()
            )

            return {
                "documents": [
                    {"id": d.id, "title": d.title or f"Document {d.id}"}
                    for d in documents
                ],
                "entities": [
                    {"id": e.id, "name": e.canonical_name, "type": e.label}
                    for e in entities
                ],
            }
        finally:
            session.close()

    def _get_corpus_context(
        self, doc_ids: List[int] = None, entity_ids: List[int] = None
    ) -> Dict[str, Any]:
        """Gather context about the corpus for speculation.

        Args:
            doc_ids: If provided, only include entities from these documents
            entity_ids: If provided, only include these specific entities
        """
        session = self.Session()
        try:
            # Build entity query with optional filters
            entity_query = session.query(CanonicalEntity).filter(
                CanonicalEntity.total_mentions > 0
            )

            # Filter by specific entity IDs if provided
            if entity_ids:
                entity_query = entity_query.filter(CanonicalEntity.id.in_(entity_ids))
            # Or filter by document IDs (entities mentioned in those docs)
            elif doc_ids:
                entity_ids_in_docs = (
                    session.query(EntityMention.canonical_entity_id)
                    .join(Chunk, EntityMention.chunk_id == Chunk.id)
                    .filter(Chunk.document_id.in_(doc_ids))
                    .distinct()
                    .subquery()
                )
                entity_query = entity_query.filter(
                    CanonicalEntity.id.in_(entity_ids_in_docs)
                )

            # Get entity counts by type
            entity_types = (
                entity_query.with_entities(
                    CanonicalEntity.label, func.count(CanonicalEntity.id)
                )
                .group_by(CanonicalEntity.label)
                .all()
            )

            # Get top entities
            top_entities = (
                entity_query.order_by(desc(CanonicalEntity.total_mentions))
                .limit(20)
                .all()
            )

            # Get entity IDs for relationship filtering
            selected_entity_ids = [e.id for e in top_entities]

            # Get sample relationships (filtered to selected entities)
            rel_query = session.query(EntityRelationship)
            if selected_entity_ids:
                rel_query = rel_query.filter(
                    (EntityRelationship.entity1_id.in_(selected_entity_ids))
                    | (EntityRelationship.entity2_id.in_(selected_entity_ids))
                )
            relationships = (
                rel_query.order_by(desc(EntityRelationship.co_occurrence_count))
                .limit(15)
                .all()
            )

            rel_descriptions = []
            for rel in relationships:
                e1 = session.query(CanonicalEntity).filter_by(id=rel.entity1_id).first()
                e2 = session.query(CanonicalEntity).filter_by(id=rel.entity2_id).first()
                if e1 and e2:
                    rel_descriptions.append(
                        f"{e1.canonical_name} <-> {e2.canonical_name} ({rel.relationship_type or 'associated'})"
                    )

            return {
                "entity_types": {
                    label: count for label, count in entity_types if label
                },
                "top_entities": [
                    {
                        "name": e.canonical_name,
                        "type": e.label,
                        "mentions": e.total_mentions,
                    }
                    for e in top_entities
                ],
                "key_relationships": rel_descriptions,
            }
        finally:
            session.close()

    def generate_what_if_scenarios(
        self,
        focus_topic: str = None,
        doc_ids: List[int] = None,
        entity_ids: List[int] = None,
    ) -> List[Dict[str, Any]]:
        """Generate what-if scenarios for investigation."""
        context = self._get_corpus_context(doc_ids=doc_ids, entity_ids=entity_ids)

        entities_text = "\n".join(
            [
                f"- {e['name']} ({e['type']}): {e['mentions']} mentions"
                for e in context["top_entities"][:15]
            ]
        )

        relationships_text = "\n".join(
            [f"- {r}" for r in context["key_relationships"][:10]]
        )

        focus_text = f"\nFOCUS AREA: {focus_topic}\n" if focus_topic else ""

        prompt = f"""Based on this investigative corpus, generate "what-if" scenarios worth exploring.

KEY ENTITIES:
{entities_text}

KEY RELATIONSHIPS:
{relationships_text}
{focus_text}
Generate 5-7 investigative "what-if" scenarios that could reveal hidden patterns or connections.
Each scenario should:
1. Be based on observed data patterns
2. Suggest a plausible but unconfirmed connection
3. Identify what evidence would confirm or refute it
4. Assess the potential significance if true

Return as JSON:
{{
  "scenarios": [
    {{
      "id": "1",
      "hypothesis": "What if [entity] was actually [speculation]...",
      "basis": "Based on [observed pattern]...",
      "evidence_needed": ["What to look for..."],
      "significance": "High/Medium/Low",
      "significance_explanation": "Why this matters...",
      "investigation_steps": ["Step 1...", "Step 2..."]
    }}
  ]
}}

Return valid JSON only. Be creative but grounded in the data."""

        response = chat_with_llm(
            prompt, max_tokens=2500, json_schema=SPECULATION_SCENARIOS_SCHEMA
        )

        try:
            json_start = response.find("{")
            json_end = response.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                result = json.loads(response[json_start:json_end])
                return result.get("scenarios", [])
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse scenarios JSON: {e}")

        return []

    def identify_gaps(
        self, doc_ids: List[int] = None, entity_ids: List[int] = None
    ) -> List[Dict[str, Any]]:
        """Identify gaps in the corpus that warrant investigation."""
        session = self.Session()
        try:
            context = self._get_corpus_context(doc_ids=doc_ids, entity_ids=entity_ids)

            # Get document count
            doc_count = session.query(func.count(Document.id)).scalar()

            # Get entities with few relationships
            lonely_entities = (
                session.query(CanonicalEntity)
                .filter(CanonicalEntity.total_mentions >= 3)
                .limit(30)
                .all()
            )

            lonely_list = []
            for entity in lonely_entities:
                rel_count = (
                    session.query(func.count(EntityRelationship.id))
                    .filter(
                        (EntityRelationship.entity1_id == entity.id)
                        | (EntityRelationship.entity2_id == entity.id)
                    )
                    .scalar()
                )
                if rel_count < 2 and entity.total_mentions >= 3:
                    lonely_list.append(
                        {
                            "name": entity.canonical_name,
                            "type": entity.label,
                            "mentions": entity.total_mentions,
                            "relationships": rel_count,
                        }
                    )

            entities_text = "\n".join(
                [
                    f"- {e['name']} ({e['type']}): {e['mentions']} mentions"
                    for e in context["top_entities"][:10]
                ]
            )

            lonely_text = "\n".join(
                [
                    f"- {e['name']} ({e['type']}): {e['mentions']} mentions but only {e['relationships']} relationships"
                    for e in lonely_list[:10]
                ]
            )

            prompt = f"""Analyze this investigative corpus and identify information gaps.

CORPUS STATS:
- {doc_count} documents
- {len(context["top_entities"])} key entities

KEY ENTITIES:
{entities_text}

ISOLATED ENTITIES (frequently mentioned but few connections):
{lonely_text}

Identify 5-7 significant gaps in the corpus:
1. Missing documents that likely exist
2. Unexplored connections between entities
3. Time periods with sparse coverage
4. Entity types that seem underrepresented
5. Questions that the data raises but doesn't answer

Return as JSON:
{{
  "gaps": [
    {{
      "id": "1",
      "type": "missing_document/unexplored_connection/time_gap/underrepresented_entity/unanswered_question",
      "description": "Description of the gap...",
      "importance": "High/Medium/Low",
      "indicators": ["Why we think this is missing..."],
      "suggested_sources": ["Where to look for answers..."]
    }}
  ]
}}

Return valid JSON only."""

            response = chat_with_llm(prompt, max_tokens=2000, json_schema=GAPS_SCHEMA)

            try:
                json_start = response.find("{")
                json_end = response.rfind("}") + 1
                if json_start >= 0 and json_end > json_start:
                    result = json.loads(response[json_start:json_end])
                    return result.get("gaps", [])
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse gaps JSON: {e}")

            return []

        finally:
            session.close()

    def generate_investigative_questions(
        self,
        entity_id: int = None,
        doc_ids: List[int] = None,
        entity_ids: List[int] = None,
    ) -> List[Dict[str, Any]]:
        """Generate investigative questions based on the corpus or specific entity."""
        session = self.Session()
        try:
            if entity_id:
                entity = session.query(CanonicalEntity).filter_by(id=entity_id).first()
                if not entity:
                    return [{"error": "Entity not found"}]

                # Get entity context
                chunk_ids = (
                    session.query(EntityMention.chunk_id)
                    .filter(EntityMention.canonical_entity_id == entity_id)
                    .distinct()
                    .limit(10)
                    .all()
                )
                chunk_ids = [c[0] for c in chunk_ids]
                chunks = session.query(Chunk).filter(Chunk.id.in_(chunk_ids)).all()

                evidence = " | ".join([c.text[:150] for c in chunks[:5]])

                prompt = f"""Generate investigative questions about this entity.

ENTITY: {entity.canonical_name} ({entity.label})
MENTIONS: {entity.total_mentions}

SAMPLE EVIDENCE:
{evidence}

Generate 5-7 investigative questions that would deepen understanding of this entity:
- Who are their key associates?
- What is their role in events?
- What are their motivations?
- What connections might be hidden?
- What patterns do they follow?

Return as JSON:
{{
  "questions": [
    {{
      "id": "1",
      "question": "The investigative question...",
      "priority": "High/Medium/Low",
      "rationale": "Why this question matters...",
      "potential_sources": ["Where to find answers..."]
    }}
  ]
}}

Return valid JSON only."""

            else:
                context = self._get_corpus_context(
                    doc_ids=doc_ids, entity_ids=entity_ids
                )

                entities_text = "\n".join(
                    [
                        f"- {e['name']} ({e['type']})"
                        for e in context["top_entities"][:10]
                    ]
                )

                prompt = f"""Generate priority investigative questions for this corpus.

KEY ENTITIES:
{entities_text}

KEY RELATIONSHIPS:
{chr(10).join(context["key_relationships"][:8])}

Generate 7-10 high-value investigative questions that would advance the investigation:
- Questions about hidden connections
- Questions about unexplained patterns
- Questions about entity motivations
- Questions about missing information
- Questions about contradictions

Return as JSON:
{{
  "questions": [
    {{
      "id": "1",
      "question": "The investigative question...",
      "priority": "High/Medium/Low",
      "rationale": "Why this question matters...",
      "related_entities": ["Entity names..."],
      "potential_sources": ["Where to find answers..."]
    }}
  ]
}}

Return valid JSON only."""

            response = chat_with_llm(
                prompt, max_tokens=2000, json_schema=QUESTIONS_SCHEMA
            )

            try:
                json_start = response.find("{")
                json_end = response.rfind("}") + 1
                if json_start >= 0 and json_end > json_start:
                    result = json.loads(response[json_start:json_end])
                    return result.get("questions", [])
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse questions JSON: {e}")

            return []

        finally:
            session.close()

    def get_speculation_summary(self) -> Dict[str, Any]:
        """Get a quick speculation summary without full LLM calls."""
        session = self.Session()
        try:
            doc_count = session.query(func.count(Document.id)).scalar()
            entity_count = session.query(func.count(CanonicalEntity.id)).scalar()
            rel_count = session.query(func.count(EntityRelationship.id)).scalar()

            return {
                "documents": doc_count or 0,
                "entities": entity_count or 0,
                "relationships": rel_count or 0,
                "ready_for_analysis": (doc_count or 0) > 0,
            }
        finally:
            session.close()


# Singleton
_service_instance = None


def get_speculation_service() -> SpeculationService:
    global _service_instance
    if _service_instance is None:
        _service_instance = SpeculationService()
    return _service_instance
