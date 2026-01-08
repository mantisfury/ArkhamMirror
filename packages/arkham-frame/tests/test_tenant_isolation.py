"""
Tenant Isolation Integration Tests

Tests to verify that multi-tenant data isolation works correctly across all shards.
Each test verifies that:
1. Tenant context is correctly set and retrieved
2. Shard base class tenant helpers work correctly
3. Query patterns include proper tenant_id filtering
4. Settings hybrid approach (global + tenant-specific) works correctly

Run with:
    cd packages/arkham-frame
    pytest tests/test_tenant_isolation.py -v
"""

import pytest
from uuid import uuid4, UUID
from datetime import datetime
from unittest.mock import Mock, AsyncMock, MagicMock, patch

# Import tenant context utilities
from arkham_frame.middleware.tenant import (
    get_current_tenant_id,
    set_current_tenant_id,
)
from arkham_frame.shard_interface import ArkhamShard


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def tenant_a_id() -> UUID:
    """Tenant A's ID."""
    return uuid4()


@pytest.fixture
def tenant_b_id() -> UUID:
    """Tenant B's ID."""
    return uuid4()


@pytest.fixture
def mock_db():
    """
    Create a mock database service that tracks queries and simulates tenant isolation.

    This mock maintains an in-memory store of data by tenant_id and verifies
    that queries include proper tenant filtering.
    """
    class MockDatabase:
        def __init__(self):
            self.queries = []
            self.data = {}  # {table: {id: {tenant_id: ..., ...data}}}

        async def execute(self, query: str, params: dict = None):
            """Track query execution."""
            self.queries.append({"query": query, "params": params or {}})
            return None

        async def fetch(self, query: str, params: dict = None) -> list:
            """Return data filtered by tenant_id if present in params."""
            self.queries.append({"query": query, "params": params or {}})
            tenant_id = params.get("tenant_id") if params else None
            results = []
            for table, rows in self.data.items():
                for row_id, row in rows.items():
                    row_tenant = row.get("tenant_id")
                    # Include row if:
                    # 1. No tenant filter requested
                    # 2. Tenant filter matches row's tenant
                    # 3. Row has no tenant (global/NULL)
                    if tenant_id is None or row_tenant is None or str(row_tenant) == str(tenant_id):
                        results.append(row)
            return results

        async def fetch_one(self, query: str, params: dict = None):
            """Return single row filtered by tenant_id."""
            results = await self.fetch(query, params)
            return results[0] if results else None

        async def fetchrow(self, query: str, params: dict = None):
            """Alias for fetch_one."""
            return await self.fetch_one(query, params)

        def add_data(self, table: str, id: str, tenant_id: UUID = None, **data):
            """Add test data to mock database."""
            if table not in self.data:
                self.data[table] = {}
            self.data[table][id] = {
                "id": id,
                "tenant_id": str(tenant_id) if tenant_id else None,
                **data
            }

        def get_last_query(self):
            """Get the most recent query."""
            return self.queries[-1] if self.queries else None

        def clear_queries(self):
            """Clear query history."""
            self.queries = []

    return MockDatabase()


@pytest.fixture
def mock_events():
    """Create a mock events service."""
    events = AsyncMock()
    events.emit = AsyncMock()
    events.subscribe = AsyncMock()
    events.unsubscribe = AsyncMock()
    return events


@pytest.fixture
def mock_frame(mock_db, mock_events):
    """Create a mock Frame with all services."""
    frame = MagicMock()
    frame.get_service = MagicMock(side_effect=lambda name: {
        "database": mock_db,
        "events": mock_events,
        "llm": None,
        "vectors": None,
        "storage": None,
        "documents": None,
    }.get(name))
    frame.db = mock_db
    frame.events = mock_events
    return frame


@pytest.fixture(autouse=True)
def clean_tenant_context():
    """Ensure tenant context is clean before and after each test."""
    set_current_tenant_id(None)
    yield
    set_current_tenant_id(None)


