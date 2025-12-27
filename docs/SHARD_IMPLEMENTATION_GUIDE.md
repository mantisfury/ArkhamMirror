# Shard Implementation Guide

This guide documents the workflow for implementing a fully functional shard in the SHATTERED architecture. It's based on lessons learned from implementing the Settings shard end-to-end.

## Overview

A complete shard implementation requires work in three areas:
1. **Backend** - Python shard with database operations and API endpoints
2. **Frame Integration** - Ensuring the shard can access Frame services
3. **Frontend** - React UI in the shell

## Prerequisites

Before starting, ensure:
- Docker Desktop is running (PostgreSQL, Redis, Qdrant)
- Frame is installed: `cd packages/arkham-frame && pip install -e .`
- Shard is installed: `cd packages/arkham-shard-{name} && pip install -e .`
- Shell dependencies: `cd packages/arkham-shard-shell && npm install`

## Phase 1: Backend Implementation

### 1.1 Review Existing Shard Structure

Every shard should have:
```
packages/arkham-shard-{name}/
├── pyproject.toml          # Package with entry point
├── shard.yaml              # Manifest v5 format
├── arkham_shard_{name}/
│   ├── __init__.py         # Exports {Name}Shard
│   ├── shard.py            # Main shard class
│   ├── api.py              # FastAPI router
│   ├── models.py           # Pydantic/dataclass models
│   └── services/           # Business logic (optional)
```

### 1.2 Check Database Schema Creation

Most shards need database tables. In `shard.py`, find `_create_schema()`:

```python
async def _create_schema(self) -> None:
    """Create database schema for this shard."""
    await self._db.execute("""
        CREATE TABLE IF NOT EXISTS arkham_{shard_name} (
            id TEXT PRIMARY KEY,
            -- your columns here
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP
        )
    """)

    # Create indexes
    await self._db.execute("""
        CREATE INDEX IF NOT EXISTS idx_arkham_{shard_name}_field
        ON arkham_{shard_name}(field_name)
    """)

    logger.info("{Name} database schema created")
```

**Common issues:**
- Schema creation is a stub (`pass` or empty)
- Missing indexes for frequently queried fields
- JSONB fields not properly defined

### 1.3 Implement Service Methods

Replace stub implementations with real database operations:

```python
async def get_item(self, id: str) -> Optional[Item]:
    """Get item by ID."""
    if not self._db:
        raise RuntimeError("Shard not initialized")

    # Check cache first (if applicable)
    if id in self._cache:
        return self._cache[id]

    # Query database
    row = await self._db.fetch_one(
        "SELECT * FROM arkham_{table} WHERE id = :id",
        {"id": id}
    )

    if row:
        item = self._row_to_item(row)
        self._cache[id] = item
        return item

    return None
```

**Key patterns:**
- Always check `if not self._db: raise RuntimeError("Shard not initialized")`
- Use parameterized queries with `:param` syntax
- Parse JSONB fields: `json.loads(row["json_field"])` if stored as string
- Emit events after mutations: `await self._event_bus.publish("shard.event", data)`

### 1.4 Add JSONB Parser and Row-to-Model Converter

**IMPORTANT:** SQLAlchemy with PostgreSQL JSONB has a tricky behavior. When you store a JSON string value like `"SHATTERED"`, the database stores it as JSONB `"SHATTERED"` (with quotes). But SQLAlchemy returns it as the Python string `'SHATTERED'` (without quotes) - already parsed!

This means:
- Complex values (objects, arrays) come back as Python dicts/lists
- Simple string values come back as Python strings
- If you try `json.loads('SHATTERED')`, it fails because `SHATTERED` is not valid JSON

Create a robust JSONB parser that handles all cases:

```python
def _parse_jsonb(self, value: Any, default: Any = None) -> Any:
    """Parse a JSONB field that may be str, dict, list, or None.

    PostgreSQL JSONB with SQLAlchemy may return:
    - Already parsed Python objects (dict, list, bool, int, float)
    - String that IS the value (when JSON string was stored, e.g., "SHATTERED")
    - String that needs parsing (raw JSON, e.g., '{"key": "value"}')
    """
    if value is None:
        return default
    if isinstance(value, (dict, list, bool, int, float)):
        return value
    if isinstance(value, str):
        if not value or value.strip() == "":
            return default
        # Try to parse as JSON first (for complex values)
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            # If it's not valid JSON, it's already the string value
            # (e.g., JSONB stored "SHATTERED" comes back as 'SHATTERED')
            return value
    return default
```

