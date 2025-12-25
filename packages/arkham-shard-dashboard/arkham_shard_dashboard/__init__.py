"""
ArkhamMirror Dashboard Shard

System monitoring, LLM configuration, database controls, and worker management.
"""

__version__ = "0.1.0"

from .shard import DashboardShard

__all__ = ["DashboardShard", "__version__"]
