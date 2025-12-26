"""
Summary Shard - Auto-summarization for ArkhamFrame

Provides LLM-powered summarization of documents, collections, and analysis results.
"""

from .shard import SummaryShard
from .models import (
    Summary,
    SummaryType,
    SummaryStatus,
    SourceType,
    SummaryLength,
    SummaryRequest,
    SummaryResult,
    SummaryFilter,
    SummaryStatistics,
)

__version__ = "0.1.0"

__all__ = [
    "SummaryShard",
    "Summary",
    "SummaryType",
    "SummaryStatus",
    "SourceType",
    "SummaryLength",
    "SummaryRequest",
    "SummaryResult",
    "SummaryFilter",
    "SummaryStatistics",
]
