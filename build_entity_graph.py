"""
Build Entity Relationship Graph

Analyzes entity co-occurrences within documents and chunks to build
a relationship graph showing which entities appear together.

Usage:
    python build_entity_graph.py
"""

import os
import logging
from collections import defaultdict
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

from backend.db.models import Entity, CanonicalEntity, EntityRelationship, Chunk, Document

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)


def build_relationships():
    """
    Build entity relationships based on co-occurrence in chunks.
    Two entities are related if they appear in the same chunk.
    """
    session = Session()

    try:
        logger.info("Building entity relationship graph...")

        # Clear existing relationships (idempotent operation)
        session.query(EntityRelationship).delete()
        session.commit()
        logger.info("Cleared existing relationships")

        # Get all chunks
        chunks = session.query(Chunk).all()
        logger.info(f"Analyzing {len(chunks)} chunks for entity co-occurrences...")

        # Track co-occurrences: (entity1_id, entity2_id, doc_id) -> count
        co_occurrences = defaultdict(int)

        for i, chunk in enumerate(chunks):
            if i % 100 == 0:
                logger.info(f"Processed {i}/{len(chunks)} chunks")

            # Get all entities mentioned in this chunk's document
            # Note: We need to figure out which entities appear in this specific chunk
            # For now, we'll use a simple heuristic: check if entity text appears in chunk

            doc_entities = (
                session.query(Entity)
                .filter_by(doc_id=chunk.doc_id)
                .filter(Entity.canonical_entity_id.isnot(None))
                .all()
            )

            # Filter entities that actually appear in this chunk
            chunk_entities = []
            for entity in doc_entities:
                if entity.text.lower() in chunk.text.lower():
                    chunk_entities.append(entity)

            # Create relationships for all pairs in this chunk
            for j in range(len(chunk_entities)):
                for k in range(j + 1, len(chunk_entities)):
                    e1 = chunk_entities[j]
                    e2 = chunk_entities[k]

                    # Use canonical IDs (always lower ID first for consistency)
                    id1 = min(e1.canonical_entity_id, e2.canonical_entity_id)
                    id2 = max(e1.canonical_entity_id, e2.canonical_entity_id)

                    key = (id1, id2, chunk.doc_id)
                    co_occurrences[key] += 1

        logger.info(f"Found {len(co_occurrences)} unique entity pairs")

        # Create EntityRelationship records
        for (entity1_id, entity2_id, doc_id), count in co_occurrences.items():
            relationship = EntityRelationship(
                entity1_id=entity1_id,
                entity2_id=entity2_id,
                relationship_type="co-occurrence",
                strength=float(count),
                doc_id=doc_id,
            )
            session.add(relationship)

        session.commit()
        logger.info(f"✓ Created {len(co_occurrences)} entity relationships")

        # Print some stats
        canonical_count = session.query(CanonicalEntity).count()
        logger.info(f"Total canonical entities: {canonical_count}")

        # Find most connected entities
        from sqlalchemy import func

        top_entities = (
            session.query(
                CanonicalEntity.canonical_name,
                func.count(EntityRelationship.id).label("connections"),
            )
            .join(
                EntityRelationship,
                (CanonicalEntity.id == EntityRelationship.entity1_id)
                | (CanonicalEntity.id == EntityRelationship.entity2_id),
            )
            .group_by(CanonicalEntity.id)
            .order_by(func.count(EntityRelationship.id).desc())
            .limit(10)
            .all()
        )

        logger.info("\nTop 10 most connected entities:")
        for name, connections in top_entities:
            logger.info(f"  {name}: {connections} connections")

    except Exception as e:
        logger.error(f"Failed to build relationships: {e}")
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    build_relationships()
