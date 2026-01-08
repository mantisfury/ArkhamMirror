# SHATTERED Security Review Report

**Date:** January 8, 2026
**Reviewer:** Claude Code Security Analysis
**Version:** Pre-Production Review
**Status:** REQUIRES REMEDIATION BEFORE PRODUCTION

---

## Executive Summary

This security review identifies **17 security issues** across the SHATTERED codebase, ranging from critical to low severity. The most significant concerns are:

1. **No Authentication/Authorization** - All API endpoints are publicly accessible
2. **Overly Permissive CORS** - Allows any origin with credentials
3. **NPM Vulnerabilities** - 3 known vulnerabilities (1 high, 2 moderate)
4. **Potential Path Traversal** - User-controllable filesystem paths
5. **XSS Risk** - Use of `dangerouslySetInnerHTML` without sanitization

**Recommendation:** Address all CRITICAL and HIGH severity issues before production deployment.

---

## Severity Classification

| Severity | Count | Description |
|----------|-------|-------------|
| CRITICAL | 2 | Immediate exploitation risk, must fix before production |
| HIGH | 4 | Significant security risk, strongly recommended to fix |
| MEDIUM | 6 | Moderate risk, should be addressed |
| LOW | 5 | Minor issues, fix when possible |

---

## Detailed Findings

### CRITICAL Severity

#### 1. No Authentication or Authorization (CRITICAL)

**Location:** All API endpoints across all shards
**Files:** `packages/arkham-frame/arkham_frame/main.py`, all `api.py` files

**Description:**
The entire API is unauthenticated. Any user who can reach the application can:
- Upload arbitrary files
- Access and modify all documents
- Delete data
- Access administrative functions
- Execute analysis operations

**Evidence:**
```python
# packages/arkham-frame/arkham_frame/main.py
# No authentication middleware configured
app = FastAPI(
    title="ArkhamFrame",
    description="ArkhamMirror Shattered Frame - Core Infrastructure API",
    version="0.1.0",
    lifespan=lifespan,
)
# No auth dependency injection on routes
```

**Impact:** Complete system compromise by any network-adjacent attacker.

**Remediation:**
1. Implement authentication middleware (JWT, OAuth2, or API keys)
2. Add authorization checks to all endpoints
3. Consider role-based access control (RBAC)
4. Protect sensitive endpoints with additional verification

**Example Fix:**
```python
from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()

async def verify_token(credentials: HTTPAuthorizationCredentials = Security(security)):
    # Implement token verification
    token = credentials.credentials
    # Validate token against your auth provider
    if not is_valid_token(token):
        raise HTTPException(status_code=401, detail="Invalid token")
    return token

# Apply to routes:
@router.get("/sensitive-data")
async def get_data(token: str = Depends(verify_token)):
    ...
```

---

#### 2. Overly Permissive CORS Configuration (CRITICAL)

**Location:** `packages/arkham-frame/arkham_frame/main.py:124-130`

**Description:**
CORS is configured to allow ALL origins with credentials enabled. This is extremely dangerous as it allows any website to make authenticated requests to the API.

**Evidence:**
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,  # This + allow_origins=["*"] is dangerous
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Impact:**
- Cross-Site Request Forgery (CSRF) attacks
- Data exfiltration from authenticated sessions
- Malicious websites can perform actions on behalf of users

**Remediation:**
```python
# For production, specify allowed origins explicitly
ALLOWED_ORIGINS = [
    "https://yourdomain.com",
    "https://app.yourdomain.com",
]

# For development only
if os.environ.get("DEV_MODE"):
    ALLOWED_ORIGINS.append("http://localhost:5173")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["Authorization", "Content-Type"],
)
```

---

### HIGH Severity

#### 3. NPM Dependency Vulnerabilities (HIGH)

**Location:** `packages/arkham-shard-shell/`

**Description:**
npm audit reports 3 vulnerabilities:

| Package | Severity | Issue |
|---------|----------|-------|
| preact | HIGH | JSON VNode Injection (GHSA-36hm-qxxp-pg3m) |
| esbuild | MODERATE | Development server request vulnerability (GHSA-67mh-4wv8-2f99) |
| vite | MODERATE | Depends on vulnerable esbuild |

**Evidence:**
```
# npm audit report
preact  10.28.0 - 10.28.1
Severity: high
Preact has JSON VNode Injection issue

esbuild  <=0.24.2
Severity: moderate
esbuild enables any website to send any requests to development server
```

