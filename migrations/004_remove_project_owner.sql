-- Migration 004: Remove owner_id from projects
-- This migration removes the owner concept from projects. All access is now via member roles.
-- Date: 2026-01-28

-- Note: This migration is automatically handled by the projects shard's _create_schema method.
-- You can run this manually if needed, but it's not required as the shard handles it automatically.

-- Add tenant_id column if it doesn't exist (for multi-tenancy support)
ALTER TABLE arkham_projects ADD COLUMN IF NOT EXISTS tenant_id TEXT;

-- Drop the owner_id index
DROP INDEX IF EXISTS idx_projects_owner;

-- Drop the owner_id column (CAUTION: This is irreversible!)
ALTER TABLE arkham_projects DROP COLUMN IF EXISTS owner_id;

-- Create tenant_id index
CREATE INDEX IF NOT EXISTS idx_projects_tenant ON arkham_projects(tenant_id);

-- Migration complete
-- After running this migration, all projects should have at least one member with ADMIN role.
