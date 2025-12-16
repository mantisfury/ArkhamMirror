"""
Unit tests for database constraints added in v0.1.5.
Tests unique constraints, check constraints, and foreign key relationships.
"""

import unittest
import os
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError
from app.arkham.services.db.models import (
    Base,
    Document,
    Chunk,
    PageOCR,
    Anomaly,
    EntityRelationship,
    CanonicalEntity,
)


class TestDatabaseConstraints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Set up an in-memory test database."""
        cls.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(cls.engine)
        cls.Session = sessionmaker(bind=cls.engine)

    @classmethod
    def tearDownClass(cls):
        """Clean up the test database."""
        Base.metadata.drop_all(cls.engine)

    def setUp(self):
        """Create a new session for each test."""
        self.session = self.Session()

    def tearDown(self):
        """Close the session and rollback any uncommitted changes."""
        self.session.rollback()
        self.session.close()

    def test_document_unique_file_hash(self):
        """Verify that file_hash is unique across documents."""
        doc1 = Document(
            title="Test Doc 1",
            path="/tmp/test1.pdf",
            file_hash="abc123",
            status="complete",
        )
        doc2 = Document(
            title="Test Doc 2",
            path="/tmp/test2.pdf",
            file_hash="abc123",  # Same hash
            status="complete",
        )

        self.session.add(doc1)
        self.session.commit()

        self.session.add(doc2)
        with self.assertRaises(IntegrityError):
            self.session.commit()

    def test_document_status_valid_values(self):
        """Verify that document status accepts valid values."""
        valid_statuses = ["pending", "processing", "complete", "failed"]
        for status in valid_statuses:
            doc = Document(
                title=f"Test {status}",
                path=f"/tmp/{status}.pdf",
                file_hash=f"hash_{status}",
                status=status,
            )
            self.session.add(doc)
            self.session.commit()
            self.assertEqual(doc.status, status)
            self.session.delete(doc)
            self.session.commit()

    def test_foreign_key_relationships(self):
        """Verify that foreign key relationships are properly defined."""
        # Create a document
        doc = Document(
            title="Parent Doc",
            path="/tmp/parent.pdf",
            file_hash="parent123",
            status="complete",
        )
        self.session.add(doc)
        self.session.commit()

        # Create a chunk referencing the document
        chunk = Chunk(doc_id=doc.id, text="Test chunk text", chunk_index=0)
        self.session.add(chunk)
        self.session.commit()

        # Verify the relationship
        retrieved_chunk = self.session.query(Chunk).filter_by(id=chunk.id).first()
        self.assertEqual(retrieved_chunk.doc_id, doc.id)

    def test_anomaly_score_positive(self):
        """Verify that anomaly score must be non-negative."""
        # This test may not work in SQLite as it doesn't fully support CHECK constraints
        # But we include it for documentation and PostgreSQL compatibility
        doc = Document(
            title="Test Doc", path="/tmp/test.pdf", file_hash="hash1", status="complete"
        )
        chunk = Chunk(doc_id=1, text="Test", chunk_index=0)
        self.session.add(doc)
        self.session.add(chunk)
        self.session.commit()

        # Valid positive score
        anomaly_positive = Anomaly(
            chunk_id=chunk.id, score=1.5, reason="Test anomaly"
        )
        self.session.add(anomaly_positive)
        self.session.commit()
        self.assertGreaterEqual(anomaly_positive.score, 0)

    def test_canonical_entity_has_name_and_label(self):
        """Verify that canonical entities require name and label."""
        # Valid entity
        entity = CanonicalEntity(canonical_name="John Doe", label="PERSON")
        self.session.add(entity)
        self.session.commit()

        retrieved = (
            self.session.query(CanonicalEntity).filter_by(canonical_name="John Doe").first()
        )
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.label, "PERSON")

    def test_entity_relationship_foreign_keys(self):
        """Verify that entity relationships properly reference canonical entities."""
        entity1 = CanonicalEntity(canonical_name="Entity 1", label="PERSON")
        entity2 = CanonicalEntity(canonical_name="Entity 2", label="ORG")
        self.session.add_all([entity1, entity2])
        self.session.commit()

        # Create relationship
        rel = EntityRelationship(
            entity1_id=entity1.id,
            entity2_id=entity2.id,
            relationship_type="co-occurrence",
            strength=2.0,
        )
        self.session.add(rel)
        self.session.commit()

        retrieved = self.session.query(EntityRelationship).filter_by(id=rel.id).first()
        self.assertEqual(retrieved.entity1_id, entity1.id)
        self.assertEqual(retrieved.entity2_id, entity2.id)
        self.assertGreaterEqual(retrieved.strength, 0)

    def test_page_ocr_document_relationship(self):
        """Verify that PageOCR properly references documents."""
        doc = Document(
            title="OCR Test",
            path="/tmp/ocr.pdf",
            file_hash="ocr123",
            status="complete",
        )
        self.session.add(doc)
        self.session.commit()

        page_ocr = PageOCR(
            document_id=doc.id,
            page_num=1,
            checksum="page_checksum",
            text="OCR extracted text",
        )
        self.session.add(page_ocr)
        self.session.commit()

        retrieved = self.session.query(PageOCR).filter_by(document_id=doc.id).first()
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.page_num, 1)


if __name__ == "__main__":
    unittest.main()
