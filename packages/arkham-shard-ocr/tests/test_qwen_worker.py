"""Tests for Qwen VLM OCR worker."""

import pytest
import pytest_asyncio
from unittest.mock import MagicMock, AsyncMock, patch
import base64
import json

from arkham_shard_ocr.workers.qwen_worker import (
    QwenWorker,
    DEFAULT_ENDPOINT,
    DEFAULT_MODEL,
    OCR_SYSTEM_PROMPT,
    DEFAULT_OCR_PROMPT,
)


class TestQwenWorkerMetadata:
    """Test QwenWorker metadata."""

    def test_worker_pool(self):
        """Test worker has correct pool."""
        assert QwenWorker.pool == "gpu-qwen"

    def test_worker_name(self):
        """Test worker has name."""
        assert QwenWorker.name == "QwenWorker"

    def test_worker_timeout(self):
        """Test worker has timeout configured."""
        assert QwenWorker.job_timeout == 180.0

    def test_default_endpoint(self):
        """Test default endpoint is LM Studio."""
        assert "localhost:1234" in DEFAULT_ENDPOINT

    def test_default_model(self):
        """Test default model is Qwen."""
        assert "qwen" in DEFAULT_MODEL.lower()


class TestQwenWorkerInitialization:
    """Test QwenWorker initialization."""

    def test_worker_creation(self):
        """Test creating a worker instance."""
        worker = QwenWorker(database_url="postgresql://localhost/test")
        assert worker._client is None

    @pytest.mark.asyncio
    async def test_get_client_creates_client(self):
        """Test client is created on first use."""
        worker = QwenWorker(database_url="postgresql://localhost/test")

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client

            client = await worker._get_client()

            assert client == mock_client
            mock_client_class.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_client_reuses_client(self):
        """Test client is reused."""
        worker = QwenWorker(database_url="postgresql://localhost/test")

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client

            client1 = await worker._get_client()
            client2 = await worker._get_client()

            assert client1 == client2
            # Should only create once
            mock_client_class.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_closes_client(self):
        """Test cleanup closes HTTP client."""
        worker = QwenWorker(database_url="postgresql://localhost/test")

        mock_client = AsyncMock()
        worker._client = mock_client

        await worker.cleanup()

        mock_client.aclose.assert_called_once()
        assert worker._client is None


