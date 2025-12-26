"""
Tests for Documents Shard data models.

Tests all dataclasses, enums, and validation logic.

Run with:
    cd packages/arkham-shard-documents
    pytest tests/test_models.py -v
"""

import pytest
from datetime import datetime, timedelta
from arkham_shard_documents.models import (
    # Enums
    DocumentStatus,
    ViewMode,
    ChunkDisplayMode,
    # Dataclasses
    DocumentRecord,
    ViewingRecord,
    CustomMetadataField,
    UserPreferences,
    DocumentPage,
    DocumentChunkRecord,
    EntityOccurrence,
    DocumentEntity,
    DocumentFilter,
    DocumentStatistics,
    BatchOperationResult,
)


# =============================================================================
# Enum Tests
# =============================================================================


class TestDocumentStatus:
    """Test DocumentStatus enum."""

    def test_all_values_exist(self):
        """Test that all expected status values exist."""
        assert DocumentStatus.UPLOADED.value == "uploaded"
        assert DocumentStatus.PROCESSING.value == "processing"
        assert DocumentStatus.PROCESSED.value == "processed"
        assert DocumentStatus.FAILED.value == "failed"
        assert DocumentStatus.ARCHIVED.value == "archived"

    def test_enum_count(self):
        """Test that we have exactly 5 status values."""
        assert len(DocumentStatus) == 5

    def test_enum_comparison(self):
        """Test enum comparison."""
        status1 = DocumentStatus.UPLOADED
        status2 = DocumentStatus.UPLOADED
        status3 = DocumentStatus.PROCESSED

        assert status1 == status2
        assert status1 != status3


class TestViewMode:
    """Test ViewMode enum."""

    def test_all_values_exist(self):
        """Test that all expected view modes exist."""
        assert ViewMode.METADATA.value == "metadata"
        assert ViewMode.CONTENT.value == "content"
        assert ViewMode.CHUNKS.value == "chunks"
        assert ViewMode.ENTITIES.value == "entities"

    def test_enum_count(self):
        """Test that we have exactly 4 view modes."""
        assert len(ViewMode) == 4


class TestChunkDisplayMode:
    """Test ChunkDisplayMode enum."""

    def test_all_values_exist(self):
        """Test that all expected display modes exist."""
        assert ChunkDisplayMode.COMPACT.value == "compact"
        assert ChunkDisplayMode.DETAILED.value == "detailed"
        assert ChunkDisplayMode.CONTEXT.value == "context"

    def test_enum_count(self):
        """Test that we have exactly 3 display modes."""
        assert len(ChunkDisplayMode) == 3


# =============================================================================
# DocumentRecord Tests
# =============================================================================


class TestDocumentRecord:
    """Test DocumentRecord dataclass."""

    def test_minimal_document_record(self):
        """Test creating a minimal document record."""
        doc = DocumentRecord(
            id="doc-123",
            title="Test Document",
            filename="test.pdf",
            file_type="pdf",
            file_size=1024,
            status=DocumentStatus.UPLOADED,
        )

        assert doc.id == "doc-123"
        assert doc.title == "Test Document"
        assert doc.filename == "test.pdf"
        assert doc.file_type == "pdf"
        assert doc.file_size == 1024
        assert doc.status == DocumentStatus.UPLOADED

        # Check defaults
        assert doc.page_count == 0
        assert doc.chunk_count == 0
        assert doc.entity_count == 0
        assert doc.word_count == 0
        assert doc.project_id is None
        assert isinstance(doc.created_at, datetime)
        assert isinstance(doc.updated_at, datetime)
        assert doc.processed_at is None
        assert doc.tags == []
        assert doc.custom_metadata == {}
        assert doc.processing_error is None

    def test_full_document_record(self):
        """Test creating a complete document record."""
        now = datetime.utcnow()
        doc = DocumentRecord(
            id="doc-456",
            title="Complete Document",
            filename="complete.pdf",
            file_type="pdf",
            file_size=2048,
            status=DocumentStatus.PROCESSED,
            page_count=10,
            chunk_count=25,
            entity_count=15,
            word_count=5000,
            project_id="proj-1",
            created_at=now,
            updated_at=now,
            processed_at=now,
            tags=["important", "legal"],
            custom_metadata={"department": "legal", "priority": "high"},
            processing_error=None,
        )

        assert doc.page_count == 10
        assert doc.chunk_count == 25
        assert doc.entity_count == 15
        assert doc.word_count == 5000
        assert doc.project_id == "proj-1"
        assert len(doc.tags) == 2
        assert "important" in doc.tags
        assert doc.custom_metadata["department"] == "legal"

    def test_failed_document_record(self):
        """Test document record with processing error."""
        doc = DocumentRecord(
            id="doc-789",
            title="Failed Document",
            filename="failed.pdf",
            file_type="pdf",
            file_size=512,
            status=DocumentStatus.FAILED,
            processing_error="OCR failed: Invalid file format",
        )

        assert doc.status == DocumentStatus.FAILED
        assert doc.processing_error == "OCR failed: Invalid file format"


