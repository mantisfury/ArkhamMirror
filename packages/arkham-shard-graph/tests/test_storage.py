"""Tests for graph storage."""

import pytest
import pytest_asyncio
from unittest.mock import MagicMock, AsyncMock

from arkham_shard_graph.storage import GraphStorage
from arkham_shard_graph.models import Graph, GraphNode, GraphEdge


class TestGraphStorageCreation:
    """Test graph storage creation."""

    def test_storage_creation_no_db(self):
        """Test creating storage without database service."""
        storage = GraphStorage()

        assert storage.db_service is None
        assert storage._cache == {}

    def test_storage_creation_with_db(self):
        """Test creating storage with database service."""
        db_service = MagicMock()
        storage = GraphStorage(db_service=db_service)

        assert storage.db_service == db_service
        assert storage._cache == {}


class TestGraphCaching:
    """Test in-memory caching."""

    @pytest.mark.asyncio
    async def test_save_graph_to_cache(self):
        """Test saving graph to cache."""
        storage = GraphStorage()

        graph = Graph(project_id="proj1")

        await storage.save_graph(graph)

        assert "proj1" in storage._cache
        assert storage._cache["proj1"] == graph

    @pytest.mark.asyncio
    async def test_load_graph_from_cache(self):
        """Test loading graph from cache."""
        storage = GraphStorage()

        graph = Graph(project_id="proj1")
        storage._cache["proj1"] = graph

        loaded = await storage.load_graph("proj1")

        assert loaded == graph

    @pytest.mark.asyncio
    async def test_load_graph_not_found(self):
        """Test loading graph that doesn't exist."""
        storage = GraphStorage()

        with pytest.raises(ValueError, match="Graph not found"):
            await storage.load_graph("nonexistent")

    @pytest.mark.asyncio
    async def test_delete_graph_from_cache(self):
        """Test deleting graph from cache."""
        storage = GraphStorage()

        graph = Graph(project_id="proj1")
        storage._cache["proj1"] = graph

        await storage.delete_graph("proj1")

        assert "proj1" not in storage._cache

    def test_clear_cache(self):
        """Test clearing entire cache."""
        storage = GraphStorage()

        storage._cache["proj1"] = Graph(project_id="proj1")
        storage._cache["proj2"] = Graph(project_id="proj2")

        storage.clear_cache()

        assert len(storage._cache) == 0


class TestGraphPersistence:
    """Test database persistence."""

    @pytest.mark.asyncio
    async def test_save_graph_with_db(self):
        """Test saving graph with database service."""
        db_service = MagicMock()
        storage = GraphStorage(db_service=db_service)

        graph = Graph(project_id="proj1")

        await storage.save_graph(graph)

        # Graph should be in cache
        assert "proj1" in storage._cache

    @pytest.mark.asyncio
    async def test_save_graph_db_error_handled(self):
        """Test that database errors during save are handled."""
        db_service = MagicMock()
        storage = GraphStorage(db_service=db_service)

        # Mock persist to raise error
        storage._persist_graph = AsyncMock(side_effect=Exception("DB error"))

        graph = Graph(project_id="proj1")

        # Should not raise error, just log it
        await storage.save_graph(graph)

        # Graph should still be in cache
        assert "proj1" in storage._cache

    @pytest.mark.asyncio
    async def test_load_graph_from_db(self):
        """Test loading graph from database."""
        db_service = MagicMock()
        storage = GraphStorage(db_service=db_service)

        # Mock database loading
        graph = Graph(project_id="proj1")
        storage._load_from_db = AsyncMock(return_value=graph)

        loaded = await storage.load_graph("proj1")

        assert loaded.project_id == "proj1"
        # Should be cached after loading
        assert "proj1" in storage._cache

    @pytest.mark.asyncio
    async def test_load_graph_db_error(self):
        """Test loading graph from database with error."""
        db_service = MagicMock()
        storage = GraphStorage(db_service=db_service)

        # Mock database loading to raise error
        storage._load_from_db = AsyncMock(side_effect=Exception("DB error"))

        with pytest.raises(ValueError, match="Graph not found"):
            await storage.load_graph("proj1")

    @pytest.mark.asyncio
    async def test_delete_graph_with_db(self):
        """Test deleting graph with database service."""
        db_service = MagicMock()
        storage = GraphStorage(db_service=db_service)

        # Add to cache
        storage._cache["proj1"] = Graph(project_id="proj1")

        await storage.delete_graph("proj1")

        # Should be removed from cache
        assert "proj1" not in storage._cache

    @pytest.mark.asyncio
    async def test_delete_graph_db_error_handled(self):
        """Test that database errors during delete are handled."""
        db_service = MagicMock()
        storage = GraphStorage(db_service=db_service)

        # Mock delete to raise error
        storage._delete_from_db = AsyncMock(side_effect=Exception("DB error"))

        # Add to cache
        storage._cache["proj1"] = Graph(project_id="proj1")

        # Should not raise error, just log it
        await storage.delete_graph("proj1")

        # Should still be removed from cache
        assert "proj1" not in storage._cache


class TestMultipleGraphs:
    """Test storing multiple graphs."""

    @pytest.mark.asyncio
    async def test_save_multiple_graphs(self):
        """Test saving multiple graphs."""
        storage = GraphStorage()

        graph1 = Graph(project_id="proj1")
        graph2 = Graph(project_id="proj2")
        graph3 = Graph(project_id="proj3")

        await storage.save_graph(graph1)
        await storage.save_graph(graph2)
        await storage.save_graph(graph3)

        assert len(storage._cache) == 3
        assert "proj1" in storage._cache
        assert "proj2" in storage._cache
        assert "proj3" in storage._cache

    @pytest.mark.asyncio
    async def test_overwrite_graph(self):
        """Test overwriting existing graph."""
        storage = GraphStorage()

        graph1 = Graph(project_id="proj1", nodes=[])
        await storage.save_graph(graph1)

        # Overwrite with different graph
        graph2 = Graph(
            project_id="proj1",
            nodes=[GraphNode(id="n1", entity_id="e1", label="E1", entity_type="person")]
        )
        await storage.save_graph(graph2)

        loaded = await storage.load_graph("proj1")
        assert len(loaded.nodes) == 1
