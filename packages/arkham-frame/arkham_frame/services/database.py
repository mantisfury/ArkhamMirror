"""
DatabaseService - PostgreSQL database access with schema isolation.
"""

from typing import Optional, List, Dict, Any
import logging

logger = logging.getLogger(__name__)


class DatabaseError(Exception):
    """Base database error."""
    pass


class SchemaNotFoundError(DatabaseError):
    """Schema does not exist."""
    def __init__(self, schema: str):
        super().__init__(f"Schema not found: {schema}")


class SchemaExistsError(DatabaseError):
    """Schema already exists."""
    def __init__(self, schema: str):
        super().__init__(f"Schema already exists: {schema}")


class QueryExecutionError(DatabaseError):
    """Query execution failed."""
    def __init__(self, message: str, query: str = ""):
        super().__init__(f"{message} - Query: {query[:100]}")


class DatabaseService:
    """
    Database service with schema isolation.

    Each shard gets its own schema (arkham_{shard_name}).
    """

    def __init__(self, config):
        self.config = config
        self._engine = None
        self._session_factory = None
        self._connected = False

    async def initialize(self) -> None:
        """Initialize database connection."""
        try:
            from sqlalchemy import create_engine
            from sqlalchemy.orm import sessionmaker

            self._engine = create_engine(
                self.config.database_url,
                pool_pre_ping=True,
                pool_size=5,
                max_overflow=10,
            )
            self._session_factory = sessionmaker(bind=self._engine)
            self._connected = True
            logger.info(f"Database connected: {self.config.database_url.split('@')[-1]}")
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            self._connected = False

    async def shutdown(self) -> None:
        """Close database connection."""
        if self._engine:
            self._engine.dispose()
        self._connected = False
        logger.info("Database connection closed")

    async def is_connected(self) -> bool:
        """Check if database is connected."""
        if not self._connected or not self._engine:
            return False
        try:
            with self._engine.connect() as conn:
                conn.execute("SELECT 1")
            return True
        except Exception:
            return False

    async def list_schemas(self) -> List[str]:
        """List all arkham schemas."""
        if not self._connected:
            return []
        try:
            from sqlalchemy import text
            with self._engine.connect() as conn:
                result = conn.execute(text(
                    "SELECT schema_name FROM information_schema.schemata "
                    "WHERE schema_name LIKE 'arkham_%'"
                ))
                return [row[0] for row in result]
        except Exception as e:
            logger.error(f"Failed to list schemas: {e}")
            return []

    async def get_stats(self) -> Dict[str, Any]:
        """Get database statistics."""
        return {"connected": self._connected}
