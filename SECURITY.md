# SHATTERED Security Guide

This document covers security best practices for deploying and operating SHATTERED.

## Table of Contents

- [Quick Security Checklist](#quick-security-checklist)
- [Authentication](#authentication)
- [Authorization & Roles](#authorization--roles)
- [Multi-Tenancy](#multi-tenancy)
- [Network Security](#network-security)
- [Rate Limiting](#rate-limiting)
- [Audit Logging](#audit-logging)
- [Production Deployment](#production-deployment)
- [Security Headers](#security-headers)
- [Data Protection](#data-protection)
- [Reporting Vulnerabilities](#reporting-vulnerabilities)

---

## Quick Security Checklist

Before deploying to production, verify:

- [ ] `AUTH_SECRET_KEY` is set to a secure random value (not the default)
- [ ] `CORS_ORIGINS` is set to your actual domain (not `*`)
- [ ] PostgreSQL, Redis, and Qdrant are not exposed externally
- [ ] HTTPS is enabled via Traefik or your own reverse proxy
- [ ] Default admin password has been changed after setup
- [ ] Rate limiting is enabled
- [ ] Audit logging is enabled

---

## Authentication

### JWT-Based Authentication

SHATTERED uses JWT (JSON Web Tokens) for stateless authentication:

- Tokens are signed with `AUTH_SECRET_KEY`
- Default expiration: 1 hour (configurable via `JWT_LIFETIME_SECONDS`)
- Tokens are stored in browser localStorage

### Secret Key Requirements

```bash
# Generate a secure key (minimum 32 bytes)
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

**Important**:
- Never use the default key in production
- Rotate keys periodically (existing sessions will be invalidated)
- Keep the key secret - do not commit to version control

### Initial Setup

On first access, SHATTERED prompts for initial configuration:

1. **Tenant Creation**: Organization name and settings
2. **Admin Account**: Email, password, and display name

This is a one-time setup. After completion, the setup endpoint is disabled.

### Password Requirements

- Minimum 8 characters
- No complexity requirements enforced (users should choose strong passwords)
- Passwords are hashed with bcrypt before storage

---

## Authorization & Roles

### Role Hierarchy

| Role | Description | Capabilities |
|------|-------------|--------------|
| **Admin** | Full system access | User management, settings, audit logs, all features |
| **Analyst** | Standard user | Read/write access to documents and analyses |
| **Viewer** | Read-only access | View documents and analyses, no modifications |

### Role-Based Access Control

Endpoints are protected by role requirements:

```python
# Admin-only endpoints
@router.get("/users", dependencies=[Depends(require_admin)])

# Any authenticated user
@router.get("/documents", dependencies=[Depends(require_auth)])
```

### Frontend Route Protection

- `ProtectedRoute`: Requires authentication
- `AdminRoute`: Requires admin role

Unauthorized access redirects to login.

---

## Multi-Tenancy

### Tenant Isolation

Each tenant has completely isolated data:

- All database tables include `tenant_id` column
- Queries automatically filter by tenant context
- Cross-tenant data access is prevented at the database layer

### Tenant Context Flow

1. User authenticates → JWT includes `tenant_id`
2. Request middleware extracts tenant from JWT
3. Database queries automatically scope to tenant
4. Response contains only tenant's data

### Tenant-Aware Queries

All shard queries use tenant helpers:

```python
# Automatically includes WHERE tenant_id = ?
rows = await self.tenant_fetch("SELECT * FROM my_table")
```

---

## Network Security

### Development vs Production

| Mode | Ports Exposed | Use Case |
|------|---------------|----------|
| Development | 8100 (app), 5432 (postgres), 6379 (redis), 6333 (qdrant) | Local development |
| Production | 80, 443 only | Internet-facing deployment |

### Production Network Isolation

Using `docker-compose.traefik.yml`:

- Only Traefik exposes ports 80/443
- PostgreSQL, Redis, Qdrant are internal only
- Application communicates via Docker network

### Firewall Recommendations

```bash
# Allow only HTTP/HTTPS
ufw allow 80/tcp
ufw allow 443/tcp
ufw deny 5432/tcp   # Block external PostgreSQL
ufw deny 6379/tcp   # Block external Redis
ufw deny 6333/tcp   # Block external Qdrant
```

---

## Rate Limiting

### Configuration

```env
RATE_LIMIT_DEFAULT=100/minute    # General API endpoints
RATE_LIMIT_UPLOAD=20/minute      # File upload endpoints
RATE_LIMIT_AUTH=10/minute        # Login/authentication endpoints
```

### Rate Limit Headers

Responses include:
- `X-RateLimit-Limit`: Maximum requests allowed
- `X-RateLimit-Remaining`: Requests remaining
- `X-RateLimit-Reset`: Time until limit resets

### 429 Too Many Requests

When rate limited, clients receive:

```json
{
  "detail": "Rate limit exceeded. Retry after X seconds."
}
```

---

## Audit Logging

### Events Logged

| Event Type | Trigger |
|------------|---------|
| `tenant.created` | Initial setup completed |
| `user.created` | New user created by admin |
| `user.updated` | User profile modified |
| `user.deleted` | User removed from system |
| `user.deactivated` | User account disabled |
| `user.reactivated` | User account re-enabled |
| `user.role.changed` | User role modified |

### Audit Log Contents

Each entry includes:
- Timestamp (UTC)
- Event type
- Actor (user who performed action)
- Target (affected resource)
- IP address
- User agent
- Additional metadata

### Retention

Audit logs are stored indefinitely. Consider implementing log rotation for long-running deployments.

### Accessing Logs

- **UI**: Settings → Audit Log (admin only)
- **API**: `GET /api/auth/audit`
- **Export**: CSV or JSON via API

---

## Production Deployment

### Traefik Configuration

SHATTERED includes Traefik configuration for production:

```bash
docker compose -f docker-compose.yml -f docker-compose.traefik.yml up -d
```

### Let's Encrypt Certificates

- Automatic certificate provisioning
- Automatic renewal (30 days before expiry)
- HTTP-01 challenge (requires port 80 access)

### Certificate Storage

```bash
# Create with correct permissions
touch traefik/acme.json
chmod 600 traefik/acme.json
```

**Important**: `acme.json` must have 600 permissions or Traefik will refuse to start.

### TLS Configuration

- TLS 1.2 and 1.3 only (older versions disabled)
- Strong cipher suites
- HSTS enabled with 1-year max-age

---

## Security Headers

### Headers Applied

| Header | Value | Purpose |
|--------|-------|---------|
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains; preload` | Force HTTPS |
| `X-Content-Type-Options` | `nosniff` | Prevent MIME sniffing |
| `X-Frame-Options` | `DENY` | Prevent clickjacking |
| `X-XSS-Protection` | `1; mode=block` | XSS filter (legacy) |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Limit referrer info |
| `Content-Security-Policy` | See below | Control resource loading |

### Content Security Policy

```
default-src 'self';
script-src 'self' 'unsafe-inline' 'unsafe-eval';
style-src 'self' 'unsafe-inline';
img-src 'self' data: blob:;
font-src 'self' data:;
connect-src 'self' ws: wss:;
frame-ancestors 'none';
```

**Note**: `unsafe-inline` and `unsafe-eval` are required for React development builds. Consider removing for production builds with pre-built assets.

---

## Data Protection

### Data at Rest

- Database files stored on Docker volumes
- Consider full-disk encryption for sensitive deployments
- Regular backups recommended

### Data in Transit

- HTTPS enforced via Traefik in production
- Internal Docker network for service-to-service communication
- No sensitive data in URLs or query parameters

### Sensitive Data Handling

- Passwords hashed with bcrypt
- JWT secrets never logged
- API keys stored in environment variables (not in database)

### File Upload Security

- Filename sanitization (special characters removed)
- Path traversal prevention
- File type validation
- Configurable allowed directories

---

## CORS Configuration

### Development (Default)

```env
# Allows localhost variants
CORS_ORIGINS=http://localhost:3100,http://127.0.0.1:3100
```

### Production

```env
# Restrict to your domain only
CORS_ORIGINS=https://your-domain.com
```

### With Traefik

The `docker-compose.traefik.yml` automatically sets:

```env
CORS_ORIGINS=https://${DOMAIN}
```

---

## Environment Security

### Required Variables

| Variable | Description |
|----------|-------------|
| `AUTH_SECRET_KEY` | JWT signing key (generate securely) |
| `POSTGRES_PASSWORD` | Database password |

### Production Variables

| Variable | Description |
|----------|-------------|
| `DOMAIN` | Your domain name |
| `ACME_EMAIL` | Let's Encrypt notification email |
| `CORS_ORIGINS` | Allowed CORS origins |

### Secrets Management

For production:
- Use Docker secrets or environment files
- Never commit `.env` to version control
- Consider HashiCorp Vault or similar for enterprise

---

## Reporting Vulnerabilities

If you discover a security vulnerability:

1. **Do not** open a public GitHub issue
2. Email security concerns to the maintainer
3. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

We aim to respond within 48 hours and provide a fix within 7 days for critical issues.

---

## Security Roadmap

### Implemented

- [x] JWT authentication
- [x] Role-based access control
- [x] Multi-tenant data isolation
- [x] Rate limiting
- [x] CORS configuration
- [x] Security headers
- [x] XSS prevention (DOMPurify)
- [x] Path traversal protection
- [x] Audit logging
- [x] HTTPS via Traefik

### Planned

- [ ] Login attempt logging
- [ ] Session management (logout all devices)
- [ ] Two-factor authentication (2FA)
- [ ] API key authentication
- [ ] IP allowlisting
- [ ] Automated security scanning

---

*Last updated: January 2026*
