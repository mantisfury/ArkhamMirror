"""Tests for PaddleOCR worker."""

import pytest
import pytest_asyncio
from unittest.mock import MagicMock, AsyncMock, patch
import base64
from io import BytesIO

from arkham_shard_ocr.workers.paddle_worker import PaddleWorker


class TestPaddleWorkerMetadata:
    """Test PaddleWorker metadata."""

    def test_worker_pool(self):
        """Test worker has correct pool."""
        assert PaddleWorker.pool == "gpu-paddle"

    def test_worker_name(self):
        """Test worker has name."""
        assert PaddleWorker.name == "PaddleWorker"

    def test_worker_timeout(self):
        """Test worker has timeout configured."""
        assert PaddleWorker.job_timeout == 120.0


class TestPaddleWorkerEngine:
    """Test PaddleWorker engine management."""

    def setup_method(self):
        """Setup before each test."""
        PaddleWorker._ocr_engine = None
        PaddleWorker._lang = None

    def teardown_method(self):
        """Reset class-level engine between tests."""
        PaddleWorker._ocr_engine = None
        PaddleWorker._lang = None

    def test_get_engine_lazy_loads(self):
        """Test engine is lazy loaded on first use."""
        # Mock the import before calling _get_engine
        mock_paddleocr_module = MagicMock()
        mock_engine = MagicMock()
        mock_paddleocr_class = MagicMock(return_value=mock_engine)
        mock_paddleocr_module.PaddleOCR = mock_paddleocr_class

        with patch.dict("sys.modules", {"paddleocr": mock_paddleocr_module}):
            engine = PaddleWorker._get_engine()

            assert engine == mock_engine
            mock_paddleocr_class.assert_called_once_with(
                use_angle_cls=True,
                lang="en",
                show_log=False,
            )

    def test_get_engine_reuses_instance(self):
        """Test engine instance is reused."""
        mock_paddleocr_module = MagicMock()
        mock_engine = MagicMock()
        mock_paddleocr_class = MagicMock(return_value=mock_engine)
        mock_paddleocr_module.PaddleOCR = mock_paddleocr_class

        with patch.dict("sys.modules", {"paddleocr": mock_paddleocr_module}):
            engine1 = PaddleWorker._get_engine()
            engine2 = PaddleWorker._get_engine()

            assert engine1 == engine2
            # Should only initialize once
            mock_paddleocr_class.assert_called_once()

    def test_get_engine_with_custom_language(self):
        """Test engine with custom language."""
        mock_paddleocr_module = MagicMock()
        mock_engine = MagicMock()
        mock_paddleocr_class = MagicMock(return_value=mock_engine)
        mock_paddleocr_module.PaddleOCR = mock_paddleocr_class

        with patch.dict("sys.modules", {"paddleocr": mock_paddleocr_module}):
            engine = PaddleWorker._get_engine(lang="zh")

            mock_paddleocr_class.assert_called_once_with(
                use_angle_cls=True,
                lang="zh",
                show_log=False,
            )

    def test_get_engine_reinitializes_on_language_change(self):
        """Test engine is reinitialized when language changes."""
        mock_paddleocr_module = MagicMock()
        mock_engine1 = MagicMock()
        mock_engine2 = MagicMock()
        mock_paddleocr_class = MagicMock(side_effect=[mock_engine1, mock_engine2])
        mock_paddleocr_module.PaddleOCR = mock_paddleocr_class

        with patch.dict("sys.modules", {"paddleocr": mock_paddleocr_module}):
            engine1 = PaddleWorker._get_engine(lang="en")
            engine2 = PaddleWorker._get_engine(lang="zh")

            # Should initialize twice due to language change
            assert mock_paddleocr_class.call_count == 2
            assert engine1 == mock_engine1
            assert engine2 == mock_engine2

    def test_get_engine_without_angle_cls(self):
        """Test engine without angle classification."""
        mock_paddleocr_module = MagicMock()
        mock_engine = MagicMock()
        mock_paddleocr_class = MagicMock(return_value=mock_engine)
        mock_paddleocr_module.PaddleOCR = mock_paddleocr_class

        with patch.dict("sys.modules", {"paddleocr": mock_paddleocr_module}):
            engine = PaddleWorker._get_engine(use_angle_cls=False)

            mock_paddleocr_class.assert_called_once_with(
                use_angle_cls=False,
                lang="en",
                show_log=False,
            )

    def test_get_engine_missing_paddleocr(self):
        """Test error when PaddleOCR not installed."""
        # Temporarily remove paddleocr from sys.modules
        import sys
        paddleocr_backup = sys.modules.get("paddleocr")
        if "paddleocr" in sys.modules:
            del sys.modules["paddleocr"]

        try:
            # Mock the import to fail
            with patch("builtins.__import__", side_effect=ImportError("No module named 'paddleocr'")):
                with pytest.raises(ImportError, match="paddleocr not installed"):
                    PaddleWorker._get_engine()
        finally:
            # Restore paddleocr if it was there
            if paddleocr_backup is not None:
                sys.modules["paddleocr"] = paddleocr_backup