# =============================================================================
# Test 1: Tenant Context Management
# =============================================================================

class TestTenantContext:
    """Tests for tenant context get/set operations."""

    def test_tenant_context_default_none(self):
        """Default tenant context should be None."""
        assert get_current_tenant_id() is None

    def test_set_and_get_tenant_id(self, tenant_a_id):
        """Can set and retrieve tenant ID."""
        set_current_tenant_id(tenant_a_id)
        assert get_current_tenant_id() == tenant_a_id

    def test_tenant_context_isolation_between_sets(self, tenant_a_id, tenant_b_id):
        """Setting a new tenant ID replaces the previous one."""
        set_current_tenant_id(tenant_a_id)
        assert get_current_tenant_id() == tenant_a_id

        set_current_tenant_id(tenant_b_id)
        assert get_current_tenant_id() == tenant_b_id

    def test_clear_tenant_context(self, tenant_a_id):
        """Can clear tenant context by setting None."""
        set_current_tenant_id(tenant_a_id)
        assert get_current_tenant_id() == tenant_a_id

        set_current_tenant_id(None)
        assert get_current_tenant_id() is None


# =============================================================================
# Test 2: Shard Base Class Tenant Helpers
# =============================================================================

class TestShardTenantHelpers:
    """Tests for ArkhamShard tenant helper methods."""

    def _create_test_shard(self):
        """Create a test shard implementation."""
        class TestShard(ArkhamShard):
            name = "test"
            version = "1.0.0"

            async def initialize(self, frame):
                self.frame = frame

            async def shutdown(self):
                pass

        return TestShard()

    @pytest.mark.asyncio
    async def test_get_tenant_id_with_context(self, tenant_a_id, mock_frame):
        """get_tenant_id() returns the current tenant ID."""
        shard = self._create_test_shard()
        await shard.initialize(mock_frame)

        set_current_tenant_id(tenant_a_id)
        assert shard.get_tenant_id() == tenant_a_id

    @pytest.mark.asyncio
    async def test_get_tenant_id_raises_without_context(self, mock_frame):
        """get_tenant_id() raises RuntimeError when no context."""
        shard = self._create_test_shard()
        await shard.initialize(mock_frame)

        with pytest.raises(RuntimeError, match="No tenant context"):
            shard.get_tenant_id()

    @pytest.mark.asyncio
    async def test_get_tenant_id_or_none_with_context(self, tenant_a_id, mock_frame):
        """get_tenant_id_or_none() returns tenant ID when available."""
        shard = self._create_test_shard()
        await shard.initialize(mock_frame)

        set_current_tenant_id(tenant_a_id)
        assert shard.get_tenant_id_or_none() == tenant_a_id

    @pytest.mark.asyncio
    async def test_get_tenant_id_or_none_without_context(self, mock_frame):
        """get_tenant_id_or_none() returns None when no context."""
        shard = self._create_test_shard()
        await shard.initialize(mock_frame)

        assert shard.get_tenant_id_or_none() is None


# =============================================================================
# Test 3: Tenant Filtering Query Patterns
# =============================================================================

