"""Tests for OCR shard data models."""

import pytest
from pydantic import ValidationError

from arkham_shard_ocr.models import (
    OCREngine,
    BoundingBox,
    TextBlock,
    PageOCRResult,
    DocumentOCRResult,
)


class TestOCREngine:
    """Test the OCREngine enum."""

    def test_valid_engines(self):
        """Test valid engine values."""
        assert OCREngine.PADDLE == "paddle"
        assert OCREngine.QWEN == "qwen"

    def test_engine_membership(self):
        """Test engine value membership."""
        assert "paddle" in [e.value for e in OCREngine]
        assert "qwen" in [e.value for e in OCREngine]

    def test_engine_count(self):
        """Test that we have exactly 2 engines."""
        assert len(OCREngine) == 2


class TestBoundingBox:
    """Test the BoundingBox model."""

    def test_valid_bounding_box(self):
        """Test creating a valid bounding box."""
        bbox = BoundingBox(x=10, y=20, width=100, height=50, confidence=0.95)
        assert bbox.x == 10
        assert bbox.y == 20
        assert bbox.width == 100
        assert bbox.height == 50
        assert bbox.confidence == 0.95

    def test_default_confidence(self):
        """Test bounding box with default confidence."""
        bbox = BoundingBox(x=0, y=0, width=10, height=10)
        assert bbox.confidence == 0.0

    def test_negative_coordinates(self):
        """Test bounding box with negative coordinates (allowed)."""
        bbox = BoundingBox(x=-10, y=-20, width=100, height=50)
        assert bbox.x == -10
        assert bbox.y == -20

    def test_zero_dimensions(self):
        """Test bounding box with zero dimensions."""
        bbox = BoundingBox(x=0, y=0, width=0, height=0)
        assert bbox.width == 0
        assert bbox.height == 0

    def test_confidence_range(self):
        """Test confidence values at boundaries."""
        bbox1 = BoundingBox(x=0, y=0, width=10, height=10, confidence=0.0)
        bbox2 = BoundingBox(x=0, y=0, width=10, height=10, confidence=1.0)
        assert bbox1.confidence == 0.0
        assert bbox2.confidence == 1.0

    def test_invalid_types(self):
        """Test that invalid types raise validation errors."""
        with pytest.raises(ValidationError):
            BoundingBox(x="invalid", y=0, width=10, height=10)

    def test_missing_required_fields(self):
        """Test that missing required fields raise validation errors."""
        with pytest.raises(ValidationError):
            BoundingBox(x=10, y=20)  # Missing width and height


class TestTextBlock:
    """Test the TextBlock model."""

    def test_valid_text_block(self):
        """Test creating a valid text block."""
        bbox = BoundingBox(x=10, y=20, width=100, height=50)
        block = TextBlock(text="Hello World", bbox=bbox, line_number=1, block_number=1)
        assert block.text == "Hello World"
        assert block.bbox.x == 10
        assert block.line_number == 1
        assert block.block_number == 1

    def test_default_line_and_block_numbers(self):
        """Test text block with default line and block numbers."""
        bbox = BoundingBox(x=0, y=0, width=10, height=10)
        block = TextBlock(text="Test", bbox=bbox)
        assert block.line_number == 0
        assert block.block_number == 0

    def test_empty_text(self):
        """Test text block with empty text."""
        bbox = BoundingBox(x=0, y=0, width=10, height=10)
        block = TextBlock(text="", bbox=bbox)
        assert block.text == ""

    def test_multiline_text(self):
        """Test text block with multiline text."""
        bbox = BoundingBox(x=0, y=0, width=100, height=50)
        block = TextBlock(text="Line 1\nLine 2\nLine 3", bbox=bbox)
        assert "\n" in block.text
        assert block.text.count("\n") == 2

    def test_nested_bounding_box(self):
        """Test that bounding box is properly nested."""
        bbox = BoundingBox(x=10, y=20, width=100, height=50, confidence=0.8)
        block = TextBlock(text="Test", bbox=bbox)
        assert isinstance(block.bbox, BoundingBox)
        assert block.bbox.confidence == 0.8

    def test_missing_required_fields(self):
        """Test that missing required fields raise validation errors."""
        with pytest.raises(ValidationError):
            TextBlock(text="Test")  # Missing bbox