class TestPaddleWorkerProcessJob:
    """Test PaddleWorker job processing."""

    def setup_method(self):
        """Setup before each test."""
        PaddleWorker._ocr_engine = None
        PaddleWorker._lang = None

    def teardown_method(self):
        """Reset class-level engine between tests."""
        PaddleWorker._ocr_engine = None
        PaddleWorker._lang = None

    @pytest.mark.asyncio
    async def test_process_job_single_image_path(self):
        """Test processing single image from path."""
        worker = PaddleWorker(redis_url="redis://localhost")

        # Mock the engine and file operations
        mock_engine = MagicMock()
        mock_engine.ocr.return_value = [
            [
                [
                    [[0, 0], [100, 0], [100, 20], [0, 20]],
                    ("Hello World", 0.95),
                ]
            ]
        ]

        with patch.object(PaddleWorker, "_get_engine", return_value=mock_engine), \
             patch("os.path.exists", return_value=True), \
             patch("PIL.Image.open") as mock_image:

            mock_img = MagicMock()
            mock_image.return_value = mock_img

            payload = {
                "image_path": "/path/to/image.png",
                "lang": "en",
            }

            result = await worker.process_job("job-123", payload)

            assert result["success"] is True
            assert result["text"] == "Hello World"
            assert len(result["lines"]) == 1
            assert result["lines"][0]["text"] == "Hello World"
            assert result["lines"][0]["confidence"] == 0.95
            assert result["source"] == "/path/to/image.png"

    @pytest.mark.asyncio
    async def test_process_job_image_not_found(self):
        """Test processing with non-existent image."""
        worker = PaddleWorker(redis_url="redis://localhost")

        # Mock paddleocr module
        mock_paddleocr_module = MagicMock()
        mock_engine = MagicMock()
        mock_paddleocr_module.PaddleOCR = MagicMock(return_value=mock_engine)

        with patch.dict("sys.modules", {"paddleocr": mock_paddleocr_module}), \
             patch("os.path.exists", return_value=False):
            payload = {"image_path": "/missing/image.png"}

            with pytest.raises(FileNotFoundError):
                await worker.process_job("job-123", payload)

    @pytest.mark.asyncio
    async def test_process_job_base64_image(self):
        """Test processing base64 encoded image."""
        worker = PaddleWorker(redis_url="redis://localhost")

        # Create fake image
        fake_img_data = b"fake image bytes"
        fake_b64 = base64.b64encode(fake_img_data).decode("utf-8")

        mock_engine = MagicMock()
        mock_engine.ocr.return_value = [
            [
                [
                    [[0, 0], [50, 0], [50, 10], [0, 10]],
                    ("Test", 0.88),
                ]
            ]
        ]

        with patch.object(PaddleWorker, "_get_engine", return_value=mock_engine), \
             patch("PIL.Image.open") as mock_image:

            mock_img = MagicMock()
            mock_image.return_value = mock_img

            payload = {
                "image_base64": fake_b64,
                "filename": "test.png",
            }

            result = await worker.process_job("job-123", payload)

            assert result["success"] is True
            assert result["text"] == "Test"
            assert result["source"] == "test.png"

    @pytest.mark.asyncio
    async def test_process_job_no_image_provided(self):
        """Test processing without image."""
        worker = PaddleWorker(redis_url="redis://localhost")

        # Mock paddleocr module
        mock_paddleocr_module = MagicMock()
        mock_engine = MagicMock()
        mock_paddleocr_module.PaddleOCR = MagicMock(return_value=mock_engine)

        with patch.dict("sys.modules", {"paddleocr": mock_paddleocr_module}):
            payload = {}

            with pytest.raises(ValueError, match="Must provide"):
                await worker.process_job("job-123", payload)

    @pytest.mark.asyncio
    async def test_process_job_multiple_lines(self):
        """Test processing image with multiple text lines."""
        worker = PaddleWorker(redis_url="redis://localhost")

        mock_engine = MagicMock()
        mock_engine.ocr.return_value = [
            [
                [
                    [[0, 0], [100, 0], [100, 20], [0, 20]],
                    ("Line 1", 0.95),
                ],
                [
                    [[0, 25], [100, 25], [100, 45], [0, 45]],
                    ("Line 2", 0.92),
                ],
                [
                    [[0, 50], [100, 50], [100, 70], [0, 70]],
                    ("Line 3", 0.89),
                ],
            ]
        ]

        with patch.object(PaddleWorker, "_get_engine", return_value=mock_engine), \
             patch("os.path.exists", return_value=True), \
             patch("PIL.Image.open"):

            payload = {"image_path": "/test.png"}

            result = await worker.process_job("job-123", payload)

            assert result["success"] is True
            assert result["text"] == "Line 1\nLine 2\nLine 3"
            assert len(result["lines"]) == 3
            assert result["line_count"] == 3

    @pytest.mark.asyncio
    async def test_process_job_empty_result(self):
        """Test processing image with no text detected."""
        worker = PaddleWorker(redis_url="redis://localhost")

        mock_engine = MagicMock()
        mock_engine.ocr.return_value = [[]]  # No text detected

        with patch.object(PaddleWorker, "_get_engine", return_value=mock_engine), \
             patch("os.path.exists", return_value=True), \
             patch("PIL.Image.open"):

            payload = {"image_path": "/blank.png"}

            result = await worker.process_job("job-123", payload)

            assert result["success"] is True
            assert result["text"] == ""
            assert len(result["lines"]) == 0

    @pytest.mark.asyncio
    async def test_process_job_detection_only(self):
        """Test detection only mode."""
        worker = PaddleWorker(redis_url="redis://localhost")

        mock_engine = MagicMock()
        mock_engine.ocr.return_value = [[]]

        with patch.object(PaddleWorker, "_get_engine", return_value=mock_engine), \
             patch("os.path.exists", return_value=True), \
             patch("PIL.Image.open"):

            payload = {
                "image_path": "/test.png",
                "det_only": True,
            }

            result = await worker.process_job("job-123", payload)

            # Verify OCR was called with rec=False
            mock_engine.ocr.assert_called_once()
            call_args = mock_engine.ocr.call_args
            assert call_args.kwargs.get("rec") is False
            assert result["det_only"] is True

    @pytest.mark.asyncio
    async def test_process_job_custom_language(self):
        """Test processing with custom language."""
        worker = PaddleWorker(redis_url="redis://localhost")

        mock_engine = MagicMock()
        mock_engine.ocr.return_value = [[]]

        with patch.object(PaddleWorker, "_get_engine", return_value=mock_engine) as mock_get_engine, \
             patch("os.path.exists", return_value=True), \
             patch("PIL.Image.open"):

            payload = {
                "image_path": "/test.png",
                "lang": "zh",
            }

            await worker.process_job("job-123", payload)

            # Verify engine was requested with correct language
            mock_get_engine.assert_called_once()
            call_args = mock_get_engine.call_args
            assert call_args.kwargs.get("lang") == "zh"