**Remediation:**
```bash
cd packages/arkham-shard-shell

# Fix preact vulnerability
npm audit fix

# For breaking changes (vite/esbuild), test thoroughly first:
npm audit fix --force

# Or update specific packages:
npm update preact
npm update vite
```

---

#### 4. Path Traversal Vulnerability (HIGH)

**Location:** `packages/arkham-shard-ingest/arkham_shard_ingest/api.py:249-304`

**Description:**
The `/api/ingest/ingest-path` endpoint accepts a user-provided filesystem path and reads files from it. While there's a `Path.exists()` check, there's no validation to prevent access outside the intended data directory.

**Evidence:**
```python
@router.post("/ingest-path", response_model=BatchUploadResponse)
async def ingest_from_path(request: IngestPathRequest):
    path = Path(request.path)  # User-controlled path
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Path not found: {path}")
    # No validation to ensure path is within allowed directories
    batch = await _intake_manager.receive_path(path=path, ...)
```

**Impact:**
- Read arbitrary files from the filesystem
- Access sensitive configuration files
- Read system files like `/etc/passwd`

**Remediation:**
```python
import os

ALLOWED_INGEST_PATHS = [
    Path("/app/data_silo/imports"),
    Path("/app/uploads"),
]

def validate_path(user_path: Path) -> Path:
    """Ensure path is within allowed directories."""
    resolved = user_path.resolve()

    for allowed in ALLOWED_INGEST_PATHS:
        try:
            resolved.relative_to(allowed.resolve())
            return resolved
        except ValueError:
            continue

    raise HTTPException(
        status_code=403,
        detail="Access to this path is not allowed"
    )

@router.post("/ingest-path")
async def ingest_from_path(request: IngestPathRequest):
    path = validate_path(Path(request.path))
    # ... rest of implementation
```

---

#### 5. XSS via dangerouslySetInnerHTML (HIGH)

**Location:**
- `packages/arkham-shard-shell/src/pages/reports/ReportsPage.tsx:639`
- `packages/arkham-shard-shell/src/pages/search/SearchResultCard.tsx:46`

**Description:**
React's `dangerouslySetInnerHTML` is used to render content that may contain unsanitized user input or content from external sources.

**Evidence:**
```tsx
// ReportsPage.tsx:639
<div
  className="report-html-content"
  dangerouslySetInnerHTML={{ __html: reportContent }}
/>

// SearchResultCard.tsx:46
<div
  className="search-result-excerpt"
  dangerouslySetInnerHTML={{ __html: result.highlights[0] }}
/>
```

**Impact:**
- Stored XSS if reports contain malicious scripts
- Reflected XSS via search highlighting

**Remediation:**
Install and use DOMPurify:
```bash
npm install dompurify @types/dompurify
```

```tsx
import DOMPurify from 'dompurify';

// Sanitize before rendering
<div
  className="report-html-content"
  dangerouslySetInnerHTML={{
    __html: DOMPurify.sanitize(reportContent, {
      ALLOWED_TAGS: ['p', 'br', 'strong', 'em', 'ul', 'ol', 'li', 'h1', 'h2', 'h3'],
      ALLOWED_ATTR: ['class']
    })
  }}
/>
```

---

#### 6. Missing HTTP Security Headers (HIGH)

**Location:** `packages/arkham-frame/arkham_frame/main.py`

**Description:**
The application doesn't set any HTTP security headers, leaving it vulnerable to various attacks.

**Missing Headers:**
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `X-XSS-Protection: 1; mode=block`
- `Strict-Transport-Security` (HSTS)
- `Content-Security-Policy`
- `Referrer-Policy`

**Remediation:**
```python
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=()"
        # Add HSTS in production with HTTPS
        # response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

app.add_middleware(SecurityHeadersMiddleware)
```

---

### MEDIUM Severity

#### 7. Default Database Credentials in Environment (MEDIUM)

**Location:** `.env`, `docker-compose.yml`

**Description:**
Default database credentials are used in configuration files.

**Evidence:**
```env
# .env
POSTGRES_USER=arkham
POSTGRES_PASSWORD=arkhampass
```

**Remediation:**
1. Use strong, unique passwords
2. Use environment variable injection from secrets manager
3. Never commit `.env` files with real credentials
4. Document that these are example values only

```yaml
# docker-compose.yml - use external secrets
services:
  postgres:
    environment:
      - POSTGRES_PASSWORD_FILE=/run/secrets/db_password
    secrets:
      - db_password
```

---

#### 8. No Rate Limiting (MEDIUM)

**Location:** All API endpoints

