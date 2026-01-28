-- Backfill project_id/tenant_id for entities & mentions created without scoping.
--
-- Why:
-- - `/entities` is project-scoped.
-- - Older extraction runs could insert into `arkham_entities` / `arkham_entity_mentions`
--   with NULL `project_id` / `tenant_id`, making the Entities UI appear empty even
--   though documents show entity counts.
--
-- Safe to run multiple times (idempotent-ish).

BEGIN;

-- 1) Mentions: fill from the owning document.
UPDATE arkham_entity_mentions em
SET
  project_id = d.project_id,
  tenant_id  = COALESCE(em.tenant_id, d.tenant_id)
FROM arkham_frame.documents d
WHERE em.document_id = d.id
  AND (em.project_id IS NULL OR em.tenant_id IS NULL)
  AND d.project_id IS NOT NULL;

-- 2) Entities: infer project_id/tenant_id from their mentions.
-- If an entity appears in multiple projects (should be rare), this picks one deterministically.
WITH inferred AS (
  SELECT
    em.entity_id,
    MAX(em.project_id) AS project_id,
    MAX(em.tenant_id::text) AS tenant_id
  FROM arkham_entity_mentions em
  WHERE em.project_id IS NOT NULL OR em.tenant_id IS NOT NULL
  GROUP BY em.entity_id
)
UPDATE arkham_entities e
SET
  project_id = COALESCE(e.project_id, inferred.project_id),
  tenant_id  = COALESCE(e.tenant_id, inferred.tenant_id::uuid)
FROM inferred
WHERE e.id = inferred.entity_id
  AND (e.project_id IS NULL OR e.tenant_id IS NULL);

COMMIT;