Then use it in the row converter:

```python
def _row_to_item(self, row: Dict[str, Any]) -> Item:
    """Convert database row to Item object."""
    # Use _parse_jsonb for all JSONB fields
    metadata = self._parse_jsonb(row.get("metadata"), {})
    tags = self._parse_jsonb(row.get("tags"), [])
    config = self._parse_jsonb(row.get("config"), {})

    return Item(
        id=row["id"],
        name=row["name"],
        metadata=metadata,
        tags=tags,
        config=config,
        created_at=row.get("created_at"),
    )
```

### 1.5 Register Shard in App State

For the API to access the shard instance, register it during initialization:

```python
async def initialize(self, frame) -> None:
    # ... existing initialization ...

    # Register self in app state for API access
    if hasattr(frame, "app") and frame.app:
        frame.app.state.{shard_name}_shard = self

    logger.info("{Name} shard initialized")
```

**Note:** This requires Frame to set `frame.app = app` before loading shards (already done in `main.py`).

## Phase 2: API Implementation

### 2.1 Get Shard Instance Helper

Add a helper function to get the shard from app state:

```python
from fastapi import Request, HTTPException

def get_shard(request: Request) -> "{Name}Shard":
    """Get the shard instance from app state."""
    shard = getattr(request.app.state, "{shard_name}_shard", None)
    if not shard:
        raise HTTPException(status_code=503, detail="{Name} shard not available")
    return shard
```

### 2.2 Update Endpoints to Use Real Methods

Replace stub endpoints:

```python
# Before (stub)
@router.get("/", response_model=List[ItemResponse])
async def list_items():
    return []  # Stub

# After (real)
@router.get("/", response_model=List[ItemResponse])
async def list_items(
    request: Request,
    search: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
):
    shard = get_shard(request)
    items = await shard.list_items(search=search, limit=limit)
    return [item_to_response(i) for i in items]
```

### 2.3 Create Response Converter

Convert internal models to API response models:

```python
def item_to_response(item: Item) -> ItemResponse:
    """Convert Item to API response."""
    return ItemResponse(
        id=item.id,
        name=item.name,
        # Convert enums to strings
        status=item.status.value if hasattr(item.status, 'value') else item.status,
        created_at=item.created_at.isoformat() if item.created_at else None,
    )
```

### 2.4 Handle Errors Properly

```python
@router.put("/{id}")
async def update_item(id: str, body: UpdateRequest, request: Request):
    shard = get_shard(request)
    try:
        item = await shard.update_item(id, body.dict())
        if not item:
            raise HTTPException(status_code=404, detail=f"Item not found: {id}")
        return item_to_response(item)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
```

## Phase 3: Frontend Implementation

### 3.1 Create Page Component

Create `src/pages/{shard}/` directory with:

```typescript
// {Shard}Page.tsx
import { useState, useEffect } from 'react';
import { Icon } from '../../components/common/Icon';
import { useToast } from '../../context/ToastContext';
import { useFetch } from '../../hooks/useFetch';
import './{Shard}Page.css';

interface Item {
  id: string;
  name: string;
  // ... fields matching API response
}

export function {Shard}Page() {
  const { toast } = useToast();

  // Fetch data
  const { data, loading, error, refetch } = useFetch<Item[]>('/api/{shard}/');

  // Handle actions
  const handleAction = async (id: string) => {
    try {
      const response = await fetch(`/api/{shard}/${id}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ /* data */ }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Action failed');
      }

      toast.success('Action completed');
      refetch();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Action failed');
    }
  };

  // Render
  return (
    <div className="{shard}-page">
      <header className="page-header">
        <div className="page-title">
          <Icon name="{IconName}" size={28} />
          <div>
            <h1>{Shard Title}</h1>
            <p className="page-description">Description here</p>
          </div>
        </div>
      </header>

      <main>
        {loading && <div>Loading...</div>}
        {error && <div>Error: {error.message}</div>}
        {data && /* render data */}
      </main>
    </div>
  );
}
```

### 3.2 Toast API

The toast context uses method-based API:
```typescript
// Correct
toast.success('Message');
toast.error('Error message');
toast.info('Info message');
toast.warning('Warning message');