**Description:**
No rate limiting is implemented, allowing unlimited API requests. This enables:
- Denial of Service attacks
- Brute force attacks
- Resource exhaustion

**Remediation:**
Install slowapi:
```bash
pip install slowapi
```

```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@router.post("/upload")
@limiter.limit("10/minute")
async def upload_file(request: Request, ...):
    ...
```

---

#### 9. SQL String Interpolation (MEDIUM)

**Location:** Multiple files including:
- `packages/arkham-shard-documents/arkham_shard_documents/shard.py:504`
- `packages/arkham-frame/arkham_frame/services/documents.py:356`
- `packages/arkham-shard-contradictions/arkham_shard_contradictions/storage.py:334`

**Description:**
Some SQL queries use f-strings for table/schema names. While the values appear to be constants, this pattern is risky.

**Evidence:**
```python
# shard.py:504
query = f"UPDATE arkham_frame.documents SET {', '.join(updates)} WHERE id = :id"

# documents.py:356
text(f"SELECT * FROM {self.SCHEMA}.documents WHERE id = :id")
```

**Assessment:**
- The `updates` list appears to be built from validated field names
- Schema names are class constants, not user input
- Parameters use proper placeholders (`:id`)

**Recommendation:**
Review all dynamic SQL to ensure:
1. Table/column names come from constants, not user input
2. Use parameterized queries for all values
3. Consider using an ORM for additional safety

---

#### 10. Docker PostgreSQL Exposed to Host (MEDIUM)

**Location:** `docker-compose.yml:86-87`

**Description:**
PostgreSQL port 5432 is exposed to the host network, potentially allowing external connections.

**Evidence:**
```yaml
postgres:
  ports:
    - "5432:5432"  # Exposed to host
```

**Remediation:**
For production, remove external port mapping or bind to localhost:
```yaml
postgres:
  # Option 1: Remove external port (services communicate via Docker network)
  # ports:
  #   - "5432:5432"

  # Option 2: Bind to localhost only
  ports:
    - "127.0.0.1:5432:5432"
```

---

#### 11. Redis/Qdrant Exposed Without Authentication (MEDIUM)

**Location:** `docker-compose.yml:108, 128`

**Description:**
Redis and Qdrant ports are exposed without authentication configured.

**Remediation:**
```yaml
redis:
  command: redis-server --appendonly yes --requirepass ${REDIS_PASSWORD}
  ports:
    - "127.0.0.1:6379:6379"  # Localhost only

qdrant:
  environment:
    - QDRANT__SERVICE__API_KEY=${QDRANT_API_KEY}
  ports:
    - "127.0.0.1:6333:6333"
```

---

#### 12. Incomplete Filename Sanitization (MEDIUM)

**Location:** `packages/arkham-shard-ingest/arkham_shard_ingest/intake.py:419-427`

**Description:**
The filename sanitization function doesn't handle all dangerous patterns.

**Evidence:**
```python
def _sanitize_filename(self, filename: str) -> str:
    """Sanitize filename for safe storage."""
    # Removes / and \ but doesn't check for ..
    safe = filename.replace("/", "_").replace("\\", "_").replace("\x00", "")
    # ...
```

**Missing Protections:**
- `..` sequences (directory traversal)
- Control characters beyond null
- Reserved Windows filenames (CON, PRN, AUX, NUL, COM1-9, LPT1-9)

**Remediation:**
```python
import re
import unicodedata

def _sanitize_filename(self, filename: str) -> str:
    """Sanitize filename for safe storage."""
    # Normalize unicode
    safe = unicodedata.normalize('NFKD', filename)

    # Remove path separators and parent directory references
    safe = re.sub(r'[/\\]', '_', safe)
    safe = re.sub(r'\.\.+', '_', safe)

    # Remove control characters
    safe = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', safe)

    # Remove Windows reserved characters
    safe = re.sub(r'[<>:"|?*]', '_', safe)

    # Block Windows reserved names
    reserved = {'CON', 'PRN', 'AUX', 'NUL'} | {f'COM{i}' for i in range(1,10)} | {f'LPT{i}' for i in range(1,10)}
    name_upper = safe.split('.')[0].upper()
    if name_upper in reserved:
        safe = f"_{safe}"

    # Limit length
    if len(safe) > 200:
        name, ext = os.path.splitext(safe)
        safe = name[:200-len(ext)] + ext

    return safe or "unnamed"
```

---

### LOW Severity

#### 13. Sensitive Information in Logs (LOW)

**Location:** Various files

**Description:**
Environment variables and configuration details are printed to logs during startup.