class TestQwenWorkerProcessJob:
    """Test QwenWorker job processing."""

    @pytest.mark.asyncio
    async def test_process_job_single_image_path(self):
        """Test processing single image from path."""
        worker = QwenWorker(database_url="postgresql://localhost/test")

        # Mock HTTP response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": "Extracted text from image"
                    }
                }
            ]
        }

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch.object(worker, "_get_client", return_value=mock_client), \
             patch("os.path.exists", return_value=True), \
             patch("builtins.open", create=True) as mock_open:

            mock_file = MagicMock()
            mock_file.read.return_value = b"fake image bytes"
            mock_open.return_value.__enter__.return_value = mock_file

            payload = {
                "image_path": "/path/to/image.png",
            }

            result = await worker.process_job("job-123", payload)

            assert result["success"] is True
            assert result["text"] == "Extracted text from image"
            assert result["source"] == "/path/to/image.png"
            assert result["endpoint"] == DEFAULT_ENDPOINT
            assert result["model"] == DEFAULT_MODEL

    @pytest.mark.asyncio
    async def test_process_job_image_not_found(self):
        """Test processing with non-existent image."""
        worker = QwenWorker(database_url="postgresql://localhost/test")

        with patch("os.path.exists", return_value=False):
            payload = {"image_path": "/missing/image.png"}

            with pytest.raises(FileNotFoundError):
                await worker.process_job("job-123", payload)

    @pytest.mark.asyncio
    async def test_process_job_base64_image(self):
        """Test processing base64 encoded image."""
        worker = QwenWorker(database_url="postgresql://localhost/test")

        fake_img_data = b"fake image bytes"
        fake_b64 = base64.b64encode(fake_img_data).decode("utf-8")

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Test text"}}]
        }

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch.object(worker, "_get_client", return_value=mock_client):
            payload = {
                "image_base64": fake_b64,
                "filename": "test.png",
            }

            result = await worker.process_job("job-123", payload)

            assert result["success"] is True
            assert result["text"] == "Test text"
            assert result["source"] == "test.png"

    @pytest.mark.asyncio
    async def test_process_job_no_image_provided(self):
        """Test processing without image."""
        worker = QwenWorker(database_url="postgresql://localhost/test")

        payload = {}

        with pytest.raises(ValueError, match="Must provide"):
            await worker.process_job("job-123", payload)

    @pytest.mark.asyncio
    async def test_process_job_custom_endpoint(self):
        """Test processing with custom endpoint."""
        worker = QwenWorker(database_url="postgresql://localhost/test")

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Text"}}]
        }

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch.object(worker, "_get_client", return_value=mock_client), \
             patch("os.path.exists", return_value=True), \
             patch("builtins.open", create=True) as mock_open:

            mock_file = MagicMock()
            mock_file.read.return_value = b"fake"
            mock_open.return_value.__enter__.return_value = mock_file

            custom_endpoint = "http://custom-server:8000/v1"
            payload = {
                "image_path": "/test.png",
                "endpoint": custom_endpoint,
            }

            result = await worker.process_job("job-123", payload)

            # Verify endpoint was used
            assert result["endpoint"] == custom_endpoint
            mock_client.post.assert_called_once()
            call_args = mock_client.post.call_args
            assert custom_endpoint in call_args[0][0]

    @pytest.mark.asyncio
    async def test_process_job_custom_model(self):
        """Test processing with custom model."""
        worker = QwenWorker(database_url="postgresql://localhost/test")

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Text"}}]
        }

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch.object(worker, "_get_client", return_value=mock_client), \
             patch("os.path.exists", return_value=True), \
             patch("builtins.open", create=True) as mock_open:

            mock_file = MagicMock()
            mock_file.read.return_value = b"fake"
            mock_open.return_value.__enter__.return_value = mock_file

            custom_model = "llava-v1.6"
            payload = {
                "image_path": "/test.png",
                "model": custom_model,
            }

            result = await worker.process_job("job-123", payload)

            # Verify model was used
            assert result["model"] == custom_model
            mock_client.post.assert_called_once()
            request_body = mock_client.post.call_args.kwargs["json"]
            assert request_body["model"] == custom_model

    @pytest.mark.asyncio
    async def test_process_job_custom_prompt(self):
        """Test processing with custom prompt."""
        worker = QwenWorker(database_url="postgresql://localhost/test")

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Text"}}]
        }

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch.object(worker, "_get_client", return_value=mock_client), \
             patch("os.path.exists", return_value=True), \
             patch("builtins.open", create=True) as mock_open:

            mock_file = MagicMock()
            mock_file.read.return_value = b"fake"
            mock_open.return_value.__enter__.return_value = mock_file

            custom_prompt = "Extract handwritten notes"
            payload = {
                "image_path": "/test.png",
                "prompt": custom_prompt,
            }

            await worker.process_job("job-123", payload)

            # Verify prompt was used
            request_body = mock_client.post.call_args.kwargs["json"]
            user_message = request_body["messages"][1]
            text_content = [c for c in user_message["content"] if c["type"] == "text"][0]
            assert text_content["text"] == custom_prompt

    @pytest.mark.asyncio
    async def test_process_job_temperature(self):
        """Test processing with custom temperature."""
        worker = QwenWorker(database_url="postgresql://localhost/test")

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Text"}}]
        }

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch.object(worker, "_get_client", return_value=mock_client), \
             patch("os.path.exists", return_value=True), \
             patch("builtins.open", create=True) as mock_open:

            mock_file = MagicMock()
            mock_file.read.return_value = b"fake"
            mock_open.return_value.__enter__.return_value = mock_file

            payload = {
                "image_path": "/test.png",
                "temperature": 0.5,
            }

            await worker.process_job("job-123", payload)

            # Verify temperature was used
            request_body = mock_client.post.call_args.kwargs["json"]
            assert request_body["temperature"] == 0.5

    @pytest.mark.asyncio
    async def test_process_job_connection_error(self):
        """Test handling connection error."""
        worker = QwenWorker(database_url="postgresql://localhost/test")

        import httpx

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection failed"))

        with patch.object(worker, "_get_client", return_value=mock_client), \
             patch("os.path.exists", return_value=True), \
             patch("builtins.open", create=True) as mock_open:

            mock_file = MagicMock()
            mock_file.read.return_value = b"fake"
            mock_open.return_value.__enter__.return_value = mock_file

            payload = {"image_path": "/test.png"}

            with pytest.raises(ConnectionError, match="Failed to connect"):
                await worker.process_job("job-123", payload)

    @pytest.mark.asyncio
    async def test_process_job_http_error(self):
        """Test handling HTTP error."""
        worker = QwenWorker(database_url="postgresql://localhost/test")

        import httpx

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal server error"

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "Error", request=MagicMock(), response=mock_response
            )
        )

        with patch.object(worker, "_get_client", return_value=mock_client), \
             patch("os.path.exists", return_value=True), \
             patch("builtins.open", create=True) as mock_open:

            mock_file = MagicMock()
            mock_file.read.return_value = b"fake"
            mock_open.return_value.__enter__.return_value = mock_file

            payload = {"image_path": "/test.png"}

            with pytest.raises(RuntimeError, match="VLM API error"):
                await worker.process_job("job-123", payload)

    @pytest.mark.asyncio
    async def test_process_job_image_types(self):
        """Test processing different image types."""
        worker = QwenWorker(database_url="postgresql://localhost/test")

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Text"}}]
        }

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch.object(worker, "_get_client", return_value=mock_client), \
             patch("os.path.exists", return_value=True), \
             patch("builtins.open", create=True) as mock_open:

            mock_file = MagicMock()
            mock_file.read.return_value = b"fake"
            mock_open.return_value.__enter__.return_value = mock_file

            # Test different extensions
            for ext, expected_mime in [
                (".png", "image/png"),
                (".jpg", "image/jpeg"),
                (".jpeg", "image/jpeg"),
                (".gif", "image/gif"),
                (".webp", "image/webp"),
                (".bmp", "image/png"),  # Unknown defaults to png
            ]:
                payload = {"image_path": f"/test{ext}"}
                await worker.process_job("job-123", payload)

                # Verify correct mime type was used
                request_body = mock_client.post.call_args.kwargs["json"]
                user_message = request_body["messages"][1]
                image_content = [c for c in user_message["content"] if c["type"] == "image_url"][0]
                assert expected_mime in image_content["image_url"]["url"]


