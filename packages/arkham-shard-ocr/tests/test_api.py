"""Tests for OCR shard API routes."""

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch
from io import BytesIO

from arkham_shard_ocr.api import router, init_api, OCRRequest, OCRResponse


@pytest.fixture
def client():
    """Create a test client."""
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


@pytest.fixture
def mock_shard():
    """Create a mock shard instance."""
    shard = MagicMock()
    shard.ocr_page = AsyncMock()
    shard.ocr_document = AsyncMock()
    return shard


class TestOCRRequest:
    """Test the OCRRequest model."""

    def test_valid_request_with_document_id(self):
        """Test valid request with document_id."""
        req = OCRRequest(document_id="doc123", engine="paddle", language="en")
        assert req.document_id == "doc123"
        assert req.engine == "paddle"
        assert req.language == "en"

    def test_valid_request_with_image_path(self):
        """Test valid request with image_path."""
        req = OCRRequest(image_path="/path/to/image.png", engine="qwen")
        assert req.image_path == "/path/to/image.png"
        assert req.engine == "qwen"

    def test_default_language(self):
        """Test default language value."""
        req = OCRRequest()
        assert req.language == "en"

    def test_optional_fields(self):
        """Test all fields are optional."""
        req = OCRRequest()
        assert req.document_id is None
        assert req.image_path is None
        assert req.engine is None


class TestOCRResponse:
    """Test the OCRResponse model."""

    def test_success_response(self):
        """Test successful response."""
        resp = OCRResponse(
            success=True,
            text="Extracted text",
            pages_processed=5,
            engine="paddle",
        )
        assert resp.success is True
        assert resp.text == "Extracted text"
        assert resp.pages_processed == 5
        assert resp.engine == "paddle"
        assert resp.error is None

    def test_error_response(self):
        """Test error response."""
        resp = OCRResponse(success=False, error="Something went wrong")
        assert resp.success is False
        assert resp.error == "Something went wrong"

    def test_default_values(self):
        """Test default values."""
        resp = OCRResponse(success=True)
        assert resp.text == ""
        assert resp.pages_processed == 0
        assert resp.engine == ""
        assert resp.error is None


