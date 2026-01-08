# SHATTERED Security Implementation Plan v2

**Created:** January 8, 2026
**Last Updated:** January 8, 2026
**Status:** Phase 4 In Progress

---

## Overview

### Goals

1. Secure all API endpoints with authentication
2. Enable multi-tenant deployments for team use
3. Fix all identified security vulnerabilities
4. Add audit logging for accountability
5. Provide complete frontend authentication UI
6. Optional production-ready deployment with Traefik

### Progress Summary

| Phase | Status | Description |
|-------|--------|-------------|
| Phase 1: Security Fixes | **COMPLETE** | CORS, XSS, headers, rate limiting |
| Phase 2: Auth Backend | **COMPLETE** | FastAPI-Users, JWT, roles |
| Phase 3: Auth Frontend | **COMPLETE** | Login, setup wizard, protected routes |
| Phase 4: Multi-tenant Backend | **IN PROGRESS** | tenant_id across all shards |
| Phase 5: Multi-tenant Frontend | Pending | Tenant selector, user management |
| Phase 6: Audit Logging | Pending | Backend + admin UI viewer |
| Phase 7: Traefik | Pending | Optional HTTPS setup |
| Phase 8: Docs & Polish | Pending | README, help, final polish |

---

## Phase 1: Core Security Fixes - COMPLETE

All security fixes have been implemented:

| Fix | File(s) Modified |
|-----|------------------|
| 1.1 NPM Vulnerabilities | `packages/arkham-shard-shell/package.json` - Vite upgraded to 7.3.1 |
| 1.2 CORS Configuration | `arkham_frame/main.py` - Configurable origins via `CORS_ORIGINS` env var |
| 1.3 Security Headers | `arkham_frame/middleware/__init__.py` - X-Frame-Options, CSP, etc. |
| 1.4 Path Traversal | `arkham_shard_ingest/api.py` - `validate_ingest_path()` function |
| 1.5 XSS Prevention | `arkham-shard-shell/src/utils/sanitize.ts` - DOMPurify integration |
| 1.6 Filename Sanitization | `arkham_shard_ingest/intake.py` - Enhanced `_sanitize_filename()` |
| 1.7 Rate Limiting | `arkham_frame/middleware/rate_limit.py` - slowapi integration |

**Environment Variables Added:**
```env
CORS_ORIGINS=https://your-domain.com
RATE_LIMIT_DEFAULT=100/minute
RATE_LIMIT_UPLOAD=20/minute
RATE_LIMIT_AUTH=10/minute
```

---

## Phase 2: Authentication Backend - COMPLETE

Authentication system implemented with FastAPI-Users:

| Component | File |
|-----------|------|
| Models | `arkham_frame/auth/models.py` - Tenant, User, UserRole |
| Schemas | `arkham_frame/auth/schemas.py` - Pydantic models |
| Manager | `arkham_frame/auth/manager.py` - User lifecycle |
| Dependencies | `arkham_frame/auth/dependencies.py` - JWT, role checks |
| Router | `arkham_frame/auth/router.py` - Auth API endpoints |
| Schema SQL | `arkham_frame/auth/schema.sql` - Database tables |

**API Endpoints:**
- `POST /api/auth/login` - JWT login
- `POST /api/auth/logout` - Token invalidation
- `GET /api/auth/me` - Current user info
- `POST /api/auth/setup` - Initial setup wizard
- `GET /api/auth/setup-required` - Check if setup needed
- `GET /api/auth/users` - List users (admin)
- `POST /api/auth/users` - Create user (admin)

**Environment Variables:**
```env
AUTH_SECRET_KEY=your-secret-key-here
JWT_LIFETIME_SECONDS=86400
```

---

## Phase 3: Authentication Frontend - COMPLETE

React authentication UI components:

| Component | File |
|-----------|------|
| Auth Context | `src/context/AuthContext.tsx` - Global auth state |
| API Client | `src/utils/api.ts` - Fetch with auth headers |
| Login Page | `src/pages/auth/LoginPage.tsx` |
| Setup Wizard | `src/pages/auth/SetupPage.tsx` |
| Protected Route | `src/components/auth/ProtectedRoute.tsx` |
| User Menu | `src/components/auth/UserMenu.tsx` |
| Styles | `src/pages/auth/AuthPages.css`, `src/components/auth/UserMenu.css` |

**Features:**
- JWT token storage in localStorage
- Auto-redirect to login when unauthenticated
- Setup wizard for initial tenant/admin creation
- Role-based UI (admin sees user management)
- User dropdown with profile info and logout

---

## Phase 4: Multi-tenancy Backend - IN PROGRESS

### Completed

1. **Tenant Context Middleware** (`arkham_frame/middleware/tenant.py`)
   - Uses Python contextvars for per-request tenant tracking
   - Automatically extracts tenant_id from authenticated user

2. **Shard Base Class Helpers** (`arkham_frame/shard_interface.py`)
   ```python
   get_tenant_id() -> UUID           # Get current tenant (raises if none)
   get_tenant_id_or_none() -> UUID   # Safe version for optional filtering
   tenant_query(sql, params)         # Auto-inject tenant_id
   tenant_fetch(sql, params)         # Fetch with tenant_id
   tenant_fetchrow(sql, params)      # Single row with tenant_id
   ```

3. **Schema Migrations** - All 25 shards updated with:
   - `tenant_id UUID` column added to all tables
   - Indexes on `tenant_id` for query performance
   - Idempotent migrations (safe to run multiple times)

