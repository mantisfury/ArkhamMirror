# Phase 6: Audit Logging Implementation Plan

**Status: COMPLETE**

## Overview

Implement comprehensive audit logging for security-relevant actions. This enables accountability, compliance, and forensic analysis of user activities within tenants.

## Scope

Based on the security plan, Phase 6 includes:
1. **Audit Events Table** - Database schema for persistent audit logs
2. **Audit Service** - Backend service for logging events
3. **Audit Middleware** - Automatic capture of auth events
4. **Audit API** - Endpoints for viewing/filtering logs
5. **Audit Viewer UI** - Admin page at `/settings/audit`
6. **Export Capability** - Download audit logs as CSV/JSON

## Design Decisions

### Event Categories

| Category | Events |
|----------|--------|
| Authentication | `auth.login.success`, `auth.login.failure`, `auth.logout`, `auth.token.refresh` |
| User Management | `user.created`, `user.updated`, `user.deleted`, `user.deactivated`, `user.reactivated` |
| Role Changes | `user.role.changed` |
| Tenant | `tenant.created`, `tenant.updated` |
| Data Access | `document.accessed`, `project.accessed` (optional, deferred) |

### Audit Event Structure

```python
@dataclass
class AuditEvent:
    id: UUID
    tenant_id: UUID
    user_id: UUID | None        # None for unauthenticated events (failed login)
    event_type: str             # e.g., "auth.login.success"
    target_type: str | None     # e.g., "user", "document"
    target_id: str | None       # ID of the affected resource
    action: str                 # e.g., "create", "read", "update", "delete"
    details: dict               # Additional context (JSON)
    ip_address: str | None
    user_agent: str | None
    timestamp: datetime
```

### Retention Policy

- Default: 90 days retention
- Configurable via environment variable `AUDIT_RETENTION_DAYS`
- Cleanup job runs daily

## Backend Implementation

### File Structure

```
packages/arkham-frame/arkham_frame/auth/
├── schema.sql              # MODIFIED - Add audit tables
├── audit.py                # NEW - Audit service and models
├── router.py               # MODIFIED - Add audit endpoints + logging calls
└── dependencies.py         # MODIFIED - Add audit dependency
```

### Step 1: Database Schema

Add to `auth/schema.sql`:

```sql
-- Audit events table
CREATE TABLE IF NOT EXISTS arkham_auth.audit_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES arkham_auth.tenants(id) ON DELETE CASCADE,
    user_id UUID REFERENCES arkham_auth.users(id) ON DELETE SET NULL,
    event_type VARCHAR(100) NOT NULL,
    target_type VARCHAR(50),
    target_id VARCHAR(255),
    action VARCHAR(50) NOT NULL,
    details JSONB DEFAULT '{}',
    ip_address VARCHAR(45),
    user_agent TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_tenant ON arkham_auth.audit_events(tenant_id);
CREATE INDEX IF NOT EXISTS idx_audit_user ON arkham_auth.audit_events(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_type ON arkham_auth.audit_events(event_type);
CREATE INDEX IF NOT EXISTS idx_audit_created ON arkham_auth.audit_events(created_at);
CREATE INDEX IF NOT EXISTS idx_audit_target ON arkham_auth.audit_events(target_type, target_id);
```

### Step 2: Audit Service

Create `auth/audit.py`:

```python
from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

class AuditEventCreate(BaseModel):
    event_type: str
    action: str
    target_type: Optional[str] = None
    target_id: Optional[str] = None
    details: dict = {}

class AuditEventRead(BaseModel):
    id: UUID
    tenant_id: Optional[UUID]
    user_id: Optional[UUID]
    user_email: Optional[str]  # Joined from users table
    event_type: str
    target_type: Optional[str]
    target_id: Optional[str]
    action: str
    details: dict
    ip_address: Optional[str]
    user_agent: Optional[str]
    created_at: datetime

async def log_audit_event(
    session: AsyncSession,
    event_type: str,
    action: str,
    tenant_id: Optional[UUID] = None,
    user_id: Optional[UUID] = None,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    details: dict = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> None:
    """Log an audit event to the database."""
    # Insert via raw SQL for simplicity
    ...

async def get_audit_events(
    session: AsyncSession,
    tenant_id: UUID,
    event_type: Optional[str] = None,
    user_id: Optional[UUID] = None,
    target_type: Optional[str] = None,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    limit: int = 100,
    offset: int = 0,
) -> list[AuditEventRead]:
    """Query audit events with filters."""
    ...
```