// WRONG - this will cause TypeScript errors
toast('Message', 'success');
```

### 3.3 Add Route to App.tsx

```typescript
// Import
import { {Shard}Page } from './pages/{shard}';

// Add route (before catch-all)
<Route path="/{shard}" element={<{Shard}Page />} />
```

### 3.4 Create Index Export

```typescript
// src/pages/{shard}/index.ts
export { {Shard}Page } from './{Shard}Page';
```

### 3.5 Update shard.yaml

Set `has_custom_ui: true` in the shard manifest:

```yaml
ui:
  has_custom_ui: true
```

## Phase 4: Testing

### 4.1 Verify Python Syntax

```bash
python -m py_compile packages/arkham-shard-{name}/arkham_shard_{name}/shard.py
python -m py_compile packages/arkham-shard-{name}/arkham_shard_{name}/api.py
```

### 4.2 Build Frontend

```bash
cd packages/arkham-shard-shell && npm run build
```

Note: Pre-existing errors in other files don't block your work. Focus on errors in files you created/modified.

### 4.3 Start Services

```bash
# Terminal 1 - Backend
python -m uvicorn arkham_frame.main:app --host 127.0.0.1 --port 8105 --reload

# Terminal 2 - Frontend
cd packages/arkham-shard-shell && npm run dev
```

### 4.4 Test API Endpoints

```bash
# Health check
curl http://localhost:8105/api/{shard}/health

# List items
curl http://localhost:8105/api/{shard}/

# Get specific item
curl http://localhost:8105/api/{shard}/{id}
```

### 4.5 Test UI

Navigate to `http://localhost:5173/{shard}` and verify:
- Page loads without errors
- Data fetches correctly
- Actions work (create, update, delete)
- Error handling works

## Common Issues & Solutions

### Issue: "Shard not initialized"
**Cause:** Database service not available or shard didn't initialize properly.
**Solution:** Check Frame startup logs. Ensure Docker is running.

### Issue: "Settings shard not available" (503)
**Cause:** Shard not registered in app.state.
**Solution:** Add `frame.app.state.{name}_shard = self` in initialize().

### Issue: JSONB fields returning strings
**Cause:** PostgreSQL returns JSONB as strings via some drivers.
**Solution:** Parse in row converter: `json.loads(row["field"]) if isinstance(row["field"], str) else row["field"]`

### Issue: TypeScript "not callable" errors for toast
**Cause:** Using `toast('msg', 'type')` instead of `toast.success('msg')`.
**Solution:** Use method syntax: `toast.success()`, `toast.error()`, etc.

### Issue: Route shows "Shard Unavailable"
**Cause:** No explicit route defined, falling through to GenericShardPage.
**Solution:** Add explicit route in App.tsx before the catch-all.

### Issue: EventBus subscribe returns None
**Cause:** subscribe() was sync but called with await.
**Solution:** Already fixed in Frame - subscribe/unsubscribe are async.

### Issue: frame.database not found
**Cause:** Shard uses `frame.database` but Frame only had `frame.db`.
**Solution:** Already fixed in Frame - `database` property alias added.

## Checklist

Before marking a shard as complete:

- [ ] Database schema creates tables and indexes
- [ ] Service methods query real database (not stubs)
- [ ] Shard registers in app.state during initialize
- [ ] API endpoints use get_shard() helper
- [ ] API endpoints return proper responses and handle errors
- [ ] Frontend page created with proper styling
- [ ] Route added to App.tsx
- [ ] shard.yaml has `has_custom_ui: true`
- [ ] Python files pass syntax check
- [ ] Frontend builds without new errors
- [ ] Manual testing confirms functionality

## Reference Implementation

The Settings shard (`packages/arkham-shard-settings/`) serves as the reference implementation. Key files:

- `shard.py` - Complete service methods with database operations
- `api.py` - Endpoints using get_shard() pattern
- `defaults.py` - Default data population
- `src/pages/settings/SettingsPage.tsx` - Full UI implementation
