"""Sampling strategies for wide event logging."""

import random
from typing import Optional, TYPE_CHECKING

from .config import WideEventConfig

if TYPE_CHECKING:
    from .wide_event import WideEvent


class SamplingStrategy:
    """Implements tail sampling for wide events.
    
    Tail sampling means making the sampling decision after the request
    completes, based on its outcome. This ensures we never lose important
    events (errors, slow requests) while reducing costs for normal traffic.
    """
    
    def __init__(self, config: WideEventConfig):
        """Initialize sampling strategy.
        
        Args:
            config: Wide event configuration
        """
        self.config = config
    
    def should_sample(self, event: "WideEvent") -> bool:
        """Determine if an event should be sampled.
        
        Rules:
        1. Always keep errors (100% of errors)
        2. Always keep slow requests (above threshold)
        3. Always keep specific users/projects (from config)
        4. Randomly sample the rest based on sampling_rate
        
        Args:
            event: Wide event to evaluate
            
        Returns:
            True if event should be sampled (logged)
        """
        # Always sample errors if configured
        if self.config.always_sample_errors:
            if event.outcome == "error":
                return True
            
            # Check status code for HTTP errors
            if hasattr(event, "status_code") and event.status_code:
                if event.status_code >= 500:
                    return True
        
        # Always sample slow requests if configured
        if self.config.always_sample_slow:
            if event.duration_ms > self.config.slow_threshold_ms:
                return True
        
        # Always sample specific users
        if event.user and isinstance(event.user, dict):
            user_id = event.user.get("id") or event.user.get("user_id")
            if user_id and user_id in self.config.always_sample_users:
                return True
        
        # Always sample specific projects
        if hasattr(event, "project_id") and event.project_id:
            if event.project_id in self.config.always_sample_projects:
                return True
        
        # Check extra fields for project_id
        if event.extra:
            project_id = event.extra.get("project_id")
            if project_id and project_id in self.config.always_sample_projects:
                return True
        
        # Random sample the rest
        if self.config.tail_sampling:
            # Tail sampling: make decision after request completes
            return random.random() < self.config.sampling_rate
        else:
            # Head sampling: make decision before request starts
            # (not recommended, but supported)
            return random.random() < self.config.sampling_rate
    
    def get_sampling_rate(self) -> float:
        """Get current sampling rate.
        
        Returns:
            Sampling rate (0.0-1.0)
        """
        return self.config.sampling_rate


# Global instance (will be initialized by LoggingManager)
_default_sampler: Optional[SamplingStrategy] = None


def set_sampler(sampler: SamplingStrategy) -> None:
    """Set the default sampler instance.
    
    Args:
        sampler: SamplingStrategy instance
    """
    global _default_sampler
    _default_sampler = sampler


def get_sampler() -> Optional[SamplingStrategy]:
    """Get the default sampler instance.
    
    Returns:
        SamplingStrategy instance or None
    """
    return _default_sampler
