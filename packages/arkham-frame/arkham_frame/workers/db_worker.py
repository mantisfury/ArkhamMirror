"""
DBWorker - Async database operations for the io-db pool.

Handles:
- Query execution (SELECT)
- Statement execution (INSERT/UPDATE/DELETE)
- Bulk operations (execute_many, COPY)
- Transactions (multiple statements)
- Table metadata queries

All operations use asyncpg for async PostgreSQL access with connection pooling.
"""

import asyncio
import json
import logging
import os
import re
from datetime import datetime, date
from decimal import Decimal
from typing import Dict, Any, List, Optional, Union
from uuid import UUID

from .base import BaseWorker

logger = logging.getLogger(__name__)


class DBWorker(BaseWorker):
    """
    Worker for async database operations.

    Supports operations:
    - query: Execute SELECT query
    - execute: Execute INSERT/UPDATE/DELETE statement
    - execute_many: Bulk execute with multiple parameter sets
    - transaction: Execute multiple statements in a transaction
    - copy_from: Bulk COPY from data (fast bulk insert)
    - table_exists: Check if table exists
    - count: Count rows in table with optional filter
    """

    pool = "io-db"
    name = "DBWorker"
    job_timeout = 120.0  # Database operations can take time for bulk ops
    poll_interval = 0.5  # Poll frequently for DB tasks

    # Class-level connection pool (shared across instances)
    _db_pool = None
    _pool_lock = asyncio.Lock()

    # Table name validation pattern (alphanumeric + underscore only)
    _TABLE_NAME_PATTERN = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._database_url = os.environ.get(
            "DATABASE_URL",
            "postgresql://localhost:5432/arkham"
        )
        self._asyncpg_available = False

        # Try to import asyncpg
        try:
            import asyncpg
            self._asyncpg_available = True
            logger.info("asyncpg available for async database I/O")
        except ImportError:
            logger.error("asyncpg not available - DBWorker cannot function!")
            raise

    async def _get_pool(self):
        """Get or create the connection pool."""
        if DBWorker._db_pool is None:
            async with DBWorker._pool_lock:
                # Double-check after acquiring lock
                if DBWorker._db_pool is None:
                    import asyncpg
                    try:
                        DBWorker._db_pool = await asyncpg.create_pool(
                            self._database_url,
                            min_size=2,
                            max_size=10,
                            timeout=30.0,
                            command_timeout=60.0,
                        )
                        logger.info("Database connection pool created")
                    except Exception as e:
                        logger.error(f"Failed to create database pool: {e}")
                        raise
        return DBWorker._db_pool

    async def shutdown(self):
        """Graceful shutdown with pool cleanup."""
        await super().shutdown()

        # Close pool if this is the last worker
        if DBWorker._db_pool is not None:
            async with DBWorker._pool_lock:
                if DBWorker._db_pool is not None:
                    await DBWorker._db_pool.close()
                    DBWorker._db_pool = None
                    logger.info("Database connection pool closed")

    def _validate_table_name(self, table_name: str) -> bool:
        """Validate table name to prevent SQL injection."""
        return bool(self._TABLE_NAME_PATTERN.match(table_name))

    def _serialize_value(self, value: Any) -> Any:
        """Serialize database value for JSON transport."""
        if value is None:
            return None
        elif isinstance(value, (datetime, date)):
            return value.isoformat()
        elif isinstance(value, UUID):
            return str(value)
        elif isinstance(value, Decimal):
            return float(value)
        elif isinstance(value, bytes):
            return value.hex()
        elif isinstance(value, (list, dict)):
            return value  # Already JSON-compatible
        else:
            return value

    def _serialize_row(self, row: Any) -> Dict[str, Any]:
        """Serialize database row to dict."""
        if row is None:
            return None
        return {key: self._serialize_value(row[key]) for key in row.keys()}

    def _serialize_rows(self, rows: List[Any]) -> List[Dict[str, Any]]:
        """Serialize list of database rows."""
        return [self._serialize_row(row) for row in rows]

    async def process_job(self, job_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a database task.

        Args:
            job_id: Job identifier
            payload: Job data with 'operation' field and operation-specific params

        Returns:
            Result dict based on operation type
        """
        operation = payload.get("operation", "")

        if not operation:
            return {"error": "No operation specified", "success": False}

        # Route to appropriate handler
        if operation == "query":
            return await self._query(payload)
        elif operation == "execute":
            return await self._execute(payload)
        elif operation == "execute_many":
            return await self._execute_many(payload)
        elif operation == "transaction":
            return await self._transaction(payload)
        elif operation == "copy_from":
            return await self._copy_from(payload)
        elif operation == "table_exists":
            return await self._table_exists(payload)
        elif operation == "count":
            return await self._count(payload)
        else:
            return {"error": f"Unknown operation: {operation}", "success": False}

    async def _query(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a SELECT query.

        Args:
            payload: {
                "sql": str - SELECT query (parameterized)
                "params": List - Query parameters (default: [])
                "fetch": str - "all" | "one" | "scalar" (default: "all")
            }

        Returns:
            {
                "rows": List[Dict] - Query results (for "all")
                "row": Dict - Single row (for "one")
                "value": Any - Scalar value (for "scalar")
                "count": int - Number of rows returned
                "success": bool
            }
        """
        sql = payload.get("sql")
        params = payload.get("params", [])
        fetch = payload.get("fetch", "all")

        if not sql:
            return {"error": "No SQL query specified", "success": False}

        # Basic validation: must be a SELECT
        if not sql.strip().upper().startswith("SELECT"):
            return {"error": "Only SELECT queries allowed in query operation", "success": False}

        try:
            pool = await self._get_pool()

            async with pool.acquire() as conn:
                if fetch == "one":
                    row = await conn.fetchrow(sql, *params)
                    return {
                        "row": self._serialize_row(row),
                        "count": 1 if row else 0,
                        "success": True,
                    }
                elif fetch == "scalar":
                    value = await conn.fetchval(sql, *params)
                    return {
                        "value": self._serialize_value(value),
                        "count": 1 if value is not None else 0,
                        "success": True,
                    }
                else:  # "all"
                    rows = await conn.fetch(sql, *params)
                    return {
                        "rows": self._serialize_rows(rows),
                        "count": len(rows),
                        "success": True,
                    }

        except Exception as e:
            logger.error(f"Query failed: {e}")
            return {"error": str(e), "success": False}

    async def _execute(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute INSERT/UPDATE/DELETE statement.

        Args:
            payload: {
                "sql": str - SQL statement (parameterized)
                "params": List - Statement parameters (default: [])
            }

        Returns:
            {
                "affected": int - Number of rows affected
                "success": bool
            }
        """
        sql = payload.get("sql")
        params = payload.get("params", [])

        if not sql:
            return {"error": "No SQL statement specified", "success": False}

        try:
            pool = await self._get_pool()

            async with pool.acquire() as conn:
                result = await conn.execute(sql, *params)

                # Parse affected rows from result string (e.g., "UPDATE 5")
                affected = 0
                if result:
                    parts = result.split()
                    if len(parts) >= 2:
                        try:
                            affected = int(parts[-1])
                        except ValueError:
                            pass

                return {
                    "affected": affected,
                    "success": True,
                }

        except Exception as e:
            logger.error(f"Execute failed: {e}")
            return {"error": str(e), "success": False}

    async def _execute_many(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute statement with multiple parameter sets (bulk insert/update).

        Args:
            payload: {
                "sql": str - SQL statement (parameterized)
                "params_list": List[List] - List of parameter sets
            }

        Returns:
            {
                "affected": int - Total number of rows affected
                "success": bool
            }
        """
        sql = payload.get("sql")
        params_list = payload.get("params_list", [])

        if not sql:
            return {"error": "No SQL statement specified", "success": False}

        if not params_list:
            return {"error": "No parameter sets provided", "success": False}

        try:
            pool = await self._get_pool()

            async with pool.acquire() as conn:
                await conn.executemany(sql, params_list)

                return {
                    "affected": len(params_list),
                    "success": True,
                }

        except Exception as e:
            logger.error(f"Execute many failed: {e}")
            return {"error": str(e), "success": False}

    async def _transaction(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute multiple statements in a transaction.

        Args:
            payload: {
                "statements": List[Dict] - List of {sql: str, params: List}
            }

        Returns:
            {
                "results": List[Any] - Results for each statement
                "success": bool
            }
        """
        statements = payload.get("statements", [])

        if not statements:
            return {"error": "No statements provided", "success": False}

        try:
            pool = await self._get_pool()

            async with pool.acquire() as conn:
                async with conn.transaction():
                    results = []

                    for stmt in statements:
                        sql = stmt.get("sql")
                        params = stmt.get("params", [])

                        if not sql:
                            raise ValueError("Statement missing SQL")

                        result = await conn.execute(sql, *params)
                        results.append(result)

                    return {
                        "results": results,
                        "success": True,
                    }

        except Exception as e:
            logger.error(f"Transaction failed: {e}")
            return {"error": str(e), "success": False}

    async def _copy_from(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Bulk COPY from data (fast bulk insert).

        Args:
            payload: {
                "table": str - Table name
                "columns": List[str] - Column names
                "records": List[List] - Records to insert
                "schema": str - Schema name (default: "public")
            }

        Returns:
            {
                "copied": int - Number of records copied
                "success": bool
            }
        """
        table = payload.get("table")
        columns = payload.get("columns", [])
        records = payload.get("records", [])
        schema = payload.get("schema", "public")

        if not table:
            return {"error": "No table specified", "success": False}

        if not columns:
            return {"error": "No columns specified", "success": False}

        if not records:
            return {"error": "No records provided", "success": False}

        # Validate table and schema names
        if not self._validate_table_name(table):
            return {"error": f"Invalid table name: {table}", "success": False}

        if not self._validate_table_name(schema):
            return {"error": f"Invalid schema name: {schema}", "success": False}

        # Validate column names
        for col in columns:
            if not self._validate_table_name(col):
                return {"error": f"Invalid column name: {col}", "success": False}

        try:
            pool = await self._get_pool()

            async with pool.acquire() as conn:
                result = await conn.copy_records_to_table(
                    table,
                    records=records,
                    columns=columns,
                    schema_name=schema,
                )

                # Result format is "COPY N"
                copied = 0
                if result:
                    parts = result.split()
                    if len(parts) >= 2:
                        try:
                            copied = int(parts[-1])
                        except ValueError:
                            copied = len(records)

                return {
                    "copied": copied,
                    "success": True,
                }

        except Exception as e:
            logger.error(f"Copy from failed: {e}")
            return {"error": str(e), "success": False}

    async def _table_exists(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Check if table exists.

        Args:
            payload: {
                "table": str - Table name
                "schema": str - Schema name (default: "public")
            }

        Returns:
            {
                "exists": bool - Whether table exists
                "success": bool
            }
        """
        table = payload.get("table")
        schema = payload.get("schema", "public")

        if not table:
            return {"error": "No table specified", "success": False}

        # Validate names
        if not self._validate_table_name(table):
            return {"error": f"Invalid table name: {table}", "success": False}

        if not self._validate_table_name(schema):
            return {"error": f"Invalid schema name: {schema}", "success": False}

        try:
            pool = await self._get_pool()

            async with pool.acquire() as conn:
                result = await conn.fetchval(
                    """
                    SELECT EXISTS (
                        SELECT 1
                        FROM information_schema.tables
                        WHERE table_schema = $1
                        AND table_name = $2
                    )
                    """,
                    schema,
                    table,
                )

                return {
                    "exists": bool(result),
                    "success": True,
                }

        except Exception as e:
            logger.error(f"Table exists check failed: {e}")
            return {"error": str(e), "success": False}

    async def _count(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Count rows in table with optional filter.

        Args:
            payload: {
                "table": str - Table name
                "where": str - WHERE clause (parameterized, optional)
                "params": List - WHERE clause parameters (default: [])
                "schema": str - Schema name (default: "public")
            }

        Returns:
            {
                "count": int - Number of rows
                "success": bool
            }
        """
        table = payload.get("table")
        where = payload.get("where", "")
        params = payload.get("params", [])
        schema = payload.get("schema", "public")

        if not table:
            return {"error": "No table specified", "success": False}

        # Validate table and schema names
        if not self._validate_table_name(table):
            return {"error": f"Invalid table name: {table}", "success": False}

        if not self._validate_table_name(schema):
            return {"error": f"Invalid schema name: {schema}", "success": False}

        try:
            pool = await self._get_pool()

            async with pool.acquire() as conn:
                # Build query (safe since we validated table/schema names)
                if where:
                    sql = f'SELECT COUNT(*) FROM "{schema}"."{table}" WHERE {where}'
                else:
                    sql = f'SELECT COUNT(*) FROM "{schema}"."{table}"'

                count = await conn.fetchval(sql, *params)

                return {
                    "count": count or 0,
                    "success": True,
                }

        except Exception as e:
            logger.error(f"Count failed: {e}")
            return {"error": str(e), "success": False}