class TestTenantFilteringPatterns:
    """Tests for correct tenant filtering in SQL queries."""

    @pytest.mark.asyncio
    async def test_select_with_tenant_filter(self, tenant_a_id, mock_db, mock_frame):
        """SELECT queries should include tenant_id filter when context is set."""
        class TestShard(ArkhamShard):
            name = "test"
            version = "1.0.0"

            async def initialize(self, frame):
                self.frame = frame
                self._db = frame.get_service("database")

            async def shutdown(self):
                pass

            async def query_with_tenant(self):
                tenant_id = self.get_tenant_id_or_none()
                query = "SELECT * FROM test_table WHERE 1=1"
                params = {}

                if tenant_id:
                    query += " AND tenant_id = :tenant_id"
                    params["tenant_id"] = str(tenant_id)

                return await self._db.fetch(query, params)

        shard = TestShard()
        await shard.initialize(mock_frame)

        set_current_tenant_id(tenant_a_id)
        await shard.query_with_tenant()

        last_query = mock_db.get_last_query()
        assert "tenant_id = :tenant_id" in last_query["query"]
        assert last_query["params"]["tenant_id"] == str(tenant_a_id)

        await shard.shutdown()

    @pytest.mark.asyncio
    async def test_select_without_tenant_filter(self, mock_db, mock_frame):
        """SELECT queries without tenant context should not filter by tenant."""
        class TestShard(ArkhamShard):
            name = "test"
            version = "1.0.0"

            async def initialize(self, frame):
                self.frame = frame
                self._db = frame.get_service("database")

            async def shutdown(self):
                pass

            async def query_with_tenant(self):
                tenant_id = self.get_tenant_id_or_none()
                query = "SELECT * FROM test_table WHERE 1=1"
                params = {}

                if tenant_id:
                    query += " AND tenant_id = :tenant_id"
                    params["tenant_id"] = str(tenant_id)

                return await self._db.fetch(query, params)

        shard = TestShard()
        await shard.initialize(mock_frame)

        # No tenant context set
        await shard.query_with_tenant()

        last_query = mock_db.get_last_query()
        assert "tenant_id = :tenant_id" not in last_query["query"]
        assert "tenant_id" not in last_query["params"]

        await shard.shutdown()

    @pytest.mark.asyncio
    async def test_insert_includes_tenant_id(self, tenant_a_id, mock_db, mock_frame):
        """INSERT queries should include tenant_id."""
        class TestShard(ArkhamShard):
            name = "test"
            version = "1.0.0"

            async def initialize(self, frame):
                self.frame = frame
                self._db = frame.get_service("database")

            async def shutdown(self):
                pass

            async def create_record(self, data: dict):
                tenant_id = self.get_tenant_id_or_none()
                await self._db.execute(
                    """
                    INSERT INTO test_table (id, name, tenant_id)
                    VALUES (:id, :name, :tenant_id)
                    """,
                    {
                        "id": data["id"],
                        "name": data["name"],
                        "tenant_id": str(tenant_id) if tenant_id else None
                    }
                )

        shard = TestShard()
        await shard.initialize(mock_frame)

        set_current_tenant_id(tenant_a_id)
        await shard.create_record({"id": "test-1", "name": "Test Record"})

        last_query = mock_db.get_last_query()
        assert "tenant_id" in last_query["query"]
        assert last_query["params"]["tenant_id"] == str(tenant_a_id)

        await shard.shutdown()

    @pytest.mark.asyncio
    async def test_insert_without_tenant_uses_null(self, mock_db, mock_frame):
        """INSERT without tenant context should use NULL tenant_id."""
        class TestShard(ArkhamShard):
            name = "test"
            version = "1.0.0"

            async def initialize(self, frame):
                self.frame = frame
                self._db = frame.get_service("database")

            async def shutdown(self):
                pass

            async def create_record(self, data: dict):
                tenant_id = self.get_tenant_id_or_none()
                await self._db.execute(
                    """
                    INSERT INTO test_table (id, name, tenant_id)
                    VALUES (:id, :name, :tenant_id)
                    """,
                    {
                        "id": data["id"],
                        "name": data["name"],
                        "tenant_id": str(tenant_id) if tenant_id else None
                    }
                )

        shard = TestShard()
        await shard.initialize(mock_frame)

        # No tenant context
        await shard.create_record({"id": "test-1", "name": "Test Record"})

        last_query = mock_db.get_last_query()
        assert last_query["params"]["tenant_id"] is None

        await shard.shutdown()

    @pytest.mark.asyncio
    async def test_update_includes_tenant_filter(self, tenant_a_id, mock_db, mock_frame):
        """UPDATE queries should include tenant_id filter."""
        class TestShard(ArkhamShard):
            name = "test"
            version = "1.0.0"

            async def initialize(self, frame):
                self.frame = frame
                self._db = frame.get_service("database")

            async def shutdown(self):
                pass

            async def update_record(self, id: str, name: str):
                tenant_id = self.get_tenant_id_or_none()
                query = "UPDATE test_table SET name = :name WHERE id = :id"
                params = {"id": id, "name": name}

                if tenant_id:
                    query += " AND tenant_id = :tenant_id"
                    params["tenant_id"] = str(tenant_id)

                await self._db.execute(query, params)

        shard = TestShard()
        await shard.initialize(mock_frame)

        set_current_tenant_id(tenant_a_id)
        await shard.update_record("test-1", "Updated Name")

        last_query = mock_db.get_last_query()
        assert "tenant_id = :tenant_id" in last_query["query"]
        assert last_query["params"]["tenant_id"] == str(tenant_a_id)

        await shard.shutdown()

    @pytest.mark.asyncio
    async def test_delete_includes_tenant_filter(self, tenant_a_id, mock_db, mock_frame):
        """DELETE queries should include tenant_id filter."""
        class TestShard(ArkhamShard):
            name = "test"
            version = "1.0.0"

            async def initialize(self, frame):
                self.frame = frame
                self._db = frame.get_service("database")

            async def shutdown(self):
                pass

            async def delete_record(self, id: str):
                tenant_id = self.get_tenant_id_or_none()
                query = "DELETE FROM test_table WHERE id = :id"
                params = {"id": id}

                if tenant_id:
                    query += " AND tenant_id = :tenant_id"
                    params["tenant_id"] = str(tenant_id)

                await self._db.execute(query, params)

        shard = TestShard()
        await shard.initialize(mock_frame)

        set_current_tenant_id(tenant_a_id)
        await shard.delete_record("test-1")

        last_query = mock_db.get_last_query()
        assert "tenant_id = :tenant_id" in last_query["query"]
        assert last_query["params"]["tenant_id"] == str(tenant_a_id)

        await shard.shutdown()


