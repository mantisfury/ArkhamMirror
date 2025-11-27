import unittest
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import json

# Import models
from backend.db.models import (
    Base,
    Document,
    Chunk,
    Entity,
    CanonicalEntity,
    EntityRelationship,
)
from backend.entity_resolution import EntityResolver
from build_entity_graph import build_relationships

# Mock the database connection for build_entity_graph
import build_entity_graph


class TestEntityIntegration(unittest.TestCase):
    def setUp(self):
        # Use in-memory SQLite for testing
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

        # Patch the session maker in build_entity_graph to use our test DB
        build_entity_graph.Session = self.Session

        self.resolver = EntityResolver()

    def tearDown(self):
        Base.metadata.drop_all(self.engine)

    def simulate_embed_worker_resolution(self, session, doc_id, local_counts):
        """
        Simulates the entity resolution logic block from embed_worker.py
        """
        resolver = self.resolver

        for (text, label), count in local_counts.items():
            # 1. Check if entity mention already exists
            entity = (
                session.query(Entity)
                .filter_by(doc_id=doc_id, text=text, label=label)
                .first()
            )

            if entity:
                entity.count += count
            else:
                entity = Entity(doc_id=doc_id, text=text, label=label, count=count)
                session.add(entity)
                session.flush()

            # 2. Find or create canonical entity
            if not entity.canonical_entity_id:
                existing_canonicals = (
                    session.query(CanonicalEntity).filter_by(label=label).all()
                )

                canonical_dicts = [
                    {
                        "id": c.id,
                        "canonical_name": c.canonical_name,
                        "aliases": c.aliases,
                    }
                    for c in existing_canonicals
                ]

                canonical_id = resolver.find_canonical_match(
                    text, label, canonical_dicts
                )

                if canonical_id:
                    canonical = session.query(CanonicalEntity).get(canonical_id)
                    entity.canonical_entity_id = canonical_id

                    # Update canonical stats
                    canonical.total_mentions += count

                    # Update aliases
                    canonical.aliases = resolver.merge_aliases(
                        canonical.aliases or "", text
                        total_mentions=count,
                        aliases=json.dumps([text]),
                    )
                    session.add(canonical)
                    session.flush()
                    entity.canonical_entity_id = canonical.id

        session.commit()

    def test_full_entity_pipeline(self):
        session = self.Session()

        # --- Step 1: Create Documents ---
        doc1 = Document(title="Doc 1", path="/tmp/doc1.pdf", status="processing")
        doc2 = Document(title="Doc 2", path="/tmp/doc2.pdf", status="processing")
        session.add_all([doc1, doc2])
        session.commit()

        # --- Step 2: Simulate Extraction (NER) ---
        # Doc 1: "John Doe" works at "Microsoft"
        counts1 = {("John Doe", "PERSON"): 1, ("Microsoft", "ORG"): 1}

        # Doc 2: "J. Doe" works at "Microsoft Corp."
        counts2 = {("J. Doe", "PERSON"): 1, ("Microsoft Corp.", "ORG"): 1}

        # --- Step 3: Run Resolution Logic ---
        print("\nRunning resolution for Doc 1...")
        self.simulate_embed_worker_resolution(session, doc1.id, counts1)

        print("Running resolution for Doc 2...")
        self.simulate_embed_worker_resolution(session, doc2.id, counts2)

        # --- Step 4: Verify Canonical Entities ---
        canonicals = session.query(CanonicalEntity).all()
        print(f"\nCanonical Entities Found: {len(canonicals)}")
        for c in canonicals:
            print(f" - {c.canonical_name} ({c.label}): {c.aliases}")

        # Assertions
        self.assertEqual(
            len(canonicals), 2, "Should have merged into exactly 2 canonical entities"
        )

        person = session.query(CanonicalEntity).filter_by(label="PERSON").first()
        self.assertEqual(person.canonical_name, "John Doe")
        self.assertIn("J. Doe", person.aliases)

        org = session.query(CanonicalEntity).filter_by(label="ORG").first()
        # "Microsoft Corp." is longer, so it should be the canonical name if logic works
        self.assertEqual(org.canonical_name, "Microsoft Corp.")
        self.assertIn("Microsoft", org.aliases)

        # --- Step 5: Create Chunks for Relationship Building ---
        # We need chunks that contain the entity text for the co-occurrence logic to work
        chunk1 = Chunk(
            doc_id=doc1.id, text="John Doe works at Microsoft.", chunk_index=0
        )
        chunk2 = Chunk(
            doc_id=doc2.id,
            text="J. Doe is an employee of Microsoft Corp.",
            chunk_index=0,
        )
        session.add_all([chunk1, chunk2])
        session.commit()

        # --- Step 6: Run Relationship Builder ---
        print("\nBuilding relationships...")
        build_relationships()

        # --- Step 7: Verify Relationships ---
        rels = session.query(EntityRelationship).all()
        print(f"Relationships Found: {len(rels)}")
        for r in rels:
            print(f" - {r.entity1_id} <-> {r.entity2_id} (Strength: {r.strength})")

        self.assertEqual(
            len(rels), 2, "Should have 2 relationship records (one per doc)"
        )

        r1 = session.query(EntityRelationship).filter_by(doc_id=doc1.id).first()
        self.assertIsNotNone(r1)
        self.assertEqual(r1.strength, 1.0)

        r2 = session.query(EntityRelationship).filter_by(doc_id=doc2.id).first()
        self.assertIsNotNone(r2)
        self.assertEqual(r2.strength, 1.0)

        session.close()


if __name__ == "__main__":
    unittest.main()
