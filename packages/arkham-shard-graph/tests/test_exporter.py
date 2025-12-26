"""Tests for graph exporter."""

import pytest
import json
from xml.etree import ElementTree as ET

from arkham_shard_graph.exporter import GraphExporter
from arkham_shard_graph.models import Graph, GraphNode, GraphEdge, ExportFormat


class TestGraphExporterCreation:
    """Test graph exporter creation."""

    def test_exporter_creation(self):
        """Test creating exporter instance."""
        exporter = GraphExporter()
        assert exporter is not None


class TestJSONExport:
    """Test JSON export."""

    def test_export_json_simple(self):
        """Test exporting simple graph as JSON."""
        exporter = GraphExporter()

        nodes = [
            GraphNode(id="n1", entity_id="e1", label="E1", entity_type="person"),
        ]

        graph = Graph(project_id="proj1", nodes=nodes)

        json_str = exporter.export_json(graph)

        assert isinstance(json_str, str)
        data = json.loads(json_str)
        assert data["project_id"] == "proj1"
        assert len(data["nodes"]) == 1
        assert "metadata" in data

    def test_export_json_with_edges(self):
        """Test exporting graph with edges as JSON."""
        exporter = GraphExporter()

        nodes = [
            GraphNode(id="n1", entity_id="e1", label="E1", entity_type="person"),
            GraphNode(id="n2", entity_id="e2", label="E2", entity_type="person"),
        ]

        edges = [
            GraphEdge(source="n1", target="n2", relationship_type="works_for", weight=0.8),
        ]

        graph = Graph(project_id="proj1", nodes=nodes, edges=edges)

        json_str = exporter.export_json(graph)

        data = json.loads(json_str)
        assert len(data["edges"]) == 1
        assert data["edges"][0]["source"] == "n1"
        assert data["edges"][0]["target"] == "n2"

    def test_export_json_without_metadata(self):
        """Test exporting JSON without metadata."""
        exporter = GraphExporter()

        graph = Graph(project_id="proj1")

        json_str = exporter.export_json(graph, include_metadata=False)

        data = json.loads(json_str)
        assert "metadata" not in data

    def test_export_json_complex_properties(self):
        """Test exporting graph with complex properties."""
        exporter = GraphExporter()

        nodes = [
            GraphNode(
                id="n1",
                entity_id="e1",
                label="E1",
                entity_type="person",
                properties={"age": 30, "city": "NYC"},
            ),
        ]

        graph = Graph(project_id="proj1", nodes=nodes)

        json_str = exporter.export_json(graph)

        data = json.loads(json_str)
        assert data["nodes"][0]["properties"]["age"] == 30
        assert data["nodes"][0]["properties"]["city"] == "NYC"


class TestGraphMLExport:
    """Test GraphML export."""

    def test_export_graphml_simple(self):
        """Test exporting simple graph as GraphML."""
        exporter = GraphExporter()

        nodes = [
            GraphNode(id="n1", entity_id="e1", label="E1", entity_type="person"),
        ]

        graph = Graph(project_id="proj1", nodes=nodes)

        graphml_str = exporter.export_graphml(graph)

        assert isinstance(graphml_str, str)
        assert "graphml" in graphml_str
        assert "<?xml" in graphml_str

        # Parse XML to verify structure
        root = ET.fromstring(graphml_str)
        assert root.tag.endswith("graphml")

    def test_export_graphml_with_edges(self):
        """Test exporting graph with edges as GraphML."""
        exporter = GraphExporter()

        nodes = [
            GraphNode(id="n1", entity_id="e1", label="E1", entity_type="person", degree=1),
            GraphNode(id="n2", entity_id="e2", label="E2", entity_type="person", degree=1),
        ]

        edges = [
            GraphEdge(
                source="n1",
                target="n2",
                relationship_type="works_for",
                weight=0.8,
                co_occurrence_count=5,
            ),
        ]

        graph = Graph(project_id="proj1", nodes=nodes, edges=edges)

        graphml_str = exporter.export_graphml(graph)

        root = ET.fromstring(graphml_str)

        # Find graph element
        graph_elem = root.find(".//{http://graphml.graphdrawing.org/xmlns}graph")
        assert graph_elem is not None

        # Find nodes
        nodes_elem = graph_elem.findall(".//{http://graphml.graphdrawing.org/xmlns}node")
        assert len(nodes_elem) == 2

        # Find edges
        edges_elem = graph_elem.findall(".//{http://graphml.graphdrawing.org/xmlns}edge")
        assert len(edges_elem) == 1

    def test_export_graphml_attributes(self):
        """Test GraphML includes node/edge attributes."""
        exporter = GraphExporter()

        nodes = [
            GraphNode(
                id="n1",
                entity_id="e1",
                label="E1",
                entity_type="person",
                document_count=10,
                degree=2,
            ),
        ]

        graph = Graph(project_id="proj1", nodes=nodes)

        graphml_str = exporter.export_graphml(graph)

        # Should contain attribute definitions
        assert "label" in graphml_str
        assert "entity_type" in graphml_str
        assert "document_count" in graphml_str
        assert "degree" in graphml_str

    def test_export_graphml_without_metadata(self):
        """Test GraphML export without custom metadata."""
        exporter = GraphExporter()

        nodes = [
            GraphNode(
                id="n1",
                entity_id="e1",
                label="E1",
                entity_type="person",
                properties={"custom": "value"},
            ),
        ]

        graph = Graph(project_id="proj1", nodes=nodes)

        graphml_str = exporter.export_graphml(graph, include_metadata=False)

        # Should not include custom properties
        assert "prop_custom" not in graphml_str


