"""
Cross-Document Big Picture Engine

High-level synthesis of entire corpus:
- LLM-generated executive summaries
- Key actors, events, and relationships overview
- Automated investigation briefing generation
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
    BIG_PICTURE_SCHEMA,
    INVESTIGATION_BRIEF_SCHEMA,
)
from app.arkham.services.utils.security_utils import get_display_filename

load_dotenv()
logger = logging.getLogger(__name__)




class BigPictureService:
    """Service for corpus-wide synthesis and analysis."""

    def __init__(self):
        self.engine = create_engine(DATABASE_URL)
        self.Session = sessionmaker(bind=self.engine)

    def get_corpus_stats(self) -> Dict[str, Any]:
        """Get basic statistics about the corpus."""
        session = self.Session()
        try:
            doc_count = session.query(func.count(Document.id)).scalar()
            chunk_count = session.query(func.count(Chunk.id)).scalar()
            entity_count = session.query(func.count(CanonicalEntity.id)).scalar()
            relationship_count = session.query(
                func.count(EntityRelationship.id)
            ).scalar()

            # Get entity type breakdown
            entity_types = (
                session.query(CanonicalEntity.label, func.count(CanonicalEntity.id))
                .group_by(CanonicalEntity.label)
                .all()
            )

            return {
                "documents": doc_count or 0,
                "chunks": chunk_count or 0,
                "entities": entity_count or 0,
                "relationships": relationship_count or 0,
                "entity_types": {
                    label: count for label, count in entity_types if label
                },
            }
        finally:
            session.close()

    def get_key_actors(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get the most prominent entities in the corpus."""
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

    def get_key_relationships(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get the most significant relationships in the corpus."""
        session = self.Session()
        try:
            relationships = (
                session.query(EntityRelationship)
                .order_by(desc(EntityRelationship.co_occurrence_count))
                .limit(limit)
                .all()
            )

            result = []
            for rel in relationships:
                entity1 = (
                    session.query(CanonicalEntity).filter_by(id=rel.entity1_id).first()
                )
                entity2 = (
                    session.query(CanonicalEntity).filter_by(id=rel.entity2_id).first()
                )
                if entity1 and entity2:
                    result.append(
                        {
                            "entity1": entity1.canonical_name,
                            "entity2": entity2.canonical_name,
                            "type": rel.relationship_type or "associated",
                            "strength": rel.co_occurrence_count or 1,
                        }
                    )

            return result
        finally:
            session.close()

    def generate_executive_summary(self) -> Dict[str, Any]:
        """Generate an LLM-powered executive summary of the corpus."""
        logger.info("Starting executive summary generation...")
        session = self.Session()
        try:
            # Gather context
            stats = self.get_corpus_stats()
            key_actors = self.get_key_actors(15)
            key_relationships = self.get_key_relationships(15)

            # Get sample document content
            documents = (
                session.query(Document)
                .order_by(desc(Document.created_at))
                .limit(10)
                .all()
            )
            doc_summaries = []
            for doc in documents:
                chunks = session.query(Chunk).filter_by(doc_id=doc.id).limit(3).all()
                text_sample = " ".join([c.text[:200] for c in chunks])
                doc_name = get_display_filename(doc)
                doc_summaries.append(f"- {doc_name}: {text_sample[:300]}...")

            # Build prompt
            actors_text = "\n".join(
                [
                    f"- {a['name']} ({a['type']}): {a['mentions']} mentions"
                    for a in key_actors
                ]
            )

            relationships_text = "\n".join(
                [
                    f"- {r['entity1']} <-> {r['entity2']} ({r['type']})"
                    for r in key_relationships[:10]
                ]
            )

            prompt = f"""Analyze this document corpus and generate an executive summary.

CORPUS STATISTICS:
- {stats["documents"]} documents
- {stats["entities"]} unique entities
- {stats["relationships"]} relationships

KEY ACTORS:
{actors_text}

KEY RELATIONSHIPS:
{relationships_text}

SAMPLE DOCUMENTS:
{chr(10).join(doc_summaries[:5])}

Generate a comprehensive executive summary that includes:

1. EXECUTIVE SUMMARY (2-3 paragraphs): What is this corpus about? What's the main story?

2. KEY THEMES: Major topics/themes that emerge from the documents

3. CENTRAL FIGURES: Who are the most important entities and why?

4. NETWORK ANALYSIS: What do the relationships reveal?

5. TIMELINE INSIGHTS: Any chronological patterns visible?

6. RED FLAGS: Suspicious patterns or areas requiring attention

7. INFORMATION GAPS: What's missing that would be valuable?

8. RECOMMENDED FOCUS AREAS: Where should investigation focus?

Return as JSON:
{{
  "executive_summary": "...",
  "key_themes": ["theme1", "theme2"],
  "central_figures": [{{"name": "...", "role": "...", "significance": "..."}}],
  "network_insights": "...",
  "timeline_patterns": "...",
  "red_flags": ["flag1", "flag2"],
  "information_gaps": ["gap1", "gap2"],
  "focus_areas": ["area1", "area2"],
  "generated_at": "{datetime.now().isoformat()}"
}}

Return valid JSON only."""

            logger.info(
                f"Calling LLM for executive summary (prompt length: {len(prompt)} chars)..."
            )
            response = chat_with_llm(
                prompt, max_tokens=3000, json_schema=BIG_PICTURE_SCHEMA
            )
            logger.info(f"LLM response received (length: {len(response)} chars)")

            try:
                json_start = response.find("{")
                json_end = response.rfind("}") + 1
                if json_start >= 0 and json_end > json_start:
                    result = json.loads(response[json_start:json_end])
                    result["stats"] = stats
                    result["key_actors"] = key_actors[:5]
                    return result
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse executive summary JSON: {e}")

            return {
                "executive_summary": response,
                "stats": stats,
                "key_actors": key_actors[:5],
                "error": "Failed to structure response",
            }

        finally:
            session.close()

    def generate_investigation_brief(
        self, focus_entities: List[int] = None
    ) -> Dict[str, Any]:
        """Generate a focused investigation brief."""
        session = self.Session()
        try:
            # Get target entities
            if focus_entities:
                entities = (
                    session.query(CanonicalEntity)
                    .filter(CanonicalEntity.id.in_(focus_entities))
                    .all()
                )
            else:
                entities = (
                    session.query(CanonicalEntity)
                    .filter(CanonicalEntity.total_mentions > 0)
                    .order_by(desc(CanonicalEntity.total_mentions))
                    .limit(5)
                    .all()
                )

            if not entities:
                return {"error": "No entities found for briefing"}

            # Gather evidence for each entity
            entity_evidence = []
            for entity in entities:
                chunk_ids = (
                    session.query(EntityMention.chunk_id)
                    .filter(EntityMention.canonical_entity_id == entity.id)
                    .distinct()
                    .limit(5)
                    .all()
                )
                chunk_ids = [c[0] for c in chunk_ids]
                chunks = session.query(Chunk).filter(Chunk.id.in_(chunk_ids)).all()

                evidence = " | ".join([c.text[:150] for c in chunks[:3]])
                entity_evidence.append(
                    f"**{entity.canonical_name}** ({entity.label}): {evidence[:400]}..."
                )

            # Get relationships between focus entities
            entity_ids = [e.id for e in entities]
            relationships = (
                session.query(EntityRelationship)
                .filter(
                    EntityRelationship.entity1_id.in_(entity_ids),
                    EntityRelationship.entity2_id.in_(entity_ids),
                )
                .all()
            )

            rel_text = []
            for rel in relationships:
                e1 = next((e for e in entities if e.id == rel.entity1_id), None)
                e2 = next((e for e in entities if e.id == rel.entity2_id), None)
                if e1 and e2:
                    rel_text.append(f"{e1.canonical_name} <-> {e2.canonical_name}")

            prompt = f"""Generate an investigation brief based on these key subjects:

SUBJECTS UNDER INVESTIGATION:
{chr(10).join(entity_evidence)}

KNOWN CONNECTIONS:
{chr(10).join(rel_text) if rel_text else "No direct connections found"}

Create an investigation brief with:

1. SUBJECT PROFILES: Brief on each key subject
2. CONNECTION ANALYSIS: How subjects relate to each other
3. TIMELINE: Key events and their sequence (if discernible)
4. EVIDENCE ASSESSMENT: Strength of available evidence
5. HYPOTHESES: Possible explanations for observed patterns
6. PRIORITY ACTIONS: What to investigate next
7. RISKS: Potential issues or complications

Return as JSON:
{{
  "title": "Investigation Brief: [subject]",
  "subjects": [{{"name": "...", "profile": "...", "risk_level": "High/Medium/Low"}}],
  "connections": [{{"from": "...", "to": "...", "nature": "..."}}],
  "key_events": [{{"event": "...", "date": "...", "significance": "..."}}],
  "evidence_strength": "Strong/Moderate/Weak",
  "hypotheses": [{{"hypothesis": "...", "confidence": "...", "supporting_evidence": "..."}}],
  "priority_actions": ["action1", "action2"],
  "risks": ["risk1", "risk2"],
  "classification": "CONFIDENTIAL",
  "generated_at": "{datetime.now().isoformat()}"
}}

Return valid JSON only."""

            response = chat_with_llm(
                prompt, max_tokens=3000, json_schema=INVESTIGATION_BRIEF_SCHEMA
            )

            try:
                json_start = response.find("{")
                json_end = response.rfind("}") + 1
                if json_start >= 0 and json_end > json_start:
                    result = json.loads(response[json_start:json_end])
                    result["entity_ids"] = [e.id for e in entities]
                    return result
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse investigation brief JSON: {e}")

            return {
                "raw_brief": response,
                "entity_ids": [e.id for e in entities],
                "error": "Failed to structure response",
            }

        finally:
            session.close()

    def get_corpus_overview(self) -> Dict[str, Any]:
        """Get a comprehensive corpus overview for the UI."""
        stats = self.get_corpus_stats()
        key_actors = self.get_key_actors(10)
        key_relationships = self.get_key_relationships(15)

        return {
            "stats": stats,
            "key_actors": key_actors,
            "key_relationships": key_relationships,
            "generated_at": datetime.now().isoformat(),
        }


# Singleton
_service_instance = None


def get_big_picture_service() -> BigPictureService:
    global _service_instance
    if _service_instance is None:
        _service_instance = BigPictureService()
    return _service_instance
