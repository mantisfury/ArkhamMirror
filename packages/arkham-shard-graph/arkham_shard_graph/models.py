"""Data models for the Graph Shard."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from pydantic import BaseModel


class RelationshipType(Enum):
    """Types of entity relationships."""
    # Basic relationships
    WORKS_FOR = "works_for"
    AFFILIATED_WITH = "affiliated_with"
    LOCATED_IN = "located_in"
    MENTIONED_WITH = "mentioned_with"
    RELATED_TO = "related_to"
    TEMPORAL = "temporal"
    HIERARCHICAL = "hierarchical"

    # Organizational relationships
    OWNS = "owns"
    FOUNDED = "founded"
    EMPLOYED_BY = "employed_by"
    MEMBER_OF = "member_of"
    REPORTS_TO = "reports_to"
    SUBSIDIARY_OF = "subsidiary_of"
    PARTNER_OF = "partner_of"

    # Personal relationships
    MARRIED_TO = "married_to"
    CHILD_OF = "child_of"
    PARENT_OF = "parent_of"
    SIBLING_OF = "sibling_of"
    RELATIVE_OF = "relative_of"
    KNOWS = "knows"
    FRIEND_OF = "friend_of"

    # Interaction relationships
    COMMUNICATED_WITH = "communicated_with"
    MET_WITH = "met_with"
    TRANSACTED_WITH = "transacted_with"
    COLLABORATED_WITH = "collaborated_with"

    # Spatial relationships
    VISITED = "visited"
    RESIDES_IN = "resides_in"
    HEADQUARTERED_IN = "headquartered_in"
    TRAVELED_TO = "traveled_to"

    # Temporal relationships
    PRECEDED_BY = "preceded_by"
    FOLLOWED_BY = "followed_by"
    CONCURRENT_WITH = "concurrent_with"

    # Cross-shard relationship types
    CONTRADICTS = "contradicts"
    SUPPORTS = "supports"
    PATTERN_MATCH = "pattern_match"
    DERIVED_FROM = "derived_from"
    EVIDENCE_FOR = "evidence_for"
    EVIDENCE_AGAINST = "evidence_against"

    # Co-occurrence (default for extracted relationships)
    CO_OCCURRENCE = "co_occurrence"


class CentralityMetric(Enum):
    """Centrality calculation metrics."""
    DEGREE = "degree"
    BETWEENNESS = "betweenness"
    PAGERANK = "pagerank"
    EIGENVECTOR = "eigenvector"
    HITS = "hits"
    CLOSENESS = "closeness"
    ALL = "all"


class ExportFormat(Enum):
    """Graph export formats."""
    JSON = "json"
    GRAPHML = "graphml"
    GEXF = "gexf"


class CommunityAlgorithm(Enum):
    """Community detection algorithms."""
    LOUVAIN = "louvain"
    LABEL_PROPAGATION = "label_propagation"
    CONNECTED_COMPONENTS = "connected_components"


@dataclass
class GraphNode:
    """A node in the entity graph."""
    id: str
    entity_id: str
    label: str
    entity_type: str

    # Metrics
    document_count: int = 0
    degree: int = 0

    # Properties
    properties: dict[str, Any] = field(default_factory=dict)

    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        """Convert node to dictionary."""
        return {
            "id": self.id,
            "entity_id": self.entity_id,
            "label": self.label,
            "entity_type": self.entity_type,
            "document_count": self.document_count,
            "degree": self.degree,
            "properties": self.properties,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


@dataclass
class GraphEdge:
    """An edge in the entity graph."""
    source: str
    target: str
    relationship_type: str
    weight: float

    # Supporting evidence
    document_ids: list[str] = field(default_factory=list)
    co_occurrence_count: int = 0

    # Properties
    properties: dict[str, Any] = field(default_factory=dict)

    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        """Convert edge to dictionary."""
        return {
            "source": self.source,
            "target": self.target,
            "relationship_type": self.relationship_type,
            "weight": self.weight,
            "document_ids": self.document_ids,
            "co_occurrence_count": self.co_occurrence_count,
            "properties": self.properties,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


@dataclass
class Graph:
    """Entity relationship graph."""
    project_id: str
    nodes: list[GraphNode] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        """Convert graph to dictionary."""
        return {
            "project_id": self.project_id,
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "metadata": {
                **self.metadata,
                "created_at": self.created_at.isoformat() if self.created_at else None,
                "updated_at": self.updated_at.isoformat() if self.updated_at else None,
                "entity_count": len(self.nodes),
                "relationship_count": len(self.edges),
            }
        }


@dataclass
class GraphPath:
    """A path through the graph."""
    source_entity_id: str
    target_entity_id: str
    path: list[str]
    edges: list[GraphEdge]
    total_weight: float
    path_length: int

    def to_dict(self) -> dict[str, Any]:
        """Convert path to dictionary."""
        return {
            "source_entity_id": self.source_entity_id,
            "target_entity_id": self.target_entity_id,
            "path": self.path,
            "path_length": self.path_length,
            "edges": [e.to_dict() for e in self.edges],
            "total_weight": self.total_weight,
        }


@dataclass
class CentralityResult:
    """Result of centrality calculation."""
    entity_id: str
    label: str
    score: float
    rank: int
    entity_type: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "entity_id": self.entity_id,
            "label": self.label,
            "score": self.score,
            "rank": self.rank,
            "entity_type": self.entity_type,
        }


@dataclass
class Community:
    """A detected community in the graph."""
    id: str
    entity_ids: list[str]
    size: int
    density: float
    description: str = ""

    # Metrics
    modularity_contribution: float = 0.0
    internal_edges: int = 0
    external_edges: int = 0

    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "entity_ids": self.entity_ids,
            "size": self.size,
            "density": self.density,
            "description": self.description,
            "modularity_contribution": self.modularity_contribution,
            "internal_edges": self.internal_edges,
            "external_edges": self.external_edges,
        }


@dataclass
class GraphStatistics:
    """Graph statistics and metrics."""
    project_id: str
    node_count: int
    edge_count: int
    density: float
    avg_degree: float
    avg_clustering: float
    connected_components: int
    diameter: int
    avg_path_length: float
    entity_type_distribution: dict[str, int] = field(default_factory=dict)
    relationship_type_distribution: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "project_id": self.project_id,
            "node_count": self.node_count,
            "edge_count": self.edge_count,
            "density": self.density,
            "avg_degree": self.avg_degree,
            "avg_clustering": self.avg_clustering,
            "connected_components": self.connected_components,
            "diameter": self.diameter,
            "avg_path_length": self.avg_path_length,
            "entity_type_distribution": self.entity_type_distribution,
            "relationship_type_distribution": self.relationship_type_distribution,
        }


# --- Pydantic Request/Response Models ---


class BuildGraphRequest(BaseModel):
    """Request to build entity graph."""
    project_id: str
    document_ids: list[str] | None = None
    entity_types: list[str] | None = None
    min_co_occurrence: int = 1
    # Primary data sources (base graph)
    include_document_entities: bool = True  # Include entities from documents
    include_cooccurrences: bool = True      # Include co-occurrence edges
    # Cross-shard node sources
    include_temporal: bool = False          # Timeline events
    include_claims: bool = False
    include_ach_evidence: bool = False
    include_ach_hypotheses: bool = False
    include_provenance_artifacts: bool = False
    # Cross-shard edge sources
    include_contradictions: bool = False
    include_patterns: bool = False
    # Weight modifiers
    apply_credibility_weights: bool = False


class PathRequest(BaseModel):
    """Request to find path between entities."""
    project_id: str
    source_entity_id: str
    target_entity_id: str
    max_depth: int = 6


class PathResponse(BaseModel):
    """Response for path query."""
    path_found: bool
    path_length: int
    path: list[str]
    edges: list[dict[str, Any]]
    total_weight: float


class CentralityRequest(BaseModel):
    """Request to calculate centrality."""
    project_id: str
    metric: str = "all"
    limit: int = 50


class CentralityResponse(BaseModel):
    """Response for centrality calculation."""
    project_id: str
    metric: str
    results: list[dict[str, Any]]
    calculated_at: str


class CommunityRequest(BaseModel):
    """Request for community detection."""
    project_id: str
    algorithm: str = "louvain"
    min_community_size: int = 3
    resolution: float = 1.0


class CommunityResponse(BaseModel):
    """Response for community detection."""
    project_id: str
    community_count: int
    communities: list[dict[str, Any]]
    modularity: float


class NeighborsRequest(BaseModel):
    """Request for entity neighbors."""
    entity_id: str
    project_id: str
    depth: int = 1
    min_weight: float = 0.0
    limit: int = 50


class ExportRequest(BaseModel):
    """Request to export graph."""
    project_id: str
    format: str = "json"
    include_metadata: bool = True
    filter: dict[str, Any] | None = None


class ExportResponse(BaseModel):
    """Response for graph export."""
    format: str
    data: str
    node_count: int
    edge_count: int
    file_size_bytes: int


class FilterRequest(BaseModel):
    """Request to filter graph."""
    project_id: str
    entity_types: list[str] | None = None
    min_degree: int | None = None
    min_edge_weight: float | None = None
    relationship_types: list[str] | None = None
    document_ids: list[str] | None = None


class GraphResponse(BaseModel):
    """Response containing graph data."""
    project_id: str
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]
    metadata: dict[str, Any]


# --- Scoring Models ---


class ScoreConfigRequest(BaseModel):
    """Request for composite scoring configuration."""
    project_id: str
    centrality_type: str = "pagerank"  # pagerank, betweenness, eigenvector, hits, closeness, degree
    centrality_weight: float = 0.25
    frequency_weight: float = 0.20
    recency_weight: float = 0.20
    credibility_weight: float = 0.20
    corroboration_weight: float = 0.15
    recency_half_life_days: int | None = 30
    entity_type_weights: dict[str, float] | None = None
    limit: int = 100


class EntityScoreResponse(BaseModel):
    """Individual entity score."""
    entity_id: str
    label: str
    entity_type: str
    composite_score: float
    centrality_score: float
    frequency_score: float
    recency_score: float
    credibility_score: float
    corroboration_score: float
    rank: int
    degree: int
    document_count: int
    source_count: int


class ScoreResponse(BaseModel):
    """Response for composite scoring."""
    project_id: str
    scores: list[EntityScoreResponse]
    config: dict[str, Any]
    calculation_time_ms: float
    entity_count: int