4. **Query Filtering** - Implemented for:
   - Core: ACH, Documents, Projects
   - Data: Ingest
   - Analysis: Entities, Claims, Contradictions, Anomalies, Credibility, Patterns
   - Visualization: Graph, Timeline

### Query Filtering Status

| Category | Shards | Status |
|----------|--------|--------|
| Core | ACH, Documents, Projects | COMPLETE |
| Data | Ingest | COMPLETE |
| Analysis | Entities, Claims, Contradictions, Anomalies, Credibility, Patterns | COMPLETE |
| Visualization | Graph, Timeline | COMPLETE |
| Export | Export | COMPLETE |
| Export | Reports | COMPLETE |
| Export | Letters | COMPLETE |
| Export | Packets | COMPLETE |
| Export | Templates | COMPLETE |
| Export | Summary | COMPLETE |
| System | Provenance | COMPLETE |
| System | Settings | COMPLETE |

### Remaining Work

- [x] Query filtering complete for all shards
- [ ] Integration testing for tenant isolation

---

## Phase 5: Multi-tenancy Frontend

**Not yet started.** Will include:

- Tenant selector in header (for users with multi-tenant access)
- User management page (`/settings/users`)
- Invite user flow with email
- Role assignment UI
- User deactivation

---

## Phase 6: Audit Logging

**Not yet started.** Will include:

- `arkham_audit.events` table for all security-relevant actions
- Automatic logging of: login/logout, CRUD operations, permission changes
- Admin UI for viewing/filtering audit logs
- Export capability for compliance

---

## Phase 7: Traefik Setup (Optional)

**Not yet started.** Will include:

- `docker-compose.traefik.yml` for HTTPS termination
- Let's Encrypt automatic certificate management
- HTTP to HTTPS redirect
- Security headers at edge

---

## Phase 8: Documentation & Polish

**Not yet started.** Will include:

- Updated README with auth setup instructions
- `.env.example` with all security variables
- In-app help for login/setup flows
- Security best practices guide

---

## Testing Checklist

### Phase 1: Security Fixes - COMPLETE
- [x] `npm audit` reports 0 vulnerabilities
- [x] CORS rejects unauthorized origins
- [x] Security headers present in responses
- [x] Path traversal blocked outside allowed dirs
- [x] HTML properly sanitized in UI
- [x] Rate limiting returns 429 on excess requests

### Phase 2: Auth Backend - COMPLETE
- [x] Login returns JWT token
- [x] Invalid credentials rejected
- [x] Protected endpoints return 401 without token
- [x] Role checks enforce permissions
- [x] Setup creates tenant + admin user

### Phase 3: Auth Frontend - COMPLETE
- [x] Setup wizard completes successfully
- [x] Login page works
- [x] Protected routes redirect to login
- [x] User menu shows correct info
- [x] Logout clears token and redirects

### Phase 4: Multi-tenant Backend - IN PROGRESS
- [x] All tables have tenant_id (schema migrations complete)
- [x] Tenant context middleware created
- [x] Shard base class tenant helpers added
- [x] Core shards query filtering (ACH, Documents, Projects)
- [x] Data shards query filtering (Ingest)
- [x] Analysis shards query filtering (Entities, Claims, Contradictions, Anomalies, Credibility, Patterns)
- [x] Visualization shards query filtering (Graph, Timeline)
- [x] Export shard query filtering
- [x] Reports shard query filtering
- [x] Letters shard query filtering
- [x] Packets shard query filtering
- [x] Templates shard query filtering
- [x] Summary shard query filtering
- [x] Provenance shard query filtering
- [x] Settings shard query filtering
- [ ] Integration testing for tenant isolation

### Phase 5: Multi-tenant Frontend
- [ ] User management page works
- [ ] Can invite new users
- [ ] Can change user roles
- [ ] Can deactivate users

### Phase 6: Audit Logging
- [ ] Login events logged
- [ ] CRUD operations logged
- [ ] Audit viewer shows entries
- [ ] Filters work correctly

### Phase 7: Traefik
- [ ] HTTPS works with certificate
- [ ] HTTP redirects to HTTPS

---

## Implementation Order

1. **Phase 1.1-1.7** - Security fixes - **COMPLETE**
2. **Phase 2** - Auth backend - **COMPLETE**
3. **Phase 3** - Auth frontend - **COMPLETE**
4. **Phase 4** - Multi-tenant backend - **IN PROGRESS** (schema complete)
5. **Phase 5** - Multi-tenant frontend
6. **Phase 6** - Audit logging
7. **Phase 7** - Traefik setup
8. **Phase 8** - Documentation

---

## Key Files Reference

### Authentication
- `packages/arkham-frame/arkham_frame/auth/` - Backend auth module
- `packages/arkham-shard-shell/src/context/AuthContext.tsx` - Frontend state
- `packages/arkham-shard-shell/src/pages/auth/` - Login/Setup pages

### Security Middleware
- `packages/arkham-frame/arkham_frame/middleware/__init__.py` - Security headers
- `packages/arkham-frame/arkham_frame/middleware/rate_limit.py` - Rate limiting
- `packages/arkham-frame/arkham_frame/middleware/tenant.py` - Tenant context

### Multi-tenancy
- `packages/arkham-frame/arkham_frame/shard_interface.py` - Tenant helpers
- Each shard's `shard.py` - Contains tenant_id migration in `_create_schema()`

---

*Document created: January 8, 2026*