class TestPaddleWorkerBatchMode:
    """Test PaddleWorker batch processing."""

    def setup_method(self):
        """Setup before each test."""
        PaddleWorker._ocr_engine = None
        PaddleWorker._lang = None

    def teardown_method(self):
        """Reset class-level engine between tests."""
        PaddleWorker._ocr_engine = None
        PaddleWorker._lang = None

    @pytest.mark.asyncio
    async def test_process_batch(self):
        """Test batch processing multiple images."""
        worker = PaddleWorker(redis_url="redis://localhost")

        mock_engine = MagicMock()
        mock_engine.ocr.return_value = [
            [
                [
                    [[0, 0], [100, 0], [100, 20], [0, 20]],
                    ("Text", 0.9),
                ]
            ]
        ]

        with patch.object(PaddleWorker, "_get_engine", return_value=mock_engine), \
             patch("os.path.exists", return_value=True), \
             patch("PIL.Image.open"):

            payload = {
                "batch": True,
                "images": [
                    {"path": "/img1.png"},
                    {"path": "/img2.png"},
                    {"path": "/img3.png"},
                ],
            }

            result = await worker.process_job("job-123", payload)

            assert result["count"] == 3
            assert len(result["results"]) == 3
            assert all(r["success"] for r in result["results"])

    @pytest.mark.asyncio
    async def test_process_batch_empty(self):
        """Test batch processing with no images."""
        worker = PaddleWorker(redis_url="redis://localhost")

        # Mock paddleocr module
        mock_paddleocr_module = MagicMock()
        mock_engine = MagicMock()
        mock_paddleocr_module.PaddleOCR = MagicMock(return_value=mock_engine)

        with patch.dict("sys.modules", {"paddleocr": mock_paddleocr_module}):
            payload = {
                "batch": True,
                "images": [],
            }

            with pytest.raises(ValueError, match="requires 'images' field"):
                await worker.process_job("job-123", payload)

    @pytest.mark.asyncio
    async def test_process_batch_with_errors(self):
        """Test batch processing with some failures."""
        worker = PaddleWorker(redis_url="redis://localhost")

        mock_engine = MagicMock()
        mock_engine.ocr.return_value = [
            [
                [
                    [[0, 0], [100, 0], [100, 20], [0, 20]],
                    ("Text", 0.9),
                ]
            ]
        ]

        with patch.object(PaddleWorker, "_get_engine", return_value=mock_engine), \
             patch("os.path.exists", side_effect=[True, False, True]), \
             patch("PIL.Image.open"):

            payload = {
                "batch": True,
                "images": [
                    {"path": "/img1.png"},
                    {"path": "/missing.png"},  # Will fail
                    {"path": "/img3.png"},
                ],
            }

            result = await worker.process_job("job-123", payload)

            assert result["count"] == 3
            assert len(result["results"]) == 3
            assert result["results"][0]["success"] is True
            assert result["results"][1]["success"] is False
            assert "error" in result["results"][1]
            assert result["results"][2]["success"] is True
            assert result["success"] is False  # Overall failed due to one error

    @pytest.mark.asyncio
    async def test_process_batch_mixed_formats(self):
        """Test batch with both path and base64 images."""
        worker = PaddleWorker(redis_url="redis://localhost")

        fake_b64 = base64.b64encode(b"fake").decode("utf-8")

        mock_engine = MagicMock()
        mock_engine.ocr.return_value = [[]]

        with patch.object(PaddleWorker, "_get_engine", return_value=mock_engine), \
             patch("os.path.exists", return_value=True), \
             patch("PIL.Image.open"):

            payload = {
                "batch": True,
                "images": [
                    {"path": "/img1.png"},
                    {"base64": fake_b64, "filename": "img2.png"},
                ],
            }

            result = await worker.process_job("job-123", payload)

            assert result["count"] == 2
            assert result["results"][0]["source"] == "/img1.png"
            assert result["results"][1]["source"] == "img2.png"


class TestPaddleWorkerHelpers:
    """Test helper functions."""

    def test_run_paddle_worker_function_exists(self):
        """Test run_paddle_worker function exists."""
        from arkham_shard_ocr.workers.paddle_worker import run_paddle_worker
        assert callable(run_paddle_worker)
