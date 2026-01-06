"""Temporal graph analysis - snapshots and evolution over time.

This module provides functionality to:
- Generate graph snapshots at specific points in time
- Track network evolution with added/removed nodes and edges
- Calculate temporal metrics (growth rate, churn)
- Support time-slider visualization in the frontend
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from .models import Graph, GraphNode, GraphEdge

logger = logging.getLogger(__name__)


@dataclass
class TemporalSnapshot:
    """A snapshot of the graph at a point in time."""
    timestamp: datetime
    nodes: list[GraphNode] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)

    # Change tracking (relative to previous snapshot)
    added_nodes: list[str] = field(default_factory=list)   # Node IDs added since previous
    removed_nodes: list[str] = field(default_factory=list)  # Node IDs removed since previous
    added_edges: list[tuple[str, str]] = field(default_factory=list)  # Edge pairs added
    removed_edges: list[tuple[str, str]] = field(default_factory=list)  # Edge pairs removed

    # Metrics at this point
    node_count: int = 0
    edge_count: int = 0
    density: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert snapshot to dictionary for API response."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "added_nodes": self.added_nodes,
            "removed_nodes": self.removed_nodes,
            "added_edges": [{"source": s, "target": t} for s, t in self.added_edges],
            "removed_edges": [{"source": s, "target": t} for s, t in self.removed_edges],
            "node_count": self.node_count,
            "edge_count": self.edge_count,
            "density": self.density,
        }


@dataclass
class TemporalRange:
    """Time range for temporal analysis."""
    start_date: datetime
    end_date: datetime
    interval: timedelta
    snapshot_count: int

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "interval_days": self.interval.days,
            "snapshot_count": self.snapshot_count,
        }


@dataclass
class EvolutionMetrics:
    """Metrics describing graph evolution over time."""
    total_nodes_added: int = 0
    total_nodes_removed: int = 0
    total_edges_added: int = 0
    total_edges_removed: int = 0

    # Growth rates (per interval)
    node_growth_rate: float = 0.0  # Average new nodes per interval
    edge_growth_rate: float = 0.0  # Average new edges per interval

    # Churn metrics
    node_churn_rate: float = 0.0   # (added + removed) / total
    edge_churn_rate: float = 0.0

    # Stability
    stable_node_count: int = 0     # Nodes present in all snapshots
    stable_edge_count: int = 0     # Edges present in all snapshots

    # Peak values
    peak_node_count: int = 0
    peak_edge_count: int = 0
    peak_timestamp: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_nodes_added": self.total_nodes_added,
            "total_nodes_removed": self.total_nodes_removed,
            "total_edges_added": self.total_edges_added,
            "total_edges_removed": self.total_edges_removed,
            "node_growth_rate": self.node_growth_rate,
            "edge_growth_rate": self.edge_growth_rate,
            "node_churn_rate": self.node_churn_rate,
            "edge_churn_rate": self.edge_churn_rate,
            "stable_node_count": self.stable_node_count,
            "stable_edge_count": self.stable_edge_count,
            "peak_node_count": self.peak_node_count,
            "peak_edge_count": self.peak_edge_count,
            "peak_timestamp": self.peak_timestamp.isoformat() if self.peak_timestamp else None,
        }


class TemporalGraphEngine:
    """Generate and analyze temporal graph snapshots.

    Supports both cumulative mode (all data up to each point) and
    window mode (only data within a time window).
    """

    def __init__(self, db_service=None):
        """Initialize temporal engine.

        Args:
            db_service: Database service for temporal queries
        """
        self.db_service = db_service

    async def get_temporal_range(
        self,
        project_id: str,
    ) -> TemporalRange | None:
        """
        Get the time range of data available for temporal analysis.

        Returns:
            TemporalRange with start/end dates, or None if no temporal data
        """
        if not self.db_service:
            logger.warning("No database service available for temporal queries")
            return None

        try:
            # Get min/max dates from entity mentions
            query = """
                SELECT
                    MIN(created_at) as earliest,
                    MAX(created_at) as latest,
                    COUNT(DISTINCT DATE(created_at)) as distinct_days
                FROM arkham_entity_mentions
                WHERE created_at IS NOT NULL
            """
            rows = await self.db_service.fetch_all(query, {})

            if not rows or not rows[0]["earliest"]:
                return None

            row = rows[0]
            start_date = row["earliest"]
            end_date = row["latest"]
            distinct_days = row["distinct_days"] or 1

            # Suggest interval based on data spread
            total_days = (end_date - start_date).days
            if total_days <= 7:
                interval = timedelta(days=1)
            elif total_days <= 30:
                interval = timedelta(days=7)
            elif total_days <= 365:
                interval = timedelta(days=30)
            else:
                interval = timedelta(days=90)

            snapshot_count = max(1, total_days // interval.days)

            return TemporalRange(
                start_date=start_date,
                end_date=end_date,
                interval=interval,
                snapshot_count=snapshot_count,
            )

        except Exception as e:
            logger.error(f"Error getting temporal range: {e}")
            return None

    async def generate_snapshots(
        self,
        project_id: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        interval: timedelta | None = None,
        cumulative: bool = True,
        max_snapshots: int = 50,
    ) -> list[TemporalSnapshot]:
        """
        Generate graph snapshots at regular intervals.

        Args:
            project_id: Project to analyze
            start_date: Start of time range (default: earliest data)
            end_date: End of time range (default: now)
            interval: Time between snapshots (default: auto-calculated)
            cumulative: If True, each snapshot includes all data up to that point.
                       If False, only data within that interval window.
            max_snapshots: Maximum number of snapshots to generate

        Returns:
            List of TemporalSnapshot objects in chronological order
        """
        if not self.db_service:
            logger.warning("No database service available")
            return []

        # Get available range
        available_range = await self.get_temporal_range(project_id)
        if not available_range:
            logger.warning("No temporal data available")
            return []

        # Use defaults from available range
        start_date = start_date or available_range.start_date
        end_date = end_date or available_range.end_date
        interval = interval or available_range.interval

        # Ensure we don't exceed max snapshots
        total_intervals = max(1, (end_date - start_date).days // max(1, interval.days))
        if total_intervals > max_snapshots:
            # Adjust interval to fit max_snapshots
            total_days = (end_date - start_date).days
            interval = timedelta(days=max(1, total_days // max_snapshots))

        snapshots: list[TemporalSnapshot] = []
        current_date = start_date
        previous_node_ids: set[str] = set()
        previous_edge_keys: set[tuple[str, str]] = set()

        while current_date <= end_date:
            # Get snapshot at this point
            snapshot = await self.get_snapshot_at(
                project_id=project_id,
                timestamp=current_date,
                cumulative=cumulative,
                window_size=interval if not cumulative else None,
            )

            # Calculate changes from previous snapshot
            current_node_ids = {n.id for n in snapshot.nodes}
            current_edge_keys = {(e.source, e.target) for e in snapshot.edges}

            snapshot.added_nodes = list(current_node_ids - previous_node_ids)
            snapshot.removed_nodes = list(previous_node_ids - current_node_ids)
            snapshot.added_edges = list(current_edge_keys - previous_edge_keys)
            snapshot.removed_edges = list(previous_edge_keys - current_edge_keys)

            snapshots.append(snapshot)

            previous_node_ids = current_node_ids
            previous_edge_keys = current_edge_keys
            current_date += interval

        logger.info(f"Generated {len(snapshots)} temporal snapshots for project {project_id}")
        return snapshots

    async def get_snapshot_at(
        self,
        project_id: str,
        timestamp: datetime,
        cumulative: bool = True,
        window_size: timedelta | None = None,
    ) -> TemporalSnapshot:
        """
        Get a single graph snapshot at a specific time.

        Args:
            project_id: Project ID
            timestamp: Point in time for snapshot
            cumulative: Include all data up to this point
            window_size: If not cumulative, window size for data inclusion

        Returns:
            TemporalSnapshot at the specified time
        """
        nodes: list[GraphNode] = []
        edges: list[GraphEdge] = []

        if not self.db_service:
            return TemporalSnapshot(
                timestamp=timestamp,
                nodes=nodes,
                edges=edges,
                node_count=0,
                edge_count=0,
            )

        try:
            # Build date filter
            if cumulative:
                date_filter = "created_at <= :timestamp"
                params: dict[str, Any] = {"timestamp": timestamp}
            else:
                window_start = timestamp - (window_size or timedelta(days=7))
                date_filter = "created_at >= :window_start AND created_at <= :timestamp"
                params = {"timestamp": timestamp, "window_start": window_start}

            # Get entities that existed at this point
            # Use entity_mentions to determine when entities were first seen
            entity_query = f"""
                SELECT DISTINCT ON (e.id)
                    e.id,
                    e.name as label,
                    e.entity_type,
                    e.metadata,
                    e.mention_count as document_count,
                    MIN(m.created_at) OVER (PARTITION BY e.id) as first_seen
                FROM arkham_entities e
                JOIN arkham_entity_mentions m ON e.id = m.entity_id
                WHERE m.{date_filter}
                  AND e.canonical_id IS NULL
                ORDER BY e.id, e.mention_count DESC
                LIMIT 500
            """

            entity_rows = await self.db_service.fetch_all(entity_query, params)

            for row in entity_rows:
                node = GraphNode(
                    id=str(row["id"]),
                    entity_id=str(row["id"]),
                    label=row["label"] or "Unknown",
                    entity_type=row["entity_type"] or "unknown",
                    document_count=row["document_count"] or 0,
                    properties=row.get("metadata") or {},
                    created_at=row.get("first_seen") or timestamp,
                )
                nodes.append(node)

            # Get co-occurrences that existed at this point
            if nodes:
                node_ids = [n.id for n in nodes]

                cooccurrence_query = f"""
                    SELECT
                        m1.entity_id as entity_a,
                        m2.entity_id as entity_b,
                        COUNT(DISTINCT m1.document_id) as co_occurrence_count,
                        ARRAY_AGG(DISTINCT m1.document_id::text) as document_ids,
                        MIN(GREATEST(m1.created_at, m2.created_at)) as first_co_occurrence
                    FROM arkham_entity_mentions m1
                    JOIN arkham_entity_mentions m2
                        ON m1.document_id = m2.document_id
                        AND m1.entity_id < m2.entity_id
                    WHERE m1.entity_id = ANY(:entity_ids)
                      AND m2.entity_id = ANY(:entity_ids)
                      AND m1.{date_filter}
                      AND m2.{date_filter}
                    GROUP BY m1.entity_id, m2.entity_id
                    HAVING COUNT(DISTINCT m1.document_id) >= 1
                    ORDER BY co_occurrence_count DESC
                    LIMIT 1000
                """
                params["entity_ids"] = node_ids

                edge_rows = await self.db_service.fetch_all(cooccurrence_query, params)

                for row in edge_rows:
                    source = str(row["entity_a"])
                    target = str(row["entity_b"])
                    count = row["co_occurrence_count"]

                    edge = GraphEdge(
                        source=source,
                        target=target,
                        relationship_type="mentioned_with",
                        weight=min(1.0, count / 10.0),
                        document_ids=row.get("document_ids") or [],
                        co_occurrence_count=count,
                        created_at=row.get("first_co_occurrence") or timestamp,
                    )
                    edges.append(edge)

            # Calculate density
            n = len(nodes)
            e = len(edges)
            max_edges = n * (n - 1) / 2 if n > 1 else 1
            density = e / max_edges if max_edges > 0 else 0.0

            return TemporalSnapshot(
                timestamp=timestamp,
                nodes=nodes,
                edges=edges,
                node_count=len(nodes),
                edge_count=len(edges),
                density=density,
            )

        except Exception as ex:
            logger.error(f"Error getting snapshot at {timestamp}: {ex}")
            return TemporalSnapshot(
                timestamp=timestamp,
                nodes=[],
                edges=[],
                node_count=0,
                edge_count=0,
            )

    def calculate_evolution_metrics(
        self,
        snapshots: list[TemporalSnapshot],
    ) -> EvolutionMetrics:
        """
        Calculate metrics describing network evolution.

        Args:
            snapshots: List of temporal snapshots in chronological order

        Returns:
            EvolutionMetrics summarizing the evolution
        """
        if not snapshots:
            return EvolutionMetrics()

        metrics = EvolutionMetrics()

        # Count total additions/removals
        for snapshot in snapshots:
            metrics.total_nodes_added += len(snapshot.added_nodes)
            metrics.total_nodes_removed += len(snapshot.removed_nodes)
            metrics.total_edges_added += len(snapshot.added_edges)
            metrics.total_edges_removed += len(snapshot.removed_edges)

        # Growth rates (per interval)
        num_intervals = max(1, len(snapshots) - 1)
        metrics.node_growth_rate = metrics.total_nodes_added / num_intervals
        metrics.edge_growth_rate = metrics.total_edges_added / num_intervals

        # Find peak
        for snapshot in snapshots:
            if snapshot.node_count > metrics.peak_node_count:
                metrics.peak_node_count = snapshot.node_count
                metrics.peak_edge_count = snapshot.edge_count
                metrics.peak_timestamp = snapshot.timestamp

        # Calculate stable elements (present in all snapshots)
        if snapshots:
            all_node_sets = [set(n.id for n in s.nodes) for s in snapshots]
            all_edge_sets = [set((e.source, e.target) for e in s.edges) for s in snapshots]

            stable_nodes = all_node_sets[0]
            stable_edges = all_edge_sets[0]

            for node_set, edge_set in zip(all_node_sets[1:], all_edge_sets[1:]):
                stable_nodes &= node_set
                stable_edges &= edge_set

            metrics.stable_node_count = len(stable_nodes)
            metrics.stable_edge_count = len(stable_edges)

        # Churn rates
        final_count = snapshots[-1].node_count if snapshots else 0
        if final_count > 0:
            metrics.node_churn_rate = (
                metrics.total_nodes_added + metrics.total_nodes_removed
            ) / final_count

        final_edges = snapshots[-1].edge_count if snapshots else 0
        if final_edges > 0:
            metrics.edge_churn_rate = (
                metrics.total_edges_added + metrics.total_edges_removed
            ) / final_edges

        return metrics

    def filter_snapshot_by_date_range(
        self,
        snapshot: TemporalSnapshot,
        date_field: str = "created_at",
        min_date: datetime | None = None,
        max_date: datetime | None = None,
    ) -> TemporalSnapshot:
        """
        Filter a snapshot's nodes/edges by a date range.

        Useful for temporal exploration within a snapshot.

        Args:
            snapshot: The snapshot to filter
            date_field: Property field containing the date
            min_date: Minimum date (inclusive)
            max_date: Maximum date (inclusive)

        Returns:
            Filtered snapshot
        """
        filtered_nodes = []
        for node in snapshot.nodes:
            node_date = node.created_at
            if min_date and node_date < min_date:
                continue
            if max_date and node_date > max_date:
                continue
            filtered_nodes.append(node)

        node_ids = {n.id for n in filtered_nodes}

        filtered_edges = []
        for edge in snapshot.edges:
            # Only include edges between remaining nodes
            if edge.source not in node_ids or edge.target not in node_ids:
                continue
            # Check edge date
            edge_date = edge.created_at
            if min_date and edge_date < min_date:
                continue
            if max_date and edge_date > max_date:
                continue
            filtered_edges.append(edge)

        n = len(filtered_nodes)
        e = len(filtered_edges)
        max_edges = n * (n - 1) / 2 if n > 1 else 1

        return TemporalSnapshot(
            timestamp=snapshot.timestamp,
            nodes=filtered_nodes,
            edges=filtered_edges,
            node_count=n,
            edge_count=e,
            density=e / max_edges if max_edges > 0 else 0.0,
        )
