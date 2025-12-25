"""
ArkhamFrame Pipeline - Document processing stages.
"""

from .base import PipelineStage, PipelineError, StageResult
from .ingest import IngestStage
from .ocr import OCRStage
from .parse import ParseStage
from .embed import EmbedStage
from .coordinator import PipelineCoordinator

__all__ = [
    "PipelineStage",
    "PipelineError",
    "StageResult",
    "IngestStage",
    "OCRStage",
    "ParseStage",
    "EmbedStage",
    "PipelineCoordinator",
]