class TestQwenWorkerTableExtraction:
    """Test table extraction functionality."""

    @pytest.mark.asyncio
    async def test_extract_tables_success(self):
        """Test successful table extraction."""
        worker = QwenWorker(database_url="postgresql://localhost/test")

        # Mock table extraction response
        table_data = [
            {
                "headers": ["Name", "Age", "City"],
                "rows": [
                    ["Alice", "30", "NYC"],
                    ["Bob", "25", "LA"],
                ],
            }
        ]

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": json.dumps(table_data)}}]
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch.object(worker, "_get_client", return_value=mock_client):
            tables = await worker._extract_tables(
                job_id="job-123",
                image_b64="fake_base64",
                mime_type="image/png",
                endpoint="http://localhost:1234/v1",
                model="qwen",
                max_tokens=4096,
            )

            assert len(tables) == 1
            assert tables[0]["headers"] == ["Name", "Age", "City"]
            assert len(tables[0]["rows"]) == 2

    @pytest.mark.asyncio
    async def test_extract_tables_no_tables(self):
        """Test table extraction when no tables found."""
        worker = QwenWorker(database_url="postgresql://localhost/test")

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "[]"}}]
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch.object(worker, "_get_client", return_value=mock_client):
            tables = await worker._extract_tables(
                job_id="job-123",
                image_b64="fake",
                mime_type="image/png",
                endpoint="http://localhost:1234/v1",
                model="qwen",
                max_tokens=4096,
            )

            assert tables == []

    @pytest.mark.asyncio
    async def test_extract_tables_with_markdown(self):
        """Test table extraction with markdown code blocks."""
        worker = QwenWorker(database_url="postgresql://localhost/test")

        table_data = [{"headers": ["A"], "rows": [["1"]]}]
        content_with_markdown = f"```json\n{json.dumps(table_data)}\n```"

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": content_with_markdown}}]
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch.object(worker, "_get_client", return_value=mock_client):
            tables = await worker._extract_tables(
                job_id="job-123",
                image_b64="fake",
                mime_type="image/png",
                endpoint="http://localhost:1234/v1",
                model="qwen",
                max_tokens=4096,
            )

            assert len(tables) == 1

    @pytest.mark.asyncio
    async def test_extract_tables_error(self):
        """Test table extraction error handling."""
        worker = QwenWorker(database_url="postgresql://localhost/test")

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=Exception("API error"))

        with patch.object(worker, "_get_client", return_value=mock_client):
            tables = await worker._extract_tables(
                job_id="job-123",
                image_b64="fake",
                mime_type="image/png",
                endpoint="http://localhost:1234/v1",
                model="qwen",
                max_tokens=4096,
            )

            # Should return empty list on error
            assert tables == []

    @pytest.mark.asyncio
    async def test_process_job_with_table_extraction(self):
        """Test processing with table extraction enabled."""
        worker = QwenWorker(database_url="postgresql://localhost/test")

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Text with table"}}]
        }

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        table_data = [{"headers": ["A"], "rows": [["1"]]}]

        with patch.object(worker, "_get_client", return_value=mock_client), \
             patch.object(worker, "_extract_tables", return_value=table_data), \
             patch("os.path.exists", return_value=True), \
             patch("builtins.open", create=True) as mock_open:

            mock_file = MagicMock()
            mock_file.read.return_value = b"fake"
            mock_open.return_value.__enter__.return_value = mock_file

            payload = {
                "image_path": "/test.png",
                "extract_tables": True,
            }

            result = await worker.process_job("job-123", payload)

            assert result["success"] is True
            assert "tables" in result
            assert len(result["tables"]) == 1


