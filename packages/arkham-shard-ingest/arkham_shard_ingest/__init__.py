"""ArkhamFrame Ingest Shard - Document ingestion and processing."""

from .shard import IngestShard
from .intake import ValidationError

__version__ = "0.1.0"
__all__ = ["IngestShard", "ValidationError"]
