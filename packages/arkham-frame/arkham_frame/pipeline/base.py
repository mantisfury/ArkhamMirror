"""
Pipeline base classes.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class PipelineError(Exception):
    """Base pipeline error."""
    pass


class StageStatus(Enum):
    """Status of a pipeline stage execution."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class StageResult:
    """Result of a pipeline stage execution."""
    stage_name: str
    status: StageStatus
    output: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    @property
    def duration_seconds(self) -> Optional[float]:
        """Get execution duration in seconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    @property
    def success(self) -> bool:
        """Check if stage completed successfully."""
        return self.status == StageStatus.COMPLETED


class PipelineStage(ABC):
    """
    Abstract base class for pipeline stages.

    Each stage processes documents through a specific transformation.
    """

    def __init__(self, name: str, frame=None):
        self.name = name
        self.frame = frame

    @abstractmethod
    async def process(self, context: Dict[str, Any]) -> StageResult:
        """
        Process the stage.

        Args:
            context: Pipeline context with document data

        Returns:
            StageResult with output and status
        """
        pass

    @abstractmethod
    async def validate(self, context: Dict[str, Any]) -> bool:
        """
        Validate that the stage can process the context.

        Args:
            context: Pipeline context to validate

        Returns:
            True if stage can process, False otherwise
        """
        pass

    def should_skip(self, context: Dict[str, Any]) -> bool:
        """
        Check if stage should be skipped.

        Override in subclasses for custom skip logic.
        """
        return False

    async def on_error(self, error: Exception, context: Dict[str, Any]) -> None:
        """
        Handle stage error.

        Override in subclasses for custom error handling.
        """
        pass
