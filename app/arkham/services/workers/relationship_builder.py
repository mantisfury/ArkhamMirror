# Add project root to path for central config
from pathlib import Path
import sys

project_root = Path(__file__).resolve()
while project_root.name != "ArkhamMirror" and project_root.parent != project_root:
    project_root = project_root.parent
sys.path.insert(0, str(project_root))

"""
Batch Relationship Builder

This script retroactively creates EntityRelationship records for existing
documents that were ingested before the co-occurrence relationship feature
was implemented.

Run with: python -m arkham.services.workers.relationship_builder
"""

from config import DATABASE_URL
import logging
from itertools import combinations
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from arkham.services.db.models import (
    Document,
    Entity,
    CanonicalEntity,
    Chunk,
    EntityRelationship,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)


def build_relationships_for_document(doc_id: int) -> int:
    """
    Build co-occurrence relationships for all entities in a document.

    This uses document-level co-occurrence (entities appearing in the same document).
    For more granular relationships, we'd need chunk-level tracking.

    Returns the number of relationships created.
    """
    session = Session()
    relationships_created = 0

    try:
        # Get all canonical entity IDs mentioned in this document
        entities = (
            session.query(Entity)
            .filter(Entity.doc_id == doc_id)
            .filter(Entity.canonical_entity_id.isnot(None))
            .all()
        )

        # Collect unique canonical entity IDs
        canonical_ids = set(e.canonical_entity_id for e in entities)

        if len(canonical_ids) < 2:
            logger.debug(
                f"Document {doc_id}: Only {len(canonical_ids)} canonical entities, skipping"
            )
            return 0

        # Create pairwise relationships
        for entity1_id, entity2_id in combinations(sorted(canonical_ids), 2):
            # Check if relationship already exists
            existing = (
                session.query(EntityRelationship)
                .filter(
                    (
                        (EntityRelationship.entity1_id == entity1_id)
                        & (EntityRelationship.entity2_id == entity2_id)
                    )
                    | (
                        (EntityRelationship.entity1_id == entity2_id)
                        & (EntityRelationship.entity2_id == entity1_id)
                    )
                )
                .first()
            )

            if existing:
                # Update existing relationship
                existing.co_occurrence_count += 1
                existing.strength = min(existing.strength + 0.1, 10.0)
            else:
                # Create new relationship
                new_rel = EntityRelationship(
                    entity1_id=entity1_id,
                    entity2_id=entity2_id,
                    relationship_type="co-occurrence",
                    strength=1.0,
                    co_occurrence_count=1,
                    doc_id=doc_id,
                )
                session.add(new_rel)
                relationships_created += 1

        session.commit()
        logger.info(
            f"Document {doc_id}: Created {relationships_created} new relationships from {len(canonical_ids)} entities"
        )
        return relationships_created

    except Exception as e:
        logger.error(f"Failed to build relationships for document {doc_id}: {e}")
        session.rollback()
        return 0
    finally:
        session.close()


def build_all_relationships() -> dict:
    """
    Build co-occurrence relationships for all completed documents.

    Returns a summary of the operation.
    """
    session = Session()

    try:
        # Get all completed documents
        documents = session.query(Document).filter(Document.status == "complete").all()

        total_docs = len(documents)
        total_relationships = 0
        docs_with_relationships = 0

        logger.info(f"Processing {total_docs} completed documents...")

        for i, doc in enumerate(documents, 1):
            relationships = build_relationships_for_document(doc.id)
            if relationships > 0:
                total_relationships += relationships
                docs_with_relationships += 1

            if i % 10 == 0:
                logger.info(f"Progress: {i}/{total_docs} documents processed")

        summary = {
            "total_documents": total_docs,
            "documents_with_new_relationships": docs_with_relationships,
            "total_relationships_created": total_relationships,
        }

        logger.info(f"Completed! Summary: {summary}")
        return summary

    except Exception as e:
        logger.error(f"Failed to build relationships: {e}")
        return {"error": str(e)}
    finally:
        session.close()


def get_relationship_stats() -> dict:
    """
    Get statistics about existing entity relationships.
    """
    session = Session()

    try:
        total_relationships = session.query(EntityRelationship).count()
        total_canonicals = session.query(CanonicalEntity).count()

        # Get entities with relationships
        entities_with_rels = (
            session.query(EntityRelationship.entity1_id).distinct().count()
        )

        return {
            "total_relationships": total_relationships,
            "total_canonical_entities": total_canonicals,
            "entities_with_relationships": entities_with_rels,
            "coverage": f"{entities_with_rels}/{total_canonicals}"
            if total_canonicals > 0
            else "N/A",
        }
    finally:
        session.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Build entity co-occurrence relationships"
    )
    parser.add_argument(
        "--stats", action="store_true", help="Show relationship statistics only"
    )
    parser.add_argument(
        "--doc-id", type=int, help="Build relationships for a specific document"
    )
    args = parser.parse_args()

    if args.stats:
        stats = get_relationship_stats()
        print("\n=== Entity Relationship Statistics ===")
        for key, value in stats.items():
            print(f"  {key}: {value}")
        print()
    elif args.doc_id:
        count = build_relationships_for_document(args.doc_id)
        print(f"\nCreated {count} relationships for document {args.doc_id}")
    else:
        print("\n=== Building relationships for all documents ===")
        print("Before:")
        for key, value in get_relationship_stats().items():
            print(f"  {key}: {value}")
        print()

        summary = build_all_relationships()

        print("\nAfter:")
        for key, value in get_relationship_stats().items():
            print(f"  {key}: {value}")
        print(f"\nSummary: {summary}")
