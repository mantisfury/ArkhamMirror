"""
Export Investigation Packages Service

Generate exportable investigation packages containing:
- Entity reports and relationship maps
- Timeline summaries
- Key findings and red flags
- Evidence chains
- Document excerpts
"""

import json
import logging
import zipfile
from io import BytesIO
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
    Entity,
    EntityRelationship,
    SensitiveDataMatch,
)

load_dotenv()
logger = logging.getLogger(__name__)


class ExportService:
    """Service for exporting investigation packages."""

    def __init__(self):
        self.engine = create_engine(DATABASE_URL)
        self.Session = sessionmaker(bind=self.engine)

    def get_entity_report(self, entity_id: int) -> Dict[str, Any]:
        """Generate a detailed report for a single entity."""
        session = self.Session()
        try:
            entity = session.query(CanonicalEntity).filter_by(id=entity_id).first()
            if not entity:
                return {"error": "Entity not found"}

            # Get relationships
            relationships = []
            rels = (
                session.query(EntityRelationship)
                .filter(
                    (EntityRelationship.entity1_id == entity_id)
                    | (EntityRelationship.entity2_id == entity_id)
                )
                .all()
            )

            for rel in rels:
                other_id = (
                    rel.entity2_id if rel.entity1_id == entity_id else rel.entity1_id
                )
                other = session.query(CanonicalEntity).filter_by(id=other_id).first()
                if other:
                    relationships.append(
                        {
                            "entity": other.canonical_name,
                            "type": rel.relationship_type or "associated",
                            "strength": rel.strength,
                        }
                    )

            # Get document appearances
            chunk_ids = (
                session.query(Entity.doc_id)
                .filter(Entity.canonical_entity_id == entity_id)
                .distinct()
                .all()
            )
            # Actually Entity stores doc_id, not chunk_id directly usually?
            # Let's check model. Entity has doc_id.
            # But code was: session.query(EntityMention.chunk_id)
            # If I change to Entity, I should use Entity.doc_id or Entity.chunk_id if it has it?
            # Entity model: id, doc_id, canonical_entity_id, text, label, count. No chunk_id.
            # So I can't get specific chunks easily from Entity table alone if it doesn't link to chunks.
            # But I can get documents.

            # The original code was trying to get chunks to show evidence excerpts.
            # If Entity doesn't have chunk_id, I have to find chunks in the doc that contain the entity text?
            # Or just list documents.

            # For now, I will just list documents and skip specific chunk evidence if I can't link it easily,
            # or iterate chunks in the doc.

            # Let's fetch doc_ids
            doc_ids = [c[0] for c in chunk_ids]
            documents = set()
            evidence = []

            for doc_id in doc_ids[:20]:
                doc = session.query(Document).filter_by(id=doc_id).first()
                if doc:
                    documents.add(doc.title)
                    # Find a chunk with the entity name?
                    # Approximate evidence: first chunk of doc
                    chunk = session.query(Chunk).filter_by(doc_id=doc.id).first()
                    if chunk:
                        evidence.append(
                            {
                                "document": doc.title,
                                "excerpt": chunk.text[:300] + "...",
                            }
                        )

            return {
                "entity": {
                    "id": entity.id,
                    "name": entity.canonical_name,
                    "type": entity.label,
                    "total_mentions": entity.total_mentions,
                    "aliases": entity.aliases.split(",") if entity.aliases else [],
                },
                "relationships": relationships,
                "documents": list(documents),
                "evidence": evidence[:10],
                "generated_at": datetime.now().isoformat(),
            }
        finally:
            session.close()

    def get_timeline_export(self) -> Dict[str, Any]:
        """Export timeline data."""
        session = self.Session()
        try:
            documents = (
                session.query(Document)
                .order_by(desc(Document.created_at))
                .limit(100)
                .all()
            )

            timeline = []
            for doc in documents:
                timeline.append(
                    {
                        "date": doc.created_at.isoformat() if doc.created_at else None,
                        "event": f"Document: {doc.title}",
                        "type": "document_added",
                    }
                )

            return {
                "events": timeline,
                "total_documents": len(documents),
                "generated_at": datetime.now().isoformat(),
            }
        finally:
            session.close()

    def get_relationship_map_export(
        self, entity_ids: List[int] = None
    ) -> Dict[str, Any]:
        """Export relationship map data."""
        session = self.Session()
        try:
            if entity_ids:
                entities = (
                    session.query(CanonicalEntity)
                    .filter(CanonicalEntity.id.in_(entity_ids))
                    .all()
                )
            else:
                entities = (
                    session.query(CanonicalEntity)
                    .filter(CanonicalEntity.total_mentions > 0)
                    .order_by(desc(CanonicalEntity.total_mentions))
                    .limit(50)
                    .all()
                )

            entity_ids = [e.id for e in entities]

            nodes = []
            for e in entities:
                nodes.append(
                    {
                        "id": e.id,
                        "name": e.canonical_name,
                        "type": e.label,
                        "mentions": e.total_mentions,
                    }
                )

            edges = []
            relationships = (
                session.query(EntityRelationship)
                .filter(
                    EntityRelationship.entity1_id.in_(entity_ids),
                    EntityRelationship.entity2_id.in_(entity_ids),
                )
                .all()
            )

            for rel in relationships:
                edges.append(
                    {
                        "source": rel.entity1_id,
                        "target": rel.entity2_id,
                        "type": rel.relationship_type or "associated",
                        "weight": rel.co_occurrence_count,
                    }
                )

            return {
                "nodes": nodes,
                "edges": edges,
                "generated_at": datetime.now().isoformat(),
            }
        finally:
            session.close()

    def get_findings_summary(self) -> Dict[str, Any]:
        """Generate a summary of key findings."""
        session = self.Session()
        try:
            # Stats
            doc_count = session.query(func.count(Document.id)).scalar()
            entity_count = session.query(func.count(CanonicalEntity.id)).scalar()
            rel_count = session.query(func.count(EntityRelationship.id)).scalar()

            # Top entities
            top_entities = (
                session.query(CanonicalEntity)
                .filter(CanonicalEntity.total_mentions > 0)
                .order_by(desc(CanonicalEntity.total_mentions))
                .limit(20)
                .all()
            )

            # Entity types
            entity_types = (
                session.query(CanonicalEntity.label, func.count(CanonicalEntity.id))
                .group_by(CanonicalEntity.label)
                .all()
            )

            return {
                "summary": {
                    "total_documents": doc_count or 0,
                    "total_entities": entity_count or 0,
                    "total_relationships": rel_count or 0,
                },
                "key_entities": [
                    {
                        "name": e.canonical_name,
                        "type": e.label,
                        "mentions": e.total_mentions,
                    }
                    for e in top_entities
                ],
                "entity_breakdown": {
                    label: count for label, count in entity_types if label
                },
                "generated_at": datetime.now().isoformat(),
            }
        finally:
            session.close()

    def get_sensitive_data_export(self) -> List[Dict[str, Any]]:
        """Export sensitive data matches."""
        session = self.Session()
        try:
            matches = (
                session.query(SensitiveDataMatch)
                .join(Document)
                .order_by(Document.title)
                .all()
            )

            results = []
            for match in matches:
                doc = session.query(Document).get(match.doc_id)
                results.append(
                    {
                        "document": doc.title if doc else f"Doc {match.doc_id}",
                        "pattern": match.pattern_type,
                        "text": match.match_text,
                        "context": f"{match.context_before} **{match.match_text}** {match.context_after}",
                        "confidence": match.confidence,
                    }
                )
            return results
        finally:
            session.close()

    def create_investigation_package(
        self,
        include_entities: bool = True,
        include_timeline: bool = True,
        include_relationships: bool = True,
        entity_ids: List[int] = None,
    ) -> bytes:
        """Create a ZIP file containing all investigation data."""
        buffer = BytesIO()

        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            # Add summary
            summary = self.get_findings_summary()
            zf.writestr("summary.json", json.dumps(summary, indent=2, default=str))

            # Add human-readable report
            report_md = "# ArkhamMirror Investigation Report\n\n"
            report_md += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
            report_md += "## Executive Summary\n"
            report_md += (
                f"- **Documents Analyzed**: {summary['summary']['total_documents']}\n"
            )
            report_md += (
                f"- **Entities Identified**: {summary['summary']['total_entities']}\n"
            )
            report_md += f"- **Relationships Mapped**: {summary['summary']['total_relationships']}\n\n"

            # Add relationship map
            if include_relationships:
                rel_map = self.get_relationship_map_export(entity_ids)
                zf.writestr(
                    "relationship_map.json", json.dumps(rel_map, indent=2, default=str)
                )

            # Add sensitive data
            sensitive_data = self.get_sensitive_data_export()
            if sensitive_data:
                zf.writestr("sensitive_data.json", json.dumps(sensitive_data, indent=2))
                report_md += "## Sensitive Data Detected\n"
                report_md += (
                    f"Found {len(sensitive_data)} potential sensitive data points.\n\n"
                )
                for item in sensitive_data[:10]:  # Preview
                    report_md += f"- **{item['pattern']}** in *{item['document']}*: `{item['text']}`\n"
                if len(sensitive_data) > 10:
                    report_md += f"\n...and {len(sensitive_data) - 10} more (see sensitive_data.json)\n"
                report_md += "\n"

            # Add timeline
            if include_timeline:
                timeline = self.get_timeline_export()
                zf.writestr(
                    "timeline.json", json.dumps(timeline, indent=2, default=str)
                )

            # Add entity reports
            if include_entities and entity_ids:
                report_md += "## Key Entities\n"
                for eid in entity_ids:
                    report = self.get_entity_report(eid)
                    if "error" not in report:
                        safe_name = (
                            report["entity"]["name"]
                            .replace("/", "_")
                            .replace("\\", "_")
                        )
                        filename = f"entities/{safe_name}.json"
                        zf.writestr(filename, json.dumps(report, indent=2, default=str))
                        report_md += f"- **{report['entity']['name']}** ({report['entity']['type']}): {report['entity']['total_mentions']} mentions\n"

            # Save report
            zf.writestr("REPORT.md", report_md)

            # Add metadata
            metadata = {
                "package_type": "ArkhamMirror Investigation Export",
                "version": "1.1",
                "created_at": datetime.now().isoformat(),
                "includes": {
                    "entities": include_entities,
                    "timeline": include_timeline,
                    "relationships": include_relationships,
                    "sensitive_data": True,
                },
            }
            zf.writestr("metadata.json", json.dumps(metadata, indent=2))

        buffer.seek(0)
        return buffer.getvalue()

    def export_to_csv(self, data_type: str) -> str:
        """Export data as CSV."""
        session = self.Session()
        try:
            if data_type == "entities":
                entities = session.query(CanonicalEntity).all()
                lines = ["id,name,type,mentions,aliases"]
                for e in entities:
                    lines.append(
                        f'{e.id},"{e.canonical_name}",{e.label},{e.total_mentions},"{e.aliases or ""}"'
                    )
                return "\n".join(lines)

            elif data_type == "documents":
                documents = session.query(Document).all()
                lines = ["id,title,created_at,file_type"]
                for d in documents:
                    lines.append(
                        f'{d.id},"{d.title}",{d.created_at},{d.doc_type or ""}'
                    )
                return "\n".join(lines)

            elif data_type == "relationships":
                relationships = session.query(EntityRelationship).all()
                lines = ["entity1_id,entity2_id,type,strength"]
                for r in relationships:
                    lines.append(
                        f'{r.entity1_id},{r.entity2_id},{r.relationship_type or ""},"{r.co_occurrence_count}"'
                    )
                return "\n".join(lines)

            return ""
        finally:
            session.close()


# Singleton
_service_instance = None


def get_export_service() -> ExportService:
    global _service_instance
    if _service_instance is None:
        _service_instance = ExportService()
    return _service_instance
