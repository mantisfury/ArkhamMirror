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
            from sqlalchemy import text
            with self._engine.connect() as conn:
                conn.execute(text("SELECT 1"))
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
        if not self._connected:
            return {"connected": False}

        stats = {"connected": True}

        try:
            from sqlalchemy import text

            with self._engine.connect() as conn:
                # Database size
                size_result = conn.execute(text(
                    "SELECT pg_database_size(current_database()) as size"
                ))
                row = size_result.fetchone()
                stats["database_size_bytes"] = row[0] if row else 0

                # Table count per schema
                schema_stats = []
                schemas = await self.list_schemas()

                for schema in schemas:
                    # Get table count
                    table_result = conn.execute(text(
                        "SELECT COUNT(*) FROM information_schema.tables "
                        "WHERE table_schema = :schema"
                    ), {"schema": schema})
                    table_count = table_result.fetchone()[0]

                    # Get total row count (approximate via pg_stat)
                    row_result = conn.execute(text(
                        "SELECT COALESCE(SUM(n_live_tup), 0) as rows "
                        "FROM pg_stat_user_tables "
                        "WHERE schemaname = :schema"
                    ), {"schema": schema})
                    row_count = row_result.fetchone()[0]

                    # Get schema size
                    size_result = conn.execute(text(
                        "SELECT COALESCE(SUM(pg_total_relation_size(quote_ident(schemaname) || '.' || quote_ident(tablename))), 0) "
                        "FROM pg_tables WHERE schemaname = :schema"
                    ), {"schema": schema})
                    schema_size = size_result.fetchone()[0]

                    schema_stats.append({
                        "name": schema,
                        "tables": table_count,
                        "rows": int(row_count),
                        "size_bytes": int(schema_size),
                    })

                stats["schemas"] = schema_stats
                stats["total_tables"] = sum(s["tables"] for s in schema_stats)
                stats["total_rows"] = sum(s["rows"] for s in schema_stats)

        except Exception as e:
            logger.error(f"Failed to get database stats: {e}")
            stats["error"] = str(e)

        return stats

    async def get_table_info(self, schema: str) -> List[Dict[str, Any]]:
        """Get detailed table information for a schema."""
        if not self._connected:
            return []

        try:
            from sqlalchemy import text

            with self._engine.connect() as conn:
                result = conn.execute(text("""
                    SELECT
                        t.table_name,
                        COALESCE(s.n_live_tup, 0) as row_count,
                        pg_total_relation_size(quote_ident(:schema) || '.' || quote_ident(t.table_name)) as size_bytes,
                        COALESCE(s.last_vacuum, s.last_autovacuum) as last_vacuum,
                        COALESCE(s.last_analyze, s.last_autoanalyze) as last_analyze
                    FROM information_schema.tables t
                    LEFT JOIN pg_stat_user_tables s
                        ON s.schemaname = t.table_schema AND s.relname = t.table_name
                    WHERE t.table_schema = :schema
                    ORDER BY t.table_name
                """), {"schema": schema})

                return [
                    {
                        "name": row[0],
                        "row_count": int(row[1]),
                        "size_bytes": int(row[2]) if row[2] else 0,
                        "last_vacuum": row[3].isoformat() if row[3] else None,
                        "last_analyze": row[4].isoformat() if row[4] else None,
                    }
                    for row in result.fetchall()
                ]
        except Exception as e:
            logger.error(f"Failed to get table info for {schema}: {e}")
            return []

    async def vacuum_analyze(self) -> Dict[str, Any]:
        """Run VACUUM ANALYZE on all arkham schemas."""
        if not self._connected:
            return {"success": False, "error": "Database not connected"}

        try:
            from sqlalchemy import text

            schemas = await self.list_schemas()
            vacuumed_tables = 0

            with self._engine.connect() as conn:
                # Need to set isolation level for VACUUM
                conn.execution_options(isolation_level="AUTOCOMMIT")

                for schema in schemas:
                    # Get tables in schema
                    result = conn.execute(text(
                        "SELECT table_name FROM information_schema.tables "
                        "WHERE table_schema = :schema"
                    ), {"schema": schema})

                    for row in result.fetchall():
                        table_name = row[0]
                        try:
                            conn.execute(text(
                                f'VACUUM ANALYZE "{schema}"."{table_name}"'
                            ))
                            vacuumed_tables += 1
                        except Exception as e:
                            logger.warning(f"Failed to vacuum {schema}.{table_name}: {e}")

            return {
                "success": True,
                "message": f"VACUUM ANALYZE completed on {vacuumed_tables} tables across {len(schemas)} schemas",
                "tables_vacuumed": vacuumed_tables,
                "schemas": schemas,
            }
        except Exception as e:
            logger.error(f"VACUUM ANALYZE failed: {e}")
            return {"success": False, "error": str(e)}

    async def reset_database(self) -> Dict[str, Any]:
        """Drop and recreate all arkham schemas. DANGEROUS!"""
        if not self._connected:
            return {"success": False, "error": "Database not connected"}

        try:
            from sqlalchemy import text

            schemas = await self.list_schemas()
            dropped = []

            with self._engine.connect() as conn:
                for schema in schemas:
                    try:
                        conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
                        conn.commit()
                        dropped.append(schema)
                        logger.info(f"Dropped schema: {schema}")
                    except Exception as e:
                        logger.error(f"Failed to drop schema {schema}: {e}")

            return {
                "success": True,
                "message": f"Dropped {len(dropped)} schemas: {', '.join(dropped)}",
                "schemas_dropped": dropped,
            }
        except Exception as e:
            logger.error(f"Database reset failed: {e}")
            return {"success": False, "error": str(e)}

    async def execute(self, query: str, params: Optional[Dict[str, Any]] = None) -> None:
        """Execute a query (for DDL, INSERT, UPDATE, DELETE)."""
        if not self._connected:
            raise DatabaseError("Database not connected")
        try:
            from sqlalchemy import text
            with self._engine.connect() as conn:
                conn.execute(text(query), params or {})
                conn.commit()
        except Exception as e:
            raise QueryExecutionError(str(e), query)

    async def fetch_one(self, query: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """Fetch a single row."""
        if not self._connected:
            raise DatabaseError("Database not connected")
        try:
            from sqlalchemy import text
            with self._engine.connect() as conn:
                result = conn.execute(text(query), params or {})
                row = result.fetchone()
                if row:
                    return dict(row._mapping)
                return None
        except Exception as e:
            raise QueryExecutionError(str(e), query)

    async def fetch_all(self, query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Fetch all rows."""
        if not self._connected:
            raise DatabaseError("Database not connected")
        try:
            from sqlalchemy import text
            with self._engine.connect() as conn:
                result = conn.execute(text(query), params or {})
                return [dict(row._mapping) for row in result.fetchall()]
        except Exception as e:
            raise QueryExecutionError(str(e), query)
