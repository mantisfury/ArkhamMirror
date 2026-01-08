# Phase 7: Traefik HTTPS Setup

**Status: COMPLETE**

## Overview

Add production-ready HTTPS support using Traefik as a reverse proxy. This provides:
- Automatic TLS/SSL certificate management via Let's Encrypt
- HTTP to HTTPS redirection
- Security headers at the edge
- Simplified production deployment

## Design Decisions

### Why Traefik?

1. **Automatic Certificates**: Let's Encrypt integration with automatic renewal
2. **Docker Integration**: Native Docker provider for service discovery
3. **Zero Downtime**: Certificate renewals don't require restarts
4. **Modern**: HTTP/2, WebSocket support, modern TLS configuration
5. **Lightweight**: Single binary, minimal resource usage

### Architecture

```
                     Internet
                         |
                    [Port 443]
                         |
                  +------v------+
                  |   Traefik   |  <-- HTTPS termination, Let's Encrypt
                  |   (Edge)    |
                  +------+------+
                         |
                    [Port 8100]
                         |
                  +------v------+
                  | SHATTERED   |  <-- Application (HTTP internal)
                  |    App      |
                  +-------------+
```

### Security Headers (Edge)

Traefik adds these headers to all responses:
- `Strict-Transport-Security` (HSTS)
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `X-XSS-Protection: 1; mode=block`
- `Referrer-Policy: strict-origin-when-cross-origin`

## File Structure

```
traefik/
├── traefik.yml           # Static configuration
├── acme.json             # Certificate storage (auto-created)
└── dynamic/
    └── security.yml      # Security headers middleware
```

## Configuration Files

### traefik/traefik.yml

Static Traefik configuration:
- Entry points (HTTP on 80, HTTPS on 443)
- Let's Encrypt ACME configuration
- Docker provider settings
- Dashboard settings

### traefik/dynamic/security.yml

Dynamic configuration:
- Security headers middleware
- Rate limiting at edge (optional)
- IP whitelist (optional)

### docker-compose.traefik.yml

Docker Compose override file that:
- Adds Traefik service
- Removes direct port exposure from app
- Adds Traefik labels to app service
- Configures certificate storage volume

## Environment Variables

```env
# Required for HTTPS
DOMAIN=your-domain.com
ACME_EMAIL=admin@your-domain.com

# Optional
TRAEFIK_DASHBOARD=true          # Enable Traefik dashboard
TRAEFIK_DASHBOARD_USER=admin    # Dashboard basic auth user
TRAEFIK_DASHBOARD_PASS=...      # Dashboard basic auth password (htpasswd format)
```

## Usage

### Development (HTTP only)

```bash
# Standard docker-compose (HTTP on port 8100)
docker compose up -d
```

### Production (HTTPS with Traefik)

```bash
# Set required variables
export DOMAIN=your-domain.com
export ACME_EMAIL=admin@your-domain.com

# Create certificate storage file with correct permissions
mkdir -p traefik
touch traefik/acme.json
chmod 600 traefik/acme.json

# Start with Traefik overlay
docker compose -f docker-compose.yml -f docker-compose.traefik.yml up -d
```

### Verify HTTPS

```bash
# Check certificate
curl -I https://your-domain.com

# Verify HTTP redirect
curl -I http://your-domain.com
# Should return 301 redirect to HTTPS

# Check security headers
curl -I https://your-domain.com | grep -E "(Strict-Transport|X-Frame|X-Content)"
```

## Implementation Details

### Let's Encrypt Staging (Testing)

For testing, use Let's Encrypt staging to avoid rate limits:

```yaml
certificatesResolvers:
  letsencrypt:
    acme:
      caServer: https://acme-staging-v02.api.letsencrypt.org/directory  # Staging
      # caServer: https://acme-v02.api.letsencrypt.org/directory       # Production
```

### Certificate Storage

Certificates are stored in `traefik/acme.json`:
- Must have `chmod 600` permissions
- Persisted via Docker volume
- Contains all domain certificates
- Automatically renewed before expiry

### Wildcard Certificates (Optional)

For wildcard certificates, DNS challenge is required:

```yaml
certificatesResolvers:
  letsencrypt:
    acme:
      dnsChallenge:
        provider: cloudflare  # or route53, digitalocean, etc.
```

## Testing Checklist

- [ ] HTTP redirects to HTTPS (301)
- [ ] HTTPS works with valid certificate
- [ ] Certificate auto-renews (check logs)
- [ ] Security headers present in responses
- [ ] Traefik dashboard accessible (if enabled)
- [ ] Application works through proxy
- [ ] WebSocket connections work (if used)

## Troubleshooting

### Certificate Not Issued

```bash
# Check Traefik logs
docker compose logs traefik

# Common issues:
# - Domain not pointing to server IP
# - Port 80 not accessible (Let's Encrypt HTTP challenge)
# - Rate limited (use staging first)
```

### 502 Bad Gateway

```bash
# Check app is running
docker compose ps

# Check app logs
docker compose logs app

# Verify internal connectivity
docker compose exec traefik wget -qO- http://app:8100/health
```

### Permission Denied on acme.json

```bash
# Fix permissions (must be 600)
chmod 600 traefik/acme.json
```

## Security Considerations

1. **TLS 1.2+**: Only TLS 1.2 and 1.3 are enabled
2. **Strong Ciphers**: Modern cipher suites only
3. **HSTS**: Enforces HTTPS for 1 year with includeSubDomains
4. **No Dashboard in Production**: Or secure with strong auth

## Rollback

To revert to HTTP-only:

```bash
# Stop all services
docker compose -f docker-compose.yml -f docker-compose.traefik.yml down

# Start without Traefik
docker compose up -d
```
