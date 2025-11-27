"""
Unit tests for Entity Resolution Service
"""

import unittest
from backend.entity_resolution import EntityResolver


class TestEntityResolver(unittest.TestCase):
    def setUp(self):
        self.resolver = EntityResolver()

    def test_normalize_text(self):
        """Test text normalization"""
        self.assertEqual(
            self.resolver.normalize_text("John Doe"),
            "john doe"
        )
        self.assertEqual(
            self.resolver.normalize_text("  J. Doe  "),
            "j doe"
        )
        self.assertEqual(
            self.resolver.normalize_text("Microsoft Corp."),
            "microsoft corp"
        )

    def test_extract_initials(self):
        """Test initial extraction"""
        self.assertEqual(
            self.resolver.extract_initials("John Doe"),
            "jd"
        )
        self.assertEqual(
            self.resolver.extract_initials("J. Doe"),
            "jd"
        )
        self.assertEqual(
            self.resolver.extract_initials("John Q. Public"),
            "jqp"
        )

    def test_exact_match(self):
        """Test exact matching (case-insensitive)"""
        self.assertTrue(
            self.resolver.is_match("John Doe", "john doe", "PERSON")
        )
        self.assertTrue(
            self.resolver.is_match("Microsoft", "MICROSOFT", "ORG")
        )

    def test_fuzzy_match_person(self):
        """Test fuzzy matching for person names"""
        # Should match: same last name, matching first initial
        self.assertTrue(
            self.resolver.is_match("John Doe", "J. Doe", "PERSON")
        )
        self.assertTrue(
            self.resolver.is_match("Jane Smith", "J. Smith", "PERSON")
        )

        # Should NOT match: different last names
        self.assertFalse(
            self.resolver.is_match("John Doe", "John Smith", "PERSON")
        )

        # Should NOT match: different first initial
        self.assertFalse(
            self.resolver.is_match("John Doe", "Jane Doe", "PERSON")
        )

    def test_fuzzy_match_org(self):
        """Test fuzzy matching for organizations"""
        # Substring matching for ORG
        self.assertTrue(
            self.resolver.is_match("Microsoft", "Microsoft Corporation", "ORG")
        )
        self.assertTrue(
            self.resolver.is_match("IBM", "IBM Corp", "ORG")
        )

        # Should require minimum length (avoid short acronyms)
        # "US" should not match "US Bank" automatically
        self.assertFalse(
            self.resolver.is_match("US", "US Bank", "ORG")
        )

    def test_fuzzy_match_gpe(self):
        """Test fuzzy matching for locations (stricter)"""
        # GPE should be very strict
        self.assertTrue(
            self.resolver.is_match("New York", "new york", "GPE")
        )

        # Small typos should still match
        self.assertTrue(
            self.resolver.is_match("New York", "New Yotk", "GPE", threshold=0.85)
        )

    def test_find_canonical_match(self):
        """Test finding canonical entity from list"""
        existing = [
            {"id": 1, "canonical_name": "John Doe", "aliases": '["J. Doe"]'},
            {"id": 2, "canonical_name": "Microsoft Corporation", "aliases": '["Microsoft", "MSFT"]'},
        ]

        # Should match by canonical name
        match_id = self.resolver.find_canonical_match("john doe", "PERSON", existing)
        self.assertEqual(match_id, 1)

        # Should match by alias
        match_id = self.resolver.find_canonical_match("J. Doe", "PERSON", existing)
        self.assertEqual(match_id, 1)

        # Should match by alias for ORG
        match_id = self.resolver.find_canonical_match("Microsoft", "ORG", existing)
        self.assertEqual(match_id, 2)

        # Should not match unrelated entity
        match_id = self.resolver.find_canonical_match("Jane Smith", "PERSON", existing)
        self.assertIsNone(match_id)

    def test_select_best_name(self):
        """Test selecting best canonical name"""
        names = ["J. Doe", "John Doe", "John D."]
        best = self.resolver.select_best_name(names)
        self.assertEqual(best, "John Doe")  # Longest, least punctuation

        names = ["Microsoft", "Microsoft Corp.", "Microsoft Corporation"]
        best = self.resolver.select_best_name(names)
        self.assertEqual(best, "Microsoft Corporation")

    def test_merge_aliases(self):
        """Test alias merging"""
        # Start with empty
        result = self.resolver.merge_aliases("", "John Doe")
        self.assertIn("John Doe", result)

        # Add to existing
        result = self.resolver.merge_aliases('["J. Doe"]', "John D.")
        self.assertIn("J. Doe", result)
        self.assertIn("John D.", result)

        # Don't duplicate
        result = self.resolver.merge_aliases('["J. Doe"]', "J. Doe")
        self.assertEqual(result.count("J. Doe"), 1)


if __name__ == "__main__":
    unittest.main()
