# API Key Rotation Guide

This document describes how to safely rotate API keys and credentials in SHATTERED.

## Overview

SHATTERED uses several types of credentials:
- **LLM API Keys** (OpenRouter, OpenAI, Anthropic, etc.)
- **Database Credentials** (PostgreSQL)
- **SMTP Credentials** (Email notifications)
- **Webhook Auth Tokens** (Notification webhooks)

All credentials are loaded from environment variables and never stored in code or config files.

## LLM API Key Rotation

### Step 1: Generate New Key
1. Go to your LLM provider's dashboard (e.g., [OpenRouter](https://openrouter.ai/settings/keys))
2. Create a new API key
3. Note: Keep the old key active until rotation is complete

### Step 2: Update Environment
```bash
# Update your .env file
LLM_API_KEY=sk-or-v1-your-new-key-here
```

### Step 3: Restart Application
```bash
# The application must be restarted to load new credentials
# Option 1: Via Dashboard UI - use the restart button
# Option 2: Via command line
pkill -f "uvicorn.*arkham"
python -m uvicorn arkham_frame.main:app --host 127.0.0.1 --port 8100
```

### Step 4: Verify New Key Works
1. Go to Dashboard > LLM tab
2. Click "Test Connection"
3. Verify success response

### Step 5: Revoke Old Key
1. Return to your LLM provider's dashboard
2. Delete/revoke the old API key

## Database Credential Rotation

### Step 1: Create New Database User (PostgreSQL)
```sql
-- Connect as superuser
CREATE USER arkham_new WITH PASSWORD 'new-secure-password';
GRANT ALL PRIVILEGES ON DATABASE arkhamdb TO arkham_new;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO arkham_new;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO arkham_new;
```

### Step 2: Update Environment
```bash
# Update your .env file
POSTGRES_USER=arkham_new
POSTGRES_PASSWORD=new-secure-password
```

### Step 3: Restart Application
```bash
pkill -f "uvicorn.*arkham"
python -m uvicorn arkham_frame.main:app --host 127.0.0.1 --port 8100
```

### Step 4: Verify Connection
1. Go to Dashboard > Database tab
2. Verify database is connected

### Step 5: Remove Old User
```sql
-- After confirming new credentials work
DROP USER arkham_old;
```

## SMTP Credential Rotation

SMTP credentials are configured via the Notification API, not environment variables.

### Step 1: Update SMTP Password with Provider
1. Go to your email provider's settings
2. Generate new app password or rotate credentials

### Step 2: Reconfigure Email Channel
```python
# Via API or application code
notification_service.configure_email(
    name="alerts",
    smtp_host="smtp.example.com",
    smtp_port=587,
    username="alerts@example.com",
    password="new-password",  # New password
    from_address="alerts@example.com",
)
```

### Step 3: Test Email Delivery
Send a test notification to verify the new credentials work.

## Webhook Token Rotation

### Step 1: Generate New Token
Create a new authentication token for your webhook endpoint.

### Step 2: Update Webhook Channel
```python
# Remove old channel (clears credentials from memory)
notification_service.remove_channel("my-webhook")

# Configure with new token
notification_service.configure_webhook(
    name="my-webhook",
    url="https://api.example.com/webhook",
    auth_token="new-bearer-token",
)
```

## Security Best Practices

### Key Storage
- Store keys only in `.env` files (gitignored)
- Never commit keys to version control
- Use different keys for development/staging/production

### Key Strength
- Use keys with at least 32 characters
- Use cryptographically secure random generation
- Avoid patterns or dictionary words

### Rotation Schedule
| Credential Type | Recommended Rotation |
|-----------------|---------------------|
| LLM API Keys | Every 90 days or after suspected compromise |
| Database Passwords | Every 90 days |
| SMTP Passwords | Every 90 days |
| Webhook Tokens | Every 90 days or when endpoints change |

### Monitoring
- Monitor API usage for anomalies
- Set up alerts for authentication failures
- Review access logs regularly

### Emergency Rotation
If you suspect a key has been compromised:
1. **Immediately** revoke the compromised key at the provider
2. Generate and deploy a new key
3. Review logs for unauthorized access
4. Notify affected parties if data was exposed

## Security Features in SHATTERED

SHATTERED implements several security measures for credential handling:

1. **Environment-Only Loading**: Keys are only loaded from environment variables, never from config files or databases

2. **`__slots__` Protection**: Service classes use `__slots__` to prevent dynamic attribute access that could leak credentials

3. **Reference Clearing**: Credential references are cleared on service shutdown or channel removal, allowing garbage collection

4. **Truncated Error Messages**: Error responses are truncated to 200 characters to prevent credential leakage in logs

5. **Safe Logging**: Database URLs are logged without credentials (only host:port/database)

### Python Memory Limitations

Note: Python strings are immutable and may be interned by the interpreter, which means true secure memory clearing (overwriting with zeros) is not reliably possible without native extensions. SHATTERED clears references to allow garbage collection, but for environments requiring cryptographic-grade memory security, consider:

- Using `SecretStr` from Pydantic for sensitive fields
- Native extensions with secure memory allocation (e.g., `cryptography` library)
- Hardware Security Modules (HSM) for key storage
- Process isolation with short-lived worker processes

## Verifying Security Configuration

Run these checks to verify your security configuration:

```bash
# Check .env is gitignored
git check-ignore .env && echo "OK: .env is ignored"

# Check no keys in git history
git log --all -p -- "*.env" | grep -E "sk-|password=" || echo "OK: No keys in history"

# Verify API doesn't expose keys
curl -s http://localhost:8100/api/dashboard/llm | grep -o '"api_key_configured":[^,]*'
# Should show: "api_key_configured":true (not the actual key)
```