# =============================================================================
# ViewingRecord Tests
# =============================================================================


class TestViewingRecord:
    """Test ViewingRecord dataclass."""

    def test_minimal_viewing_record(self):
        """Test creating a minimal viewing record."""
        view = ViewingRecord(
            id="view-1",
            document_id="doc-123",
            user_id=None,
        )

        assert view.id == "view-1"
        assert view.document_id == "doc-123"
        assert view.user_id is None
        assert isinstance(view.viewed_at, datetime)
        assert view.view_mode == ViewMode.CONTENT
        assert view.page_number is None
        assert view.duration_seconds is None

    def test_full_viewing_record(self):
        """Test creating a complete viewing record."""
        now = datetime.utcnow()
        view = ViewingRecord(
            id="view-2",
            document_id="doc-456",
            user_id="user-1",
            viewed_at=now,
            view_mode=ViewMode.CHUNKS,
            page_number=5,
            duration_seconds=120,
        )

        assert view.user_id == "user-1"
        assert view.view_mode == ViewMode.CHUNKS
        assert view.page_number == 5
        assert view.duration_seconds == 120


# =============================================================================
# CustomMetadataField Tests
# =============================================================================


class TestCustomMetadataField:
    """Test CustomMetadataField dataclass."""

    def test_minimal_metadata_field(self):
        """Test creating a minimal metadata field."""
        field = CustomMetadataField(
            id="field-1",
            field_name="department",
            field_type="text",
        )

        assert field.id == "field-1"
        assert field.field_name == "department"
        assert field.field_type == "text"
        assert field.description == ""
        assert field.required is False
        assert field.default_value is None
        assert isinstance(field.created_at, datetime)

    def test_full_metadata_field(self):
        """Test creating a complete metadata field."""
        now = datetime.utcnow()
        field = CustomMetadataField(
            id="field-2",
            field_name="priority",
            field_type="number",
            description="Document priority level (1-5)",
            required=True,
            default_value=3,
            created_at=now,
        )

        assert field.description == "Document priority level (1-5)"
        assert field.required is True
        assert field.default_value == 3

    def test_various_field_types(self):
        """Test different metadata field types."""
        field_types = ["text", "number", "date", "boolean", "tags"]

        for field_type in field_types:
            field = CustomMetadataField(
                id=f"field-{field_type}",
                field_name=f"test_{field_type}",
                field_type=field_type,
            )
            assert field.field_type == field_type


# =============================================================================
# UserPreferences Tests
# =============================================================================


class TestUserPreferences:
    """Test UserPreferences dataclass."""

    def test_default_preferences(self):
        """Test creating user preferences with defaults."""
        prefs = UserPreferences(user_id="user-1")

        assert prefs.user_id == "user-1"
        assert prefs.viewer_zoom == 1.0
        assert prefs.show_metadata is True
        assert prefs.chunk_display_mode == ChunkDisplayMode.DETAILED
        assert prefs.items_per_page == 20
        assert prefs.default_sort == "created_at"
        assert prefs.default_sort_order == "desc"
        assert prefs.default_filter is None
        assert prefs.saved_filters == {}
        assert isinstance(prefs.updated_at, datetime)

    def test_custom_preferences(self):
        """Test creating user preferences with custom values."""
        now = datetime.utcnow()
        saved_filters = {
            "recent": {"created_after": "2024-01-01"},
            "important": {"tags": ["important"]},
        }

        prefs = UserPreferences(
            user_id="user-2",
            viewer_zoom=1.5,
            show_metadata=False,
            chunk_display_mode=ChunkDisplayMode.COMPACT,
            items_per_page=50,
            default_sort="title",
            default_sort_order="asc",
            default_filter="recent",
            saved_filters=saved_filters,
            updated_at=now,
        )

        assert prefs.viewer_zoom == 1.5
        assert prefs.show_metadata is False
        assert prefs.chunk_display_mode == ChunkDisplayMode.COMPACT
        assert prefs.items_per_page == 50
        assert prefs.default_sort == "title"
        assert prefs.default_sort_order == "asc"
        assert prefs.default_filter == "recent"
        assert len(prefs.saved_filters) == 2


