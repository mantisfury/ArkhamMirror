"""
Typed models for Red Flags page.

These models provide proper typing for Reflex Var system.
"""

from typing import Optional
from dataclasses import dataclass


@dataclass
class RedFlag:
    """Red flag data model for proper Reflex typing."""

    id: int
    severity: str  # CRITICAL, HIGH, MEDIUM, LOW
    flag_category: str
    title: str
    description: str
    detected_at: str
    status: str  # active, reviewed, dismissed, escalated
    confidence: float
    evidence: dict
    document_id: Optional[int] = None

    def __post_init__(self):
        """Ensure confidence is a float between 0 and 1."""
        if isinstance(self.confidence, (int, float)):
            if self.confidence > 1:
                self.confidence = self.confidence / 100.0
