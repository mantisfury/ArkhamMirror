-- Authentication schema for SHATTERED
-- Run this manually or let the app auto-create tables

CREATE SCHEMA IF NOT EXISTS arkham_auth;

-- Tenants table (organizations)
CREATE TABLE IF NOT EXISTS arkham_auth.tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT true,
    max_users INTEGER NOT NULL DEFAULT 100,
    max_documents INTEGER NOT NULL DEFAULT 10000,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    settings TEXT DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_tenants_slug ON arkham_auth.tenants(slug);

-- Users table (FastAPI-Users compatible)
CREATE TABLE IF NOT EXISTS arkham_auth.users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(320) UNIQUE NOT NULL,
    hashed_password VARCHAR(1024) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT true,
    is_superuser BOOLEAN NOT NULL DEFAULT false,
    is_verified BOOLEAN NOT NULL DEFAULT false,
    tenant_id UUID NOT NULL REFERENCES arkham_auth.tenants(id) ON DELETE CASCADE,
    display_name VARCHAR(255),
    role VARCHAR(50) NOT NULL DEFAULT 'analyst',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    last_login TIMESTAMP,
    CONSTRAINT valid_role CHECK (role IN ('admin', 'analyst', 'viewer'))
);

CREATE INDEX IF NOT EXISTS idx_users_email ON arkham_auth.users(email);
CREATE INDEX IF NOT EXISTS idx_users_tenant ON arkham_auth.users(tenant_id);

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION arkham_auth.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger for tenants updated_at
DROP TRIGGER IF EXISTS update_tenants_updated_at ON arkham_auth.tenants;
CREATE TRIGGER update_tenants_updated_at
    BEFORE UPDATE ON arkham_auth.tenants
    FOR EACH ROW
    EXECUTE FUNCTION arkham_auth.update_updated_at_column();

-- Audit events table for security logging
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