# =============================================================================
# DocumentPage Tests
# =============================================================================


class TestDocumentPage:
    """Test DocumentPage dataclass."""

    def test_minimal_page(self):
        """Test creating a minimal document page."""
        page = DocumentPage(
            document_id="doc-123",
            page_number=1,
            content="This is page 1 content",
        )

        assert page.document_id == "doc-123"
        assert page.page_number == 1
        assert page.content == "This is page 1 content"
        assert page.word_count == 0
        assert page.has_images is False
        assert page.ocr_confidence is None
        assert page.width is None
        assert page.height is None

    def test_full_page(self):
        """Test creating a complete document page."""
        page = DocumentPage(
            document_id="doc-456",
            page_number=5,
            content="OCR extracted text",
            word_count=250,
            has_images=True,
            ocr_confidence=0.95,
            width=8.5,
            height=11.0,
        )

        assert page.word_count == 250
        assert page.has_images is True
        assert page.ocr_confidence == 0.95
        assert page.width == 8.5
        assert page.height == 11.0


# =============================================================================
# DocumentChunkRecord Tests
# =============================================================================


class TestDocumentChunkRecord:
    """Test DocumentChunkRecord dataclass."""

    def test_minimal_chunk(self):
        """Test creating a minimal chunk record."""
        chunk = DocumentChunkRecord(
            id="chunk-1",
            document_id="doc-123",
            chunk_index=0,
            content="First chunk of text",
            token_count=5,
            word_count=4,
            char_count=20,
        )

        assert chunk.id == "chunk-1"
        assert chunk.document_id == "doc-123"
        assert chunk.chunk_index == 0
        assert chunk.content == "First chunk of text"
        assert chunk.token_count == 5
        assert chunk.word_count == 4
        assert chunk.char_count == 20
        assert chunk.page_number is None
        assert chunk.embedding_id is None
        assert chunk.has_embedding is False
        assert chunk.previous_chunk_id is None
        assert chunk.next_chunk_id is None
        assert isinstance(chunk.created_at, datetime)

    def test_full_chunk_with_embeddings(self):
        """Test creating a chunk with embeddings and context."""
        now = datetime.utcnow()
        chunk = DocumentChunkRecord(
            id="chunk-2",
            document_id="doc-456",
            chunk_index=5,
            content="Middle chunk with embeddings",
            page_number=3,
            token_count=10,
            word_count=8,
            char_count=30,
            embedding_id="embed-123",
            has_embedding=True,
            previous_chunk_id="chunk-1",
            next_chunk_id="chunk-3",
            created_at=now,
        )

        assert chunk.page_number == 3
        assert chunk.embedding_id == "embed-123"
        assert chunk.has_embedding is True
        assert chunk.previous_chunk_id == "chunk-1"
        assert chunk.next_chunk_id == "chunk-3"


# =============================================================================
# EntityOccurrence Tests
# =============================================================================


class TestEntityOccurrence:
    """Test EntityOccurrence dataclass."""

    def test_minimal_occurrence(self):
        """Test creating a minimal entity occurrence."""
        occurrence = EntityOccurrence(
            document_id="doc-123",
            entity_id="entity-1",
        )

        assert occurrence.document_id == "doc-123"
        assert occurrence.entity_id == "entity-1"
        assert occurrence.page_number is None
        assert occurrence.chunk_id is None
        assert occurrence.start_offset == 0
        assert occurrence.end_offset == 0
        assert occurrence.context_before == ""
        assert occurrence.context_after == ""
        assert occurrence.sentence == ""

    def test_full_occurrence_with_context(self):
        """Test creating a complete entity occurrence."""
        occurrence = EntityOccurrence(
            document_id="doc-456",
            entity_id="entity-2",
            page_number=5,
            chunk_id="chunk-10",
            start_offset=100,
            end_offset=115,
            context_before="The meeting with ",
            context_after=" was scheduled for Tuesday.",
            sentence="The meeting with John Smith was scheduled for Tuesday.",
        )

        assert occurrence.page_number == 5
        assert occurrence.chunk_id == "chunk-10"
        assert occurrence.start_offset == 100
        assert occurrence.end_offset == 115
        assert occurrence.context_before == "The meeting with "
        assert occurrence.context_after == " was scheduled for Tuesday."
        assert occurrence.sentence == "The meeting with John Smith was scheduled for Tuesday."