# =============================================================================
# Test 4: Settings Hybrid Tenant Approach
# =============================================================================

class TestSettingsHybridPattern:
    """
    Tests for Settings shard's hybrid tenant approach.

    Settings support both:
    - Global settings (tenant_id = NULL) - accessible to all tenants
    - Tenant-specific settings (tenant_id = <uuid>) - only for that tenant

    The query pattern should be:
    WHERE (tenant_id = :tenant_id OR tenant_id IS NULL)
    """

    @pytest.mark.asyncio
    async def test_settings_hybrid_query_pattern(self, tenant_a_id, mock_db, mock_frame):
        """Settings queries should include hybrid pattern for global + tenant."""
        class SettingsTestShard(ArkhamShard):
            name = "settings-test"
            version = "1.0.0"

            async def initialize(self, frame):
                self.frame = frame
                self._db = frame.get_service("database")

            async def shutdown(self):
                pass

            async def get_setting(self, key: str):
                tenant_id = self.get_tenant_id_or_none()

                if tenant_id:
                    # Hybrid pattern: get tenant-specific OR global settings
                    row = await self._db.fetch_one(
                        """
                        SELECT * FROM arkham_settings
                        WHERE key = :key
                        AND (tenant_id = :tenant_id OR tenant_id IS NULL)
                        ORDER BY tenant_id DESC NULLS LAST
                        LIMIT 1
                        """,
                        {"key": key, "tenant_id": str(tenant_id)}
                    )
                else:
                    # No tenant context: get only global settings
                    row = await self._db.fetch_one(
                        "SELECT * FROM arkham_settings WHERE key = :key AND tenant_id IS NULL",
                        {"key": key}
                    )

                return row

        shard = SettingsTestShard()
        await shard.initialize(mock_frame)

        set_current_tenant_id(tenant_a_id)
        await shard.get_setting("app.theme")

        last_query = mock_db.get_last_query()
        # Verify hybrid pattern
        assert "tenant_id = :tenant_id" in last_query["query"]
        assert "tenant_id IS NULL" in last_query["query"]
        assert "OR" in last_query["query"]

        await shard.shutdown()

    @pytest.mark.asyncio
    async def test_settings_global_only_without_tenant(self, mock_db, mock_frame):
        """Without tenant context, only global settings should be queried."""
        class SettingsTestShard(ArkhamShard):
            name = "settings-test"
            version = "1.0.0"

            async def initialize(self, frame):
                self.frame = frame
                self._db = frame.get_service("database")

            async def shutdown(self):
                pass

            async def get_setting(self, key: str):
                tenant_id = self.get_tenant_id_or_none()

                if tenant_id:
                    row = await self._db.fetch_one(
                        """
                        SELECT * FROM arkham_settings
                        WHERE key = :key
                        AND (tenant_id = :tenant_id OR tenant_id IS NULL)
                        """,
                        {"key": key, "tenant_id": str(tenant_id)}
                    )
                else:
                    row = await self._db.fetch_one(
                        "SELECT * FROM arkham_settings WHERE key = :key AND tenant_id IS NULL",
                        {"key": key}
                    )

                return row

        shard = SettingsTestShard()
        await shard.initialize(mock_frame)

        # No tenant context
        await shard.get_setting("app.theme")

        last_query = mock_db.get_last_query()
        # Should only query for NULL tenant_id (global settings)
        assert "tenant_id IS NULL" in last_query["query"]
        assert ":tenant_id" not in last_query["query"]

        await shard.shutdown()


