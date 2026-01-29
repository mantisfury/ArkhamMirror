"""
Session Service - Per-user active project storage.

Stores active project selection per user in database for persistence across requests.
"""

import logging
from typing import Optional
from datetime import datetime, timedelta
import json

logger = logging.getLogger(__name__)


class SessionService:
    """
    Manages user sessions, primarily for storing active project per user.
    
    Uses database table for persistence. Falls back to in-memory cache if needed.
    """

    def __init__(self, db):
        """
        Initialize session service.
        
        Args:
            db: Database service instance
        """
        self.db = db
        self._cache: dict[str, tuple[str, datetime]] = {}  # user_id -> (project_id, expiry)
        self._initialized = False

    async def initialize(self) -> None:
        """Create session table if it doesn't exist."""
        if self._initialized:
            return

        try:
            await self.db.execute("""
                CREATE TABLE IF NOT EXISTS arkham_sessions (
                    user_id TEXT PRIMARY KEY,
                    active_project_id TEXT,
                    updated_at TEXT,
                    expires_at TEXT
                )
            """)
            
            await self.db.execute("""
                CREATE INDEX IF NOT EXISTS idx_sessions_user ON arkham_sessions(user_id)
            """)
            
            await self.db.execute("""
                CREATE INDEX IF NOT EXISTS idx_sessions_expires ON arkham_sessions(expires_at)
            """)
            
            self._initialized = True
            logger.info("SessionService initialized")
        except Exception as e:
            logger.warning(f"Failed to create session table: {e}")
            # Continue with in-memory cache only

    async def get_active_project(self, user_id: str) -> Optional[str]:
        """
        Get the active project ID for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            Active project ID or None if not set
        """
        # Normalize user_id to lowercase for consistent UUID format
        user_id = str(user_id).lower().strip()
        
        if not self._initialized:
            # Fallback to cache
            if user_id in self._cache:
                project_id, expiry = self._cache[user_id]
                if expiry > datetime.utcnow():
                    return project_id
                else:
                    del self._cache[user_id]
            return None

        try:
            # Check cache first
            if user_id in self._cache:
                project_id, expiry = self._cache[user_id]
                if expiry > datetime.utcnow():
                    return project_id
                else:
                    del self._cache[user_id]

            # Query database
            row = await self.db.fetch_one(
                "SELECT active_project_id, expires_at FROM arkham_sessions WHERE LOWER(user_id) = LOWER(?)",
                [user_id]
            )
            
            if not row:
                return None
            
            expires_at_str = row.get("expires_at")
            if expires_at_str:
                try:
                    expires_at = datetime.fromisoformat(expires_at_str)
                    if expires_at < datetime.utcnow():
                        # Expired, clean up
                        await self.db.execute(
                            "DELETE FROM arkham_sessions WHERE user_id = ?",
                            [str(user_id)]
                        )
                        return None
                except (ValueError, TypeError):
                    pass
            
            project_id = row.get("active_project_id")
            if project_id:
                # Cache for 5 minutes
                expiry = datetime.utcnow() + timedelta(minutes=5)
                self._cache[user_id] = (project_id, expiry)
            
            return project_id
        except Exception as e:
            logger.warning(f"Failed to get active project for user {user_id}: {e}")
            # Fallback to cache
            if user_id in self._cache:
                project_id, expiry = self._cache[user_id]
                if expiry > datetime.utcnow():
                    return project_id
            return None

    async def set_active_project(self, user_id: str, project_id: Optional[str], ttl_days: int = 30) -> None:
        """
        Set the active project for a user.
        
        Args:
            user_id: User ID
            project_id: Project ID to set as active, or None to clear
            ttl_days: Time to live in days (default: 30)
        """
        # Normalize user_id to lowercase for consistent UUID format
        user_id = str(user_id).lower().strip()
        
        if not self._initialized:
            # Fallback to cache only
            if project_id:
                expiry = datetime.utcnow() + timedelta(days=ttl_days)
                self._cache[user_id] = (project_id, expiry)
            else:
                self._cache.pop(user_id, None)
            return

        try:
            now = datetime.utcnow()
            expires_at = now + timedelta(days=ttl_days) if project_id else None

            if project_id:
                await self.db.execute("""
                    INSERT INTO arkham_sessions (user_id, active_project_id, updated_at, expires_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(user_id) DO UPDATE SET
                        active_project_id = ?,
                        updated_at = ?,
                        expires_at = ?
                """, [
                    user_id,
                    str(project_id),
                    now.isoformat(),
                    expires_at.isoformat() if expires_at else None,
                    str(project_id),
                    now.isoformat(),
                    expires_at.isoformat() if expires_at else None,
                ])
                
                # Update cache
                self._cache[user_id] = (project_id, expires_at)
            else:
                await self.db.execute(
                    "DELETE FROM arkham_sessions WHERE user_id = ?",
                    [str(user_id)]
                )
                self._cache.pop(user_id, None)
                
            logger.debug(f"Set active project for user {user_id}: {project_id}")
        except Exception as e:
            logger.warning(f"Failed to set active project for user {user_id}: {e}")
            # Fallback to cache
            if project_id:
                expiry = datetime.utcnow() + timedelta(days=ttl_days)
                self._cache[user_id] = (project_id, expiry)
            else:
                self._cache.pop(user_id, None)

    async def clear_expired_sessions(self) -> int:
        """
        Clean up expired sessions from database.
        
        Returns:
            Number of sessions deleted
        """
        if not self._initialized:
            return 0

        try:
            now = datetime.utcnow().isoformat()
            result = await self.db.execute(
                "DELETE FROM arkham_sessions WHERE expires_at < ?",
                [now]
            )
            # Clear expired from cache
            expired_users = [
                user_id for user_id, (_, expiry) in self._cache.items()
                if expiry < datetime.utcnow()
            ]
            for user_id in expired_users:
                del self._cache[user_id]
            
            return len(expired_users)
        except Exception as e:
            logger.warning(f"Failed to clear expired sessions: {e}")
            return 0
