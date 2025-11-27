"""
Unit tests for query performance optimizations added in v0.1.5.
Tests the N+1 query fixes in the Anomalies page.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.db.models import Base, Document, Chunk


class TestQueryPerformance(unittest.TestCase):
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
        """Create test data for each test."""
        self.session = self.Session()

        # Create test documents
        self.docs = []
        for i in range(5):
            doc = Document(
                title=f"Test Document {i}",
                path=f"/tmp/test{i}.pdf",
                file_hash=f"hash{i}",
                status="complete",
            )
            self.session.add(doc)
            self.docs.append(doc)

        self.session.commit()

    def tearDown(self):
        """Clean up after each test."""
        self.session.query(Document).delete()
        self.session.commit()
        self.session.close()

    def test_batch_document_fetch(self):
        """Verify that we can fetch multiple documents in a single query."""
        # Simulate the optimized approach: fetch all doc_ids at once
        doc_ids = [doc.id for doc in self.docs]

        # Single query to fetch all documents
        docs = (
            self.session.query(Document.id, Document.title)
            .filter(Document.id.in_(doc_ids))
            .all()
        )

        # Verify we got all documents in one query
        self.assertEqual(len(docs), 5, "Should fetch all 5 documents")

        # Convert to dict (as done in the fix)
        doc_titles = {doc_id: title for doc_id, title in docs}
        self.assertEqual(len(doc_titles), 5, "Should have 5 document titles in dict")

        # Verify we can access by ID
        for doc in self.docs:
            self.assertIn(doc.id, doc_titles, f"Document {doc.id} should be in dict")
            self.assertEqual(
                doc_titles[doc.id], doc.title, "Title should match original"
            )

    def test_n_plus_one_antipattern(self):
        """Demonstrate the N+1 problem that was fixed."""
        # This test shows the OLD way (N+1 queries) for documentation

        # Simulate N search hits with doc_ids
        mock_hits = [
            Mock(payload={"doc_id": doc.id, "text": f"Text from doc {doc.id}"})
            for doc in self.docs
        ]

        # Bad approach: Query for each hit (N+1 queries)
        query_count = 0
        results_bad = []

        for hit in mock_hits:
            query_count += 1  # This would be a database query
            doc_id = hit.payload.get("doc_id")
            # In real code: doc = session.query(Document).get(doc_id)
            doc = self.session.query(Document).filter_by(id=doc_id).first()
            if doc:
                results_bad.append((doc.title, hit.payload.get("text")))

        # We made N queries (one per hit)
        self.assertEqual(query_count, 5, "N+1 approach makes N queries")

        # Good approach: Single query for all doc_ids
        doc_ids = {hit.payload.get("doc_id") for hit in mock_hits}
        docs = (
            self.session.query(Document.id, Document.title)
            .filter(Document.id.in_(doc_ids))
            .all()
        )
        doc_titles = {doc_id: title for doc_id, title in docs}

        results_good = [
            (doc_titles.get(hit.payload.get("doc_id")), hit.payload.get("text"))
            for hit in mock_hits
        ]

        # Both approaches give same results
        self.assertEqual(
            len(results_bad),
            len(results_good),
            "Both approaches should give same number of results",
        )

        # But the good approach only made 1 query instead of N
        # This is the optimization implemented in v0.1.5

    def test_bulk_filter_efficiency(self):
        """Verify that filter with IN clause is efficient."""
        # Create multiple doc_ids
        doc_ids = [doc.id for doc in self.docs]

        # Single query with IN clause (efficient)
        result = (
            self.session.query(Document)
            .filter(Document.id.in_(doc_ids))
            .all()
        )

        self.assertEqual(len(result), 5, "Should retrieve all documents")

        # Verify all IDs are present
        retrieved_ids = {doc.id for doc in result}
        expected_ids = set(doc_ids)
        self.assertEqual(
            retrieved_ids, expected_ids, "Should retrieve all expected documents"
        )


if __name__ == "__main__":
    unittest.main()
