-- Migration 003: Migrate projects from arkham_frame.projects to public.arkham_projects
-- This unifies project storage so the projects shard's member/document tables can reference projects

-- Ensure expected shard columns exist (some installs may have a newer schema already)
ALTER TABLE public.arkham_projects
    ADD COLUMN IF NOT EXISTS owner_id TEXT;

-- Copy all projects from arkham_frame.projects to public.arkham_projects
-- Map columns and set defaults for shard table structure
INSERT INTO public.arkham_projects (
    id,
    name,
    description,
    status,
    owner_id,
    created_at,
    updated_at,
    settings,
    metadata,
    member_count,
    document_count
)
SELECT
    id,
    name,
    COALESCE(description, '') as description,
    COALESCE(
        (settings::jsonb->>'status')::text,
        'active'
    ) as status,
    COALESCE(
        (settings::jsonb->>'owner_id')::text,
        'system'
    ) as owner_id,
    COALESCE(
        created_at::text,
        CURRENT_TIMESTAMP::text
    ) as created_at,
    COALESCE(
        updated_at::text,
        CURRENT_TIMESTAMP::text
    ) as updated_at,
    COALESCE(settings::text, '{}') as settings,
    COALESCE(metadata::text, '{}') as metadata,
    0 as member_count,
    0 as document_count
FROM arkham_frame.projects
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    updated_at = EXCLUDED.updated_at,
    settings = EXCLUDED.settings;

-- Update member_count and document_count from existing associations
UPDATE public.arkham_projects p SET
    member_count = (
        SELECT COUNT(*) 
        FROM arkham_project_members m 
        WHERE m.project_id = p.id
    ),
    document_count = (
        SELECT COUNT(*) 
        FROM arkham_project_documents d 
        WHERE d.project_id = p.id
    );
