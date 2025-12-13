"""
Typed models for Metadata Forensics page.

These models provide proper typing for Reflex Var system.
"""

from typing import Optional
from dataclasses import dataclass


@dataclass
class ProducerInfo:
    """PDF Producer information."""

    name: str
    count: int
    percentage: float
    suspicion: str  # NORMAL, MEDIUM, HIGH


@dataclass
class CreatorInfo:
    """PDF Creator information."""

    name: str
    count: int
    percentage: float


@dataclass
class AuthorInfo:
    """Author information."""

    name: str
    count: int
    percentage: float


@dataclass
class YearInfo:
    """Year distribution information."""

    year: int
    count: int
    percentage: float


@dataclass
class MonthInfo:
    """Month distribution information."""

    month: str
    created: int
    modified: int
