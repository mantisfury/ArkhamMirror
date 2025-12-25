"""OCR shard workers."""
from .paddle_worker import PaddleWorker
from .qwen_worker import QwenWorker

__all__ = ["PaddleWorker", "QwenWorker"]