class TestHealthEndpoint:
    """Test the health check endpoint."""

    def test_health_check(self, client):
        """Test health endpoint returns ok."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["shard"] == "ocr"


class TestOCRPageEndpoint:
    """Test the /page endpoint."""

    def test_ocr_page_not_initialized(self, client):
        """Test OCR page when shard not initialized."""
        from arkham_shard_ocr import api
        api._shard = None

        response = client.post(
            "/page",
            json={"image_path": "/path/to/image.png"},
        )
        assert response.status_code == 503
        assert "not initialized" in response.json()["detail"]

    def test_ocr_page_missing_image_path(self, client, mock_shard):
        """Test OCR page without image_path."""
        init_api(mock_shard)

        response = client.post("/page", json={})
        assert response.status_code == 400
        assert "image_path required" in response.json()["detail"]

    def test_ocr_page_success(self, client, mock_shard):
        """Test successful OCR page."""
        init_api(mock_shard)
        mock_shard.ocr_page.return_value = {
            "text": "Extracted text from page",
            "engine": "paddle",
        }

        response = client.post(
            "/page",
            json={"image_path": "/path/to/image.png", "engine": "paddle"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["text"] == "Extracted text from page"
        assert data["pages_processed"] == 1
        assert data["engine"] == "paddle"

        # Verify shard method was called
        mock_shard.ocr_page.assert_called_once_with(
            image_path="/path/to/image.png",
            engine="paddle",
            language="en",
        )

    def test_ocr_page_with_language(self, client, mock_shard):
        """Test OCR page with custom language."""
        init_api(mock_shard)
        mock_shard.ocr_page.return_value = {"text": "你好", "engine": "paddle"}

        response = client.post(
            "/page",
            json={
                "image_path": "/path/to/chinese.png",
                "language": "zh",
            },
        )
        assert response.status_code == 200

        # Verify language was passed
        mock_shard.ocr_page.assert_called_once()
        call_args = mock_shard.ocr_page.call_args
        assert call_args.kwargs["language"] == "zh"

    def test_ocr_page_error(self, client, mock_shard):
        """Test OCR page when processing fails."""
        init_api(mock_shard)
        mock_shard.ocr_page.side_effect = Exception("OCR failed")

        response = client.post(
            "/page",
            json={"image_path": "/path/to/image.png"},
        )
        assert response.status_code == 200  # Returns 200 with error in body
        data = response.json()
        assert data["success"] is False
        assert "OCR failed" in data["error"]

    def test_ocr_page_qwen_engine(self, client, mock_shard):
        """Test OCR page with Qwen engine."""
        init_api(mock_shard)
        mock_shard.ocr_page.return_value = {"text": "Text", "engine": "qwen"}

        response = client.post(
            "/page",
            json={"image_path": "/path/to/image.png", "engine": "qwen"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["engine"] == "qwen"


class TestOCRDocumentEndpoint:
    """Test the /document endpoint."""

    def test_ocr_document_not_initialized(self, client):
        """Test OCR document when shard not initialized."""
        from arkham_shard_ocr import api
        api._shard = None

        response = client.post(
            "/document",
            json={"document_id": "doc123"},
        )
        assert response.status_code == 503
        assert "not initialized" in response.json()["detail"]

    def test_ocr_document_missing_document_id(self, client, mock_shard):
        """Test OCR document without document_id."""
        init_api(mock_shard)

        response = client.post("/document", json={})
        assert response.status_code == 400
        assert "document_id required" in response.json()["detail"]

    def test_ocr_document_success(self, client, mock_shard):
        """Test successful OCR document."""
        init_api(mock_shard)
        mock_shard.ocr_document.return_value = {
            "total_text": "Page 1\nPage 2\nPage 3",
            "pages_processed": 3,
            "engine": "paddle",
        }

        response = client.post(
            "/document",
            json={"document_id": "doc123", "engine": "paddle"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["text"] == "Page 1\nPage 2\nPage 3"
        assert data["pages_processed"] == 3
        assert data["engine"] == "paddle"

        # Verify shard method was called
        mock_shard.ocr_document.assert_called_once_with(
            document_id="doc123",
            engine="paddle",
            language="en",
        )

    def test_ocr_document_with_language(self, client, mock_shard):
        """Test OCR document with custom language."""
        init_api(mock_shard)
        mock_shard.ocr_document.return_value = {
            "total_text": "Text",
            "pages_processed": 1,
            "engine": "paddle",
        }

        response = client.post(
            "/document",
            json={
                "document_id": "doc123",
                "language": "fr",
            },
        )
        assert response.status_code == 200

        # Verify language was passed
        mock_shard.ocr_document.assert_called_once()
        call_args = mock_shard.ocr_document.call_args
        assert call_args.kwargs["language"] == "fr"

    def test_ocr_document_error(self, client, mock_shard):
        """Test OCR document when processing fails."""
        init_api(mock_shard)
        mock_shard.ocr_document.side_effect = Exception("Document not found")

        response = client.post(
            "/document",
            json={"document_id": "doc123"},
        )
        assert response.status_code == 200  # Returns 200 with error in body
        data = response.json()
        assert data["success"] is False
        assert "Document not found" in data["error"]

    def test_ocr_document_no_pages(self, client, mock_shard):
        """Test OCR document with no pages processed."""
        init_api(mock_shard)
        mock_shard.ocr_document.return_value = {
            "total_text": "",
            "pages_processed": 0,
            "engine": "paddle",
        }

        response = client.post(
            "/document",
            json={"document_id": "empty_doc"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["text"] == ""
        assert data["pages_processed"] == 0


class TestOCRUploadEndpoint:
    """Test the /upload endpoint."""

    def test_ocr_upload_not_initialized(self, client):
        """Test OCR upload when shard not initialized."""
        from arkham_shard_ocr import api
        api._shard = None

        response = client.post(
            "/upload",
            files={"file": ("test.png", BytesIO(b"fake image"), "image/png")},
        )
        assert response.status_code == 503
        assert "not initialized" in response.json()["detail"]

    def test_ocr_upload_success(self, client, mock_shard):
        """Test successful file upload and OCR."""
        init_api(mock_shard)
        mock_shard.ocr_page.return_value = {
            "text": "Uploaded image text",
            "engine": "paddle",
        }

        # Create fake image file
        fake_image = BytesIO(b"fake image data")

        response = client.post(
            "/upload",
            files={"file": ("test.png", fake_image, "image/png")},
            data={"engine": "paddle", "language": "en"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["text"] == "Uploaded image text"
        assert data["pages_processed"] == 1
        assert data["engine"] == "paddle"

        # Verify ocr_page was called
        mock_shard.ocr_page.assert_called_once()

    def test_ocr_upload_with_qwen(self, client, mock_shard):
        """Test upload with Qwen engine."""
        init_api(mock_shard)
        mock_shard.ocr_page.return_value = {"text": "Text", "engine": "qwen"}

        fake_image = BytesIO(b"fake image data")

        response = client.post(
            "/upload",
            files={"file": ("test.jpg", fake_image, "image/jpeg")},
            data={"engine": "qwen", "language": "en"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["engine"] == "qwen"

    def test_ocr_upload_custom_language(self, client, mock_shard):
        """Test upload with custom language."""
        init_api(mock_shard)
        mock_shard.ocr_page.return_value = {"text": "Text", "engine": "paddle"}

        fake_image = BytesIO(b"fake image data")

        response = client.post(
            "/upload",
            files={"file": ("test.png", fake_image, "image/png")},
            params={"language": "zh"},  # Query params, not form data
        )
        assert response.status_code == 200

        # Verify language was passed
        call_args = mock_shard.ocr_page.call_args
        assert call_args.kwargs["language"] == "zh"

    def test_ocr_upload_error(self, client, mock_shard):
        """Test upload when OCR fails."""
        init_api(mock_shard)
        mock_shard.ocr_page.side_effect = Exception("Invalid image format")

        fake_image = BytesIO(b"not an image")

        response = client.post(
            "/upload",
            files={"file": ("bad.txt", fake_image, "text/plain")},
        )
        assert response.status_code == 200  # Returns 200 with error in body
        data = response.json()
        assert data["success"] is False
        assert "Invalid image format" in data["error"]

    def test_ocr_upload_no_filename(self, client, mock_shard):
        """Test upload with simple filename."""
        init_api(mock_shard)
        mock_shard.ocr_page.return_value = {"text": "Text", "engine": "paddle"}

        fake_image = BytesIO(b"fake image data")

        # Test with a simple filename (FastAPI requires valid filename)
        response = client.post(
            "/upload",
            files={"file": ("image.png", fake_image, "image/png")},
        )
        assert response.status_code == 200
        assert response.json()["success"] is True

    @patch("os.unlink")
    def test_ocr_upload_cleanup(self, mock_unlink, client, mock_shard):
        """Test that temporary file is cleaned up."""
        init_api(mock_shard)
        mock_shard.ocr_page.return_value = {"text": "Text", "engine": "paddle"}

        fake_image = BytesIO(b"fake image data")

        response = client.post(
            "/upload",
            files={"file": ("test.png", fake_image, "image/png")},
        )
        assert response.status_code == 200

        # Verify temp file was deleted
        mock_unlink.assert_called_once()

    @patch("os.unlink")
    def test_ocr_upload_cleanup_on_error(self, mock_unlink, client, mock_shard):
        """Test that temporary file is cleaned up even on error."""
        init_api(mock_shard)
        mock_shard.ocr_page.side_effect = Exception("OCR failed")

        fake_image = BytesIO(b"fake image data")

        response = client.post(
            "/upload",
            files={"file": ("test.png", fake_image, "image/png")},
        )
        assert response.status_code == 200

        # Verify cleanup still happens
        mock_unlink.assert_called_once()


class TestInitAPI:
    """Test the init_api function."""

    def test_init_api_sets_shard(self, mock_shard):
        """Test that init_api sets the global shard."""
        from arkham_shard_ocr import api

        init_api(mock_shard)
        assert api._shard == mock_shard

    def test_init_api_can_be_called_multiple_times(self, mock_shard):
        """Test that init_api can be called multiple times."""
        from arkham_shard_ocr import api

        shard1 = MagicMock()
        shard2 = MagicMock()

        init_api(shard1)
        assert api._shard == shard1

        init_api(shard2)
        assert api._shard == shard2