class TestQwenWorkerBatchMode:
    """Test QwenWorker batch processing."""

    @pytest.mark.asyncio
    async def test_process_batch(self):
        """Test batch processing multiple images."""
        worker = QwenWorker(database_url="postgresql://localhost/test")

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Text"}}]
        }

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch.object(worker, "_get_client", return_value=mock_client), \
             patch("os.path.exists", return_value=True), \
             patch("builtins.open", create=True) as mock_open:

            mock_file = MagicMock()
            mock_file.read.return_value = b"fake"
            mock_open.return_value.__enter__.return_value = mock_file

            payload = {
                "batch": True,
                "images": [
                    {"path": "/img1.png"},
                    {"path": "/img2.png"},
                ],
            }

            result = await worker.process_job("job-123", payload)

            assert result["count"] == 2
            assert len(result["results"]) == 2
            assert all(r["success"] for r in result["results"])

    @pytest.mark.asyncio
    async def test_process_batch_empty(self):
        """Test batch processing with no images."""
        worker = QwenWorker(database_url="postgresql://localhost/test")

        payload = {
            "batch": True,
            "images": [],
        }

        with pytest.raises(ValueError, match="requires 'images' field"):
            await worker.process_job("job-123", payload)

    @pytest.mark.asyncio
    async def test_process_batch_with_errors(self):
        """Test batch processing with some failures."""
        worker = QwenWorker(database_url="postgresql://localhost/test")

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Text"}}]
        }

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch.object(worker, "_get_client", return_value=mock_client), \
             patch("os.path.exists", side_effect=[True, False]), \
             patch("builtins.open", create=True) as mock_open:

            mock_file = MagicMock()
            mock_file.read.return_value = b"fake"
            mock_open.return_value.__enter__.return_value = mock_file

            payload = {
                "batch": True,
                "images": [
                    {"path": "/img1.png"},
                    {"path": "/missing.png"},
                ],
            }

            result = await worker.process_job("job-123", payload)

            assert result["count"] == 2
            assert result["results"][0]["success"] is True
            assert result["results"][1]["success"] is False
            assert result["success"] is False


class TestQwenWorkerHelpers:
    """Test helper functions."""

    def test_run_qwen_worker_function_exists(self):
        """Test run_qwen_worker function exists."""
        from arkham_shard_ocr.workers.qwen_worker import run_qwen_worker
        assert callable(run_qwen_worker)

    def test_ocr_system_prompt_exists(self):
        """Test OCR system prompt is defined."""
        assert len(OCR_SYSTEM_PROMPT) > 0
        assert "robotic" in OCR_SYSTEM_PROMPT.lower() or "ocr" in OCR_SYSTEM_PROMPT.lower()

    def test_default_ocr_prompt_exists(self):
        """Test default OCR prompt is defined."""
        assert len(DEFAULT_OCR_PROMPT) > 0
        assert "transcribe" in DEFAULT_OCR_PROMPT.lower()