### Step 3: Add Audit Logging to Auth Router

Modify existing endpoints in `router.py` to log events:

```python
# After successful login
await log_audit_event(
    session,
    event_type="auth.login.success",
    action="authenticate",
    tenant_id=user.tenant_id,
    user_id=user.id,
    ip_address=request.client.host,
    user_agent=request.headers.get("user-agent"),
)

# After failed login
await log_audit_event(
    session,
    event_type="auth.login.failure",
    action="authenticate",
    details={"email": email, "reason": "invalid_credentials"},
    ip_address=request.client.host,
    user_agent=request.headers.get("user-agent"),
)

# After user operations
await log_audit_event(
    session,
    event_type="user.created",
    action="create",
    tenant_id=user.tenant_id,
    user_id=admin.id,
    target_type="user",
    target_id=str(new_user.id),
    details={"email": new_user.email, "role": new_user.role},
    ...
)
```

### Step 4: Audit API Endpoints

Add to `router.py`:

```python
@router.get("/audit", response_model=AuditListResponse)
async def list_audit_events(
    event_type: Optional[str] = None,
    user_id: Optional[str] = None,
    target_type: Optional[str] = None,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    limit: int = Query(50, le=500),
    offset: int = 0,
    user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_async_session),
):
    """List audit events for current tenant."""
    ...

@router.get("/audit/export")
async def export_audit_events(
    format: str = Query("csv", regex="^(csv|json)$"),
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_async_session),
):
    """Export audit events as CSV or JSON."""
    ...

@router.get("/audit/stats")
async def audit_stats(
    user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_async_session),
):
    """Get audit event statistics."""
    ...
```

## Frontend Implementation

### File Structure

```
packages/arkham-shard-shell/src/
├── pages/settings/
│   ├── AuditPage.tsx         # NEW - Audit log viewer
│   ├── AuditPage.css         # NEW - Styles
│   └── index.ts              # MODIFIED - Export AuditPage
├── App.tsx                   # MODIFIED - Add route
```

### AuditPage Features

1. **Event List**
   - Table with columns: Time, User, Event Type, Action, Target, IP Address
   - Click row to expand details

2. **Filters**
   - Date range picker (from/to)
   - Event type dropdown
   - User search
   - Target type filter

3. **Export**
   - Export as CSV button
   - Export as JSON button
   - Date range selection for export

4. **Statistics Dashboard** (optional)
   - Events per day chart
   - Top event types
   - Failed login attempts

### UI Patterns

Follow existing patterns from:
- `UsersPage.tsx` - List layout, filters, action buttons
- `SettingsPage.css` - Card styles, form groups

## API Endpoints Summary

| Endpoint | Method | Purpose | Auth |
|----------|--------|---------|------|
| `/api/auth/audit` | GET | List audit events | Admin |
| `/api/auth/audit/export` | GET | Export as CSV/JSON | Admin |
| `/api/auth/audit/stats` | GET | Get statistics | Admin |

## Implementation Order

1. Add audit table schema to `schema.sql`
2. Create `audit.py` with service functions
3. Add audit logging to existing auth endpoints
4. Add audit API endpoints to router
5. Create `AuditPage.tsx` frontend
6. Add route to `App.tsx`
7. Add styles
8. Test all flows

## Testing Checklist

- [x] Audit table created on startup
- [ ] Login success logged (deferred - requires FastAPI-Users hook)
- [ ] Login failure logged (deferred - requires FastAPI-Users hook)
- [x] User creation logged
- [x] User update logged
- [x] User deletion logged
- [x] Role change logged
- [x] Audit list endpoint works
- [x] Filters work correctly
- [x] Export CSV works
- [x] Export JSON works
- [x] IP address captured
- [x] User agent captured
- [x] Admin-only access enforced
- [x] Tenant isolation enforced

## Environment Variables

```env
AUDIT_RETENTION_DAYS=90         # Days to keep audit logs
AUDIT_CLEANUP_ENABLED=true      # Enable automatic cleanup
```

## Deferred Items

1. **Data Access Logging** - Log document/project reads (high volume)
2. **Retention Cleanup Job** - Scheduled deletion of old events
3. **Real-time Updates** - WebSocket for live audit feed
4. **Alert Rules** - Trigger alerts on suspicious activity
