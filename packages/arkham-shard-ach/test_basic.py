"""Basic smoke test for ACH shard."""

import sys
from pathlib import Path

# Add package to path
sys.path.insert(0, str(Path(__file__).parent))

from arkham_shard_ach.models import (
    ACHMatrix,
    Hypothesis,
    Evidence,
    Rating,
    ConsistencyRating,
    MatrixStatus,
)
from arkham_shard_ach.matrix import MatrixManager
from arkham_shard_ach.scoring import ACHScorer
from arkham_shard_ach.export import MatrixExporter


def test_basic_workflow():
    """Test basic ACH workflow."""
    print("Testing ACH Shard basic workflow...\n")

    # Create matrix manager
    manager = MatrixManager()

    # Create matrix
    matrix = manager.create_matrix(
        title="Test Analysis",
        description="Testing ACH functionality",
    )
    print(f"Created matrix: {matrix.id}")
    print(f"  Title: {matrix.title}")
    print(f"  Status: {matrix.status.value}\n")

    # Add hypotheses
    h1 = manager.add_hypothesis(
        matrix_id=matrix.id,
        title="Hypothesis A",
        description="First explanation",
    )
    print(f"Added hypothesis: {h1.title} (column {h1.column_index})")

    h2 = manager.add_hypothesis(
        matrix_id=matrix.id,
        title="Hypothesis B",
        description="Second explanation",
    )
    print(f"Added hypothesis: {h2.title} (column {h2.column_index})\n")

    # Add evidence
    e1 = manager.add_evidence(
        matrix_id=matrix.id,
        description="Evidence supports A",
        source="Test source",
        credibility=0.9,
        relevance=0.9,
    )
    print(f"Added evidence: {e1.description} (row {e1.row_index})")

    e2 = manager.add_evidence(
        matrix_id=matrix.id,
        description="Evidence against A",
        source="Test source 2",
        credibility=0.8,
        relevance=0.8,
    )
    print(f"Added evidence: {e2.description} (row {e2.row_index})\n")

    # Set ratings
    r1 = manager.set_rating(
        matrix_id=matrix.id,
        evidence_id=e1.id,
        hypothesis_id=h1.id,
        rating=ConsistencyRating.HIGHLY_CONSISTENT,
        reasoning="Strongly supports H1",
    )
    print(f"Set rating: E1 vs H1 = {r1.rating.value}")

    r2 = manager.set_rating(
        matrix_id=matrix.id,
        evidence_id=e1.id,
        hypothesis_id=h2.id,
        rating=ConsistencyRating.NEUTRAL,
        reasoning="Not relevant to H2",
    )
    print(f"Set rating: E1 vs H2 = {r2.rating.value}")

    r3 = manager.set_rating(
        matrix_id=matrix.id,
        evidence_id=e2.id,
        hypothesis_id=h1.id,
        rating=ConsistencyRating.INCONSISTENT,
        reasoning="Contradicts H1",
    )
    print(f"Set rating: E2 vs H1 = {r3.rating.value}")

    r4 = manager.set_rating(
        matrix_id=matrix.id,
        evidence_id=e2.id,
        hypothesis_id=h2.id,
        rating=ConsistencyRating.CONSISTENT,
        reasoning="Supports H2",
    )
    print(f"Set rating: E2 vs H2 = {r4.rating.value}\n")

    # Calculate scores
    scorer = ACHScorer()
    scores = scorer.calculate_scores(matrix)
    print("Calculated scores:")
    for score in sorted(scores, key=lambda s: s.rank):
        hypothesis = matrix.get_hypothesis(score.hypothesis_id)
        print(f"  Rank {score.rank}: {hypothesis.title}")
        print(f"    Inconsistencies: {score.inconsistency_count}")
        print(f"    Weighted Score: {score.weighted_score:.3f}")
        print(f"    Normalized Score: {score.normalized_score:.1f}")

    # Test export
    print("\nTesting export...")
    exporter = MatrixExporter()

    # JSON export
    json_export = exporter.export(matrix, "json")
    print(f"  JSON export: {len(json_export.content)} chars")

    # CSV export
    csv_export = exporter.export(matrix, "csv")
    print(f"  CSV export: {len(csv_export.content)} chars")

    # HTML export
    html_export = exporter.export(matrix, "html")
    print(f"  HTML export: {len(html_export.content)} chars")

    # Markdown export
    md_export = exporter.export(matrix, "markdown")
    print(f"  Markdown export: {len(md_export.content)} chars")

    print("\nAll tests passed!")


if __name__ == "__main__":
    test_basic_workflow()
