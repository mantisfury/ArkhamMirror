"""Tests for Provenance Shard models."""

import pytest
from datetime import datetime
from arkham_shard_provenance.models import (
    ChainStatus,
    LinkType,
    ArtifactType,
    EventType,
    EvidenceChain,
    ProvenanceLink,
    TrackedArtifact,
    AuditRecord,
    LineageNode,
    LineageEdge,
    LineageGraph,
    VerificationResult,
    ChainExport,
)


class TestEnums:
    """Test enum definitions."""

    def test_chain_status_enum(self):
        """Test ChainStatus enum values."""
        assert ChainStatus.DRAFT.value == "draft"
        assert ChainStatus.ACTIVE.value == "active"
        assert ChainStatus.VERIFIED.value == "verified"
        assert ChainStatus.COMPLETED.value == "completed"
        assert ChainStatus.ARCHIVED.value == "archived"

    def test_link_type_enum(self):
        """Test LinkType enum values."""
        assert LinkType.DERIVED_FROM.value == "derived_from"
        assert LinkType.TRANSFORMED_TO.value == "transformed_to"
        assert LinkType.EXTRACTED_FROM.value == "extracted_from"
        assert LinkType.GENERATED_BY.value == "generated_by"
        assert LinkType.USED_BY.value == "used_by"
        assert LinkType.SUPPORTS.value == "supports"
        assert LinkType.CONTRADICTS.value == "contradicts"
        assert LinkType.RELATED_TO.value == "related_to"
        assert LinkType.VERSION_OF.value == "version_of"
        assert LinkType.COPY_OF.value == "copy_of"

    def test_artifact_type_enum(self):
        """Test ArtifactType enum values."""
        assert ArtifactType.DOCUMENT.value == "document"
        assert ArtifactType.ENTITY.value == "entity"
        assert ArtifactType.CLAIM.value == "claim"
        assert ArtifactType.EVIDENCE.value == "evidence"
        assert ArtifactType.HYPOTHESIS.value == "hypothesis"
        assert ArtifactType.MATRIX.value == "matrix"
        assert ArtifactType.REPORT.value == "report"
        assert ArtifactType.EMBEDDING.value == "embedding"
        assert ArtifactType.EXTRACTION.value == "extraction"
        assert ArtifactType.TIMELINE.value == "timeline"
        assert ArtifactType.GRAPH.value == "graph"
        assert ArtifactType.SUMMARY.value == "summary"

    def test_event_type_enum(self):
        """Test EventType enum values."""
        assert EventType.CHAIN_CREATED.value == "chain_created"
        assert EventType.CHAIN_UPDATED.value == "chain_updated"
        assert EventType.CHAIN_DELETED.value == "chain_deleted"
        assert EventType.LINK_ADDED.value == "link_added"
        assert EventType.LINK_REMOVED.value == "link_removed"
        assert EventType.LINK_VERIFIED.value == "link_verified"
        assert EventType.ARTIFACT_TRACKED.value == "artifact_tracked"
        assert EventType.AUDIT_GENERATED.value == "audit_generated"
        assert EventType.EXPORT_COMPLETED.value == "export_completed"


class TestEvidenceChain:
    """Test EvidenceChain dataclass."""

    def test_create_basic_chain(self):
        """Test creating a basic evidence chain."""
        chain = EvidenceChain(
            id="chain-1",
            title="Test Chain",
            description="A test evidence chain",
        )

        assert chain.id == "chain-1"
        assert chain.title == "Test Chain"
        assert chain.description == "A test evidence chain"
        assert chain.status == ChainStatus.DRAFT
        assert chain.link_count == 0
        assert chain.artifact_count == 0
        assert chain.verified is False
        assert isinstance(chain.created_at, datetime)
        assert isinstance(chain.updated_at, datetime)

    def test_chain_with_all_fields(self):
        """Test chain with all optional fields."""
        now = datetime.utcnow()
        chain = EvidenceChain(
            id="chain-2",
            title="Complete Chain",
            description="Chain with all fields",
            status=ChainStatus.VERIFIED,
            created_at=now,
            updated_at=now,
            created_by="user-123",
            project_id="proj-456",
            link_count=5,
            artifact_count=10,
            metadata={"key": "value"},
            tags=["legal", "priority"],
            verified=True,
            verified_by="reviewer-789",
            verified_at=now,
            verification_notes="All links verified",
        )

        assert chain.status == ChainStatus.VERIFIED
        assert chain.created_by == "user-123"
        assert chain.project_id == "proj-456"
        assert chain.link_count == 5
        assert chain.artifact_count == 10
        assert chain.metadata == {"key": "value"}
        assert chain.tags == ["legal", "priority"]
        assert chain.verified is True
        assert chain.verified_by == "reviewer-789"
        assert chain.verified_at == now

    def test_chain_default_values(self):
        """Test chain default field values."""
        chain = EvidenceChain(id="chain-3", title="Defaults Test")

        assert chain.description == ""
        assert chain.status == ChainStatus.DRAFT
        assert chain.created_by is None
        assert chain.project_id is None
        assert chain.link_count == 0
        assert chain.artifact_count == 0
        assert chain.metadata == {}
        assert chain.tags == []
        assert chain.verified is False
        assert chain.verified_by is None
        assert chain.verified_at is None
        assert chain.verification_notes == ""


