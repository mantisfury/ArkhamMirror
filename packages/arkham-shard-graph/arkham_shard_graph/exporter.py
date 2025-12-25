"""Graph exporters - export graphs in various formats."""

import json
import logging
from typing import Any
from xml.etree import ElementTree as ET

from .models import Graph, ExportFormat

logger = logging.getLogger(__name__)


class GraphExporter:
    """
    Export graphs in various formats.

    Supports JSON, GraphML, and GEXF formats.
    """

    def __init__(self):
        """Initialize graph exporter."""
        pass

    def export_graph(
        self,
        graph: Graph,
        format: ExportFormat,
        include_metadata: bool = True,
    ) -> str:
        """
        Export graph in specified format.

        Args:
            graph: Graph to export
            format: Export format
            include_metadata: Include metadata in export

        Returns:
            Serialized graph as string
        """
        if format == ExportFormat.JSON:
            return self.export_json(graph, include_metadata)
        elif format == ExportFormat.GRAPHML:
            return self.export_graphml(graph, include_metadata)
        elif format == ExportFormat.GEXF:
            return self.export_gexf(graph, include_metadata)
        else:
            raise ValueError(f"Unsupported export format: {format}")

    def export_json(self, graph: Graph, include_metadata: bool = True) -> str:
        """
        Export graph as JSON.

        Args:
            graph: Graph to export
            include_metadata: Include metadata

        Returns:
            JSON string
        """
        data = graph.to_dict()

        if not include_metadata:
            data.pop("metadata", None)

        return json.dumps(data, indent=2)

    def export_graphml(self, graph: Graph, include_metadata: bool = True) -> str:
        """
        Export graph as GraphML (XML format).

        Compatible with Gephi, Cytoscape, yEd, etc.

        Args:
            graph: Graph to export
            include_metadata: Include metadata as attributes

        Returns:
            GraphML XML string
        """
        # Create root element
        root = ET.Element("graphml")
        root.set("xmlns", "http://graphml.graphdrawing.org/xmlns")
        root.set("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")
        root.set(
            "xsi:schemaLocation",
            "http://graphml.graphdrawing.org/xmlns "
            "http://graphml.graphdrawing.org/xmlns/1.0/graphml.xsd"
        )

        # Define attribute keys
        self._add_graphml_key(root, "label", "node", "string")
        self._add_graphml_key(root, "entity_type", "node", "string")
        self._add_graphml_key(root, "document_count", "node", "int")
        self._add_graphml_key(root, "degree", "node", "int")

        self._add_graphml_key(root, "relationship_type", "edge", "string")
        self._add_graphml_key(root, "weight", "edge", "double")
        self._add_graphml_key(root, "co_occurrence_count", "edge", "int")

        # Create graph element
        graph_elem = ET.SubElement(root, "graph")
        graph_elem.set("id", f"G_{graph.project_id}")
        graph_elem.set("edgedefault", "undirected")

        # Add nodes
        for node in graph.nodes:
            node_elem = ET.SubElement(graph_elem, "node")
            node_elem.set("id", node.id)

            self._add_graphml_data(node_elem, "label", node.label)
            self._add_graphml_data(node_elem, "entity_type", node.entity_type)
            self._add_graphml_data(node_elem, "document_count", str(node.document_count))
            self._add_graphml_data(node_elem, "degree", str(node.degree))

            # Add custom properties
            if include_metadata and node.properties:
                for key, value in node.properties.items():
                    self._add_graphml_data(node_elem, f"prop_{key}", str(value))

        # Add edges
        for i, edge in enumerate(graph.edges):
            edge_elem = ET.SubElement(graph_elem, "edge")
            edge_elem.set("id", f"e{i}")
            edge_elem.set("source", edge.source)
            edge_elem.set("target", edge.target)

            self._add_graphml_data(edge_elem, "relationship_type", edge.relationship_type)
            self._add_graphml_data(edge_elem, "weight", str(edge.weight))
            self._add_graphml_data(edge_elem, "co_occurrence_count", str(edge.co_occurrence_count))

        # Convert to string
        tree = ET.ElementTree(root)
        ET.indent(tree, space="  ")

        import io
        output = io.StringIO()
        tree.write(output, encoding="unicode", xml_declaration=True)
        return output.getvalue()

    def export_gexf(self, graph: Graph, include_metadata: bool = True) -> str:
        """
        Export graph as GEXF (Gephi Exchange Format).

        Args:
            graph: Graph to export
            include_metadata: Include metadata

        Returns:
            GEXF XML string
        """
        # Create root element
        root = ET.Element("gexf")
        root.set("xmlns", "http://www.gexf.net/1.2draft")
        root.set("version", "1.2")

        # Meta
        meta = ET.SubElement(root, "meta")
        meta.set("lastmodifieddate", graph.updated_at.strftime("%Y-%m-%d") if graph.updated_at else "")

        creator = ET.SubElement(meta, "creator")
        creator.text = "ArkhamMirror Graph Shard"

        description = ET.SubElement(meta, "description")
        description.text = f"Entity relationship graph for project {graph.project_id}"

        # Graph element
        graph_elem = ET.SubElement(root, "graph")
        graph_elem.set("mode", "static")
        graph_elem.set("defaultedgetype", "undirected")

        # Attributes
        attributes_nodes = ET.SubElement(graph_elem, "attributes")
        attributes_nodes.set("class", "node")

        self._add_gexf_attribute(attributes_nodes, "0", "label", "string")
        self._add_gexf_attribute(attributes_nodes, "1", "entity_type", "string")
        self._add_gexf_attribute(attributes_nodes, "2", "document_count", "integer")
        self._add_gexf_attribute(attributes_nodes, "3", "degree", "integer")

        attributes_edges = ET.SubElement(graph_elem, "attributes")
        attributes_edges.set("class", "edge")

        self._add_gexf_attribute(attributes_edges, "0", "relationship_type", "string")
        self._add_gexf_attribute(attributes_edges, "1", "co_occurrence_count", "integer")

        # Nodes
        nodes_elem = ET.SubElement(graph_elem, "nodes")

        for node in graph.nodes:
            node_elem = ET.SubElement(nodes_elem, "node")
            node_elem.set("id", node.id)
            node_elem.set("label", node.label)

            # Attributes
            attvalues = ET.SubElement(node_elem, "attvalues")
            self._add_gexf_attvalue(attvalues, "0", node.label)
            self._add_gexf_attvalue(attvalues, "1", node.entity_type)
            self._add_gexf_attvalue(attvalues, "2", str(node.document_count))
            self._add_gexf_attvalue(attvalues, "3", str(node.degree))

        # Edges
        edges_elem = ET.SubElement(graph_elem, "edges")

        for i, edge in enumerate(graph.edges):
            edge_elem = ET.SubElement(edges_elem, "edge")
            edge_elem.set("id", str(i))
            edge_elem.set("source", edge.source)
            edge_elem.set("target", edge.target)
            edge_elem.set("weight", str(edge.weight))

            # Attributes
            attvalues = ET.SubElement(edge_elem, "attvalues")
            self._add_gexf_attvalue(attvalues, "0", edge.relationship_type)
            self._add_gexf_attvalue(attvalues, "1", str(edge.co_occurrence_count))

        # Convert to string
        tree = ET.ElementTree(root)
        ET.indent(tree, space="  ")

        import io
        output = io.StringIO()
        tree.write(output, encoding="unicode", xml_declaration=True)
        return output.getvalue()

    # --- Helper Methods ---

    def _add_graphml_key(
        self, root: ET.Element, id: str, for_type: str, attr_type: str
    ) -> None:
        """Add GraphML key definition."""
        key = ET.SubElement(root, "key")
        key.set("id", id)
        key.set("for", for_type)
        key.set("attr.name", id)
        key.set("attr.type", attr_type)

    def _add_graphml_data(
        self, parent: ET.Element, key: str, value: str
    ) -> None:
        """Add GraphML data element."""
        data = ET.SubElement(parent, "data")
        data.set("key", key)
        data.text = value

    def _add_gexf_attribute(
        self, parent: ET.Element, id: str, title: str, type: str
    ) -> None:
        """Add GEXF attribute definition."""
        attr = ET.SubElement(parent, "attribute")
        attr.set("id", id)
        attr.set("title", title)
        attr.set("type", type)

    def _add_gexf_attvalue(
        self, parent: ET.Element, for_id: str, value: str
    ) -> None:
        """Add GEXF attribute value."""
        attvalue = ET.SubElement(parent, "attvalue")
        attvalue.set("for", for_id)
        attvalue.set("value", value)