class TestGEXFExport:
    """Test GEXF export."""

    def test_export_gexf_simple(self):
        """Test exporting simple graph as GEXF."""
        exporter = GraphExporter()

        nodes = [
            GraphNode(id="n1", entity_id="e1", label="E1", entity_type="person"),
        ]

        graph = Graph(project_id="proj1", nodes=nodes)

        gexf_str = exporter.export_gexf(graph)

        assert isinstance(gexf_str, str)
        assert "gexf" in gexf_str
        assert "<?xml" in gexf_str

        # Parse XML to verify structure
        root = ET.fromstring(gexf_str)
        assert root.tag.endswith("gexf")

    def test_export_gexf_with_edges(self):
        """Test exporting graph with edges as GEXF."""
        exporter = GraphExporter()

        nodes = [
            GraphNode(id="n1", entity_id="e1", label="E1", entity_type="person", degree=1),
            GraphNode(id="n2", entity_id="e2", label="E2", entity_type="person", degree=1),
        ]

        edges = [
            GraphEdge(
                source="n1",
                target="n2",
                relationship_type="works_for",
                weight=0.8,
                co_occurrence_count=5,
            ),
        ]

        graph = Graph(project_id="proj1", nodes=nodes, edges=edges)

        gexf_str = exporter.export_gexf(graph)

        root = ET.fromstring(gexf_str)

        # Find nodes element
        nodes_elem = root.find(".//{http://www.gexf.net/1.2draft}nodes")
        assert nodes_elem is not None

        # Find edges element
        edges_elem = root.find(".//{http://www.gexf.net/1.2draft}edges")
        assert edges_elem is not None

    def test_export_gexf_metadata(self):
        """Test GEXF includes metadata."""
        exporter = GraphExporter()

        graph = Graph(project_id="proj1")

        gexf_str = exporter.export_gexf(graph)

        # Should contain metadata
        assert "ArkhamMirror" in gexf_str or "Arkham" in gexf_str
        assert "proj1" in gexf_str

    def test_export_gexf_attributes(self):
        """Test GEXF includes attribute definitions."""
        exporter = GraphExporter()

        nodes = [
            GraphNode(
                id="n1",
                entity_id="e1",
                label="E1",
                entity_type="person",
                document_count=10,
                degree=2,
            ),
        ]

        graph = Graph(project_id="proj1", nodes=nodes)

        gexf_str = exporter.export_gexf(graph)

        root = ET.fromstring(gexf_str)

        # Find attributes definition for nodes
        attrs = root.findall(".//{http://www.gexf.net/1.2draft}attributes[@class='node']")
        assert len(attrs) > 0


class TestExportFormatSelection:
    """Test export format selection."""

    def test_export_graph_json_format(self):
        """Test export with JSON format enum."""
        exporter = GraphExporter()

        graph = Graph(project_id="proj1")

        data = exporter.export_graph(graph, ExportFormat.JSON)

        assert isinstance(data, str)
        # Should be valid JSON
        json.loads(data)

    def test_export_graph_graphml_format(self):
        """Test export with GraphML format enum."""
        exporter = GraphExporter()

        graph = Graph(project_id="proj1")

        data = exporter.export_graph(graph, ExportFormat.GRAPHML)

        assert isinstance(data, str)
        assert "graphml" in data

    def test_export_graph_gexf_format(self):
        """Test export with GEXF format enum."""
        exporter = GraphExporter()

        graph = Graph(project_id="proj1")

        data = exporter.export_graph(graph, ExportFormat.GEXF)

        assert isinstance(data, str)
        assert "gexf" in data

    def test_export_graph_invalid_format(self):
        """Test export with invalid format raises error."""
        exporter = GraphExporter()

        graph = Graph(project_id="proj1")

        # Create invalid enum (this is a bit tricky, but we can test the error path)
        with pytest.raises((ValueError, AttributeError)):
            # Try to use invalid format by mocking
            class InvalidFormat:
                pass
            exporter.export_graph(graph, InvalidFormat())


class TestComplexGraphExport:
    """Test exporting complex graphs."""

    def test_export_large_graph_json(self):
        """Test exporting larger graph as JSON."""
        exporter = GraphExporter()

        nodes = [
            GraphNode(id=f"n{i}", entity_id=f"e{i}", label=f"E{i}", entity_type="person")
            for i in range(50)
        ]

        edges = [
            GraphEdge(source=f"n{i}", target=f"n{i+1}", relationship_type="works_for", weight=0.8)
            for i in range(49)
        ]

        graph = Graph(project_id="proj1", nodes=nodes, edges=edges)

        json_str = exporter.export_json(graph)

        data = json.loads(json_str)
        assert len(data["nodes"]) == 50
        assert len(data["edges"]) == 49

    def test_export_graph_with_all_relationship_types(self):
        """Test exporting graph with various relationship types."""
        exporter = GraphExporter()

        nodes = [
            GraphNode(id=f"n{i}", entity_id=f"e{i}", label=f"E{i}", entity_type="person")
            for i in range(4)
        ]

        edges = [
            GraphEdge(source="n0", target="n1", relationship_type="works_for", weight=0.8),
            GraphEdge(source="n1", target="n2", relationship_type="affiliated_with", weight=0.7),
            GraphEdge(source="n2", target="n3", relationship_type="located_in", weight=0.6),
        ]

        graph = Graph(project_id="proj1", nodes=nodes, edges=edges)

        json_str = exporter.export_json(graph)

        data = json.loads(json_str)
        relationship_types = {e["relationship_type"] for e in data["edges"]}
        assert "works_for" in relationship_types
        assert "affiliated_with" in relationship_types
        assert "located_in" in relationship_types
