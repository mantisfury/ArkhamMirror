"""
Chain Service - Data transformation for Contradiction Chain visualization.
"""

import os
import json
import logging
import hashlib
from typing import List, Dict, Optional, Any
from sqlalchemy import create_engine, desc
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

from config.settings import DATABASE_URL

from app.arkham.services.db.models import (
    Contradiction,
    ContradictionEvidence,
    CanonicalEntity,
    Document,
)

load_dotenv()

logger = logging.getLogger(__name__)


def _generate_entity_color(entity_name: str) -> str:
    """Generate a consistent HSL color for an entity name."""
    # Use hash to generate consistent hue for same name
    hash_val = int(hashlib.md5(entity_name.encode()).hexdigest()[:8], 16)
    hue = hash_val % 360
    # Keep saturation and lightness in pleasing range
    return f"hsl({hue}, 70%, 50%)"


class ChainService:
    """Service for generating contradiction chain visualization data."""

    def __init__(self):
        self.engine = create_engine(DATABASE_URL)
        self.Session = sessionmaker(bind=self.engine)

    def get_chain_data(
        self,
        min_confidence: float = 0.0,
        entity_ids: Optional[List[int]] = None,
        severity_filter: Optional[List[str]] = None,
        limit: int = 50,
        sort_by: str = "mentions",  # mentions, alpha, contradictions
        x_axis_mode: str = "sequence",  # time, sequence
    ) -> Dict[str, Any]:
        """
        Get contradiction data formatted for chain visualization.

        Returns:
        {
            "points": List of claim points,
            "connections": List of connections between points,
            "entities": Sorted list of entity names for swimlanes,
            "total_count": Total contradictions before limit,
        }
        """
        session = self.Session()
        try:
            # Build base query
            query = session.query(Contradiction).filter(
                Contradiction.confidence >= min_confidence
            )

            # Filter by entity if specified
            if entity_ids:
                query = query.filter(Contradiction.entity_id.in_(entity_ids))

            # Filter by severity
            if severity_filter:
                query = query.filter(Contradiction.severity.in_(severity_filter))

            # Get total count before limit
            total_count = query.count()

            # Apply limit
            contradictions = (
                query.order_by(desc(Contradiction.confidence)).limit(limit).all()
            )

            # Build points and connections
            points = []
            connections = []
            entity_data = {}  # For sorting
            entity_id_to_name = {}  # Cache for entity lookups

            for idx, c in enumerate(contradictions):
                # Get primary entity info
                entity = (
                    session.query(CanonicalEntity)
                    .filter(CanonicalEntity.id == c.entity_id)
                    .first()
                )
                # Cache entity name for lookups
                if entity:
                    entity_id_to_name[entity.id] = entity.canonical_name

                # NEW: Get all involved entities (cross-entity support)
                involved_ids = []
                if c.involved_entity_ids:
                    try:
                        involved_ids = json.loads(c.involved_entity_ids)
                    except (json.JSONDecodeError, TypeError):
                        involved_ids = []

                # If no involved_ids, fall back to primary entity
                if not involved_ids:
                    involved_ids = [c.entity_id] if c.entity_id else []

                # Lookup names for all involved entities
                involved_entities = []  # List of (id, name) tuples
                for eid in involved_ids:
                    if eid in entity_id_to_name:
                        involved_entities.append((eid, entity_id_to_name[eid]))
                    else:
                        ent = (
                            session.query(CanonicalEntity)
                            .filter(CanonicalEntity.id == eid)
                            .first()
                        )
                        if ent:
                            entity_id_to_name[eid] = ent.canonical_name
                            involved_entities.append((eid, ent.canonical_name))

                # Add all involved entities to entity_data for swimlane sorting
                for eid, ename in involved_entities:
                    if ename not in entity_data:
                        ent = entity_id_to_name.get(eid)
                        # Get mentions count if we have the entity
                        mentions = 0
                        if eid in entity_id_to_name:
                            ent_obj = (
                                session.query(CanonicalEntity)
                                .filter(CanonicalEntity.id == eid)
                                .first()
                            )
                            mentions = ent_obj.total_mentions if ent_obj else 0
                        entity_data[ename] = {
                            "mentions": mentions,
                            "contradiction_count": 0,
                        }
                    entity_data[ename]["contradiction_count"] += 1

                # Get evidence for this contradiction
                evidence_list = (
                    session.query(ContradictionEvidence)
                    .filter(ContradictionEvidence.contradiction_id == c.id)
                    .all()
                )

                # Create points for each piece of evidence on EACH involved entity's swimlane
                point_ids = []
                for ev_idx, evidence in enumerate(evidence_list):
                    # Get document info for x-position
                    doc = (
                        session.query(Document)
                        .filter(Document.id == evidence.document_id)
                        .first()
                    )

                    # Determine x position - spread out more for readability
                    # Each contradiction gets 10 units of space, evidence points within get offset
                    SPACING = 10  # Units between contradictions

                    if x_axis_mode == "time":
                        from datetime import datetime, timedelta

                        # Try to get a real date
                        x_date = None
                        if doc:
                            x_date = doc.pdf_creation_date or doc.created_at

                        if x_date:
                            # Add offset to spread out points even with same date
                            # Each contradiction gets hours offset, evidence gets minutes
                            offset = timedelta(hours=idx * 2, minutes=ev_idx * 10)
                            adjusted_date = x_date + offset
                            x_position = adjusted_date.isoformat()
                        else:
                            # No date available - use synthetic date based on index
                            base_date = datetime(2024, 1, 1)
                            synthetic_date = base_date + timedelta(
                                days=idx, hours=ev_idx
                            )
                            x_position = synthetic_date.isoformat()
                    else:
                        # Sequence mode: spread contradictions wide apart
                        x_position = float(idx * SPACING + ev_idx * 2)

                    # Get filename for display
                    if doc:
                        filename = doc.title or doc.path.split("/")[-1].split("\\")[-1]
                    else:
                        filename = f"Doc {evidence.document_id}"

                    # NEW: Create a point on EACH involved entity's swimlane
                    # This enables cross-entity connections (red yarn across lanes)
                    for ent_idx, (eid, ename) in enumerate(involved_entities):
                        # Create unique point ID that includes entity
                        point_id = f"c{c.id}_e{ev_idx}_ent{eid}"
                        point_ids.append(point_id)

                        points.append(
                            {
                                "id": point_id,
                                "contradiction_id": c.id,
                                "entity_name": ename,  # This entity's swimlane
                                "entity_id": eid,
                                "claim_text": evidence.text_chunk[:200]
                                if evidence.text_chunk
                                else "No text",
                                "source_doc": filename,
                                "document_id": evidence.document_id,
                                "x_position": x_position,
                                "x_sequence": idx * 2 + ev_idx,
                                "confidence": c.confidence or 0.5,
                                "severity": c.severity or "Medium",
                                "status": c.status or "Open",
                                "category": c.category or "factual",
                                "is_cross_entity": len(involved_entities)
                                > 1,  # Flag for UI
                            }
                        )

                # Create connections between all points in this contradiction
                # This now connects points ACROSS different entity swimlanes!
                for i in range(len(point_ids)):
                    for j in range(i + 1, len(point_ids)):
                        connections.append(
                            {
                                "from_point_id": point_ids[i],
                                "to_point_id": point_ids[j],
                                "contradiction_id": c.id,
                                "confidence": c.confidence or 0.5,
                            }
                        )

            # Sort entities for swimlanes
            if sort_by == "alpha":
                sorted_entities = sorted(entity_data.keys())
            elif sort_by == "contradictions":
                sorted_entities = sorted(
                    entity_data.keys(),
                    key=lambda e: entity_data[e]["contradiction_count"],
                    reverse=True,
                )
            else:  # mentions (default)
                sorted_entities = sorted(
                    entity_data.keys(),
                    key=lambda e: entity_data[e]["mentions"],
                    reverse=True,
                )

            return {
                "points": points,
                "connections": connections,
                "entities": sorted_entities,
                "total_count": total_count,
            }

        except Exception as e:
            logger.error(f"Error getting chain data: {e}")
            return {
                "points": [],
                "connections": [],
                "entities": [],
                "total_count": 0,
            }
        finally:
            session.close()

    def get_web_data(
        self,
        min_confidence: float = 0.0,
        entity_ids: Optional[List[int]] = None,
        focused_entity_id: Optional[int] = None,
        limit: int = 100,
    ) -> Dict[str, Any]:
        """
        Build force-directed graph data for the Lie Web visualization.

        If focused_entity_id is set, returns only contradictions involving that entity
        plus one hop of connections.

        Returns:
            {
                "nodes": List of contradiction nodes,
                "edges": List of edges connecting nodes that share an entity,
                "entities": List of unique entities for legend,
            }
        """
        session = self.Session()
        try:
            # Build base query
            query = session.query(Contradiction).filter(
                Contradiction.confidence >= min_confidence
            )

            # Filter by entity if specified
            if entity_ids:
                query = query.filter(Contradiction.entity_id.in_(entity_ids))

            # Get contradictions
            contradictions = (
                query.order_by(desc(Contradiction.confidence)).limit(limit).all()
            )

            if not contradictions:
                return {"nodes": [], "edges": [], "entities": []}

            # Build entity info lookup
            entity_lookup = {}
            entity_colors = {}
            for c in contradictions:
                if c.entity_id and c.entity_id not in entity_lookup:
                    entity = (
                        session.query(CanonicalEntity)
                        .filter(CanonicalEntity.id == c.entity_id)
                        .first()
                    )
                    if entity:
                        entity_lookup[c.entity_id] = entity.canonical_name
                        entity_colors[c.entity_id] = _generate_entity_color(
                            entity.canonical_name
                        )

            # Build nodes - one per contradiction
            nodes = []
            # Track which entities each contradiction involves
            contradiction_entities: Dict[int, List[int]] = {}

            for c in contradictions:
                # Collect entity IDs mentioned (primary entity only for now)
                # Could be extended to extract entities from evidence documents
                connected_entity_ids = []
                if c.entity_id:
                    connected_entity_ids.append(c.entity_id)

                # Store for edge building
                contradiction_entities[c.id] = connected_entity_ids

                # Get entity name
                entity_name = entity_lookup.get(c.entity_id, "Unknown")

                nodes.append(
                    {
                        "id": f"contra_{c.id}",
                        "contradiction_id": c.id,
                        "description": c.description[:200]
                        if c.description
                        else "No description",
                        "entity_name": entity_name,
                        "entity_id": c.entity_id,
                        "severity": c.severity or "Medium",
                        "confidence": c.confidence or 0.5,
                        "category": c.category or "factual",
                        "status": c.status or "Open",
                        "connected_entity_ids": connected_entity_ids,
                    }
                )

            # Build edges - connect contradictions that share an entity
            edges = []
            for i, n1 in enumerate(nodes):
                for j, n2 in enumerate(nodes):
                    if i >= j:  # Skip self and duplicates
                        continue
                    # Check if they share an entity
                    shared = set(n1["connected_entity_ids"]) & set(
                        n2["connected_entity_ids"]
                    )
                    if shared:
                        # Use average confidence for edge strength
                        strength = (n1["confidence"] + n2["confidence"]) / 2
                        edges.append(
                            {
                                "from": n1["id"],
                                "to": n2["id"],
                                "shared_entity_id": list(shared)[0],  # Primary shared
                                "strength": strength,
                            }
                        )

            # If focused on an entity, filter to relevant nodes + 1 hop
            if focused_entity_id:
                # Find directly involved nodes
                direct_nodes = {
                    n["id"]
                    for n in nodes
                    if focused_entity_id in n["connected_entity_ids"]
                }
                # Find 1-hop connected nodes
                one_hop = set()
                for edge in edges:
                    if edge["from"] in direct_nodes:
                        one_hop.add(edge["to"])
                    if edge["to"] in direct_nodes:
                        one_hop.add(edge["from"])
                # Keep direct + 1-hop
                keep_nodes = direct_nodes | one_hop
                nodes = [n for n in nodes if n["id"] in keep_nodes]
                edges = [
                    e
                    for e in edges
                    if e["from"] in keep_nodes and e["to"] in keep_nodes
                ]

            # Build entity list for legend
            unique_entity_ids = set()
            for n in nodes:
                if n["entity_id"]:
                    unique_entity_ids.add(n["entity_id"])

            entities = [
                {
                    "id": eid,
                    "name": entity_lookup.get(eid, "Unknown"),
                    "color": entity_colors.get(eid, "#9ca3af"),
                }
                for eid in unique_entity_ids
            ]

            return {
                "nodes": nodes,
                "edges": edges,
                "entities": entities,
            }

        except Exception as e:
            logger.error(f"Error getting web data: {e}")
            import traceback

            traceback.print_exc()
            return {"nodes": [], "edges": [], "entities": []}
        finally:
            session.close()

    def get_available_entities_for_chain(self) -> List[Dict]:
        """Get entities that have contradictions (for filter UI)."""
        session = self.Session()
        try:
            # Get entity IDs that have contradictions
            contradiction_entity_ids = (
                session.query(Contradiction.entity_id)
                .filter(Contradiction.entity_id.isnot(None))
                .distinct()
                .all()
            )
            entity_ids = [e[0] for e in contradiction_entity_ids]

            if not entity_ids:
                return []

            entities = (
                session.query(CanonicalEntity)
                .filter(CanonicalEntity.id.in_(entity_ids))
                .order_by(desc(CanonicalEntity.total_mentions))
                .all()
            )

            return [
                {
                    "id": e.id,
                    "name": e.canonical_name,
                    "label": e.label,
                    "mentions": e.total_mentions,
                }
                for e in entities
            ]
        finally:
            session.close()


# Singleton
_service_instance = None


def get_chain_service() -> ChainService:
    global _service_instance
    if _service_instance is None:
        _service_instance = ChainService()
    return _service_instance