class TestProvenanceLink:
    """Test ProvenanceLink dataclass."""

    def test_create_basic_link(self):
        """Test creating a basic provenance link."""
        link = ProvenanceLink(
            id="link-1",
            chain_id="chain-1",
            source_artifact_id="artifact-src",
            target_artifact_id="artifact-tgt",
            link_type=LinkType.DERIVED_FROM,
        )

        assert link.id == "link-1"
        assert link.chain_id == "chain-1"
        assert link.source_artifact_id == "artifact-src"
        assert link.target_artifact_id == "artifact-tgt"
        assert link.link_type == LinkType.DERIVED_FROM
        assert link.confidence == 1.0
        assert link.verified is False
        assert isinstance(link.created_at, datetime)

    def test_link_with_verification(self):
        """Test link with verification details."""
        now = datetime.utcnow()
        link = ProvenanceLink(
            id="link-2",
            chain_id="chain-1",
            source_artifact_id="src",
            target_artifact_id="tgt",
            link_type=LinkType.SUPPORTS,
            confidence=0.85,
            verified=True,
            verified_by="reviewer",
            verified_at=now,
            notes="Verified link",
        )

        assert link.confidence == 0.85
        assert link.verified is True
        assert link.verified_by == "reviewer"
        assert link.verified_at == now
        assert link.notes == "Verified link"

    def test_link_with_transformation(self):
        """Test link with transformation details."""
        link = ProvenanceLink(
            id="link-3",
            chain_id="chain-1",
            source_artifact_id="doc",
            target_artifact_id="entities",
            link_type=LinkType.EXTRACTED_FROM,
            transformation_process="ner_extraction",
            transformation_params={"model": "spacy", "threshold": 0.8},
        )

        assert link.transformation_process == "ner_extraction"
        assert link.transformation_params == {"model": "spacy", "threshold": 0.8}


class TestTrackedArtifact:
    """Test TrackedArtifact dataclass."""

    def test_create_artifact(self):
        """Test creating a tracked artifact."""
        artifact = TrackedArtifact(
            id="art-1",
            artifact_id="doc-123",
            artifact_type=ArtifactType.DOCUMENT,
            shard_name="ingest",
        )

        assert artifact.id == "art-1"
        assert artifact.artifact_id == "doc-123"
        assert artifact.artifact_type == ArtifactType.DOCUMENT
        assert artifact.shard_name == "ingest"
        assert artifact.upstream_count == 0
        assert artifact.downstream_count == 0
        assert isinstance(artifact.created_at, datetime)

    def test_artifact_with_lineage_counts(self):
        """Test artifact with lineage statistics."""
        artifact = TrackedArtifact(
            id="art-2",
            artifact_id="entity-456",
            artifact_type=ArtifactType.ENTITY,
            shard_name="entities",
            upstream_count=3,
            downstream_count=5,
            metadata={"source": "document-123"},
        )

        assert artifact.upstream_count == 3
        assert artifact.downstream_count == 5
        assert artifact.metadata == {"source": "document-123"}


class TestAuditRecord:
    """Test AuditRecord dataclass."""

    def test_create_audit_record(self):
        """Test creating an audit record."""
        record = AuditRecord(
            id="audit-1",
            event_type=EventType.CHAIN_CREATED,
            event_source="provenance",
            event_data={"chain_id": "chain-1", "title": "New Chain"},
        )

        assert record.id == "audit-1"
        assert record.event_type == EventType.CHAIN_CREATED
        assert record.event_source == "provenance"
        assert record.event_data == {"chain_id": "chain-1", "title": "New Chain"}
        assert isinstance(record.timestamp, datetime)

    def test_audit_with_context(self):
        """Test audit record with context."""
        record = AuditRecord(
            id="audit-2",
            event_type=EventType.LINK_ADDED,
            event_source="provenance",
            event_data={"link_id": "link-1"},
            chain_id="chain-1",
            user_id="user-123",
            metadata={"ip": "192.168.1.1"},
        )

        assert record.chain_id == "chain-1"
        assert record.user_id == "user-123"
        assert record.metadata == {"ip": "192.168.1.1"}


