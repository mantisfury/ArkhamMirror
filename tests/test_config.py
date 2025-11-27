"""
Unit tests for configuration loading and access.
Tests the centralized configuration system added in v0.1.5.
"""

import unittest
import os
import tempfile
import yaml
from backend.config import get_config, load_config, CONFIG_PATH


class TestConfig(unittest.TestCase):
    def test_config_file_exists(self):
        """Verify that the config.yaml file exists."""
        self.assertTrue(os.path.exists(CONFIG_PATH), "config.yaml should exist")

    def test_load_config_returns_dict(self):
        """Verify that load_config returns a dictionary."""
        config = load_config()
        self.assertIsInstance(config, dict, "load_config should return a dict")

    def test_get_config_with_dot_notation(self):
        """Verify that get_config can access nested keys with dot notation."""
        # Test existing keys
        chunk_size = get_config("processing.chunk_size")
        self.assertIsNotNone(chunk_size, "Should retrieve processing.chunk_size")
        self.assertIsInstance(chunk_size, int, "chunk_size should be an integer")

    def test_get_config_with_default(self):
        """Verify that get_config returns default for missing keys."""
        value = get_config("nonexistent.key.path", default="default_value")
        self.assertEqual(value, "default_value", "Should return default for missing key")

    def test_ui_search_max_results(self):
        """Verify that UI search max_results is configured."""
        max_results = get_config("ui.search.max_results", 150)
        self.assertIsInstance(max_results, int, "max_results should be an integer")
        self.assertGreater(max_results, 0, "max_results should be positive")

    def test_ui_anomalies_max_display(self):
        """Verify that UI anomalies max_display is configured."""
        max_display = get_config("ui.anomalies.max_display", 50)
        self.assertIsInstance(max_display, int, "max_display should be an integer")
        self.assertGreater(max_display, 0, "max_display should be positive")

    def test_ui_llm_temperature(self):
        """Verify that LLM temperature is configured."""
        temperature = get_config("ui.llm.temperature", 0.3)
        self.assertIsInstance(temperature, (int, float), "temperature should be numeric")
        self.assertGreaterEqual(temperature, 0, "temperature should be >= 0")
        self.assertLessEqual(temperature, 2.0, "temperature should be <= 2.0")

    def test_processing_chunk_size(self):
        """Verify that processing chunk_size is configured."""
        chunk_size = get_config("processing.chunk_size")
        self.assertIsInstance(chunk_size, int, "chunk_size should be an integer")
        self.assertGreater(chunk_size, 0, "chunk_size should be positive")

    def test_embedding_model_name(self):
        """Verify that embedding model_name is configured."""
        model_name = get_config("embedding.model_name")
        self.assertIsInstance(model_name, str, "model_name should be a string")
        self.assertTrue(len(model_name) > 0, "model_name should not be empty")


if __name__ == "__main__":
    unittest.main()