# =============================================================================
# DocumentEntity Tests
# =============================================================================


class TestDocumentEntity:
    """Test DocumentEntity dataclass."""

    def test_minimal_entity(self):
        """Test creating a minimal document entity."""
        entity = DocumentEntity(
            id="entity-1",
            document_id="doc-123",
            entity_type="PERSON",
            text="John Smith",
            normalized_text="john smith",
        )

        assert entity.id == "entity-1"
        assert entity.document_id == "doc-123"
        assert entity.entity_type == "PERSON"
        assert entity.text == "John Smith"
        assert entity.normalized_text == "john smith"
        assert entity.confidence == 1.0
        assert entity.source == "ner"
        assert entity.occurrence_count == 0
        assert entity.occurrences == []
        assert entity.context_samples == []
        assert isinstance(entity.created_at, datetime)

    def test_full_entity_with_occurrences(self):
        """Test creating a complete entity with occurrences."""
        now = datetime.utcnow()
        occurrences = [
            EntityOccurrence(
                document_id="doc-456",
                entity_id="entity-2",
                page_number=1,
                sentence="Microsoft announced new features.",
            ),
            EntityOccurrence(
                document_id="doc-456",
                entity_id="entity-2",
                page_number=3,
                sentence="Microsoft's revenue increased.",
            ),
        ]

        entity = DocumentEntity(
            id="entity-2",
            document_id="doc-456",
            entity_type="ORG",
            text="Microsoft",
            normalized_text="microsoft",
            confidence=0.98,
            source="ner",
            occurrence_count=2,
            occurrences=occurrences,
            context_samples=["announced new features", "revenue increased"],
            created_at=now,
        )

        assert entity.entity_type == "ORG"
        assert entity.confidence == 0.98
        assert entity.occurrence_count == 2
        assert len(entity.occurrences) == 2
        assert len(entity.context_samples) == 2

    def test_various_entity_types(self):
        """Test different entity types."""
        entity_types = ["PERSON", "ORG", "GPE", "DATE", "EVENT"]

        for entity_type in entity_types:
            entity = DocumentEntity(
                id=f"entity-{entity_type}",
                document_id="doc-123",
                entity_type=entity_type,
                text=f"Test {entity_type}",
                normalized_text=f"test {entity_type.lower()}",
            )
            assert entity.entity_type == entity_type

    def test_entity_sources(self):
        """Test different entity sources."""
        sources = ["ner", "manual", "inferred"]

        for source in sources:
            entity = DocumentEntity(
                id=f"entity-{source}",
                document_id="doc-123",
                entity_type="PERSON",
                text="Test Person",
                normalized_text="test person",
                source=source,
            )
            assert entity.source == source


# =============================================================================
# DocumentFilter Tests
# =============================================================================


class TestDocumentFilter:
    """Test DocumentFilter dataclass."""

    def test_default_filter(self):
        """Test creating a filter with defaults."""
        filter = DocumentFilter()

        assert filter.status is None
        assert filter.file_type is None
        assert filter.project_id is None
        assert filter.tags == []
        assert filter.created_after is None
        assert filter.created_before is None
        assert filter.search_query is None
        assert filter.page == 1
        assert filter.page_size == 20
        assert filter.sort_field == "created_at"
        assert filter.sort_order == "desc"

    def test_full_filter(self):
        """Test creating a complete filter."""
        now = datetime.utcnow()
        last_week = now - timedelta(days=7)

        filter = DocumentFilter(
            status=DocumentStatus.PROCESSED,
            file_type="pdf",
            project_id="proj-1",
            tags=["important", "legal"],
            created_after=last_week,
            created_before=now,
            search_query="contract",
            page=2,
            page_size=50,
            sort_field="title",
            sort_order="asc",
        )

        assert filter.status == DocumentStatus.PROCESSED
        assert filter.file_type == "pdf"
        assert filter.project_id == "proj-1"
        assert len(filter.tags) == 2
        assert filter.created_after == last_week
        assert filter.created_before == now
        assert filter.search_query == "contract"
        assert filter.page == 2
        assert filter.page_size == 50
        assert filter.sort_field == "title"
        assert filter.sort_order == "asc"


# =============================================================================
# DocumentStatistics Tests
# =============================================================================


