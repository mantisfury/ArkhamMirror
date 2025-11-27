import unittest
from unittest.mock import MagicMock
import networkx as nx
from backend.graph_utils import (
    build_networkx_graph,
    detect_communities,
    get_shortest_path,
)
from backend.db.models import CanonicalEntity, EntityRelationship


class TestGraphUtils(unittest.TestCase):
    def setUp(self):
        self.session = MagicMock()

        # Mock Entities
        self.e1 = CanonicalEntity(
            id=1, canonical_name="Alice", label="PERSON", total_mentions=10
        )
        self.e2 = CanonicalEntity(
            id=2, canonical_name="Bob", label="PERSON", total_mentions=5
        )
        self.e3 = CanonicalEntity(
            id=3, canonical_name="Corp", label="ORG", total_mentions=20
        )

        self.session.query(CanonicalEntity).all.return_value = [
            self.e1,
            self.e2,
            self.e3,
        ]

        # Mock Relationships
        # Alice - Bob (Strength 2)
        # Bob - Corp (Strength 5)
        r1 = MagicMock()
        r1.entity1_id = 1
        r1.entity2_id = 2
        r1.total_strength = 2

        r2 = MagicMock()
        r2.entity1_id = 2
        r2.entity2_id = 3
        r2.total_strength = 5

        # Mock the group_by query result
        self.session.query.return_value.group_by.return_value.having.return_value.all.return_value = [
            r1,
            r2,
        ]

    def test_build_graph(self):
        G = build_networkx_graph(self.session)

        self.assertEqual(len(G.nodes), 3)
        self.assertEqual(len(G.edges), 2)

        self.assertTrue(G.has_edge(1, 2))
        self.assertTrue(G.has_edge(2, 3))
        self.assertFalse(G.has_edge(1, 3))

        self.assertEqual(G[1][2]["weight"], 2)
        self.assertEqual(G[2][3]["weight"], 5)

    def test_shortest_path(self):
        G = build_networkx_graph(self.session)
        path = get_shortest_path(G, 1, 3)
        self.assertEqual(path, [1, 2, 3])

        path_none = get_shortest_path(G, 1, 99)
        self.assertIsNone(path_none)

    def test_communities(self):
        G = build_networkx_graph(self.session)
        # With such a small graph, communities might be trivial, but let's ensure it runs
        partition = detect_communities(G)
        self.assertIsInstance(partition, dict)
        self.assertEqual(len(partition), 3)  # Should have entry for each node


if __name__ == "__main__":
    unittest.main()