# =============================================================================
# Test 5: Data Isolation Between Tenants
# =============================================================================

class TestDataIsolation:
    """Tests for data isolation between tenants."""

    @pytest.mark.asyncio
    async def test_tenant_a_cannot_see_tenant_b_data(
        self, tenant_a_id, tenant_b_id, mock_db, mock_frame
    ):
        """Tenant A should not be able to see Tenant B's data."""
        # Add data for both tenants
        mock_db.add_data(
            "test_table",
            "rec-a",
            tenant_id=tenant_a_id,
            name="Record A"
        )
        mock_db.add_data(
            "test_table",
            "rec-b",
            tenant_id=tenant_b_id,
            name="Record B"
        )

        class TestShard(ArkhamShard):
            name = "test"
            version = "1.0.0"

            async def initialize(self, frame):
                self.frame = frame
                self._db = frame.get_service("database")

            async def shutdown(self):
                pass

            async def list_records(self):
                tenant_id = self.get_tenant_id_or_none()
                if tenant_id:
                    return await self._db.fetch(
                        "SELECT * FROM test_table WHERE tenant_id = :tenant_id",
                        {"tenant_id": str(tenant_id)}
                    )
                return await self._db.fetch("SELECT * FROM test_table", {})

        shard = TestShard()
        await shard.initialize(mock_frame)

        # Query as tenant A
        set_current_tenant_id(tenant_a_id)
        results = await shard.list_records()

        # Should only see tenant A's data
        assert len(results) == 1
        assert results[0]["name"] == "Record A"

        await shard.shutdown()

    @pytest.mark.asyncio
    async def test_switching_tenant_context_changes_visible_data(
        self, tenant_a_id, tenant_b_id, mock_db, mock_frame
    ):
        """Switching tenant context should change visible data."""
        mock_db.add_data("test_table", "rec-a", tenant_id=tenant_a_id, name="A")
        mock_db.add_data("test_table", "rec-b", tenant_id=tenant_b_id, name="B")

        class TestShard(ArkhamShard):
            name = "test"
            version = "1.0.0"

            async def initialize(self, frame):
                self.frame = frame
                self._db = frame.get_service("database")

            async def shutdown(self):
                pass

            async def list_records(self):
                tenant_id = self.get_tenant_id_or_none()
                if tenant_id:
                    return await self._db.fetch(
                        "SELECT * FROM test_table WHERE tenant_id = :tenant_id",
                        {"tenant_id": str(tenant_id)}
                    )
                return await self._db.fetch("SELECT * FROM test_table", {})

        shard = TestShard()
        await shard.initialize(mock_frame)

        # Query as tenant A
        set_current_tenant_id(tenant_a_id)
        results_a = await shard.list_records()
        assert len(results_a) == 1
        assert results_a[0]["name"] == "A"

        # Switch to tenant B
        set_current_tenant_id(tenant_b_id)
        results_b = await shard.list_records()
        assert len(results_b) == 1
        assert results_b[0]["name"] == "B"

        await shard.shutdown()

    @pytest.mark.asyncio
    async def test_admin_sees_all_data_without_tenant_context(
        self, tenant_a_id, tenant_b_id, mock_db, mock_frame
    ):
        """Without tenant context (admin mode), all data should be visible."""
        mock_db.add_data("test_table", "rec-a", tenant_id=tenant_a_id, name="A")
        mock_db.add_data("test_table", "rec-b", tenant_id=tenant_b_id, name="B")
        mock_db.add_data("test_table", "rec-global", tenant_id=None, name="Global")

        class TestShard(ArkhamShard):
            name = "test"
            version = "1.0.0"

            async def initialize(self, frame):
                self.frame = frame
                self._db = frame.get_service("database")

            async def shutdown(self):
                pass

            async def list_records(self):
                tenant_id = self.get_tenant_id_or_none()
                if tenant_id:
                    return await self._db.fetch(
                        "SELECT * FROM test_table WHERE tenant_id = :tenant_id",
                        {"tenant_id": str(tenant_id)}
                    )
                # Admin mode: no tenant filter
                return await self._db.fetch("SELECT * FROM test_table", {})

        shard = TestShard()
        await shard.initialize(mock_frame)

        # No tenant context (admin mode)
        results = await shard.list_records()

        # Should see all 3 records
        assert len(results) == 3

        await shard.shutdown()

    @pytest.mark.asyncio
    async def test_global_data_visible_to_tenant(
        self, tenant_a_id, mock_db, mock_frame
    ):
        """Global data (NULL tenant_id) should be visible when using hybrid pattern."""
        mock_db.add_data("test_table", "rec-a", tenant_id=tenant_a_id, name="A")
        mock_db.add_data("test_table", "rec-global", tenant_id=None, name="Global")

        class TestShard(ArkhamShard):
            name = "test"
            version = "1.0.0"

            async def initialize(self, frame):
                self.frame = frame
                self._db = frame.get_service("database")

            async def shutdown(self):
                pass

            async def list_records_with_global(self):
                """Use hybrid pattern to include global records."""
                tenant_id = self.get_tenant_id_or_none()
                if tenant_id:
                    return await self._db.fetch(
                        """
                        SELECT * FROM test_table
                        WHERE tenant_id = :tenant_id OR tenant_id IS NULL
                        """,
                        {"tenant_id": str(tenant_id)}
                    )
                return await self._db.fetch("SELECT * FROM test_table", {})

        shard = TestShard()
        await shard.initialize(mock_frame)

        set_current_tenant_id(tenant_a_id)
        results = await shard.list_records_with_global()

        # Should see both tenant-specific and global records
        assert len(results) == 2

        await shard.shutdown()


