"""
ModelService - ML Model Management for Air-Gap Deployments.

Handles checking, downloading, and managing ML models used by shards:
- sentence-transformers (embeddings)
- PaddleOCR (OCR)

Supports offline/air-gap mode where models must be pre-cached.
"""

import logging
import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)


class ModelType(str, Enum):
    """Types of ML models managed by this service."""
    EMBEDDING = "embedding"
    OCR = "ocr"
    VISION = "vision"


class ModelStatus(str, Enum):
    """Installation status of a model."""
    INSTALLED = "installed"
    NOT_INSTALLED = "not_installed"
    DOWNLOADING = "downloading"
    ERROR = "error"
    UNKNOWN = "unknown"


@dataclass
class ModelInfo:
    """Information about an ML model."""
    id: str
    name: str
    model_type: ModelType
    description: str
    size_mb: float
    status: ModelStatus = ModelStatus.UNKNOWN
    path: str | None = None
    error: str | None = None
    required_by: list[str] = field(default_factory=list)
    is_default: bool = False


# Registry of known models
KNOWN_MODELS: dict[str, ModelInfo] = {
    # Embedding models (sentence-transformers / HuggingFace)
    "all-MiniLM-L6-v2": ModelInfo(
        id="all-MiniLM-L6-v2",
        name="all-MiniLM-L6-v2",
        model_type=ModelType.EMBEDDING,
        description="Fast, lightweight embedding model (384 dimensions). Good balance of speed and quality.",
        size_mb=90,
        required_by=["embed"],
        is_default=True,
    ),
    "all-mpnet-base-v2": ModelInfo(
        id="all-mpnet-base-v2",
        name="all-mpnet-base-v2",
        model_type=ModelType.EMBEDDING,
        description="Higher quality embedding model (768 dimensions). Better semantic understanding.",
        size_mb=420,
        required_by=["embed"],
    ),
    "multi-qa-MiniLM-L6-cos-v1": ModelInfo(
        id="multi-qa-MiniLM-L6-cos-v1",
        name="multi-qa-MiniLM-L6-cos-v1",
        model_type=ModelType.EMBEDDING,
        description="Optimized for question-answering and semantic search.",
        size_mb=90,
        required_by=["embed"],
    ),
    "bge-m3": ModelInfo(
        id="bge-m3",
        name="BGE-M3",
        model_type=ModelType.EMBEDDING,
        description="Multilingual embedding model (1024 dimensions). Supports 100+ languages with excellent cross-lingual retrieval.",
        size_mb=2200,
        required_by=["embed"],
    ),
    "bge-large-en-v1.5": ModelInfo(
        id="bge-large-en-v1.5",
        name="BGE-Large-EN v1.5",
        model_type=ModelType.EMBEDDING,
        description="High quality English embedding model (1024 dimensions). Best for English-only workloads.",
        size_mb=1300,
        required_by=["embed"],
    ),
    "paraphrase-MiniLM-L6-v2": ModelInfo(
        id="paraphrase-MiniLM-L6-v2",
        name="paraphrase-MiniLM-L6-v2",
        model_type=ModelType.EMBEDDING,
        description="Optimized for paraphrase detection (384 dimensions). Good for semantic similarity tasks.",
        size_mb=90,
        required_by=["embed"],
    ),

    # PaddleOCR models
    "paddleocr-en": ModelInfo(
        id="paddleocr-en",
        name="PaddleOCR English",
        model_type=ModelType.OCR,
        description="English OCR model for printed text recognition.",
        size_mb=150,
        required_by=["ocr"],
        is_default=True,
    ),
    "paddleocr-ch": ModelInfo(
        id="paddleocr-ch",
        name="PaddleOCR Chinese",
        model_type=ModelType.OCR,
        description="Chinese OCR model (also supports English).",
        size_mb=180,
        required_by=["ocr"],
    ),
}


