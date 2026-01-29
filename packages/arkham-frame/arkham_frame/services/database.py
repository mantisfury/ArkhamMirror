"""
DatabaseService - PostgreSQL database access with schema isolation.
"""

from typing import Optional, List, Dict, Any
import logging
import time
import re

logger = logging.getLogger(__name__)

# Import wide event logging utilities (with fallback)
try:
    from arkham_frame import log_operation
    from arkham_logging.sanitizer import DataSanitizer
    WIDE_EVENTS_AVAILABLE = True
except ImportError:
    WIDE_EVENTS_AVAILABLE = False
    # Fallback: create no-op context manager
    from contextlib import contextmanager
    @contextmanager
    def log_operation(*args, **kwargs):
        yield None
    DataSanitizer = None


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
        self._sanitizer = DataSanitizer() if WIDE_EVENTS_AVAILABLE and DataSanitizer else None
    
    def _sanitize_query(self, query: str) -> str:
        """Sanitize query for logging - remove sensitive patterns and truncate."""
        if not query:
            return ""
        
        # Truncate very long queries
        max_query_length = 500
        sanitized = query[:max_query_length]
        if len(query) > max_query_length:
            sanitized += "... [truncated]"
        
        # Remove potential password/credential patterns
        sanitized = re.sub(r'(?i)(password|pwd|passwd)\s*=\s*[\'"]?[^\'";\s]+', r'\1=***', sanitized)
        sanitized = re.sub(r'(?i)(api[_-]?key|token|secret)\s*=\s*[\'"]?[^\'";\s]+', r'\1=***', sanitized)
        
        return sanitized

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
        """Drop and recreate all arkham schemas and public arkham_* tables. DANGEROUS!"""
        if not self._connected:
            return {"success": False, "error": "Database not connected"}

        try:
            from sqlalchemy import text

            schemas = await self.list_schemas()
            dropped = []
            dropped_tables = []

            with self._engine.connect() as conn:
                # Drop arkham_* schemas
                for schema in schemas:
                    try:
                        conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
                        conn.commit()
                        dropped.append(schema)
                        logger.info(f"Dropped schema: {schema}")
                    except Exception as e:
                        logger.error(f"Failed to drop schema {schema}: {e}")

                # Also drop arkham_* tables in public schema (e.g., arkham_entities)
                try:
                    result = conn.execute(text(
                        "SELECT table_name FROM information_schema.tables "
                        "WHERE table_schema = 'public' AND table_name LIKE 'arkham_%'"
                    ))
                    public_tables = [row[0] for row in result.fetchall()]

                    for table in public_tables:
                        try:
                            conn.execute(text(f'DROP TABLE IF EXISTS "public"."{table}" CASCADE'))
                            conn.commit()
                            dropped_tables.append(table)
                            logger.info(f"Dropped public table: {table}")
                        except Exception as e:
                            logger.error(f"Failed to drop table {table}: {e}")
                except Exception as e:
                    logger.error(f"Failed to list public arkham tables: {e}")

            message = f"Dropped {len(dropped)} schemas: {', '.join(dropped)}"
            if dropped_tables:
                message += f"; {len(dropped_tables)} public tables: {', '.join(dropped_tables)}"

            return {
                "success": True,
                "message": message,
                "schemas_dropped": dropped,
                "tables_dropped": dropped_tables,
            }
        except Exception as e:
            logger.error(f"Database reset failed: {e}")
            return {"success": False, "error": str(e)}

    def _convert_params(self, query: str, params) -> tuple[str, Dict[str, Any]]:
        """Convert list-style params (?) to named params (:param_N) for SQLAlchemy."""
        if params is None:
            return query, {}
        if isinstance(params, dict):
            return query, params
        # Convert list/tuple params with ? placeholders to named params
        if isinstance(params, (list, tuple)):
            new_query = query
            param_dict = {}
            for i, value in enumerate(params):
                param_name = f"param_{i}"
                # Replace first ? with :param_N
                new_query = new_query.replace("?", f":{param_name}", 1)
                param_dict[param_name] = value
            return new_query, param_dict
        return query, {}

    async def execute(self, query: str, params=None) -> None:
        """Execute a query (for DDL, INSERT, UPDATE, DELETE)."""
        sanitized_query = self._sanitize_query(query)
        query_type = query.strip().split()[0].upper() if query.strip() else "UNKNOWN"
        
        with log_operation("database.execute", query_type=query_type) as event:
            if event:
                event.input(
                    query_type=query_type,
                    query_preview=sanitized_query,
                    has_params=params is not None,
                )
                if self._sanitizer and params:
                    sanitized_params = self._sanitizer.sanitize(params)
                    event.input(params=sanitized_params)
            
            if not self._connected:
                if event:
                    event.error("DatabaseNotConnected", "Database not connected")
                raise DatabaseError("Database not connected")
            
            start_time = time.time()
            try:
                from sqlalchemy import text
                query, params = self._convert_params(query, params)
                with self._engine.connect() as conn:
                    conn.execute(text(query), params)
                    conn.commit()
                
                duration_ms = int((time.time() - start_time) * 1000)
                if event:
                    event.dependency("postgresql", duration_ms=duration_ms)
                    event.output(executed=True)
            except Exception as e:
                duration_ms = int((time.time() - start_time) * 1000)
                if event:
                    event.dependency("postgresql", duration_ms=duration_ms, error=str(e))
                    event.error("QueryExecutionFailed", str(e))
                raise QueryExecutionError(str(e), query)

    async def fetch_one(self, query: str, params=None) -> Optional[Dict[str, Any]]:
        """Fetch a single row."""
        sanitized_query = self._sanitize_query(query)
        
        with log_operation("database.fetch_one") as event:
            if event:
                event.input(
                    query_preview=sanitized_query,
                    has_params=params is not None,
                )
                if self._sanitizer and params:
                    sanitized_params = self._sanitizer.sanitize(params)
                    event.input(params=sanitized_params)
            
            if not self._connected:
                if event:
                    event.error("DatabaseNotConnected", "Database not connected")
                raise DatabaseError("Database not connected")
            
            start_time = time.time()
            try:
                from sqlalchemy import text
                query, params = self._convert_params(query, params)
                with self._engine.connect() as conn:
                    result = conn.execute(text(query), params)
                    row = result.fetchone()
                    
                    duration_ms = int((time.time() - start_time) * 1000)
                    if event:
                        event.dependency("postgresql", duration_ms=duration_ms)
                        event.output(found=row is not None)
                    
                    if row:
                        return dict(row._mapping)
                    return None
            except Exception as e:
                duration_ms = int((time.time() - start_time) * 1000)
                if event:
                    event.dependency("postgresql", duration_ms=duration_ms, error=str(e))
                    event.error("QueryExecutionFailed", str(e))
                raise QueryExecutionError(str(e), query)

    async def fetch_all(self, query: str, params=None) -> List[Dict[str, Any]]:
        """Fetch all rows."""
        sanitized_query = self._sanitize_query(query)
        
        with log_operation("database.fetch_all") as event:
            if event:
                event.input(
                    query_preview=sanitized_query,
                    has_params=params is not None,
                )
                if self._sanitizer and params:
                    sanitized_params = self._sanitizer.sanitize(params)
                    event.input(params=sanitized_params)
            
            if not self._connected:
                if event:
                    event.error("DatabaseNotConnected", "Database not connected")
                raise DatabaseError("Database not connected")
            
            start_time = time.time()
            try:
                from sqlalchemy import text
                query, params = self._convert_params(query, params)
                with self._engine.connect() as conn:
                    result = conn.execute(text(query), params)
                    rows = [dict(row._mapping) for row in result.fetchall()]
                    
                    duration_ms = int((time.time() - start_time) * 1000)
                    if event:
                        event.dependency("postgresql", duration_ms=duration_ms)
                        event.output(row_count=len(rows))
                    
                    return rows
            except Exception as e:
                duration_ms = int((time.time() - start_time) * 1000)
                if event:
                    event.dependency("postgresql", duration_ms=duration_ms, error=str(e))
                    event.error("QueryExecutionFailed", str(e))
                raise QueryExecutionError(str(e), query)