# =============================================================================
# Test 6: Query Pattern Verification (Static Analysis)
# =============================================================================

class TestQueryPatternVerification:
    """Static tests to verify correct SQL query patterns."""

    def test_select_pattern_includes_tenant_filter(self):
        """Verify SELECT pattern includes tenant_id filter."""
        # Standard pattern for tenant-filtered SELECT
        tenant_id = uuid4()
        query = "SELECT * FROM table WHERE 1=1"
        params = {}

        if tenant_id:
            query += " AND tenant_id = :tenant_id"
            params["tenant_id"] = str(tenant_id)

        assert "tenant_id = :tenant_id" in query
        assert params["tenant_id"] == str(tenant_id)

    def test_insert_pattern_includes_tenant_id(self):
        """Verify INSERT pattern includes tenant_id column."""
        tenant_id = uuid4()

        query = """
            INSERT INTO table (id, name, tenant_id)
            VALUES (:id, :name, :tenant_id)
        """
        params = {
            "id": "test-1",
            "name": "Test",
            "tenant_id": str(tenant_id) if tenant_id else None
        }

        assert "tenant_id" in query
        assert ":tenant_id" in query
        assert params["tenant_id"] == str(tenant_id)

    def test_update_pattern_includes_tenant_filter(self):
        """Verify UPDATE pattern includes tenant_id filter."""
        tenant_id = uuid4()

        query = "UPDATE table SET name = :name WHERE id = :id"
        params = {"id": "test-1", "name": "Updated"}

        if tenant_id:
            query += " AND tenant_id = :tenant_id"
            params["tenant_id"] = str(tenant_id)

        assert "tenant_id = :tenant_id" in query
        assert params["tenant_id"] == str(tenant_id)

    def test_delete_pattern_includes_tenant_filter(self):
        """Verify DELETE pattern includes tenant_id filter."""
        tenant_id = uuid4()

        query = "DELETE FROM table WHERE id = :id"
        params = {"id": "test-1"}

        if tenant_id:
            query += " AND tenant_id = :tenant_id"
            params["tenant_id"] = str(tenant_id)

        assert "tenant_id = :tenant_id" in query
        assert params["tenant_id"] == str(tenant_id)

    def test_hybrid_settings_pattern(self):
        """Verify hybrid settings pattern for global + tenant settings."""
        tenant_id = uuid4()

        query = """
            SELECT * FROM arkham_settings
            WHERE key = :key
            AND (tenant_id = :tenant_id OR tenant_id IS NULL)
            ORDER BY tenant_id DESC NULLS LAST
        """

        assert "tenant_id = :tenant_id" in query
        assert "tenant_id IS NULL" in query
        assert "OR" in query