**Evidence:**
```python
# main.py:20
print(f"Loaded environment from {_env_path}")

# entrypoint.sh:90-94
echo "  DATABASE_URL: ${DATABASE_URL:+[configured]}"
```

**Recommendation:**
- Ensure log level is appropriately set in production
- Mask sensitive values in logs
- Use structured logging with sensitive field filtering

---

#### 14. Missing Input Validation on Settings (LOW)

**Location:** `packages/arkham-shard-ingest/arkham_shard_ingest/api.py:516-558`

**Description:**
Settings update endpoint accepts values without range validation.

**Evidence:**
```python
@router.patch("/settings")
async def update_ingest_settings(settings: IngestSettingsUpdate):
    # No validation on numeric ranges
    update_dict = settings.model_dump(exclude_none=True)
    for key, value in update_dict.items():
        _config.set(key, value)  # Direct assignment
```

**Recommendation:**
Add Pydantic validators:
```python
class IngestSettingsUpdate(BaseModel):
    ingest_max_file_size_mb: int | None = Field(None, ge=1, le=1000)
    ocr_confidence_threshold: float | None = Field(None, ge=0.0, le=1.0)
    # ...
```

---

#### 15. Container Runs as Root (LOW)

**Location:** `Dockerfile`

**Description:**
The Docker container runs as root by default.

**Remediation:**
Add non-root user:
```dockerfile
# Add before ENTRYPOINT
RUN useradd --create-home --shell /bin/bash arkham
USER arkham
```

---

#### 16. No HTTPS Enforcement (LOW)

**Location:** Application-wide

**Description:**
HTTPS is not enforced at the application level. This depends on infrastructure (reverse proxy).

**Recommendation:**
Document that a reverse proxy (nginx, Traefik) with TLS termination is required for production:
```nginx
server {
    listen 443 ssl;
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://shattered-app:8100;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

---

#### 17. .env File Committed (LOW - Mitigated)

**Location:** `.gitignore`

**Description:**
The `.env` file is properly listed in `.gitignore`, but the example `.env` in the repository contains real-looking values.

**Recommendation:**
- Rename to `.env.example` with placeholder values
- Add documentation about creating local `.env`

---

## Recommendations Summary

### Immediate Actions (Before Production)

1. **Implement Authentication** - Add JWT or OAuth2 authentication
2. **Fix CORS Configuration** - Specify allowed origins explicitly
3. **Update NPM Dependencies** - Run `npm audit fix`
4. **Add Path Validation** - Restrict filesystem access to allowed directories
5. **Sanitize HTML Output** - Install and use DOMPurify
6. **Add Security Headers** - Implement security headers middleware

### Short-Term Actions

7. **Add Rate Limiting** - Install and configure slowapi
8. **Secure Database Credentials** - Use secrets management
9. **Review SQL Queries** - Audit all dynamic SQL
10. **Restrict Docker Ports** - Bind to localhost or remove external ports
11. **Add Service Authentication** - Configure Redis/Qdrant authentication
12. **Improve Filename Sanitization** - Handle all edge cases

### Long-Term Improvements

13. **Audit Logging** - Implement security event logging
14. **Input Validation** - Add comprehensive Pydantic validators
15. **Non-Root Container** - Add unprivileged user
16. **TLS Documentation** - Document reverse proxy requirements
17. **Security Monitoring** - Add intrusion detection

---

## Compliance Considerations

If this application will process sensitive data, consider:

- **GDPR**: Data access controls, audit logging, data retention policies
- **HIPAA**: Encryption at rest and in transit, access controls, audit trails
- **SOC 2**: Access management, change management, monitoring

---

## Testing Recommendations

Before production deployment:

1. **Penetration Testing**: Engage a security firm for professional assessment
2. **Dependency Scanning**: Integrate Snyk or Dependabot for ongoing monitoring
3. **SAST**: Run static analysis tools (Bandit, Semgrep) in CI/CD
4. **DAST**: Perform dynamic application security testing

---

## Appendix: Security Checklist

- [ ] Authentication implemented
- [ ] Authorization/RBAC implemented
- [ ] CORS properly configured
- [ ] NPM vulnerabilities fixed
- [ ] Path traversal prevented
- [ ] XSS mitigations in place
- [ ] Security headers added
- [ ] Rate limiting enabled
- [ ] Database credentials secured
- [ ] Docker ports restricted
- [ ] Input validation comprehensive
- [ ] Audit logging enabled
- [ ] TLS/HTTPS configured
- [ ] Container hardened
- [ ] Secrets management in place

---

*Report generated by Claude Code Security Analysis*
