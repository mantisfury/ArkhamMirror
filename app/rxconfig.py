import reflex as rx
import sys
from pathlib import Path

# Add project root to path for central config import
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import DATABASE_URL, BACKEND_PORT, FRONTEND_PORT

config = rx.Config(
    app_name="arkham",
    # Backend API port (Reflex FastAPI server)
    backend_port=BACKEND_PORT,
    # Frontend port (Next.js dev server)
    frontend_port=FRONTEND_PORT,
    # Database URL from central config
    db_url=DATABASE_URL,
    # Disable sitemap plugin warnings
    disable_plugins=["reflex.plugins.sitemap.SitemapPlugin"],
    # Disable tailwind (not used, fixes deprecation warning in 0.7.x)
    tailwind=None,
    # Increase state lock timeout to 60s (default 10s) to handle slow DB queries on startup
    # See: https://reflex.dev/docs/api-reference/config/#reflex.config.Config.redis_lock_expiration
    redis_lock_expiration=300000,  # 5 minutes in milliseconds
    redis_lock_warning_threshold=30000,  # Warn if lock held > 30 seconds
)