class TestPageOCRResult:
    """Test the PageOCRResult model."""

    def test_valid_page_result(self):
        """Test creating a valid page OCR result."""
        result = PageOCRResult(
            page_number=1,
            text="Page text",
            language="en",
            engine=OCREngine.PADDLE,
            confidence=0.9,
            processing_time_ms=123.45,
        )
        assert result.page_number == 1
        assert result.text == "Page text"
        assert result.language == "en"
        assert result.engine == OCREngine.PADDLE
        assert result.confidence == 0.9
        assert result.processing_time_ms == 123.45

    def test_default_values(self):
        """Test page result with default values."""
        result = PageOCRResult(page_number=1, text="Test")
        assert result.blocks == []
        assert result.language == "en"
        assert result.engine == OCREngine.PADDLE
        assert result.confidence == 0.0
        assert result.processing_time_ms == 0.0

    def test_with_text_blocks(self):
        """Test page result with text blocks."""
        bbox1 = BoundingBox(x=0, y=0, width=100, height=20)
        bbox2 = BoundingBox(x=0, y=25, width=100, height=20)
        block1 = TextBlock(text="Line 1", bbox=bbox1, line_number=1)
        block2 = TextBlock(text="Line 2", bbox=bbox2, line_number=2)

        result = PageOCRResult(
            page_number=1,
            text="Line 1\nLine 2",
            blocks=[block1, block2],
        )
        assert len(result.blocks) == 2
        assert result.blocks[0].text == "Line 1"
        assert result.blocks[1].text == "Line 2"

    def test_qwen_engine(self):
        """Test page result with Qwen engine."""
        result = PageOCRResult(
            page_number=1,
            text="Test",
            engine=OCREngine.QWEN,
        )
        assert result.engine == OCREngine.QWEN

    def test_different_languages(self):
        """Test page result with different languages."""
        result_en = PageOCRResult(page_number=1, text="Hello", language="en")
        result_zh = PageOCRResult(page_number=1, text="你好", language="zh")
        assert result_en.language == "en"
        assert result_zh.language == "zh"

    def test_zero_page_number(self):
        """Test page result with zero page number."""
        result = PageOCRResult(page_number=0, text="Test")
        assert result.page_number == 0

    def test_empty_text(self):
        """Test page result with empty text."""
        result = PageOCRResult(page_number=1, text="")
        assert result.text == ""

    def test_missing_required_fields(self):
        """Test that missing required fields raise validation errors."""
        with pytest.raises(ValidationError):
            PageOCRResult(page_number=1)  # Missing text