class TestLineageModels:
    """Test lineage-related models."""

    def test_lineage_node(self):
        """Test LineageNode creation."""
        node = LineageNode(
            id="node-1",
            artifact_id="doc-123",
            artifact_type=ArtifactType.DOCUMENT,
            shard_name="ingest",
            label="Document 123",
            level=0,
            metadata={"size": 1024},
        )

        assert node.id == "node-1"
        assert node.artifact_id == "doc-123"
        assert node.artifact_type == ArtifactType.DOCUMENT
        assert node.shard_name == "ingest"
        assert node.label == "Document 123"
        assert node.level == 0
        assert node.metadata == {"size": 1024}

    def test_lineage_edge(self):
        """Test LineageEdge creation."""
        edge = LineageEdge(
            source="node-1",
            target="node-2",
            link_type=LinkType.DERIVED_FROM,
            confidence=0.95,
            metadata={"verified": True},
        )

        assert edge.source == "node-1"
        assert edge.target == "node-2"
        assert edge.link_type == LinkType.DERIVED_FROM
        assert edge.confidence == 0.95
        assert edge.metadata == {"verified": True}

    def test_lineage_graph(self):
        """Test LineageGraph creation."""
        node1 = LineageNode(
            id="n1",
            artifact_id="a1",
            artifact_type=ArtifactType.DOCUMENT,
            shard_name="ingest",
            label="Doc 1",
        )
        node2 = LineageNode(
            id="n2",
            artifact_id="a2",
            artifact_type=ArtifactType.ENTITY,
            shard_name="entities",
            label="Entity 1",
        )
        edge = LineageEdge(
            source="n1",
            target="n2",
            link_type=LinkType.EXTRACTED_FROM,
            confidence=1.0,
        )

        graph = LineageGraph(
            artifact_id="a1",
            direction="downstream",
            nodes=[node1, node2],
            edges=[edge],
            total_nodes=2,
            total_edges=1,
            max_depth=1,
        )

        assert graph.artifact_id == "a1"
        assert graph.direction == "downstream"
        assert len(graph.nodes) == 2
        assert len(graph.edges) == 1
        assert graph.total_nodes == 2
        assert graph.total_edges == 1
        assert graph.max_depth == 1
        assert isinstance(graph.generated_at, datetime)


class TestVerificationResult:
    """Test VerificationResult dataclass."""

    def test_verification_success(self):
        """Test successful verification result."""
        result = VerificationResult(
            chain_id="chain-1",
            verified=True,
            links_checked=10,
            links_verified=10,
            artifacts_checked=15,
        )

        assert result.chain_id == "chain-1"
        assert result.verified is True
        assert result.issues == []
        assert result.warnings == []
        assert result.links_checked == 10
        assert result.links_verified == 10
        assert result.artifacts_checked == 15
        assert isinstance(result.checked_at, datetime)

    def test_verification_with_issues(self):
        """Test verification with issues."""
        now = datetime.utcnow()
        result = VerificationResult(
            chain_id="chain-2",
            verified=False,
            issues=[
                {"type": "missing_artifact", "artifact_id": "art-1"},
                {"type": "broken_link", "link_id": "link-2"},
            ],
            warnings=[
                {"type": "low_confidence", "link_id": "link-3"},
            ],
            checked_at=now,
            checked_by="system",
            links_checked=5,
            links_verified=3,
            artifacts_checked=8,
        )

        assert result.verified is False
        assert len(result.issues) == 2
        assert len(result.warnings) == 1
        assert result.checked_by == "system"
        assert result.links_checked == 5
        assert result.links_verified == 3


class TestChainExport:
    """Test ChainExport dataclass."""

    def test_chain_export(self):
        """Test chain export creation."""
        chain = EvidenceChain(id="c1", title="Export Test")
        link = ProvenanceLink(
            id="l1",
            chain_id="c1",
            source_artifact_id="s1",
            target_artifact_id="t1",
            link_type=LinkType.DERIVED_FROM,
        )
        artifact = TrackedArtifact(
            id="a1",
            artifact_id="s1",
            artifact_type=ArtifactType.DOCUMENT,
            shard_name="ingest",
        )
        audit = AuditRecord(
            id="au1",
            event_type=EventType.CHAIN_CREATED,
            event_source="provenance",
            event_data={},
        )

        export = ChainExport(
            chain=chain,
            links=[link],
            artifacts=[artifact],
            audit_trail=[audit],
            exported_by="user-1",
            export_format="json",
            include_metadata=True,
            include_audit=True,
            include_verification=False,
        )

        assert export.chain.id == "c1"
        assert len(export.links) == 1
        assert len(export.artifacts) == 1
        assert len(export.audit_trail) == 1
        assert export.exported_by == "user-1"
        assert export.export_format == "json"
        assert export.include_metadata is True
        assert export.include_audit is True
        assert export.include_verification is False
        assert isinstance(export.exported_at, datetime)