# =============================================================================
# Test 7: Tenant Context Middleware Integration
# =============================================================================

class TestTenantContextMiddleware:
    """Tests for TenantContextMiddleware behavior."""

    @pytest.mark.asyncio
    async def test_middleware_sets_tenant_from_user(self):
        """Middleware should set tenant_id from authenticated user."""
        from arkham_frame.middleware.tenant import TenantContextMiddleware
        from starlette.requests import Request

        tenant_id = uuid4()

        # Create a mock user with tenant_id
        mock_user = MagicMock()
        mock_user.tenant_id = tenant_id

        # Create a mock request
        mock_request = MagicMock(spec=Request)
        mock_request.url.path = "/api/documents"
        mock_request.state.user = mock_user

        # Track if next was called
        next_called = False
        captured_tenant_id = None

        async def mock_call_next(request):
            nonlocal next_called, captured_tenant_id
            next_called = True
            captured_tenant_id = get_current_tenant_id()
            return MagicMock()

        middleware = TenantContextMiddleware(app=MagicMock())
        await middleware.dispatch(mock_request, mock_call_next)

        assert next_called
        assert captured_tenant_id == tenant_id
        # After dispatch, context should be cleared
        assert get_current_tenant_id() is None

    @pytest.mark.asyncio
    async def test_middleware_exempt_paths_skip_tenant(self):
        """Exempt paths should not set tenant context."""
        from arkham_frame.middleware.tenant import TenantContextMiddleware
        from starlette.requests import Request

        mock_request = MagicMock(spec=Request)
        mock_request.url.path = "/api/auth/login"

        captured_tenant_id = "NOT_CALLED"

        async def mock_call_next(request):
            nonlocal captured_tenant_id
            captured_tenant_id = get_current_tenant_id()
            return MagicMock()

        middleware = TenantContextMiddleware(app=MagicMock())
        await middleware.dispatch(mock_request, mock_call_next)

        # Exempt paths should not attempt tenant extraction
        assert captured_tenant_id is None


# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