class ModelService:
    """
    Service for managing ML models in SHATTERED.

    Supports:
    - Checking if models are installed locally
    - Downloading models on demand
    - Air-gap mode (prevent auto-downloads)
    - Model cache path configuration
    """

    def __init__(self, offline_mode: bool = False, cache_path: str | None = None):
        """
        Initialize the model service.

        Args:
            offline_mode: If True, prevent any network downloads
            cache_path: Custom path for model cache
        """
        self.offline_mode = offline_mode
        self.cache_path = cache_path
        self._download_callbacks: dict[str, Callable[[str, float], None]] = {}
        self._downloading: set[str] = set()

        # Set environment variables for offline mode
        if offline_mode:
            self._configure_offline_mode()

        if cache_path:
            self._configure_cache_path(cache_path)

    def _configure_offline_mode(self):
        """Configure environment for offline/air-gap mode."""
        # HuggingFace offline mode
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"

        # Disable paddle auto-download (handled in code)
        logger.info("Model service configured for offline/air-gap mode")

    def _configure_cache_path(self, path: str):
        """Configure model cache path."""
        os.environ["HF_HOME"] = path
        os.environ["TRANSFORMERS_CACHE"] = path
        os.environ["SENTENCE_TRANSFORMERS_HOME"] = path
        logger.info(f"Model cache path set to: {path}")

    def _get_hf_cache_path(self) -> Path:
        """Get the HuggingFace cache path."""
        if self.cache_path:
            return Path(self.cache_path)

        # Default HuggingFace cache locations
        hf_home = os.environ.get("HF_HOME")
        if hf_home:
            return Path(hf_home)

        # Default: ~/.cache/huggingface/hub
        return Path.home() / ".cache" / "huggingface" / "hub"

    def _get_paddle_cache_path(self) -> Path:
        """Get the PaddleOCR cache path."""
        # PaddleOCR stores models in ~/.paddleocr
        return Path.home() / ".paddleocr"

    def _check_hf_model_installed(self, model_name: str) -> tuple[bool, str | None]:
        """
        Check if a HuggingFace model is installed locally.

        Args:
            model_name: Model name (e.g., 'sentence-transformers/all-MiniLM-L6-v2')

        Returns:
            Tuple of (is_installed, path_or_none)
        """
        cache_path = self._get_hf_cache_path()

        # HuggingFace uses a specific naming scheme
        # Models are stored as: models--org--model-name
        if "/" in model_name:
            org, name = model_name.split("/", 1)
        else:
            org = "sentence-transformers"
            name = model_name

        model_dir_name = f"models--{org}--{name}"
        model_path = cache_path / model_dir_name

        if model_path.exists():
            # Check for snapshot directories
            snapshots = model_path / "snapshots"
            if snapshots.exists() and any(snapshots.iterdir()):
                return True, str(model_path)

        return False, None

    def _check_paddle_model_installed(self, lang: str = "en") -> tuple[bool, str | None]:
        """
        Check if PaddleOCR model is installed locally.

        Args:
            lang: Language code (en, ch, etc.)

        Returns:
            Tuple of (is_installed, path_or_none)
        """
        cache_path = self._get_paddle_cache_path()

        # PaddleOCR model structure: ~/.paddleocr/whl/det/en/...
        det_path = cache_path / "whl" / "det" / lang
        rec_path = cache_path / "whl" / "rec" / lang

        # Check if both detection and recognition models exist
        det_exists = det_path.exists() and any(det_path.glob("*.onnx")) or any(det_path.glob("**/inference.pdmodel"))
        rec_exists = rec_path.exists() and any(rec_path.glob("*.onnx")) or any(rec_path.glob("**/inference.pdmodel"))

        if det_exists and rec_exists:
            return True, str(cache_path)

        return False, None

    def list_models(self, model_type: ModelType | None = None) -> list[ModelInfo]:
        """
        List all known models with their installation status.

        Args:
            model_type: Filter by model type (optional)

        Returns:
            List of ModelInfo with current status
        """
        models = []

        for model_id, info in KNOWN_MODELS.items():
            if model_type and info.model_type != model_type:
                continue

            # Create a copy with updated status
            model = ModelInfo(
                id=info.id,
                name=info.name,
                model_type=info.model_type,
                description=info.description,
                size_mb=info.size_mb,
                required_by=info.required_by,
                is_default=info.is_default,
            )

            # Check installation status
            if model_id in self._downloading:
                model.status = ModelStatus.DOWNLOADING
            else:
                installed, path = self._check_model_installed(model_id, info.model_type)
                model.status = ModelStatus.INSTALLED if installed else ModelStatus.NOT_INSTALLED
                model.path = path

            models.append(model)

        return models

    def _get_hf_model_path(self, model_id: str) -> str:
        """Get the HuggingFace model path for a given model ID."""
        # Map model IDs to their HuggingFace paths
        model_paths = {
            "bge-m3": "BAAI/bge-m3",
            "bge-large-en-v1.5": "BAAI/bge-large-en-v1.5",
            # sentence-transformers models use their default org
        }
        return model_paths.get(model_id, f"sentence-transformers/{model_id}")

    def _check_model_installed(self, model_id: str, model_type: ModelType) -> tuple[bool, str | None]:
        """Check if a specific model is installed."""
        if model_type == ModelType.EMBEDDING:
            hf_path = self._get_hf_model_path(model_id)
            return self._check_hf_model_installed(hf_path)
        elif model_type == ModelType.OCR:
            lang = "en" if model_id == "paddleocr-en" else "ch"
            return self._check_paddle_model_installed(lang)
        return False, None

    def get_model_status(self, model_id: str) -> ModelInfo | None:
        """
        Get status of a specific model.

        Args:
            model_id: Model identifier

        Returns:
            ModelInfo with current status, or None if unknown
        """
        if model_id not in KNOWN_MODELS:
            return None

        info = KNOWN_MODELS[model_id]
        model = ModelInfo(
            id=info.id,
            name=info.name,
            model_type=info.model_type,
            description=info.description,
            size_mb=info.size_mb,
            required_by=info.required_by,
            is_default=info.is_default,
        )

        if model_id in self._downloading:
            model.status = ModelStatus.DOWNLOADING
        else:
            installed, path = self._check_model_installed(model_id, info.model_type)
            model.status = ModelStatus.INSTALLED if installed else ModelStatus.NOT_INSTALLED
            model.path = path

        return model

    async def download_model(self, model_id: str) -> ModelInfo:
        """
        Download a model.

        Args:
            model_id: Model identifier to download

        Returns:
            ModelInfo with updated status

        Raises:
            ValueError: If model_id is unknown
            RuntimeError: If offline mode is enabled
        """
        if self.offline_mode:
            raise RuntimeError(
                "Cannot download models in offline/air-gap mode. "
                "Pre-cache models before deployment or disable ARKHAM_OFFLINE_MODE."
            )

        if model_id not in KNOWN_MODELS:
            raise ValueError(f"Unknown model: {model_id}")

        info = KNOWN_MODELS[model_id]
        self._downloading.add(model_id)

        try:
            if info.model_type == ModelType.EMBEDDING:
                await self._download_embedding_model(model_id)
            elif info.model_type == ModelType.OCR:
                await self._download_ocr_model(model_id)
            else:
                raise ValueError(f"Unsupported model type: {info.model_type}")

            return self.get_model_status(model_id)

        finally:
            self._downloading.discard(model_id)

    async def _download_embedding_model(self, model_id: str):
        """Download an embedding model from HuggingFace."""
        import asyncio

        hf_path = self._get_hf_model_path(model_id)

        def _download():
            # Temporarily disable offline mode for download
            old_offline = os.environ.get("HF_HUB_OFFLINE")
            os.environ.pop("HF_HUB_OFFLINE", None)
            os.environ.pop("TRANSFORMERS_OFFLINE", None)

            try:
                from sentence_transformers import SentenceTransformer
                logger.info(f"Downloading embedding model: {hf_path}")
                # This triggers the download
                SentenceTransformer(hf_path)
                logger.info(f"Successfully downloaded: {hf_path}")
            finally:
                # Restore offline mode if it was set
                if old_offline:
                    os.environ["HF_HUB_OFFLINE"] = old_offline

        # Run in thread pool to not block
        await asyncio.get_event_loop().run_in_executor(None, _download)

    async def _download_ocr_model(self, model_id: str):
        """
        Download a PaddleOCR model.

        Uses subprocess to avoid PDX reinitialization errors when PaddleOCR
        was already loaded in the current process.
        """
        import asyncio
        import subprocess
        import sys

        lang = "en" if model_id == "paddleocr-en" else "ch"
        logger.info(f"Downloading PaddleOCR model: {lang}")

        # Run in subprocess to avoid "PDX has already been initialized" error
        # This happens when PaddleOCR was used earlier in the same process
        script = f"""
import os
os.environ["FLAGS_log_level"] = "3"  # Suppress paddle logging
try:
    from paddleocr import PaddleOCR
    ocr = PaddleOCR(use_angle_cls=True, lang="{lang}")
    print("SUCCESS")
except ImportError as e:
    print(f"IMPORT_ERROR: {{e}}")
except Exception as e:
    print(f"ERROR: {{e}}")
"""

        def _run_subprocess():
            result = subprocess.run(
                [sys.executable, "-c", script],
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout for download
            )
            output = result.stdout.strip()
            stderr = result.stderr.strip()

            if "SUCCESS" in output:
                logger.info(f"Successfully downloaded PaddleOCR: {lang}")
                return True
            elif "IMPORT_ERROR" in output:
                raise RuntimeError(
                    "paddleocr not installed. Install with: pip install paddleocr paddlepaddle"
                )
            else:
                error_msg = output or stderr or "Unknown error"
                raise RuntimeError(f"Failed to download PaddleOCR model: {error_msg}")

        await asyncio.get_event_loop().run_in_executor(None, _run_subprocess)

    def is_model_available(self, model_id: str) -> bool:
        """
        Quick check if a model is available for use.

        Args:
            model_id: Model identifier

        Returns:
            True if model is installed and ready
        """
        status = self.get_model_status(model_id)
        return status is not None and status.status == ModelStatus.INSTALLED

    def get_default_embedding_model(self) -> str:
        """Get the default embedding model ID."""
        for model_id, info in KNOWN_MODELS.items():
            if info.model_type == ModelType.EMBEDDING and info.is_default:
                return model_id
        return "all-MiniLM-L6-v2"

    def to_dict(self) -> dict[str, Any]:
        """Serialize service state to dictionary."""
        return {
            "offline_mode": self.offline_mode,
            "cache_path": self.cache_path,
            "hf_cache": str(self._get_hf_cache_path()),
            "paddle_cache": str(self._get_paddle_cache_path()),
            "models": [
                {
                    "id": m.id,
                    "name": m.name,
                    "type": m.model_type.value,
                    "status": m.status.value,
                    "size_mb": m.size_mb,
                    "path": m.path,
                    "is_default": m.is_default,
                }
                for m in self.list_models()
            ],
        }