class TestDocumentOCRResult:
    """Test the DocumentOCRResult model."""

    def test_valid_document_result(self):
        """Test creating a valid document OCR result."""
        page1 = PageOCRResult(page_number=1, text="Page 1")
        page2 = PageOCRResult(page_number=2, text="Page 2")

        result = DocumentOCRResult(
            document_id="doc123",
            pages=[page1, page2],
            total_text="Page 1\nPage 2",
            engine=OCREngine.PADDLE,
            total_processing_time_ms=500.0,
        )
        assert result.document_id == "doc123"
        assert len(result.pages) == 2
        assert result.total_text == "Page 1\nPage 2"
        assert result.engine == OCREngine.PADDLE
        assert result.total_processing_time_ms == 500.0

    def test_default_values(self):
        """Test document result with default values."""
        result = DocumentOCRResult(document_id="doc123")
        assert result.pages == []
        assert result.total_text == ""
        assert result.engine == OCREngine.PADDLE
        assert result.total_processing_time_ms == 0.0

    def test_empty_document(self):
        """Test document result with no pages."""
        result = DocumentOCRResult(document_id="doc123")
        assert len(result.pages) == 0
        assert result.total_text == ""

    def test_single_page_document(self):
        """Test document result with single page."""
        page = PageOCRResult(page_number=1, text="Only page")
        result = DocumentOCRResult(
            document_id="doc123",
            pages=[page],
            total_text="Only page",
        )
        assert len(result.pages) == 1
        assert result.total_text == "Only page"

    def test_multi_page_document(self):
        """Test document result with multiple pages."""
        pages = [
            PageOCRResult(page_number=i, text=f"Page {i}")
            for i in range(1, 11)
        ]
        result = DocumentOCRResult(
            document_id="doc123",
            pages=pages,
        )
        assert len(result.pages) == 10
        assert result.pages[0].page_number == 1
        assert result.pages[9].page_number == 10

    def test_qwen_engine(self):
        """Test document result with Qwen engine."""
        result = DocumentOCRResult(
            document_id="doc123",
            engine=OCREngine.QWEN,
        )
        assert result.engine == OCREngine.QWEN

    def test_document_id_formats(self):
        """Test different document ID formats."""
        result1 = DocumentOCRResult(document_id="123")
        result2 = DocumentOCRResult(document_id="doc-uuid-1234-5678")
        result3 = DocumentOCRResult(document_id="path/to/doc.pdf")
        assert result1.document_id == "123"
        assert result2.document_id == "doc-uuid-1234-5678"
        assert result3.document_id == "path/to/doc.pdf"

    def test_missing_required_fields(self):
        """Test that missing required fields raise validation errors."""
        with pytest.raises(ValidationError):
            DocumentOCRResult()  # Missing document_id

    def test_serialization(self):
        """Test that document result can be serialized."""
        bbox = BoundingBox(x=0, y=0, width=100, height=20)
        block = TextBlock(text="Test", bbox=bbox)
        page = PageOCRResult(page_number=1, text="Test", blocks=[block])
        result = DocumentOCRResult(
            document_id="doc123",
            pages=[page],
            total_text="Test",
        )

        # Test model_dump (Pydantic v2) or dict (Pydantic v1)
        data = result.model_dump() if hasattr(result, "model_dump") else result.dict()
        assert data["document_id"] == "doc123"
        assert len(data["pages"]) == 1
        assert data["pages"][0]["text"] == "Test"


class TestModelIntegration:
    """Test integration between models."""

    def test_full_document_structure(self):
        """Test creating a complete document structure."""
        # Create bounding boxes
        bbox1 = BoundingBox(x=10, y=10, width=100, height=20, confidence=0.95)
        bbox2 = BoundingBox(x=10, y=35, width=100, height=20, confidence=0.92)

        # Create text blocks
        block1 = TextBlock(text="First line", bbox=bbox1, line_number=1, block_number=1)
        block2 = TextBlock(text="Second line", bbox=bbox2, line_number=2, block_number=1)

        # Create page result
        page1 = PageOCRResult(
            page_number=1,
            text="First line\nSecond line",
            blocks=[block1, block2],
            language="en",
            engine=OCREngine.PADDLE,
            confidence=0.935,
            processing_time_ms=150.5,
        )

        # Create another page
        page2 = PageOCRResult(
            page_number=2,
            text="Page 2 text",
            engine=OCREngine.PADDLE,
            confidence=0.88,
            processing_time_ms=120.3,
        )

        # Create document result
        doc = DocumentOCRResult(
            document_id="doc-12345",
            pages=[page1, page2],
            total_text="First line\nSecond line\nPage 2 text",
            engine=OCREngine.PADDLE,
            total_processing_time_ms=270.8,
        )

        # Verify structure
        assert doc.document_id == "doc-12345"
        assert len(doc.pages) == 2
        assert len(doc.pages[0].blocks) == 2
        assert doc.pages[0].blocks[0].bbox.confidence == 0.95
        assert doc.total_processing_time_ms == 270.8

    def test_mixed_engines_in_pages(self):
        """Test document with pages processed by different engines."""
        page1 = PageOCRResult(
            page_number=1,
            text="Paddle page",
            engine=OCREngine.PADDLE,
        )
        page2 = PageOCRResult(
            page_number=2,
            text="Qwen page",
            engine=OCREngine.QWEN,
        )

        # Document level engine is Paddle, but pages can differ
        doc = DocumentOCRResult(
            document_id="doc123",
            pages=[page1, page2],
            engine=OCREngine.PADDLE,
        )

        assert doc.pages[0].engine == OCREngine.PADDLE
        assert doc.pages[1].engine == OCREngine.QWEN
        assert doc.engine == OCREngine.PADDLE  # Document level