class TestDocumentStatistics:
    """Test DocumentStatistics dataclass."""

    def test_default_statistics(self):
        """Test creating statistics with defaults."""
        stats = DocumentStatistics()

        assert stats.total_documents == 0
        assert stats.uploaded_count == 0
        assert stats.processing_count == 0
        assert stats.processed_count == 0
        assert stats.failed_count == 0
        assert stats.archived_count == 0
        assert stats.total_size_bytes == 0
        assert stats.average_size_bytes == 0
        assert stats.total_pages == 0
        assert stats.total_chunks == 0
        assert stats.total_entities == 0
        assert stats.file_type_counts == {}
        assert stats.documents_added_today == 0
        assert stats.documents_processed_today == 0
        assert isinstance(stats.computed_at, datetime)

    def test_full_statistics(self):
        """Test creating complete statistics."""
        now = datetime.utcnow()
        file_type_counts = {"pdf": 50, "docx": 30, "txt": 20}

        stats = DocumentStatistics(
            total_documents=100,
            uploaded_count=10,
            processing_count=5,
            processed_count=80,
            failed_count=3,
            archived_count=2,
            total_size_bytes=1024000,
            average_size_bytes=10240,
            total_pages=500,
            total_chunks=2000,
            total_entities=1500,
            file_type_counts=file_type_counts,
            documents_added_today=15,
            documents_processed_today=12,
            computed_at=now,
        )

        assert stats.total_documents == 100
        assert stats.uploaded_count == 10
        assert stats.processing_count == 5
        assert stats.processed_count == 80
        assert stats.failed_count == 3
        assert stats.archived_count == 2
        assert stats.total_size_bytes == 1024000
        assert stats.average_size_bytes == 10240
        assert stats.total_pages == 500
        assert stats.total_chunks == 2000
        assert stats.total_entities == 1500
        assert len(stats.file_type_counts) == 3
        assert stats.file_type_counts["pdf"] == 50
        assert stats.documents_added_today == 15
        assert stats.documents_processed_today == 12

    def test_statistics_consistency(self):
        """Test that status counts add up correctly."""
        stats = DocumentStatistics(
            total_documents=100,
            uploaded_count=10,
            processing_count=5,
            processed_count=80,
            failed_count=3,
            archived_count=2,
        )

        # Status counts should sum to total
        status_sum = (
            stats.uploaded_count +
            stats.processing_count +
            stats.processed_count +
            stats.failed_count +
            stats.archived_count
        )
        assert status_sum == stats.total_documents


# =============================================================================
# BatchOperationResult Tests
# =============================================================================


class TestBatchOperationResult:
    """Test BatchOperationResult dataclass."""

    def test_default_result(self):
        """Test creating a batch result with defaults."""
        result = BatchOperationResult(
            success=True,
            processed=10,
            failed=0,
        )

        assert result.success is True
        assert result.processed == 10
        assert result.failed == 0
        assert result.errors == []
        assert result.message == ""
        assert result.results == []

    def test_successful_batch(self):
        """Test creating a successful batch result."""
        results = [
            {"id": "doc-1", "status": "updated"},
            {"id": "doc-2", "status": "updated"},
            {"id": "doc-3", "status": "updated"},
        ]

        result = BatchOperationResult(
            success=True,
            processed=3,
            failed=0,
            message="Successfully updated 3 documents",
            results=results,
        )

        assert result.success is True
        assert result.processed == 3
        assert result.failed == 0
        assert len(result.errors) == 0
        assert result.message == "Successfully updated 3 documents"
        assert len(result.results) == 3

    def test_partial_failure_batch(self):
        """Test creating a partial failure batch result."""
        errors = [
            "doc-2: Document not found",
            "doc-4: Permission denied",
        ]
        results = [
            {"id": "doc-1", "status": "updated"},
            {"id": "doc-2", "status": "failed"},
            {"id": "doc-3", "status": "updated"},
            {"id": "doc-4", "status": "failed"},
        ]

        result = BatchOperationResult(
            success=False,
            processed=2,
            failed=2,
            errors=errors,
            message="2 of 4 documents failed to update",
            results=results,
        )

        assert result.success is False
        assert result.processed == 2
        assert result.failed == 2
        assert len(result.errors) == 2
        assert "Document not found" in result.errors[0]
        assert len(result.results) == 4

    def test_complete_failure_batch(self):
        """Test creating a complete failure batch result."""
        errors = ["Database connection failed"]

        result = BatchOperationResult(
            success=False,
            processed=0,
            failed=5,
            errors=errors,
            message="Batch operation failed completely",
        )

        assert result.success is False
        assert result.processed == 0
        assert result.failed == 5
        assert len(result.errors) == 1
        assert result.message == "Batch operation failed completely"
